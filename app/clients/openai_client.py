"""OpenAI client singleton instance."""

from typing import Optional

from openai import AsyncOpenAI

from app.core.settings import config


class OpenAIManager:
    """Singleton class for OpenAI client to ensure single instance across the application."""

    _instance: Optional["OpenAIManager"] = None
    _client: Optional[AsyncOpenAI] = None
    _initialized: bool = False

    def __new__(cls) -> "OpenAIManager":
        """Ensure only one instance is created."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the OpenAI client only once."""
        if not self.__class__._initialized:
            self._client = self._create_client()
            self.__class__._initialized = True

    def _create_client(self) -> AsyncOpenAI:
        """Create and configure the OpenAI client."""
        return AsyncOpenAI(
            api_key=config.OPENAI_KEY,
        )

    @property
    def client(self) -> AsyncOpenAI:
        """Get the OpenAI client instance."""
        if self._client is None:
            raise RuntimeError("OpenAI client not initialized")
        return self._client

    async def close(self) -> None:
        """Close the OpenAI client connection."""
        if self._client:
            await self._client.close()
            self.__class__._initialized = False
            self.__class__._instance = None
            self._client = None


# Create a singleton instance
_openai_singleton = OpenAIManager()


def get_openai_client() -> AsyncOpenAI:
    """
    Get the singleton OpenAI client instance.

    Returns:
        AsyncOpenAI: The singleton OpenAI client instance.
    """
    return _openai_singleton.client
