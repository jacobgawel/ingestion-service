import asyncio

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from app.clients import get_mixedbread_client, get_openai_client, get_qdrant_client
from app.core.temporal import WORKER_QUEUE
from app.service import IngestionService
from app.temporal.activities import IngestionActivities
from app.temporal.workflows import IngestionWorkflow


async def main():
    client = await Client.connect(
        "localhost:7233", data_converter=pydantic_data_converter
    )

    ingestion_service = IngestionService(
        qdrant_client=get_qdrant_client(),
        openai_client=get_openai_client(),
        mixedbread_client=get_mixedbread_client(),
    )
    activities = IngestionActivities(ingestion_service)

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
