import os
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Base, SessionLocal, engine
from .models import Task, TimeEntry, User
from .schemas import RegisterRequest, SyncRequest, SyncResponse, TaskPayload, TimeEntryPayload, TokenResponse


Base.metadata.create_all(bind=engine)

app = FastAPI(title="TimeCheck API")


def _get_allowed_origins() -> list[str]:
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    extra_origins = os.getenv("FRONTEND_ORIGINS", "")
    if extra_origins:
        origins.extend(
            origin.strip()
            for origin in extra_origins.split(",")
            if origin.strip()
        )
    if os.getenv("ALLOW_ALL_ORIGINS") == "1":
        return ["*"]
    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _create_access_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def _get_user(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def _get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()

def _normalize_email(value: str) -> str:
    return value.strip().lower()


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED) from exc

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    user = _get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user


def _should_apply(existing: datetime | None, incoming: datetime) -> bool:
    if existing is None:
        return True
    return incoming >= existing


def _apply_task(db: Session, user: User, payload: TaskPayload) -> None:
    task = db.get(Task, payload.id)
    if task is None:
        task = Task(id=payload.id, user_id=user.id)
        db.add(task)
    elif task.user_id != user.id:
        return

    if not _should_apply(task.client_updated_at, payload.client_updated_at):
        return

    task.title = payload.title
    task.description = payload.description
    task.created_at = payload.created_at
    task.updated_at = datetime.utcnow()
    task.deleted_at = payload.deleted_at
    task.client_updated_at = payload.client_updated_at


def _apply_time_entry(db: Session, user: User, payload: TimeEntryPayload) -> None:
    entry = db.get(TimeEntry, payload.id)
    if entry is None:
        task = db.get(Task, payload.task_id)
        if not task or task.user_id != user.id:
            return
        entry = TimeEntry(id=payload.id, user_id=user.id)
        db.add(entry)
    elif entry.user_id != user.id:
        return

    if not _should_apply(entry.client_updated_at, payload.client_updated_at):
        return

    entry.task_id = payload.task_id
    entry.started_at = payload.started_at
    entry.stopped_at = payload.stopped_at
    entry.comment = payload.comment
    entry.created_at = payload.created_at
    entry.updated_at = datetime.utcnow()
    entry.deleted_at = payload.deleted_at
    entry.client_updated_at = payload.client_updated_at


def _collapse_changes(changes):
    latest = {}
    for change in changes:
        record_id = change.data.id
        existing = latest.get(record_id)
        if not existing or change.data.client_updated_at >= existing.data.client_updated_at:
            latest[record_id] = change
    return list(latest.values())


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    email = _normalize_email(payload.email)
    password = payload.password.strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password too short")
    if _get_user_by_email(db, email):
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=email,
        password_hash=pwd_context.hash(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = _create_access_token(user.id)
    return TokenResponse(access_token=token)


@app.post("/auth/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    email = _normalize_email(form_data.username)
    password = form_data.password.strip()
    if not email or not password:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    user = _get_user_by_email(db, email)
    if not user or not pwd_context.verify(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _create_access_token(user.id)
    return TokenResponse(access_token=token)


@app.post("/sync", response_model=SyncResponse)
def sync(
    payload: SyncRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    for change in _collapse_changes(payload.changes.tasks):
        _apply_task(db, user, change.data)

    for change in _collapse_changes(payload.changes.time_entries):
        _apply_time_entry(db, user, change.data)

    db.commit()

    last_sync = payload.last_sync_at
    task_query = select(Task).where(Task.user_id == user.id)
    entry_query = select(TimeEntry).where(TimeEntry.user_id == user.id)
    if last_sync is not None:
        task_query = task_query.where(Task.updated_at >= last_sync)
        entry_query = entry_query.where(TimeEntry.updated_at >= last_sync)

    tasks = db.execute(task_query).scalars().all()
    entries = db.execute(entry_query).scalars().all()

    return SyncResponse(
        server_time=datetime.utcnow(),
        tasks=[
            TaskPayload(
                id=task.id,
                title=task.title,
                description=task.description,
                created_at=task.created_at,
                updated_at=task.updated_at,
                deleted_at=task.deleted_at,
                client_updated_at=task.client_updated_at,
            )
            for task in tasks
        ],
        time_entries=[
            TimeEntryPayload(
                id=entry.id,
                task_id=entry.task_id,
                started_at=entry.started_at,
                stopped_at=entry.stopped_at,
                comment=entry.comment,
                created_at=entry.created_at,
                updated_at=entry.updated_at,
                deleted_at=entry.deleted_at,
                client_updated_at=entry.client_updated_at,
            )
            for entry in entries
        ],
    )
