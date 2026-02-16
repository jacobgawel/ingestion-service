from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from app.models.workflows import IngestionWorkflowDTO


@workflow.defn
class IngestionWorkflow:
    @workflow.run
    async def run(self, workflow_dto: IngestionWorkflowDTO):
        # If OpenAI/Docling crashes, retry up to 5 times, waiting longer each time.
        common_retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=100),
            maximum_attempts=5,
        )

        # --- STEP 1: PARSE ---
        documents = await workflow.execute_activity(
            "parse_files",
            args=[workflow_dto.request, workflow_dto.files],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=common_retry_policy,
        )

        # --- STEP 2: EMBED ---
        result = await workflow.execute_activity(
            "embed_markdown",
            args=[workflow_dto.request, documents],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=common_retry_policy,
        )

        return "Workflow Complete: " + result
