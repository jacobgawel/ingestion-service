"""Playground script for embedding text using the same OpenAI model as the ingestion service."""

import asyncio
import os
import sys

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

MODEL = "text-embedding-3-small"
DIMENSIONS = 1536


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts and return their vectors."""
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_KEY"))

    try:
        response = await client.embeddings.create(
            input=texts,
            model=MODEL,
            dimensions=DIMENSIONS,
        )
        return [item.embedding for item in response.data]
    finally:
        await client.close()


async def main() -> None:
    if len(sys.argv) > 1:
        texts = sys.argv[1:]
    else:
        texts = [
            "Some random dog",
        ]

    print(f"Model: {MODEL} | Dimensions: {DIMENSIONS}")
    print(f"Embedding {len(texts)} text(s)...\n")

    embeddings = await embed_texts(texts)

    for i, (text, embedding) in enumerate(zip(texts, embeddings)):
        print(f'[{i}] "{text}"')
        print(f"    Dimensions: {len(embedding)}")
        print(f"    Embedding:\n{embedding}\n")


if __name__ == "__main__":
    asyncio.run(main())
