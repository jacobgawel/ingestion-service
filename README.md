# Ingestion Service

A document ingestion and vector embedding pipeline built with FastAPI. Accepts file uploads, converts documents to Markdown via Docling, generates vector embeddings (OpenAI/Mixedbread), and stores them in Qdrant. Temporal orchestrates the async workflow pipeline.

## Tech Stack

- **Language:** Python 3.14
- **Framework:** FastAPI + Uvicorn
- **Package Manager:** [UV](https://github.com/astral-sh/uv)
- **Workflow Engine:** Temporal
- **Vector DB:** Qdrant
- **Database:** ScyllaDB (via scylla-driver)
- **Object Storage:** MinIO (via boto3)
- **Messaging:** NATS (via nats-py) — pub/sub for real-time job updates
- **Embeddings:** OpenAI / Mixedbread
- **Document Parsing:** Docling

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
| `HOST` | `127.0.0.1` |
| `PORT` | `8065` |

### Start Infrastructure

Starts Qdrant, MinIO, ScyllaDB, and NATS:

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

## Project Structure

```
app/
├── clients/       # Singleton client managers (Temporal, MinIO, Qdrant, OpenAI, Mixedbread, ScyllaDB, NATS)
├── core/          # Settings (Pydantic BaseSettings), enums, logger, dependencies
├── models/        # Pydantic request/response models
├── repositories/  # Data-access layer (domain-specific DB queries)
├── routes/        # FastAPI routers (ingestion REST, jobs WebSocket)
├── service/       # Business logic (document processing, ScyllaDB query execution)
├── temporal/      # Workflow definitions and activities
└── worker.py      # Temporal worker entrypoint
main.py            # FastAPI app entrypoint
```

## Architecture

- **Temporal workflows** — 3-stage pipeline: Parse → Embed → Finalize, with retries and heartbeats
- **Job tracking** — ScyllaDB tables (`ingestion_jobs`, `ingestion_files`) persist job/file status; schema auto-created on startup
- **Event-driven updates** — NATS pub/sub decouples Temporal activities from WebSocket handlers for real-time job progress
- **Singleton pattern** for all client managers (lazy initialization)
- **Repository pattern** for domain-specific DB queries
- **Dependency injection** via FastAPI's `Depends()`

## Code Quality

Pre-commit hooks configured in `.pre-commit-config.yaml`:

```bash
pre-commit run --all-files
```

- **Black** — code formatting
- **isort** — import sorting
- **Ruff** — linting
- **MyPy** — type checking
- **Bandit** — security scanning
