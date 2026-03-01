### Tech Stack

- Temporal
- Qdrant
- ScyllaDB
- FastAPI
- Docker

As of now all the components are required to use in a containerised environemnt.

Use the below command to run all the required images

```bash
docker compose up --build -d
```

To run the temporal image please read the guide on https://docs.temporal.io/self-hosted-guide/deployment

### Start Ingestion Service

```bash
uv run .\main.py
```

### Start Temporal Worker Service

```bash
uv run -m app.worker
```
