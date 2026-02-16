import asyncio

from temporalio.worker import Worker

from app.clients import (
    get_minio_handler,
    get_mixedbread_client,
    get_openai_client,
    get_qdrant_client,
    get_temporal_client,
)
from app.clients.temporal_client import initialize_temporal
from app.core.temporal import WORKER_QUEUE
from app.service import IngestionService
from app.temporal.activities import IngestionActivities
from app.temporal.workflows import IngestionWorkflow


async def main():
    await initialize_temporal()
    minio_handler = get_minio_handler()
    minio_handler.initialize()

    client = get_temporal_client()

    ingestion_service = IngestionService(
        qdrant_client=get_qdrant_client(),
        openai_client=get_openai_client(),
        mixedbread_client=get_mixedbread_client(),
    )
    activities = IngestionActivities(ingestion_service, minio_handler)

    worker = Worker(
        client,
        task_queue=WORKER_QUEUE.INGESTION,
        workflows=[IngestionWorkflow],
        activities=[activities.parse_files, activities.embed_markdown],
    )

    print("🚀 Worker started!")

    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
