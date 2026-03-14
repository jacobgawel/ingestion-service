from io import BytesIO
from pathlib import Path

from docling.document_converter import DocumentConverter
from docling_core.types.io import DocumentStream
from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from mixedbread import AsyncMixedbread
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from app.core.logger import get_logger
from app.core.settings import config
from app.models.workflows import (
    FileProcessingContext,
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

    def _parse_file(self, ctx: FileProcessingContext) -> str:
        """Process file"""
        logger.info(f"Parsing file: {ctx.file_name}")

        markdown_text = ""

        if ctx.is_plain_text:
            if ctx.file_path:
                markdown_text = Path(ctx.file_path).read_text("utf-8")
            elif ctx.file_stream is not None:
                markdown_text = ctx.file_stream.read().decode("utf-8")
        else:
            if ctx.file_path:
                conversion_result = self.converter.convert(Path(ctx.file_path))
                markdown_text = conversion_result.document.export_to_markdown()
            elif ctx.file_stream is not None:
                doc_stream = DocumentStream(
                    name=ctx.file_name, stream=BytesIO(ctx.file_stream.read())
                )
                conversion_result = self.converter.convert(doc_stream)
                markdown_text = conversion_result.document.export_to_markdown()

        logger.info(f"Successfully parsed file: {ctx.file_name}")
        return markdown_text

    def process_file(self, ctx: FileProcessingContext) -> Document:
        result = self._parse_file(ctx)
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
    ) -> None:
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

        logger.info(f"Embedded document: {document.metadata.get('filename')}")
