from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _utcnow() -> datetime:
    return datetime.utcnow()


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    client_updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class TimeEntry(Base):
    __tablename__ = "time_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(String, ForeignKey("tasks.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    comment: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    client_updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
