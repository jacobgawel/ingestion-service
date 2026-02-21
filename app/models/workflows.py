from typing import List, Optional

from pydantic import BaseModel, Field


class IngestionFilePayload(BaseModel):
    filename: str | None
    object_name: str  # CHANGED: The key in MinIO (e.g., "uuid-file.pdf")
    content_type: str | None


class IngestionWorkflowRequest(BaseModel):
    user_id: Optional[str] = Field(
        None, description="Optional field that will append a user_id for filtering"
    )
    project_id: Optional[str] = Field(
        None, description="ID of the project that this will be associated with"
    )


class IngestionWorkflowDTO(BaseModel):
    request: IngestionWorkflowRequest = Field(
        ..., description="The request object that's being passed into ingest"
    )
    files: List[IngestionFilePayload] = Field(..., description="Files to process")
