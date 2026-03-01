from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from app.core.enums import INGESTION_STATUS
from app.core.temporal import INGESTION_ACTIVITY
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

        try:
            # --- STEP 1: PARSE ---
            documents = await workflow.execute_activity(
                INGESTION_ACTIVITY.PARSE_FILES,
                args=[workflow_dto.job_id, workflow_dto.request, workflow_dto.files],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=common_retry_policy,
            )

            # --- STEP 2: EMBED ---
            result = await workflow.execute_activity(
                INGESTION_ACTIVITY.EMBED_MARKDOWN,
                args=[workflow_dto.request, documents],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=common_retry_policy,
            )

            # --- STEP 3: FINALIZE (success) ---
            await workflow.execute_activity(
                INGESTION_ACTIVITY.FINALIZE_JOB,
                args=[workflow_dto.job_id, INGESTION_STATUS.COMPLETED, None],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=common_retry_policy,
            )

            return "Workflow Complete: " + result

        except Exception as e:
            # --- FINALIZE (failure) ---
            await workflow.execute_activity(
                INGESTION_ACTIVITY.FINALIZE_JOB,
                args=[
                    workflow_dto.job_id,
                    INGESTION_STATUS.FAILED,
                    str(e),
                ],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=common_retry_policy,
            )
            raise
