from typing import BinaryIO, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, computed_field


class IngestionFilePayload(BaseModel):
    file_id: UUID | None = None
    filename: str | None
    object_name: str  # The key in MinIO (e.g., "uuid-file.pdf")
    content_type: str | None


class IngestionWorkflowRequest(BaseModel):
    source: Optional[str] = Field(
        None, description="Optional field that will append a source for filtering"
    )
    project_id: Optional[str] = Field(
        None, description="ID of the project that this will be associated with"
    )


class FileProcessingContext(BaseModel):
    """Contains all required info for processing a single file."""

    model_config = {"arbitrary_types_allowed": True}

    file_stream: Optional[BinaryIO] = None
    file_name: str
    file_path: Optional[str] = None
    source: Optional[str] = None
    project_id: Optional[str] = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def file_extension(self) -> str:
        return (
            self.file_name.rsplit(".", 1)[-1].lower() if "." in self.file_name else ""
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_plain_text(self) -> bool:
        return self.file_extension == "txt"

    @classmethod
    def from_request(
        cls,
        file_name: str,
        request: IngestionWorkflowRequest,
        file_path: Optional[str] = None,
        file_stream: Optional[BinaryIO] = None,
    ) -> "FileProcessingContext":
        return cls(
            file_stream=file_stream,
            file_name=file_name,
            file_path=file_path,
            source=request.source,
            project_id=request.project_id,
        )


class IngestionWorkflowDTO(BaseModel):
    job_id: str = Field(..., description="ScyllaDB job ID for status tracking")
    request: IngestionWorkflowRequest = Field(
        ..., description="The request object that's being passed into ingest"
    )
    files: List[IngestionFilePayload] = Field(..., description="Files to process")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def source(self) -> str:
        return self.request.source or "api"
