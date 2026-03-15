from pydantic import BaseModel


class FileEntity(BaseModel):
    job_id: str
    project_id: str
    file_id: str
    source: str
    filename: str
    object_name: str
    content_type: str
    status: str
    created_at: str
    updated_at: str
    error_message: str


class FileSummary(BaseModel):
    file_id: str
    filename: str
    status: str
