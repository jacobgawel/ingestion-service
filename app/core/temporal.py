from enum import StrEnum


class WORKER_QUEUE(StrEnum):
    INGESTION = "ingestion-queue"


class INGESTION_ACTIVITY(StrEnum):
    PARSE_AND_EMBED = "parse_and_embed"
    FINALIZE_JOB = "finalize_job"


class INGESTION_WORKFLOW(StrEnum):
    WORKFLOW = "IngestionWorkflow"
