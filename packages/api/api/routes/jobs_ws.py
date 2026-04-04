import asyncio
import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from nats.aio.client import Client as NATSClient
from nats.aio.subscription import Subscription

from shared.clients import get_nats_client
from api.dependencies import get_ingestion_repository
from shared.core.enums import INGESTION_STATUS
from shared.core.logger import get_logger
from shared.repositories import IngestionRepository

router = APIRouter(prefix="/ws", tags=["ingestion"])
logger = get_logger("JobsWebSocket")

TERMINAL_STATUSES = {INGESTION_STATUS.COMPLETED, INGESTION_STATUS.FAILED}


@router.websocket("/jobs/{job_id}")
async def websocket_jobs(
    websocket: WebSocket,
    job_id: str,
    repo: IngestionRepository = Depends(get_ingestion_repository),
) -> None:
    await websocket.accept()

    nats_client: NATSClient = get_nats_client()
    sub: Subscription | None = None

    try:
        job = await repo.get_job(job_id)

        if job is None:
            await websocket.send_json({"error": f"Job {job_id} not found"})
            await websocket.close(code=1008, reason="Job not found")
            return

        # Subscribe FIRST to avoid missing updates between DB read and subscribe
        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=128)

        async def _on_message(msg) -> None:
            try:
                queue.put_nowait(msg.data)
            except asyncio.QueueFull:
                logger.warning(f"Queue full for job {job_id}, dropping message")

        sub = await nats_client.subscribe(f"jobs.{job_id}", cb=_on_message)

        # Now fetch current file state (any updates after this are caught by sub)
        files = await repo.get_job_file_summaries(job_id)

        await websocket.send_json(
            {
                "type": "files_snapshot",
                "job_id": job_id,
                "files": [f.model_dump(mode="json") for f in files],
            }
        )

        await websocket.send_json(
            {
                "type": "job_update",
                "job_id": job["job_id"],
                "status": job["status"],
                "total_files": job.get("total_files", 0),
                "files_completed": job.get("files_completed", 0),
                "files_failed": job.get("files_failed", 0),
            }
        )

        if job["status"] in TERMINAL_STATUSES:
            await websocket.close(code=1000, reason="Job completed")
            return

        # Relay live updates
        while True:
            data: bytes = await queue.get()
            payload: dict = json.loads(data)
            await websocket.send_json(payload)

            if (
                payload.get("type") == "job_update"
                and payload.get("status") in TERMINAL_STATUSES
            ):
                await websocket.close(code=1000, reason="Job completed")
                return

    except WebSocketDisconnect:
        logger.info(f"Client disconnected from job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}")
    finally:
        if sub:
            await sub.unsubscribe()
