"""Layer 3a/4: API DTOs (Pydantic v2) — generated from contract.json; do not hand-edit shapes."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# enums project to Literal unions on the API surface (matches the TS client exactly)
UserRole = Literal["admin", "member"]
TaskStatus = Literal["todo", "in_progress", "done"]


# --- User ---------------------------------------------------------------

class UserCreate(BaseModel):
    email: str = Field(max_length=255)
    display_name: str = Field(max_length=80)
    role: UserRole = "member"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    role: UserRole
    created_at: datetime


# --- Project ------------------------------------------------------------

class ProjectCreate(BaseModel):
    owner_id: uuid.UUID
    name: str = Field(max_length=120)
    description: Optional[str] = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    description: Optional[str]
    is_archived: bool
    created_at: datetime


# --- Task ---------------------------------------------------------------

class TaskCreate(BaseModel):
    project_id: uuid.UUID
    title: str = Field(max_length=200)
    status: TaskStatus = "todo"
    priority: int = 0
    due_date: Optional[datetime] = None
    assignee_id: Optional[uuid.UUID] = None
    metadata: Optional[dict[str, Any]] = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    status: TaskStatus
    priority: int
    due_date: Optional[datetime]
    assignee_id: Optional[uuid.UUID]
    metadata: Optional[dict[str, Any]] = Field(default=None, validation_alias="metadata_")
    created_at: datetime


# --- Comment ------------------------------------------------------------

class CommentCreate(BaseModel):
    task_id: uuid.UUID
    author_id: uuid.UUID
    body: str


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    author_id: uuid.UUID
    body: str
    created_at: datetime
