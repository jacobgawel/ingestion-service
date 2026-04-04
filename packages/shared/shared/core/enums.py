from enum import StrEnum


class LOG_LEVEL(StrEnum):
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"
    TRACE = "trace"


class INGESTION_STATUS(StrEnum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    FAILED = "failed"
