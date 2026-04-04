from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FileEntity(BaseModel):
    job_id: str
    project_id: str
    file_id: UUID
    source: str
    filename: str
    object_name: str
    content_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    error_message: str


class FileSummary(BaseModel):
    file_id: UUID
    filename: str
    status: str
