"""Qdrant client singleton instance."""

from typing import Optional

from qdrant_client import AsyncQdrantClient

from app.core.settings import config


class QdrantManager:
    """Singleton class for Qdrant client to ensure single instance across the application."""

    _instance: Optional["QdrantManager"] = None
    _client: Optional[AsyncQdrantClient] = None
    _initialized: bool = False

    def __new__(cls) -> "QdrantManager":
        """Ensure only one instance is created."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the Qdrant client only once."""
        if not self.__class__._initialized:
            self._client = self._create_client()
            self.__class__._initialized = True

    def _create_client(self) -> AsyncQdrantClient:
        """Create and configure the Qdrant client."""
        return AsyncQdrantClient(
            host=config.QDRANT_HOST,
            port=config.QDRANT_PORT,
            grpc_port=config.QDRANT_GRPC_PORT,
            api_key=config.QDRANT_API_KEY,
            prefer_grpc=config.QDRANT_PREFER_GRPC,
            cloud_inference=config.QDRANT_CLOUD_INFERENCE,
        )

    @property
    def client(self) -> AsyncQdrantClient:
        """Get the Qdrant client instance."""
        if self._client is None:
            raise RuntimeError("Qdrant client not initialized")
        return self._client

    async def close(self) -> None:
        """Close the Qdrant client connection."""
        if self._client:
            await self._client.close()
            self.__class__._initialized = False
            self.__class__._instance = None
            self._client = None


# Create a singleton instance
_qdrant_singleton = QdrantManager()


def get_qdrant_client() -> AsyncQdrantClient:
    """
    Get the singleton Qdrant client instance.

    Returns:
        QdrantClient: The singleton Qdrant client instance.
    """
    return _qdrant_singleton.client
