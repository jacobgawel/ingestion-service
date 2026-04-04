from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_ingestion_repository
from shared.core.logger import get_logger
from shared.models.api import FileStatusResponse, JobResponse, JobStatusResponse
from shared.repositories.ingestion import IngestionRepository

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = get_logger("JobsRoute")


@router.get("")
async def get_jobs(
    source: Optional[str] = Query(None, description="Filter by source"),
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    repo: IngestionRepository = Depends(get_ingestion_repository),
) -> list[JobResponse]:
    """Get all ingestion jobs, optionally filtered by source and/or project_id."""
    jobs = await repo.get_jobs(source=source, project_id=project_id)
    return [JobResponse(**job) for job in jobs]


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    repo: IngestionRepository = Depends(get_ingestion_repository),
) -> JobStatusResponse:
    """Get a single ingestion job by ID, including its files."""
    job = await repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    files = await repo.get_job_files(job_id)
    return JobStatusResponse(
        **job,
        files=[FileStatusResponse(**f) for f in files],
    )
