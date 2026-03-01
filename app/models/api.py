from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import Form
from pydantic import BaseModel, Field


class IngestionRequest(BaseModel):
    user_id: Optional[str] = Field(
        description="Optional field that will append a user_id for filtering"
    )
    project_id: Optional[str] = Field(
        description="ID of the project that this will be associated with"
    )

    @classmethod
    def as_form(
        cls,
        user_id: Optional[str] = Form(None),
        project_id: Optional[str] = Form(None),
    ):
        return cls(user_id=user_id, project_id=project_id)


class IngestionResponse(BaseModel):
    status: str
    job_id: str
    workflow_id: str
    run_id: str | None
    message: str


class FileStatusResponse(BaseModel):
    file_id: UUID
    filename: str | None
    object_name: str
    content_type: str | None
    status: str
    created_at: datetime | None
    updated_at: datetime | None
    error_message: str | None


class JobStatusResponse(BaseModel):
    job_id: str
    user_id: str | None
    project_id: str | None
    status: str
    total_files: int
    files_completed: int
    files_failed: int
    created_at: datetime | None
    updated_at: datetime | None
    error_message: str | None
    files: list[FileStatusResponse]
