"""Temporal client singleton instance."""

from typing import Optional

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from app.core.settings import config


class TemporalManager:
    """Singleton class for Temporal client to ensure single instance across the application."""

    _instance: Optional["TemporalManager"] = None
    _client: Optional[Client] = None
    _initialized: bool = False

    def __new__(cls) -> "TemporalManager":
        """Ensure only one instance is created."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def _create_client(self) -> Client:
        """Create and configure the Temporal client."""
        return await Client.connect(
            config.TEMPORAL_HOST,
            data_converter=pydantic_data_converter,
        )

    async def initialize(self) -> None:
        """Initialize the Temporal client (async). Must be called before accessing the client."""
        if not self.__class__._initialized:
            self._client = await self._create_client()
            self.__class__._initialized = True

    @property
    def client(self) -> Client:
        """Get the Temporal client instance."""
        if self._client is None:
            raise RuntimeError(
                "Temporal client not initialized. Call 'await temporal_manager.initialize()' first."
            )
        return self._client

    async def close(self) -> None:
        """Close the Temporal client connection."""
        if self._client:
            self.__class__._initialized = False
            self.__class__._instance = None
            self._client = None


# Create a singleton instance
_temporal_singleton = TemporalManager()


async def initialize_temporal() -> None:
    """Initialize the Temporal client singleton. Call during app startup."""
    await _temporal_singleton.initialize()


async def close_temporal() -> None:
    """Close the Temporal client singleton. Call during app shutdown."""
    await _temporal_singleton.close()


def get_temporal_client() -> Client:
    """
    Get the singleton Temporal client instance.

    Returns:
        Client: The singleton Temporal client instance.
    """
    return _temporal_singleton.client
