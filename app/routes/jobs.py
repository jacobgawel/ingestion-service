import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.clients import get_scylla_session
from app.core.enums import INGESTION_STATUS
from app.core.logger import get_logger
from app.repositories import IngestionRepository
from app.service.scylla import ScyllaService

router = APIRouter(prefix="/ws", tags=["ingestion"])
logger = get_logger("JobsWebSocket")


@router.websocket("/jobs/{job_id}")
async def websocket_jobs(websocket: WebSocket, job_id: str):
    await websocket.accept()
    repo = IngestionRepository(scylla=ScyllaService(session=get_scylla_session()))

    try:
        while True:
            job = await repo.get_job(job_id)

            if job is None:
                await websocket.send_json({"error": f"Job {job_id} not found"})
                await websocket.close(code=1008, reason="Job not found")
                return

            await websocket.send_json(
                {
                    "job_id": job["job_id"],
                    "status": job["status"],
                    "total_files": job.get("total_files", 0),
                    "files_completed": job.get("files_completed", 0),
                    "files_failed": job.get("files_failed", 0),
                }
            )

            if job["status"] in (
                INGESTION_STATUS.COMPLETED,
                INGESTION_STATUS.FAILED,
            ):
                await websocket.close(code=1000, reason="Job completed")
                return

            await asyncio.sleep(2)

    except WebSocketDisconnect:
        logger.info(f"Client disconnected from job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}")
