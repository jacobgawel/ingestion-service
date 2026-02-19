from typing import Optional

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
