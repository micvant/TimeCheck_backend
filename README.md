# TimeCheck Backend

API для учета времени (FastAPI + SQLAlchemy).

## Требования
- Python 3.10+

## Запуск
```bash
cd /home/micvant/PycharmProjects/TimeCheck_backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API будет доступен на `http://localhost:8000`.

## Переменные окружения
Можно указать Postgres:
```bash
export DATABASE_URL="postgresql+psycopg2://user:pass@localhost:5432/timecheck"
```

Для JWT:
```bash
export SECRET_KEY="super-secret-key"
```

## Авторизация
- `POST /auth/register` (email, password) -> токен
- `POST /auth/login` (form-urlencoded) -> токен
- `POST /sync` требует `Authorization: Bearer <token>`
