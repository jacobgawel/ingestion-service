from pydantic import Field
from pydantic_settings import BaseSettings

from app.core.enums import LOG_LEVEL


class Settings(BaseSettings):
    """Application settings"""

    ASGI_PATH: str = "main:app"
    APP_NAME: str = "Ingestion Service"
    DEBUG: bool = True
    APP_VERSION: str = "v0.1.0"
    PORT: int = Field(default=8065, description="Port for the application")
    HOST: str = Field(default="127.0.0.1", description="Host url for the application")

    APP_LOG_LEVEL: LOG_LEVEL = Field(
        default=LOG_LEVEL.INFO, description="Log level for the application"
    )

    # Qdrant configuration
    QDRANT_HOST: str = Field(default="localhost", description="Qdrant server host")
    QDRANT_PORT: int = Field(default=6333, description="Qdrant server port")
    QDRANT_GRPC_PORT: int = Field(default=6334, description="Qdrant gRPC port")
    QDRANT_API_KEY: str | None = Field(
        default=None, description="Qdrant API key (optional)"
    )
    QDRANT_PREFER_GRPC: bool = Field(
        default=False, description="Prefer gRPC over REST API"
    )
    QDRANT_CLOUD_INFERENCE: bool = Field(
        default=False, description="Enable Qdrants cloud inference"
    )

    # OpenAI
    OPENAI_KEY: str = Field(
        ..., description="OpenAI API key for embeddings and chat completions"
    )
    MIXEDBREAD_KEY: str = Field(..., description="Mixedbread API key for embeddings")

    # Temporal
    TEMPORAL_HOST: str = Field(
        default="localhost:7233", description="Temporal server host"
    )

    # ScyllaDB
    SCYLLA_HOSTS: str = Field(
        default="localhost:9042",
        description="Comma-separated ScyllaDB contact points (host:port)",
    )
    SCYLLA_KEYSPACE: str | None = Field(
        default=None, description="Default ScyllaDB keyspace"
    )
    SCYLLA_USERNAME: str | None = Field(
        default=None, description="ScyllaDB authentication username"
    )
    SCYLLA_PASSWORD: str | None = Field(
        default=None, description="ScyllaDB authentication password"
    )

    # Minio
    MINIO_HOST: str = Field(..., description="Minio host name")
    MINIO_ACCESS_KEY: str = Field(..., description="Minio access key")
    MINIO_SECRET_KEY: str = Field(..., description="Minio secret key")

    class Config:
        env_file = ".env"
        case_sensitive = True


config = Settings()  # pyright: ignore[reportCallIssue]
