from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, computed_field

from app.core.constants import IMAGE_EXTENSIONS


class PersonDetail(BaseModel):
    """A person visible in an image."""

    description: str
    action: str


class ImageCaptionResponse(BaseModel):
    """Structured response from the vision model for image captioning."""

    short_caption: str
    detailed_caption: str
    objects: list[str]
    actions: list[str]
    scene: str
    text_in_image: list[str]
    brands_or_logos: list[str]
    people: list[PersonDetail]
    colors: list[str]
    keywords: list[str]
    relationships: list[str]

    def to_dense_text(self) -> str:
        """Flatten all fields into a single dense string for embedding."""
        parts: list[str] = [
            self.short_caption,
            self.detailed_caption,
            *self.objects,
            *self.actions,
            self.scene,
            *self.text_in_image,
            *self.brands_or_logos,
            *(f"{p.description} {p.action}" for p in self.people),
            *self.colors,
            *self.keywords,
            *self.relationships,
        ]
        return " ".join(parts)


class ChunkData(BaseModel):
    """Carries chunk data between service → activity → repository."""

    content: str
    heading: str | None = None
    embedding: list[float]
    token_count: int


class IngestionFilePayload(BaseModel):
    file_id: UUID | None = None
    filename: str | None
    object_url: str  # The key in MinIO (e.g., "uuid-file.pdf")
    content_type: str | None
    file_size: int
    object_path: str  # Path to object in MinIO (e.g. {project_id}/asdasd)
    file_hash: str

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_image(self) -> bool:
        ext = (self.filename or "").rsplit(".", 1)[-1].lower()
        return ext in IMAGE_EXTENSIONS


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

    file_name: str
    file_path: Optional[str] = None
    source: Optional[str] = None
    project_id: Optional[str] = None
    object_path: str
    object_url: str

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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_image(self) -> bool:
        return self.file_extension in IMAGE_EXTENSIONS

    @classmethod
    def from_request(
        cls,
        file_name: str,
        request: IngestionWorkflowRequest,
        object_url: str,
        object_path: str,
        file_path: Optional[str] = None,
    ) -> "FileProcessingContext":
        return cls(
            file_name=file_name,
            file_path=file_path,
            source=request.source,
            project_id=request.project_id,
            object_url=object_url,
            object_path=object_path,
        )


class IngestionWorkflowDTO(BaseModel):
    job_id: str = Field(..., description="Job ID for status tracking")
    request: IngestionWorkflowRequest = Field(
        ..., description="The request object that's being passed into ingest"
    )
    files: List[IngestionFilePayload] = Field(..., description="Files to process")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def source(self) -> str:
        return self.request.source or "api"
