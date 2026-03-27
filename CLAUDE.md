# CLAUDE.md

## Project Overview

Ingestion Service — a document ingestion and vector embedding pipeline built with FastAPI. It accepts file uploads, converts documents to Markdown via Docling, generates vector embeddings (OpenAI), and stores them in AlloyDB (pgvector). Images (standalone uploads or extracted from PDFs) are captioned via OpenAI's vision model (gpt-5-mini) with structured output and stored in MinIO. Temporal orchestrates the async workflow pipeline.

## Tech Stack

- **Language:** Python 3.14
- **Framework:** FastAPI + Uvicorn
- **Package Manager:** UV (astral-sh/uv)
- **Workflow Engine:** Temporal
- **Database:** AlloyDB (via asyncpg) with pgvector for embeddings
- **Object Storage:** MinIO (via boto3)
- **Messaging:** NATS (via nats-py) — pub/sub for real-time job updates
- **Embeddings:** OpenAI (`text-embedding-3-small`, 1536 dimensions)
- **Image Captioning:** OpenAI gpt-5-mini (vision model with structured output via beta `response.parse()` API)
- **Document Parsing:** Docling
- **Indexing/Splitting:** LlamaIndex (document splitting via `MarkdownNodeParser`, vector indexing, OpenAI embeddings)
- **ML Runtime:** PyTorch (CUDA support, used for model inference)
- **Model Hub:** Hugging Face Hub

## Common Commands

```bash
# Install dependencies
uv sync

# Start the FastAPI server
uv run ./main.py

# Start the Temporal worker
uv run -m app.worker

# Start infrastructure (MinIO + NATS + AlloyDB)
docker compose up --build -d

# Run pre-commit checks (lint, format, type check, security)
pre-commit run --all-files
```

## Code Quality Tools (Pre-commit)

All configured in `.pre-commit-config.yaml`:

- **General hooks** — check-yaml, end-of-file-fixer, trailing-whitespace, check-added-large-files, check-ast, check-json, check-merge-conflict, check-toml, debug-statements, detect-private-key, mixed-line-ending, file-contents-sorter
- **Ruff** — linting with `--fix --exit-non-zero-on-fix` (auto-fixes fail the hook so you must re-stage)
- **Ruff Format** — code formatting
- **MyPy** — type checking (`--ignore-missing-imports --check-untyped-defs --explicit-package-bases`)
- **Bandit** — security scanning

## Project Structure

```
app/
├── clients/       # Singleton client managers (Temporal, MinIO, OpenAI, NATS, AlloyDB)
├── core/          # Settings (Pydantic BaseSettings), enums, constants, logger, dependencies, temporal constants
├── database/      # Database engine — AlloyDBEngine (asyncpg pool wrapper)
├── models/        # Pydantic models — api.py (request/response), ingestion.py (FileEntity, FileSummary), workflows.py (workflow DTOs, ImageCaptionResponse)
├── repositories/  # Data-access layer (domain-specific DB queries per feature)
├── routes/        # FastAPI routers (ingestion REST, jobs REST + WebSocket)
├── service/       # Business logic (document processing, image captioning, embedding)
├── temporal/      # Workflow definitions and activities
└── worker.py      # Temporal worker entrypoint
main.py            # FastAPI app entrypoint
```

## Architecture Patterns

- **Singleton pattern** for all client managers. Eager initialization in `__init__`: OpenAI. Async `initialize()` at startup: Temporal, NATS, AlloyDB. Synchronous `initialize()`: MinIO
- **Repository pattern** for domain-specific DB queries (`app/repositories/`). Each feature gets its own repository file (e.g., `ingestion.py`). Repositories depend on `AlloyDBEngine` for query execution.
- **Dependency injection** via FastAPI's `Depends()` for client access in routes
- **Async throughout** — AsyncOpenAI, asyncpg, async context managers
- **Temporal workflows** — 2-stage pipeline: Parse+Embed → Finalize, with retries (5 attempts, exponential backoff) and heartbeats
- **Image pipeline** — Image files (png, jpg, jpeg, gif, webp, bmp, tiff, svg) bypass Docling parsing; instead they are base64-encoded and sent to OpenAI's vision model for structured captioning (`ImageCaptionResponse` with captions, objects, actions, scene, text, logos, people, colors, keywords, relationships). PDF image extraction uses `images_scale=2.0` and `generate_picture_images=True`; extracted images are uploaded to MinIO at `{object_path}/images/{image_name}.png` with markdown references updated in the document
- **Job tracking** — AlloyDB tables (`ingestion_jobs`, `ingestion_files`, `documents`, `document_chunks`) persist job/file status and embeddings; schema auto-created on startup via `AlloyDBManager`
- **Deduplication** — File content hashing allows cache hits to reuse existing embeddings instead of re-processing
- **Event-driven updates** — NATS pub/sub decouples Temporal activities from WebSocket handlers; activities publish to `jobs.{job_id}` subjects, WebSocket route subscribes and relays to clients. The WebSocket route queries the initial job state from the DB, then subscribes to NATS for live updates and relays them to clients (see `docs/websocket-job-updates.md`)
- **Concurrency control** — asyncio Semaphore (max 4 concurrent file operations)

## Environment Variables

Configured via `.env` file (loaded by Pydantic BaseSettings in `app/core/settings.py`):

**Required:**
- `OPENAI_KEY` — OpenAI API key
- `MINIO_HOST`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` — MinIO credentials

**Optional (have defaults):**
- `TEMPORAL_HOST` (default: `localhost:7233`)
- `NATS_URL` (default: `nats://localhost:4222`)
- `ALLOYDB_HOST` (default: `localhost`), `ALLOYDB_PORT` (default: `5432`), `ALLOYDB_DATABASE` (default: `postgres`), `ALLOYDB_USER`, `ALLOYDB_PASSWORD`
- `MAX_CONCURRENT_FILES` (default: `4`) — concurrency limit for file processing in worker
- `EMBEDDING_DIMENTIONS` (default: `1536`), `EMBEDDING_MODEL` (default: `text-embedding-3-small`)
- `APP_LOG_LEVEL` (default: `INFO`)
- `PORT` (default: `8065`), `HOST` (default: `127.0.0.1`)

## Code Conventions

- Full type annotations on all functions and variables
- Snake_case for functions/variables, PascalCase for classes
- Imports organized: stdlib → third-party → local
- Async/await for all I/O operations
- Pydantic models for all data validation and serialization
