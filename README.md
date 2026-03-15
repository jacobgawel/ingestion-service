# Ingestion Service

A document ingestion and vector embedding pipeline built with FastAPI. Accepts file uploads, converts documents to Markdown via Docling, generates vector embeddings (OpenAI/Mixedbread), and stores them in Qdrant. Temporal orchestrates the async workflow pipeline.

## Tech Stack

- **Language:** Python 3.14
- **Framework:** FastAPI + Uvicorn
- **Package Manager:** [UV](https://github.com/astral-sh/uv)
- **Workflow Engine:** Temporal
- **Vector DB:** Qdrant
- **Databases:** ScyllaDB (via scylla-driver), AlloyDB (via asyncpg)
- **Object Storage:** MinIO (via boto3)
- **Messaging:** NATS (via nats-py) — pub/sub for real-time job updates
- **Embeddings:** OpenAI / Mixedbread
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
| `MIXEDBREAD_KEY` | Mixedbread API key |
| `MINIO_HOST` | MinIO host |
| `MINIO_ACCESS_KEY` | MinIO access key |
| `MINIO_SECRET_KEY` | MinIO secret key |

**Optional (have defaults):**

| Variable | Default |
|---|---|
| `TEMPORAL_HOST` | `localhost:7233` |
| `QDRANT_HOST` | `localhost` |
| `QDRANT_PORT` | `6333` |
| `QDRANT_GRPC_PORT` | `6334` |
| `SCYLLA_HOSTS` | `localhost` |
| `SCYLLA_PORT` | `9042` |
| `SCYLLA_KEYSPACE` | `nexus` |
| `NATS_URL` | `nats://localhost:4222` |
| `ALLOYDB_HOST` | `localhost` |
| `ALLOYDB_PORT` | `5432` |
| `ALLOYDB_DATABASE` | `postgres` |
| `MAX_CONCURRENT_FILES` | `4` |
| `APP_LOG_LEVEL` | `INFO` |
| `HOST` | `127.0.0.1` |
| `PORT` | `8065` |

### Start Infrastructure

Starts Qdrant, MinIO, ScyllaDB, NATS, and AlloyDB:

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
├── clients/       # Singleton client managers (Temporal, MinIO, Qdrant, OpenAI, Mixedbread, ScyllaDB, NATS, AlloyDB)
├── core/          # Settings (Pydantic BaseSettings), enums, constants, logger, dependencies, temporal constants
├── database/      # Database engines — ScyllaEngine (async CQL wrapper), AlloyDBEngine (asyncpg pool wrapper)
├── models/        # Pydantic models (request/response, workflow DTOs, internal entities)
├── repositories/  # Data-access layer (domain-specific DB queries)
├── routes/        # FastAPI routers (ingestion REST, jobs REST + WebSocket)
├── service/       # Business logic (document processing, image captioning, embedding)
├── temporal/      # Workflow definitions and activities
└── worker.py      # Temporal worker entrypoint
main.py            # FastAPI app entrypoint
```

## Architecture

- **Temporal workflows** — 3-stage pipeline: Parse + Embed → Finalize, with retries (5 attempts, exponential backoff) and heartbeats
- **Job tracking** — ScyllaDB tables (`ingestion_jobs`, `ingestion_files`) persist job/file status; schema auto-created on startup
- **Document storage** — AlloyDB stores documents and chunked embeddings
- **Event-driven updates** — NATS pub/sub decouples Temporal activities from WebSocket handlers for real-time job progress
- **Singleton pattern** for all client managers — eager init (OpenAI, Qdrant, Mixedbread), async init (Temporal, ScyllaDB, NATS, AlloyDB), sync init (MinIO)
- **Repository pattern** for domain-specific DB queries via `ScyllaEngine` and `AlloyDBEngine`
- **Dependency injection** via FastAPI's `Depends()`
- **Concurrency control** — asyncio Semaphore limits concurrent file processing

## Code Quality

Pre-commit hooks configured in `.pre-commit-config.yaml`:

```bash
pre-commit run --all-files
```

- **Black** — code formatting
- **isort** — import sorting
- **Ruff** — linting + formatting
- **MyPy** — type checking
- **Bandit** — security scanning
