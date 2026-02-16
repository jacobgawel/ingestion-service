import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/ws", tags=["ingestion"])


@router.websocket("/jobs/{job_id}")
async def websocket_jobs(websocket: WebSocket, job_id: str):
    await websocket.accept()
    try:
        while True:
            # 1. Check job status (replace with your real logic)
            # current_status = await get_job_status(job_id)
            # await websocket.send_json(current_status)

            # 2. SEND HEARTBEAT to prevent 1006 timeout
            await websocket.send_text("ping")

            await asyncio.sleep(5)

        await websocket.close(code=1000, reason="Job completed")

    except WebSocketDisconnect:
        print(f"Client disconnected from job {job_id}")
    except Exception as e:
        print(f"WebSocket error: {e}")
