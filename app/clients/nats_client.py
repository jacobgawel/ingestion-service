"""NATS client singleton instance."""

from typing import Optional

import nats
from nats.aio.client import Client as NATSClient

from app.core.logger import get_logger
from app.core.settings import config

logger = get_logger("NATSManager")


class NATSManager:
    """Singleton class for NATS client to ensure single instance across the application."""

    _instance: Optional["NATSManager"] = None
    _client: Optional[NATSClient] = None
    _initialized: bool = False

    def __new__(cls) -> "NATSManager":
        """Ensure only one instance is created."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self) -> None:
        """Initialize the NATS connection. Must be called during app startup."""
        if not self.__class__._initialized:
            self._client = await nats.connect(config.NATS_URL)
            logger.info("NATS client initialized successfully")
            self.__class__._initialized = True

    @property
    def client(self) -> NATSClient:
        """Get the NATS client instance."""
        if self._client is None:
            raise RuntimeError(
                "NATS client not initialized. Call 'await nats_manager.initialize()' first."
            )
        return self._client

    async def close(self) -> None:
        """Drain and close the NATS connection."""
        if self._client:
            await self._client.drain()
            logger.info("NATS client shut down")
            self.__class__._initialized = False
            self.__class__._instance = None
            self._client = None


_nats_singleton = NATSManager()


async def initialize_nats() -> None:
    """Initialize the NATS singleton client."""
    await _nats_singleton.initialize()


async def close_nats() -> None:
    """Close the NATS singleton client."""
    await _nats_singleton.close()


def get_nats_client() -> NATSClient:
    """Get the singleton NATS client instance."""
    return _nats_singleton.client
