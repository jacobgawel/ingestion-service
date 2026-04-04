from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.core.enums import LOG_LEVEL

_WORKSPACE_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    """Application settings"""

    ASGI_PATH: str = "api.main:app"
    APP_NAME: str = "Ingestion Service"
    DEBUG: bool = True
    APP_VERSION: str = "v0.1.0"
    PORT: int = Field(default=8065, description="Port for the application")
    HOST: str = Field(default="127.0.0.1", description="Host url for the application")

    APP_LOG_LEVEL: LOG_LEVEL = Field(
        default=LOG_LEVEL.INFO, description="Log level for the application"
    )

    # OpenAI
    OPENAI_KEY: str = Field(
        ..., description="OpenAI API key for embeddings and chat completions"
    )
    # Temporal
    TEMPORAL_HOST: str = Field(
        default="localhost:7233", description="Temporal server host"
    )

    # NATS
    NATS_URL: str = Field(
        default="nats://localhost:4222", description="NATS server URL"
    )

    # AlloyDB
    ALLOYDB_HOST: str = Field(default="localhost", description="AlloyDB server host")
    ALLOYDB_PORT: int = Field(default=5432, description="AlloyDB server port")
    ALLOYDB_DATABASE: str = Field(
        default="postgres", description="AlloyDB database name"
    )
    ALLOYDB_USER: str | None = Field(
        default=None, description="AlloyDB authentication username"
    )
    ALLOYDB_PASSWORD: str | None = Field(
        default=None, description="AlloyDB authentication password"
    )

    # Worker
    MAX_CONCURRENT_FILES: int = Field(
        default=4, description="Max concurrent file processing in worker"
    )

    # Embedding
    EMBEDDING_DIMENTIONS: int = Field(
        default=1536, description="Embedding model dimensions"
    )
    EMBEDDING_MODEL: str = Field(
        default="text-embedding-3-small",
        description="Model utilised for embedding",
    )

    # Minio
    MINIO_HOST: str = Field(..., description="Minio host name")
    MINIO_ACCESS_KEY: str = Field(..., description="Minio access key")
    MINIO_SECRET_KEY: str = Field(..., description="Minio secret key")

    model_config = SettingsConfigDict(
        env_file=str(_WORKSPACE_ROOT / ".env"), case_sensitive=True
    )


config = Settings()  # pyright: ignore[reportCallIssue]
