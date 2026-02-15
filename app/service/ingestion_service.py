from io import BytesIO
from typing import List

from docling.document_converter import DocumentConverter
from docling_core.types.io import DocumentStream
from fastapi import UploadFile
from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from mixedbread import AsyncMixedbread
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from app.core.logger import get_logger
from app.core.settings import config
from app.models.api import IngestionRequest

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

    def _parse_file(self, file: BytesIO, file_name: str | None) -> str:
        """Process file"""
        logger.info(f"Parsing file: {file_name or 'default'}")
        doc_stream = DocumentStream(name=file_name or "default", stream=file)

        conversion_result = self.converter.convert(doc_stream)
        markdown_text = conversion_result.document.export_to_markdown()

        logger.info(f"Successfully parsed file: {file_name or 'default'}")
        return markdown_text

    async def process_pipeline(
        self, request: IngestionRequest, files: List[UploadFile]
    ):
        logger.info(f"Processing {len(files)} file(s)")

        processed_files: list[Document] = []
        splitter = MarkdownNodeParser()

        for file in files:
            file_content = await file.read()
            file_stream = BytesIO(file_content)

            result = self._parse_file(file=file_stream, file_name=file.filename)
            doc = Document(
                text=result,
                metadata={
                    "filename": file.filename,
                    "user_id": request.user_id,
                    "project_id": request.project_id,
                },
            )
            processed_files.append(doc)

        logger.info("Splitting documents into nodes")
        nodes = splitter.get_nodes_from_documents(processed_files)
        logger.info(f"Created {len(nodes)} nodes from documents")

        for node in nodes:
            node.metadata["user_id"] = request.user_id
            node.metadata["project_id"] = request.project_id

        storage_context = StorageContext.from_defaults(vector_store=self.vector_store)

        VectorStoreIndex(
            nodes=nodes,
            storage_context=storage_context,
            show_progress=False,
            use_async=True,
        )

        logger.info("Ingestion pipeline completed successfully")
        return True
