from typing import Optional
from fastapi import Form
from pydantic import BaseModel, Field


class IngestionRequest(BaseModel):
    job_id: str = Field(..., description="ID of the workflow job")
    user_id: Optional[str] = Field(
        description="Optional field that will append a user_id for filtering"
    )
    project_id: Optional[str] = Field(
        description="ID of the project that this will be associated with"
    )

    @classmethod
    def as_form(
        cls,
        job_id: str = Form(...),
        user_id: Optional[str] = Form(None),
        project_id: Optional[str] = Form(None),
    ):
        return cls(job_id=job_id, user_id=user_id, project_id=project_id)
