"""NATS client singleton instance."""

import nats
from nats.aio.client import Client as NATSClient

from app.clients.base import ClientManager
from app.core.logger import get_logger
from app.core.settings import config

logger = get_logger("NATSManager")


class NATSManager(ClientManager[NATSClient]):
    """Singleton manager for the NATS client."""

    async def _create_client(self) -> NATSClient:
        client = await nats.connect(config.NATS_URL)
        logger.info("NATS client initialized successfully")
        return client

    async def _close_client(self) -> None:
        await self.client.drain()
        logger.info("NATS client shut down")


_nats_singleton = NATSManager()


def get_nats_client() -> NATSClient:
    return _nats_singleton.client
