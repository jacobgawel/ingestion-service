"""Repository for ingestion job, file, and document persistence in AlloyDB."""

from datetime import datetime, timezone
from typing import Any, List
from uuid import UUID

from shared.core.enums import INGESTION_STATUS
from shared.core.logger import get_logger
from shared.database import AlloyDBEngine
from shared.models.ingestion import FileSummary
from shared.models.workflows import ChunkData

logger = get_logger("IngestionRepository")


class IngestionRepository:
    """Data-access layer for ingestion jobs, files, documents, and chunks."""

    def __init__(self, alloydb: AlloyDBEngine) -> None:
        self._db = alloydb

    # ---- Jobs ----

    async def create_job(
        self,
        job_id: str,
        source: str,
        project_id: str | None,
        total_files: int,
    ) -> None:
        """Insert a new ingestion job record."""
        now = datetime.now(timezone.utc)
        await self._db.execute_write(
            """
            INSERT INTO ingestion_jobs
                (job_id, source, project_id, status, total_files, files_completed, files_failed, created_at, updated_at, error_message)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            [
                job_id,
                source,
                project_id,
                INGESTION_STATUS.IN_PROGRESS,
                total_files,
                0,
                0,
                now,
                now,
                None,
            ],
        )
        logger.info(f"Created job {job_id} with {total_files} files")

    async def update_job_status(
        self,
        job_id: str,
        source: str,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """Update the status of an ingestion job."""
        now = datetime.now(timezone.utc)
        await self._db.execute_write(
            """
            UPDATE ingestion_jobs
            SET status = $1, updated_at = $2, error_message = $3
            WHERE job_id = $4
            """,
            [status, now, error_message, job_id],
        )
        logger.info(f"Updated job {job_id} status to {status}")

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Get a single ingestion job by ID."""
        return await self._db.execute_one(
            "SELECT * FROM ingestion_jobs WHERE job_id = $1",
            [job_id],
        )

    async def get_jobs(
        self,
        source: str | None = None,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get ingestion jobs, optionally filtered by source and/or project_id."""
        if source and project_id:
            return await self._db.execute(
                "SELECT * FROM ingestion_jobs WHERE source = $1 AND project_id = $2 ORDER BY created_at DESC",
                [source, project_id],
            )
        elif source:
            return await self._db.execute(
                "SELECT * FROM ingestion_jobs WHERE source = $1 ORDER BY created_at DESC",
                [source],
            )
        elif project_id:
            return await self._db.execute(
                "SELECT * FROM ingestion_jobs WHERE project_id = $1 ORDER BY created_at DESC",
                [project_id],
            )
        else:
            return await self._db.execute(
                "SELECT * FROM ingestion_jobs ORDER BY created_at DESC",
            )

    # ---- Files ----

    async def create_file(
        self,
        job_id: str,
        source: str | None,
        project_id: str | None,
        filename: str | None,
        object_name: str,
        content_type: str | None,
    ) -> UUID:
        """Insert a new ingestion file record. Returns the generated file_id."""
        now = datetime.now(timezone.utc)
        row = await self._db.execute_one(
            """
            INSERT INTO ingestion_files
                (job_id, project_id, source, filename, object_name, content_type, status, created_at, updated_at, error_message)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING file_id
            """,
            [
                job_id,
                project_id,
                source,
                filename,
                object_name,
                content_type,
                INGESTION_STATUS.IN_PROGRESS,
                now,
                now,
                None,
            ],
        )
        file_id: UUID = row["file_id"]  # type: ignore[index]
        logger.info(f"Created file record {file_id} for job {job_id}")
        return file_id

    async def update_file_status(
        self,
        job_id: str,
        file_id: UUID,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """Update the status of an ingestion file."""
        now = datetime.now(timezone.utc)
        await self._db.execute_write(
            """
            UPDATE ingestion_files
            SET status = $1, updated_at = $2, error_message = $3
            WHERE file_id = $4
            """,
            [status, now, error_message, file_id],
        )
        logger.info(f"Updated file {file_id} status to {status}")

    async def get_job_files(self, job_id: str) -> list[dict[str, Any]]:
        """Get all files for an ingestion job."""
        return await self._db.execute(
            "SELECT * FROM ingestion_files WHERE job_id = $1",
            [job_id],
        )

    async def get_job_file_summaries(self, job_id: str) -> List[FileSummary]:
        """Get file_id, filename, and status for all files in a job."""
        rows = await self._db.execute(
            "SELECT file_id, filename, status FROM ingestion_files WHERE job_id = $1",
            [job_id],
        )
        return [
            FileSummary(
                file_id=row["file_id"],
                filename=row["filename"],
                status=row["status"],
            )
            for row in rows
        ]

    async def finalize_job(
        self,
        job_id: str,
        source: str,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """Compute file counts and update the job with final status."""
        now = datetime.now(timezone.utc)
        await self._db.execute_write(
            """
            UPDATE ingestion_jobs
            SET status = $1,
                files_completed = (SELECT count(*) FROM ingestion_files WHERE job_id = $2 AND status = $3),
                files_failed    = (SELECT count(*) FROM ingestion_files WHERE job_id = $2 AND status = $4),
                updated_at = $5,
                error_message = $6
            WHERE job_id = $2
            """,
            [
                status,
                job_id,
                INGESTION_STATUS.COMPLETED,
                INGESTION_STATUS.FAILED,
                now,
                error_message,
            ],
        )
        logger.info(f"Finalized job {job_id}: status={status}")

    # ---- Documents & Chunks ----

    async def find_cached_document(self, file_hash: str) -> dict[str, Any] | None:
        """Find an already-processed document with the same content hash."""
        return await self._db.execute_one(
            """
            SELECT d.file_id, d.markdown
            FROM documents d
            WHERE d.hash = $1
              AND d.markdown IS NOT NULL
              AND EXISTS (
                  SELECT 1 FROM document_chunks dc WHERE dc.file_id = d.file_id
              )
            LIMIT 1
            """,
            [file_hash],
        )

    async def get_chunks_by_file_id(self, file_id: UUID) -> list[ChunkData]:
        """Retrieve all chunks (with embeddings) for a given document."""
        rows = await self._db.execute(
            """
            SELECT content, heading, embedding::text AS embedding, token_count
            FROM document_chunks
            WHERE file_id = $1
            ORDER BY chunk_index
            """,
            [file_id],
        )
        chunks: list[ChunkData] = []
        for row in rows:
            embedding_str: str = row["embedding"]
            embedding = [float(v) for v in embedding_str.strip("[]").split(",")]
            chunks.append(
                ChunkData(
                    content=row["content"],
                    heading=row["heading"],
                    embedding=embedding,
                    token_count=row["token_count"],
                )
            )
        return chunks

    async def create_document(
        self,
        file_id: UUID,
        job_id: str,
        source: str | None,
        project_id: str | None,
        filename: str | None,
        content_type: str | None,
        file_size: int | None,
        object_name: str,
        file_hash: str,
    ) -> UUID | None:
        row = await self._db.execute_one(
            """
            INSERT INTO documents
                (file_id, job_id, source, project_id, filename, content_type, file_size, object_name, hash)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING file_id
            """,
            [
                file_id,
                job_id,
                source,
                project_id,
                filename,
                content_type,
                file_size,
                object_name,
                file_hash,
            ],
        )
        if row is None:
            return None
        return row["file_id"]

    async def update_markdown_by_fileid(self, file_id: UUID, markdown: str) -> None:
        await self._db.execute_write(
            """
            UPDATE documents
            SET markdown = $1
            WHERE file_id = $2
            """,
            [markdown, file_id],
        )

    async def insert_chunks(self, file_id: UUID, chunks: list[ChunkData]) -> None:
        """Insert document chunks with embeddings into AlloyDB."""
        await self._db.execute_many(
            """
            INSERT INTO document_chunks
                (file_id, chunk_index, content, heading, embedding, token_count)
            VALUES ($1, $2, $3, $4, $5::vector, $6)
            """,
            [
                [file_id, i, c.content, c.heading, str(c.embedding), c.token_count]
                for i, c in enumerate(chunks)
            ],
        )
