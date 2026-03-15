# CLAUDE.md

## Project Overview

Ingestion Service — a document ingestion and vector embedding pipeline built with FastAPI. It accepts file uploads, converts documents to Markdown via Docling, generates vector embeddings (OpenAI/Mixedbread), and stores them in Qdrant. Temporal orchestrates the async workflow pipeline.

## Tech Stack

- **Language:** Python 3.14
- **Framework:** FastAPI + Uvicorn
- **Package Manager:** UV (astral-sh/uv)
- **Workflow Engine:** Temporal
- **Vector DB:** Qdrant
- **Databases:** ScyllaDB (via scylla-driver), AlloyDB (via asyncpg)
- **Object Storage:** MinIO (via boto3)
- **Messaging:** NATS (via nats-py) — pub/sub for real-time job updates
- **Embeddings:** OpenAI / Mixedbread
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

# Start infrastructure (Qdrant + MinIO + ScyllaDB + NATS + AlloyDB)
docker compose up --build -d

# Run pre-commit checks (lint, format, type check, security)
pre-commit run --all-files
```

## Code Quality Tools (Pre-commit)

All configured in `.pre-commit-config.yaml`:

- **General hooks** — check-yaml, end-of-file-fixer, trailing-whitespace, check-added-large-files, check-ast, check-json, check-merge-conflict, check-toml, debug-statements, detect-private-key, mixed-line-ending, file-contents-sorter
- **Black** — code formatting
- **isort** — import sorting (profile: black)
- **Ruff** — linting with `--fix --exit-non-zero-on-fix` (auto-fixes fail the hook so you must re-stage)
- **Ruff Format** — code formatting (runs alongside Black)
- **MyPy** — type checking (`--ignore-missing-imports --check-untyped-defs --explicit-package-bases`)
- **Bandit** — security scanning

## Project Structure

```
app/
├── clients/       # Singleton client managers (Temporal, MinIO, Qdrant, OpenAI, Mixedbread, ScyllaDB, NATS, AlloyDB)
├── core/          # Settings (Pydantic BaseSettings), enums, logger, dependencies, minio helpers, temporal constants
├── models/        # Pydantic request/response models (api.py, workflows.py)
├── repositories/  # Data-access layer (domain-specific DB queries per feature)
├── routes/        # FastAPI routers (ingestion REST, jobs REST + WebSocket)
├── service/       # Business logic (document processing, generic ScyllaDB query execution)
├── temporal/      # Workflow definitions and activities
└── worker.py      # Temporal worker entrypoint
main.py            # FastAPI app entrypoint
```

## Architecture Patterns

- **Singleton pattern** for all client managers. Eager initialization in `__init__`: OpenAI, Qdrant, Mixedbread. Async `initialize()` at startup: Temporal, ScyllaDB, NATS, AlloyDB. Synchronous `initialize()`: MinIO
- **Repository pattern** for domain-specific DB queries (`app/repositories/`). Each feature gets its own repository file (e.g., `ingestion.py`). Repositories depend on `ScyllaService` for query execution.
- **Dependency injection** via FastAPI's `Depends()` for client access in routes
- **Async throughout** — AsyncQdrantClient, AsyncOpenAI, async context managers
- **Temporal workflows** — 3-stage pipeline: Parse → Embed → Finalize, with retries (5 attempts, exponential backoff) and heartbeats
- **Job tracking** — ScyllaDB tables (`ingestion_jobs`, `ingestion_files`) persist job/file status; schema auto-created on startup. `ingestion_jobs` uses `PRIMARY KEY ((job_id), source)` where `source` is a non-null clustering key (user ID or `"api"` for programmatic usage). A materialized view `ingestion_jobs_by_source_project` (keyed on `(source, project_id)`) serves combined filters without `ALLOW FILTERING`. For `ingestion_jobs`, secondary indexes on `project_id` and `status` support single-column filters (`source` is a clustering key, not a secondary index). For `ingestion_files`, secondary indexes on `source`, `project_id`, and `status` support single-column filters
- **Event-driven updates** — NATS pub/sub decouples Temporal activities from WebSocket handlers; activities publish to `jobs.{job_id}` subjects, WebSocket route subscribes and relays to clients. The WebSocket route queries the initial job state from the DB, then subscribes to NATS for live updates and relays them to clients (see `docs/websocket-job-updates.md`)
- **Concurrency control** — asyncio Semaphore (max 4 concurrent file operations)

## Environment Variables

Configured via `.env` file (loaded by Pydantic BaseSettings in `app/core/settings.py`):

**Required:**
- `OPENAI_KEY` — OpenAI API key
- `MIXEDBREAD_KEY` — Mixedbread API key
- `MINIO_HOST`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` — MinIO credentials

**Optional (have defaults):**
- `TEMPORAL_HOST` (default: `localhost:7233`)
- `QDRANT_HOST` (default: `localhost`), `QDRANT_PORT` (default: `6333`), `QDRANT_GRPC_PORT` (default: `6334`), `QDRANT_API_KEY`, `QDRANT_PREFER_GRPC`, `QDRANT_CLOUD_INFERENCE`
- `SCYLLA_HOSTS` (default: `localhost`), `SCYLLA_PORT` (default: `9042`), `SCYLLA_KEYSPACE` (default: `nexus`), `SCYLLA_USERNAME`, `SCYLLA_PASSWORD`
- `NATS_URL` (default: `nats://localhost:4222`)
- `ALLOYDB_HOST` (default: `localhost`), `ALLOYDB_PORT` (default: `5432`), `ALLOYDB_DATABASE` (default: `postgres`), `ALLOYDB_USER`, `ALLOYDB_PASSWORD`
- `MAX_CONCURRENT_FILES` (default: `4`) — concurrency limit for file processing in worker
- `APP_LOG_LEVEL` (default: `INFO`)
- `PORT` (default: `8065`), `HOST` (default: `127.0.0.1`)

## Code Conventions

- Full type annotations on all functions and variables
- Snake_case for functions/variables, PascalCase for classes
- Imports organized: stdlib → third-party → local
- Async/await for all I/O operations
- Pydantic models for all data validation and serialization
