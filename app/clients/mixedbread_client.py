from typing import Optional

from mixedbread import AsyncMixedbread

from app.core.settings import config


class MixedbreadManager:
    """Singleton class for Mixedbread client client to ensure single instance across the application."""

    _instance: Optional["MixedbreadManager"] = None
    _client: Optional[AsyncMixedbread] = None
    _initialized: bool = False

    def __new__(cls) -> "MixedbreadManager":
        """Ensure only one instance is created."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the Mixedbread client only once."""
        if not self.__class__._initialized:
            self._client = self._create_client()
            self.__class__._initialized = True

    def _create_client(self) -> AsyncMixedbread:
        """Create and configure the Mixedbread client."""
        return AsyncMixedbread(api_key=config.MIXEDBREAD_KEY)

    @property
    def client(self) -> AsyncMixedbread:
        """Get the MixedBread client instance"""
        if self._client is None:
            raise RuntimeError("Mixedbread client not initialized")

        return self._client

    async def close(self) -> None:
        """Close the MixedBread client connection."""
        if self._client:
            await self._client.close()
            self.__class__._initialized = False
            self.__class__._instance = None
            self._client = None


# Create a singleton instance
_mixedbread_singleton = MixedbreadManager()


def get_mixedbread_client() -> AsyncMixedbread:
    return _mixedbread_singleton.client
