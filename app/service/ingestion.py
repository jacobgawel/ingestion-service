import asyncio
import base64
from io import BytesIO
from pathlib import Path

from docling.document_converter import DocumentConverter
from docling_core.types.io import DocumentStream
from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.core.schema import TextNode
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from mixedbread import AsyncMixedbread
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from app.core.constants import IMAGE_MODEL, IMAGE_PROMPT
from app.core.logger import get_logger
from app.core.settings import config
from app.models.workflows import (
    ChunkData,
    FileProcessingContext,
    ImageCaptionResponse,
    IngestionWorkflowRequest,
)

logger = get_logger("IngestionService")


class IngestionService:
    """Ingestion service for processing data"""

    def __init__(
        self,
        qdrant_client: AsyncQdrantClient,
        openai_client: AsyncOpenAI,
        mixedbread_client: AsyncMixedbread,
    ):
        logger.info("Initializing IngestionService")
        self.converter = DocumentConverter()
        self.qdrant_client = qdrant_client
        self.openai_client = openai_client
        self.mixedbread_client = mixedbread_client
        Settings.embed_model = OpenAIEmbedding(
            model="text-embedding-3-small", api_key=config.OPENAI_KEY, dimensions=1536
        )
        self.qdrant_client = qdrant_client
        self.vector_store = QdrantVectorStore(
            client=None,
            aclient=self.qdrant_client,
            collection_name="nexus_knowledge_base",
        )
        logger.info("IngestionService initialized successfully")

    async def _caption_image(self, file_path: str) -> str:
        """Generate a dense text caption from an image using the vision model."""
        logger.info(f"Captioning image: {file_path}")

        image_bytes = await asyncio.to_thread(Path(file_path).read_bytes)
        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        suffix = Path(file_path).suffix.lstrip(".").lower()
        media_type_map = {
            "jpg": "jpeg",
            "jpeg": "jpeg",
            "png": "png",
            "gif": "gif",
            "webp": "webp",
            "bmp": "bmp",
            "tiff": "tiff",
            "svg": "svg+xml",
        }
        media_type = f"image/{media_type_map.get(suffix, 'png')}"

        logger.info(f"Sending image to vision model: {file_path}")
        response = await self.openai_client.beta.chat.completions.parse(
            model=IMAGE_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": IMAGE_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{b64_image}",
                            },
                        },
                    ],
                }
            ],
            response_format=ImageCaptionResponse,
            timeout=120.0,
        )
        logger.info(f"Received vision model response for: {file_path}")

        parsed = response.choices[0].message.parsed

        if parsed is not None:
            caption = parsed.to_dense_text()
        else:
            caption = response.choices[0].message.content or ""

        logger.info(f"Successfully captioned image: {file_path}")
        return caption

    async def _parse_file(self, ctx: FileProcessingContext) -> str:
        """Process file into text content."""
        logger.info(f"Parsing file: {ctx.file_name}")

        markdown_text = ""

        if ctx.is_image:
            if ctx.file_path:
                markdown_text = await self._caption_image(ctx.file_path)
            else:
                logger.warning(
                    f"Image file {ctx.file_name} requires file_path for captioning"
                )
        elif ctx.is_plain_text:
            if ctx.file_path:
                markdown_text = await asyncio.to_thread(
                    Path(ctx.file_path).read_text, "utf-8"
                )
            elif ctx.file_stream is not None:
                markdown_text = ctx.file_stream.read().decode("utf-8")
        else:
            if ctx.file_path:
                conversion_result = await asyncio.to_thread(
                    self.converter.convert, Path(ctx.file_path)
                )
                markdown_text = conversion_result.document.export_to_markdown()
            elif ctx.file_stream is not None:
                doc_stream = DocumentStream(
                    name=ctx.file_name, stream=BytesIO(ctx.file_stream.read())
                )
                conversion_result = await asyncio.to_thread(
                    self.converter.convert, doc_stream
                )
                markdown_text = conversion_result.document.export_to_markdown()

        logger.info(f"Successfully parsed file: {ctx.file_name}")

        return markdown_text

    async def process_file(self, ctx: FileProcessingContext) -> Document:
        result = await self._parse_file(ctx)
        return Document(
            text=result,
            metadata={
                "filename": ctx.file_name,
                "file_extension": ctx.file_extension,
                "source": ctx.source,
                "project_id": ctx.project_id,
            },
        )

    async def embed_single_document(
        self,
        request: IngestionWorkflowRequest,
        document: Document,
        is_image: bool = False,
    ) -> list[ChunkData]:
        if is_image:
            node = TextNode(
                text=document.text,
                metadata=document.metadata,
            )
            nodes = [node]
            logger.info(
                f"Created single node for image: {document.metadata.get('filename')}"
            )
        else:
            splitter = MarkdownNodeParser()
            logger.info(
                f"Splitting document into nodes: {document.metadata.get('filename')}"
            )
            nodes = splitter.get_nodes_from_documents([document])
            logger.info(f"Created {len(nodes)} nodes from document")

        for node in nodes:
            node.metadata["source"] = request.source
            node.metadata["project_id"] = request.project_id

        storage_context = StorageContext.from_defaults(vector_store=self.vector_store)

        VectorStoreIndex(
            nodes=nodes,
            storage_context=storage_context,
            show_progress=False,
            use_async=True,
            insert_batch_size=128,
        )

        chunks: list[ChunkData] = []

        for node in nodes:
            text = node.get_content()
            embedding = node.embedding
            if not embedding:
                embedding = await Settings.embed_model.aget_text_embedding(text)

            chunks.append(
                ChunkData(
                    content=text,
                    heading=node.metadata.get("header_1")
                    or node.metadata.get("Header_1"),
                    embedding=embedding,
                    token_count=len(text.split()),
                )
            )

        logger.info(
            f"Embedded document: {document.metadata.get('filename')} ({len(chunks)} chunks)"
        )

        return chunks
