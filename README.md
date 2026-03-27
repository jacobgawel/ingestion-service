# Ingestion Service

A document ingestion and vector embedding pipeline built with FastAPI. Accepts file uploads, converts documents to Markdown via Docling, generates vector embeddings (OpenAI), and stores them in AlloyDB (pgvector). Images are captioned via OpenAI's vision model with structured output and stored in MinIO. Temporal orchestrates the async workflow pipeline.

## Tech Stack

- **Language:** Python 3.14
- **Framework:** FastAPI + Uvicorn
- **Package Manager:** [UV](https://github.com/astral-sh/uv)
- **Workflow Engine:** Temporal
- **Database:** AlloyDB (via asyncpg) with pgvector for embeddings
- **Object Storage:** MinIO (via boto3)
- **Messaging:** NATS (via nats-py) — pub/sub for real-time job updates
- **Embeddings:** OpenAI (`text-embedding-3-small`, 1536 dimensions)
- **Document Parsing:** Docling
- **Indexing/Splitting:** LlamaIndex (MarkdownNodeParser, vector indexing, OpenAI embeddings)
- **ML Runtime:** PyTorch (CUDA support)

## Getting Started

### Prerequisites

- [UV](https://github.com/astral-sh/uv) package manager
- [Docker](https://www.docker.com/) & Docker Compose
- [Temporal](https://docs.temporal.io/self-hosted-guide/deployment) server (self-hosted or cloud)

### Install Dependencies

```bash
uv sync
```

### Environment Variables

Create a `.env` file in the project root. See `app/core/settings.py` for all available options.

**Required:**

| Variable | Description |
|---|---|
| `OPENAI_KEY` | OpenAI API key |
| `MINIO_HOST` | MinIO host |
| `MINIO_ACCESS_KEY` | MinIO access key |
| `MINIO_SECRET_KEY` | MinIO secret key |

**Optional (have defaults):**

| Variable | Default |
|---|---|
| `TEMPORAL_HOST` | `localhost:7233` |
| `NATS_URL` | `nats://localhost:4222` |
| `ALLOYDB_HOST` | `localhost` |
| `ALLOYDB_PORT` | `5432` |
| `ALLOYDB_DATABASE` | `postgres` |
| `ALLOYDB_USER` | `None` |
| `ALLOYDB_PASSWORD` | `None` |
| `MAX_CONCURRENT_FILES` | `4` |
| `EMBEDDING_MODEL` | `text-embedding-3-small` |
| `APP_LOG_LEVEL` | `INFO` |
| `HOST` | `127.0.0.1` |
| `PORT` | `8065` |

### Start Infrastructure

Starts MinIO, NATS, and AlloyDB:

```bash
docker compose up --build -d
```

For Temporal, follow the [self-hosted deployment guide](https://docs.temporal.io/self-hosted-guide/deployment).

### Start the Ingestion Service

```bash
uv run ./main.py
```

### Start the Temporal Worker

```bash
uv run -m app.worker
```

## API Endpoints

### REST

| Method | Path | Description |
|---|---|---|
| `POST` | `/ingestion/ingest` | Upload files and start ingestion workflow |
| `GET` | `/ingestion/ingest/{job_id}` | Get job status with file details |
| `GET` | `/jobs` | List jobs (filter by `source`, `project_id`) |
| `GET` | `/jobs/{job_id}` | Get single job with file details |

### WebSocket

| Path | Description |
|---|---|
| `/ws/jobs/{job_id}` | Real-time job progress updates via NATS pub/sub |

## Project Structure

```
app/
├── clients/       # Singleton client managers (Temporal, MinIO, OpenAI, NATS, AlloyDB)
├── core/          # Settings (Pydantic BaseSettings), enums, constants, logger, dependencies, temporal constants
├── database/      # Database engine — AlloyDBEngine (asyncpg pool wrapper)
├── models/        # Pydantic models (request/response, workflow DTOs, internal entities)
├── repositories/  # Data-access layer (domain-specific DB queries)
├── routes/        # FastAPI routers (ingestion REST, jobs REST + WebSocket)
├── service/       # Business logic (document processing, image captioning, embedding)
├── temporal/      # Workflow definitions and activities
└── worker.py      # Temporal worker entrypoint
main.py            # FastAPI app entrypoint
```

## Architecture

- **Temporal workflows** — 2-stage pipeline: Parse+Embed → Finalize, with retries (5 attempts, exponential backoff) and heartbeats
- **Job tracking** — AlloyDB tables (`ingestion_jobs`, `ingestion_files`, `documents`, `document_chunks`) persist job/file status and embeddings; schema auto-created on startup
- **Deduplication** — File content hashing allows cache hits to reuse existing embeddings
- **Event-driven updates** — NATS pub/sub decouples Temporal activities from WebSocket handlers for real-time job progress
- **Singleton pattern** for all client managers — eager init (OpenAI), async init (Temporal, NATS, AlloyDB), sync init (MinIO)
- **Repository pattern** for domain-specific DB queries via `AlloyDBEngine`
- **Dependency injection** via FastAPI's `Depends()`
- **Concurrency control** — asyncio Semaphore limits concurrent file processing

## Code Quality

Pre-commit hooks configured in `.pre-commit-config.yaml`:

```bash
pre-commit run --all-files
```

- **Ruff** — linting + formatting
- **MyPy** — type checking
- **Bandit** — security scanning
