import asyncio

from temporalio.worker import Worker

from app.clients import (
    get_alloydb_pool,
    get_minio_handler,
    get_nats_client,
    get_openai_client,
    get_temporal_client,
    initialize_all,
)
from app.core.temporal import WORKER_QUEUE
from app.database import AlloyDBEngine
from app.repositories import IngestionRepository
from app.service import IngestionService
from app.temporal.activities import IngestionActivities
from app.temporal.workflows import IngestionWorkflow


async def main():
    await initialize_all()

    alloydb_engine = AlloyDBEngine(pool=get_alloydb_pool())
    ingestion_repo = IngestionRepository(alloydb=alloydb_engine)

    ingestion_service = IngestionService(
        openai_client=get_openai_client(),
    )
    activities = IngestionActivities(
        ingestion_service, get_minio_handler(), ingestion_repo, get_nats_client()
    )

    worker = Worker(
        get_temporal_client(),
        task_queue=WORKER_QUEUE.INGESTION,
        workflows=[IngestionWorkflow],
        activities=[
            activities.parse_and_embed,
            activities.finalize_job,
        ],
    )

    print("Worker started!")

    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
