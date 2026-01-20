from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class TaskPayload(BaseModel):
    id: str
    title: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    client_updated_at: datetime


class TimeEntryPayload(BaseModel):
    id: str
    task_id: str
    started_at: datetime
    stopped_at: datetime | None = None
    comment: str | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    client_updated_at: datetime


class TaskChange(BaseModel):
    op: Literal["upsert", "delete"]
    data: TaskPayload


class TimeEntryChange(BaseModel):
    op: Literal["upsert", "delete"]
    data: TimeEntryPayload


class SyncChanges(BaseModel):
    tasks: list[TaskChange] = []
    time_entries: list[TimeEntryChange] = []


class SyncRequest(BaseModel):
    last_sync_at: datetime | None = None
    changes: SyncChanges


class SyncResponse(BaseModel):
    server_time: datetime
    tasks: list[TaskPayload]
    time_entries: list[TimeEntryPayload]
