"""Repository for ingestion job and file persistence in ScyllaDB."""

import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any, List
from uuid import UUID

from app.core.enums import INGESTION_STATUS
from app.core.logger import get_logger
from app.database import AlloyDBEngine, ScyllaEngine
from app.models.ingestion import FileSummary
from app.models.workflows import ChunkData

logger = get_logger("IngestionRepository")


class IngestionRepository:
    """Data-access layer for ingestion_jobs and ingestion_files tables."""

    def __init__(self, scylla: ScyllaEngine, alloydb: AlloyDBEngine) -> None:
        self._scylla = scylla
        self._alloydb = alloydb

    async def create_job(
        self,
        job_id: str,
        source: str,
        project_id: str | None,
        total_files: int,
    ) -> None:
        """Insert a new ingestion job record."""
        now = datetime.now(timezone.utc)
        await self._scylla.execute_prepared_write(
            """
            INSERT INTO ingestion_jobs
                (job_id, source, project_id, status, total_files, files_completed, files_failed, created_at, updated_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
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
            ),
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
        await self._scylla.execute_prepared_write(
            """
            UPDATE ingestion_jobs
            SET status = ?, updated_at = ?, error_message = ?
            WHERE job_id = ? AND source = ?
            """,
            (status, now, error_message, job_id, source),
        )
        logger.info(f"Updated job {job_id} status to {status}")

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
        file_id = uuid_mod.uuid4()
        now = datetime.now(timezone.utc)
        await self._scylla.execute_prepared_write(
            """
            INSERT INTO ingestion_files
                (job_id, project_id, source, file_id, filename, object_name, content_type, status, created_at, updated_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                project_id,
                source,
                file_id,
                filename,
                object_name,
                content_type,
                INGESTION_STATUS.IN_PROGRESS,
                now,
                now,
                None,
            ),
        )
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
        await self._scylla.execute_prepared_write(
            """
            UPDATE ingestion_files
            SET status = ?, updated_at = ?, error_message = ?
            WHERE job_id = ? AND file_id = ?
            """,
            (status, now, error_message, job_id, file_id),
        )
        logger.info(f"Updated file {file_id} status to {status}")

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Get a single ingestion job by ID."""
        return await self._scylla.execute_prepared_one(
            "SELECT * FROM ingestion_jobs WHERE job_id = ?",
            (job_id,),
        )

    async def get_jobs(
        self,
        source: str | None = None,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get ingestion jobs, optionally filtered by source and/or project_id."""
        if source and project_id:
            return await self._scylla.execute_prepared(
                "SELECT * FROM ingestion_jobs_by_source_project WHERE source = ? AND project_id = ?",
                (source, project_id),
            )
        elif source:
            return await self._scylla.execute_prepared(
                "SELECT * FROM ingestion_jobs WHERE source = ?",
                (source,),
            )
        elif project_id:
            return await self._scylla.execute_prepared(
                "SELECT * FROM ingestion_jobs WHERE project_id = ?",
                (project_id,),
            )
        else:
            return await self._scylla.execute_prepared(
                "SELECT * FROM ingestion_jobs",
            )

    async def get_job_files(self, job_id: str) -> list[dict[str, Any]]:
        """Get all files for an ingestion job."""
        return await self._scylla.execute_prepared(
            "SELECT * FROM ingestion_files WHERE job_id = ?",
            (job_id,),
        )

    async def get_job_file_summaries(self, job_id: str) -> List[FileSummary]:
        """Get file_id, filename, and status for all files in a job."""
        rows = await self._scylla.execute_prepared(
            "SELECT file_id, filename, status FROM ingestion_files WHERE job_id = ?",
            (job_id,),
        )
        return [
            FileSummary(
                file_id=str(row["file_id"]),
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
        """Compute file counts from the files table and update the job with final status."""
        files = await self.get_job_files(job_id)

        files_completed = sum(
            1 for f in files if f["status"] == INGESTION_STATUS.COMPLETED
        )

        files_failed = sum(1 for f in files if f["status"] == INGESTION_STATUS.FAILED)

        now = datetime.now(timezone.utc)
        await self._scylla.execute_prepared_write(
            """
            UPDATE ingestion_jobs
            SET status = ?, files_completed = ?, files_failed = ?, updated_at = ?, error_message = ?
            WHERE job_id = ? AND source = ?
            """,
            (
                status,
                files_completed,
                files_failed,
                now,
                error_message,
                job_id,
                source,
            ),
        )
        logger.info(
            f"Finalized job {job_id}: status={status}, completed={files_completed}, failed={files_failed}"
        )

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
    ) -> UUID | None:
        row = await self._alloydb.execute_one(
            """
            INSERT INTO public.documents
                (file_id, job_id, source, project_id, filename, content_type, file_size, object_name)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING file_id;
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
            ],
        )

        if row is None:
            return None

        file_id = row["file_id"]

        return file_id

    async def update_markdown_by_fileid(self, file_id: UUID, markdown: str) -> None:
        await self._alloydb.execute_write(
            """
            UPDATE public.documents
            SET markdown=$1
            WHERE file_id = $2
            """,
            [markdown, file_id],
        )

    async def insert_chunks(self, file_id: UUID, chunks: list[ChunkData]) -> None:
        """Insert document chunks with embeddings into AlloyDB."""
        await self._alloydb.execute_many(
            """
            INSERT INTO public.document_chunks
                (file_id, chunk_index, content, heading, embedding, token_count)
            VALUES ($1, $2, $3, $4, $5::vector, $6)
            """,
            [
                [file_id, i, c.content, c.heading, str(c.embedding), c.token_count]
                for i, c in enumerate(chunks)
            ],
        )
