import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from nats.aio.client import Client as NATSClient
from nats.aio.subscription import Subscription

from app.clients import get_nats_client, get_scylla_session
from app.core.enums import INGESTION_STATUS
from app.core.logger import get_logger
from app.repositories import IngestionRepository
from app.service.scylla import ScyllaService

router = APIRouter(prefix="/ws", tags=["ingestion"])
logger = get_logger("JobsWebSocket")

TERMINAL_STATUSES = {INGESTION_STATUS.COMPLETED, INGESTION_STATUS.FAILED}


@router.websocket("/jobs/{job_id}")
async def websocket_jobs(websocket: WebSocket, job_id: str) -> None:
    await websocket.accept()
    repo = IngestionRepository(scylla=ScyllaService(session=get_scylla_session()))
    nats_client: NATSClient = get_nats_client()
    sub: Subscription | None = None

    try:
        # Send current state so late-joiners get caught up
        job = await repo.get_job(job_id)

        if job is None:
            await websocket.send_json({"error": f"Job {job_id} not found"})
            await websocket.close(code=1008, reason="Job not found")
            return

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

        # Subscribe to live updates
        queue: asyncio.Queue[bytes] = asyncio.Queue()

        async def _on_message(msg) -> None:
            await queue.put(msg.data)

        sub = await nats_client.subscribe(f"jobs.{job_id}", cb=_on_message)

        while True:
            # we wait for updates to land on the queue
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
