from enum import StrEnum


class WORKER_QUEUE(StrEnum):
    INGESTION = "ingestion-queue"


class INGESTION_ACTIVITY(StrEnum):
    PARSE_FILES = "parse_files"
    EMBED_MARKDOWN = "embed_markdown"


class INGESTION_WORKFLOW(StrEnum):
    INGESTION_WORFKLOW = "IngestionWorkflow"
