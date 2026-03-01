from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class IngestionFilePayload(BaseModel):
    file_id: UUID | None = None
    filename: str | None
    object_name: str  # The key in MinIO (e.g., "uuid-file.pdf")
    content_type: str | None


class IngestionWorkflowRequest(BaseModel):
    user_id: Optional[str] = Field(
        None, description="Optional field that will append a user_id for filtering"
    )
    project_id: Optional[str] = Field(
        None, description="ID of the project that this will be associated with"
    )


class IngestionWorkflowDTO(BaseModel):
    job_id: str = Field(..., description="ScyllaDB job ID for status tracking")
    request: IngestionWorkflowRequest = Field(
        ..., description="The request object that's being passed into ingest"
    )
    files: List[IngestionFilePayload] = Field(..., description="Files to process")
