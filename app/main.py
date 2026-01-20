from datetime import datetime

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Base, SessionLocal, engine
from .models import Task, TimeEntry
from .schemas import SyncRequest, SyncResponse, TaskPayload, TimeEntryPayload


Base.metadata.create_all(bind=engine)

app = FastAPI(title="TimeCheck API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _should_apply(existing: datetime | None, incoming: datetime) -> bool:
    if existing is None:
        return True
    return incoming >= existing


def _apply_task(db: Session, payload: TaskPayload, op: str) -> None:
    task = db.get(Task, payload.id)
    if task is None:
        task = Task(id=payload.id)
        db.add(task)

    if not _should_apply(task.client_updated_at, payload.client_updated_at):
        return

    task.title = payload.title
    task.description = payload.description
    task.created_at = payload.created_at
    task.updated_at = datetime.utcnow()
    task.deleted_at = payload.deleted_at
    task.client_updated_at = payload.client_updated_at


def _apply_time_entry(db: Session, payload: TimeEntryPayload, op: str) -> None:
    entry = db.get(TimeEntry, payload.id)
    if entry is None:
        entry = TimeEntry(id=payload.id)
        db.add(entry)

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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/sync", response_model=SyncResponse)
def sync(payload: SyncRequest, db: Session = Depends(get_db)):
    for change in payload.changes.tasks:
        _apply_task(db, change.data, change.op)

    for change in payload.changes.time_entries:
        _apply_time_entry(db, change.data, change.op)

    db.commit()

    last_sync = payload.last_sync_at
    task_query = select(Task)
    entry_query = select(TimeEntry)
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
