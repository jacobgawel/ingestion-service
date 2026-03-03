# Feature Brainstorm

Ideas for extending the ingestion service and the broader Nexus platform. Organized from "natural extensions" to "out-of-the-box" concepts.

---

## 1. Retrieval API (RAG Query Service)

**What:** A companion `/query` endpoint (or separate microservice) that takes a natural language question, embeds it, performs similarity search against Qdrant, and returns ranked document chunks — optionally feeding them into an LLM for a synthesized answer.

**Why this is interesting:** The ingestion service builds the knowledge base but nothing queries it yet. This closes the loop and makes the whole pipeline usable end-to-end. Could support:
- Pure vector search (return top-K chunks with scores)
- RAG mode (chunks + LLM-generated answer with citations)
- Hybrid search (vector + keyword via Qdrant's sparse vectors)
- Multi-project scoped queries (filter by `project_id` / `source` metadata)

**Architecture:** Could live as a new router in this service or as a standalone FastAPI service that shares the Qdrant and OpenAI clients. A separate service keeps ingestion throughput isolated from query latency.

---

## 2. Document Diffing & Incremental Re-ingestion

**What:** When a user re-uploads a document that already exists in a project, instead of re-embedding the entire file, diff the new Markdown against what's already stored. Only re-embed changed/added chunks, and tombstone deleted ones from Qdrant.

**Why this is interesting:** Saves significant embedding API cost and Qdrant write load for large documents that change incrementally (think: wikis, legal contracts, codebases). Would need:
- Content hashing per chunk stored in ScyllaDB alongside point IDs
- A new Temporal activity: `DiffAndPatch` that sits between Parse and Embed
- MinIO versioning or a separate `document_versions` table

---

## 3. Web Crawler / URL Ingestion

**What:** Accept a URL (or a list of URLs / a sitemap) instead of file uploads. A new Temporal workflow crawls the pages, converts HTML to Markdown (Docling already handles this), and feeds into the same embed pipeline.

**Why this is interesting:** Unlocks ingesting entire documentation sites, blogs, knowledge bases, and competitor content without manual file downloads. Could support:
- Depth-limited recursive crawling
- Sitemap.xml auto-discovery
- Scheduled re-crawls (cron-triggered Temporal workflows) to keep the knowledge base fresh
- `robots.txt` compliance
- A `sources` table in ScyllaDB tracking crawl origins and schedules

---

## 4. Real-Time Ingestion via Webhooks / Connectors

**What:** Instead of requiring explicit uploads, provide webhook endpoints and integrations that automatically ingest content when it changes at the source:
- **GitHub connector** — webhook fires on push, ingests changed `.md`, `.rst`, `.txt` files from the repo
- **Notion connector** — listens for page update events, re-ingests affected pages
- **Confluence / Google Docs connector** — same pattern
- **S3/MinIO event notifications** — auto-ingest when new files land in a bucket

**Why this is interesting:** Turns the system from "batch upload" to "living knowledge base" that stays current without user intervention. Each connector is a small adapter that translates external events into the existing `POST /ingestion/ingest` workflow.

---

## 5. Audio & Video Transcription Pipeline

**What:** Extend the ingestion pipeline to accept audio/video files. A new Temporal activity runs Whisper (you already have `torch` + `torchaudio` in dependencies) to transcribe, then feeds the transcript into the existing Markdown → Embed pipeline.

**Why this is interesting:** You already have PyTorch and torchaudio as dependencies — Whisper would fit naturally. This turns meeting recordings, lectures, podcasts, and video tutorials into searchable knowledge. Could add:
- Speaker diarization (who said what)
- Timestamp-indexed chunks so retrieval can link back to the exact moment in a recording
- A `media_metadata` table tracking duration, speakers, language

---

## 6. Knowledge Graph Extraction

**What:** After parsing documents to Markdown, run a secondary LLM pass that extracts structured entities and relationships (people, organizations, concepts, events) and stores them as a graph — either in ScyllaDB as adjacency lists or in a dedicated graph DB like Neo4j.

**Why this is interesting:** Vector search finds semantically similar text, but a knowledge graph captures explicit relationships that embeddings miss. Enables:
- "How is X related to Y?" queries that traverse the graph
- Entity-centric search ("show me everything about Project Alpha")
- Graph-augmented RAG — retrieve both vector-similar chunks AND graph-connected context
- Visualization of how documents and concepts interconnect

---

## 7. Document Analytics & Insights Dashboard

**What:** A separate analytics service that processes the ingested corpus and surfaces insights:
- **Corpus statistics** — total docs, chunks, tokens, embedding coverage per project
- **Topic clustering** — run UMAP/HDBSCAN on the embeddings to discover topic clusters and visualize them
- **Duplicate / near-duplicate detection** — find redundant content across projects using cosine similarity thresholds
- **Coverage gaps** — given a topic taxonomy, identify areas with sparse or no documentation
- **Ingestion health** — failure rates, average parse times, file type distribution over time

**Why this is interesting:** Gives visibility into what's actually in the knowledge base, not just that files were ingested. The clustering and dedup features are high-value for teams with sprawling documentation.

---

## 8. Multi-Modal Embedding (Images, Diagrams, Tables)

**What:** Docling already extracts tables and can identify images in documents. Instead of discarding non-text content, embed it separately:
- **Tables** → serialize to structured text, embed with the text model
- **Images/Diagrams** → use a vision model (GPT-4o, Claude) to generate a description, embed that
- **Charts** → extract data points and trends via vision, embed the summary

**Why this is interesting:** Technical documents are full of diagrams, architecture charts, and data tables. Purely text-based embedding misses a huge chunk of the actual knowledge. A multi-modal approach makes the knowledge base dramatically more complete.

---

## 9. Access Control & Multi-Tenancy

**What:** Add proper tenant isolation and permission scoping:
- API key or JWT-based auth with tenant/user identity
- Per-project access control (who can ingest, who can query)
- Qdrant payload-based filtering at query time to enforce access
- Audit logging of all ingestion and query operations to ScyllaDB
- Rate limiting per tenant

**Why this is interesting:** The `source` field is already doing light user-scoping, but there's no enforcement. This is the foundation for making the system production-ready for multiple teams or customers.

---

## 10. Feedback Loop & Embedding Quality Scoring

**What:** After the RAG query service exists (idea #1), add a feedback mechanism:
- Users rate retrieval results (thumbs up/down, relevance score)
- Store feedback in ScyllaDB linked to the query, retrieved chunks, and response
- Periodically analyze which chunks are consistently low-rated
- Auto-suggest re-chunking strategies (different chunk sizes, overlap) or re-embedding with a better model
- A/B test different embedding models (OpenAI vs. Mixedbread vs. Qdrant cloud inference) against real queries

**Why this is interesting:** Embeddings are only as good as their retrieval quality. Without a feedback loop, you're flying blind. This turns the system from a static pipeline into a self-improving one.

---

## 11. Scheduled Workflows & Content Freshness

**What:** Add a scheduling layer on top of Temporal:
- Users define "ingestion schedules" — re-crawl a URL every 24h, re-sync a GitHub repo on push, re-process a MinIO bucket nightly
- A `schedules` table in ScyllaDB tracks configurations
- Temporal's native schedule feature triggers workflows automatically
- Stale content detection — flag chunks whose source documents haven't been re-verified in N days

**Why this is interesting:** Knowledge decays. Documents get updated, links break, information becomes outdated. Scheduled re-ingestion keeps the knowledge base trustworthy without manual intervention.

---

## 12. Plugin / Transform Pipeline

**What:** Make the ingestion pipeline extensible with user-defined transforms that run between Parse and Embed:
- **PII redaction** — strip emails, phone numbers, SSNs before embedding
- **Summarization** — generate a summary of each chunk and embed both the original and the summary
- **Translation** — translate documents to a target language before embedding for multilingual search
- **Custom metadata extraction** — user-provided regex or LLM prompts that extract domain-specific metadata (e.g., "extract the contract value and expiration date")

**Architecture:** Each transform is a Temporal activity. Users configure an ordered list of transforms per project. The workflow dynamically chains them.

---

## 13. Semantic Cache Service

**What:** A standalone caching layer that sits in front of LLM API calls:
- Before sending a query to OpenAI/Claude, embed the query and check Qdrant for semantically similar past queries
- If a cached answer exists within a similarity threshold, return it instantly
- Dramatically reduces LLM API costs for repeated or similar questions
- Cache entries have TTLs and can be invalidated when underlying documents change

**Why this is interesting:** LLM inference is expensive. A semantic cache is non-trivial to build well (exact-match caches miss paraphrases) and would be a valuable standalone service that any LLM-powered application could plug into.

---

## 14. Streaming Ingestion Progress via SSE

**What:** Add a Server-Sent Events endpoint as a lighter alternative to WebSocket for job progress:
- `GET /ingestion/ingest/{job_id}/stream` returns an SSE stream
- Same subscribe-then-snapshot pattern, but over HTTP
- More firewall/proxy friendly than WebSocket
- Clients can use native `EventSource` API

**Why this is interesting:** WebSocket is great for bidirectional comms, but ingestion progress is purely server → client. SSE is simpler, auto-reconnects natively, and works through more corporate proxies.

---
---

# Infrastructure, Scalability & Cool Tech Integrations

Ideas for making the underlying infrastructure more robust, scalable, and interesting — from production-hardening to integrating bleeding-edge tech.

---

## 15. NATS JetStream — Durable Event Streaming

**What:** Replace bare NATS core pub/sub with NATS JetStream for all job/file update events.

**Why this matters:** Right now, NATS core is fire-and-forget. If nobody is subscribed when an event publishes, it's gone. The subscribe-then-snapshot pattern in `jobs_ws.py` is a clever workaround, but JetStream solves the root problem:
- **Durable streams** — events are persisted to disk with configurable retention (time, size, or message count). A consumer that reconnects can replay everything it missed.
- **Consumer groups** — multiple worker instances can load-balance message processing with exactly-once delivery semantics. Scale out WebSocket relay handlers without duplicate deliveries.
- **Replay from offset** — new consumers (e.g., a newly connected WebSocket client) can replay the full event history for a job from the stream instead of needing a separate DB snapshot query. Could simplify or even eliminate the subscribe-then-snapshot pattern.
- **Dead letter queues** — failed message processing gets retried automatically with backoff, or routed to a DLQ for inspection.

**How it fits:** NATS JetStream is a config-level upgrade — same NATS server, same client library (`nats-py` supports JetStream natively). Define a `JOBS` stream with subjects `jobs.>`, set retention to ~24h or by message count. Consumers use durable names to survive restarts. The `_publish` method in activities switches from `nc.publish()` to `js.publish()`.

---

## 16. Horizontal Worker Scaling with Temporal Task Queues

**What:** Split the single `ingestion-queue` into specialized task queues and scale workers independently.

**Why this matters:** Right now, one worker type handles Parse, Embed, and Finalize. These have wildly different resource profiles:
- **Parse** (Docling) — CPU-heavy, memory-hungry, benefits from GPU for OCR
- **Embed** (OpenAI API) — I/O-bound, waits on network, can handle high concurrency
- **Finalize** (ScyllaDB write) — trivial, sub-second

Splitting into dedicated queues lets you:
- Run 1-2 beefy GPU-equipped parse workers but 10+ lightweight embed workers
- Auto-scale each pool independently based on queue depth
- Isolate failures — a parse worker OOM doesn't take down embed workers
- Use Temporal's worker versioning for zero-downtime deployments of individual activity types

**Architecture:**
```
PARSE_QUEUE     →  parse-worker (GPU, 16GB RAM, 2 replicas)
EMBED_QUEUE     →  embed-worker (2GB RAM, 10 replicas)
FINALIZE_QUEUE  →  finalize-worker (512MB RAM, 3 replicas)
```
The workflow definition chains activities across queues using `task_queue` parameters.

---

## 17. GPU-Accelerated Local Embeddings

**What:** Run embedding models locally on GPU instead of calling the OpenAI API, using the commented-out Mixedbread Infinity container in `docker-compose.yml` or a similar setup with `text-embeddings-inference` (TEI) from Hugging Face.

**Why this matters:**
- **Zero API cost** — embeddings become a fixed infrastructure cost instead of per-token billing
- **No rate limits** — blast through thousands of chunks without hitting OpenAI's TPM limits
- **Lower latency** — local GPU inference is 5-10ms vs 100-200ms for an API round trip
- **Data sovereignty** — document content never leaves your network
- Mixedbread's `mxbai-embed-large-v1` is already referenced in the commented-out docker-compose config — it just needs to be wired into `IngestionService.embed_markdown()` as an alternative to the OpenAI path

**Implementation:** Add an `EMBEDDING_PROVIDER` setting (`openai` | `local`) and a `LOCAL_EMBEDDING_URL` setting. In the service layer, branch on the provider and call the local inference server's `/embed` endpoint via `httpx`. The Infinity server handles batching, quantization, and GPU memory management.

---

## 18. MinIO Event-Driven Ingestion (Bucket Notifications)

**What:** Configure MinIO bucket notifications to publish events to NATS when new objects are uploaded. A listener service subscribes to these events and automatically triggers ingestion workflows.

**Why this matters:** Decouples file upload from the API entirely. Users (or other systems) can drop files into MinIO via any S3-compatible tool (AWS CLI, rclone, a data pipeline) and ingestion happens automatically. No need to call the REST API.

**How it fits:**
- MinIO natively supports publishing events to NATS, Kafka, webhooks, etc.
- Configure with `mc event add myminio/nexus-uploads arn:minio:sqs::1:nats --event put`
- A small listener process subscribes to the MinIO event subject, extracts the object key, and starts a Temporal workflow
- The object key can encode metadata: `{project_id}/{source}/{filename}` — parsed by the listener to populate `IngestionWorkflowRequest`

---

## 19. Qdrant Sharding & Collection-per-Project

**What:** Instead of a single `nexus_knowledge_base` collection with metadata filtering, create a separate Qdrant collection per project (or per tenant).

**Why this matters:**
- **Query isolation** — searches in one project never scan another project's vectors. No reliance on payload filtering, which still touches the full index.
- **Independent scaling** — hot projects can have collections on dedicated Qdrant nodes while cold projects share nodes.
- **Per-project tuning** — different projects might benefit from different distance metrics, quantization settings, or HNSW parameters.
- **Easier deletion** — dropping a project means dropping a collection, not scanning and deleting individual points.
- **Qdrant supports distributed mode** with sharding and replication. Collections can span multiple nodes for horizontal write/query throughput.

**Trade-off:** More collections = more index overhead. Best suited when you have dozens of projects, not thousands. For very high project counts, use Qdrant's built-in tenant optimization (indexed payload filtering on `project_id`).

---

## 20. Observability Stack (OpenTelemetry + Grafana)

**What:** Instrument the entire pipeline with OpenTelemetry tracing, metrics, and structured logging. Visualize with Grafana + Tempo + Loki + Prometheus.

**Why this matters:** You have a distributed system (FastAPI → MinIO → Temporal → Docling → OpenAI → Qdrant → ScyllaDB → NATS → WebSocket) but no way to trace a request end-to-end or spot bottlenecks. Adding:
- **Distributed traces** — follow a single ingestion job from HTTP request through every Temporal activity, API call, and DB write. See exactly where time is spent. OpenTelemetry integrates with Temporal's built-in tracing interceptors.
- **Metrics** — ingestion throughput (docs/sec), embedding latency P50/P99, Qdrant upsert latency, queue depth per Temporal task queue, active WebSocket connections, NATS message rates.
- **Structured logs** — correlate logs across services using trace IDs. Ship to Loki for querying.
- **Dashboards** — Grafana dashboards for ingestion health, pipeline bottlenecks, error rates, and cost tracking (embedding tokens consumed).

**Docker additions:**
```yaml
otel-collector:
  image: otel/opentelemetry-collector-contrib:latest

tempo:
  image: grafana/tempo:latest

prometheus:
  image: prom/prometheus:latest

loki:
  image: grafana/loki:latest

grafana:
  image: grafana/grafana:latest
```

---

## 21. Containerize the App + Temporal Worker with Multi-Stage Docker Builds

**What:** Create production Dockerfiles for both the FastAPI app and the Temporal worker. Use multi-stage builds to keep images lean.

**Why this matters:** There's no Dockerfile yet — the commented-out `api` service in `docker-compose.yml` references one but it doesn't exist. Without containerization, deployment is manual and environment-dependent. A proper multi-stage build:
- **Stage 1:** Install dependencies with `uv` in a build layer
- **Stage 2:** Copy only the venv and app code into a slim runtime image
- Separate images for `api` (FastAPI + Uvicorn) and `worker` (Temporal worker) so they scale independently
- Use `docker compose profiles` to group services: `infra` (Qdrant, MinIO, ScyllaDB, NATS), `app` (api, worker), `observability` (Grafana stack)

---

## 22. KEDA / Temporal-Based Autoscaling on Kubernetes

**What:** Deploy workers to Kubernetes and use KEDA (Kubernetes Event-Driven Autoscaling) to scale worker pods based on Temporal task queue backlog.

**Why this matters:** Temporal exposes queue depth metrics. KEDA can scrape these and scale worker deployments:
- Zero workers when idle (scale to zero, save cost)
- Burst to N workers when a large batch ingestion lands
- Different scaling policies per queue (parse workers scale slower due to GPU cost, embed workers scale aggressively)

**Pairs with:** Idea #16 (split task queues) and #21 (Dockerfiles).

---

## 23. ScyllaDB CDC (Change Data Capture) for Event Sourcing

**What:** Enable ScyllaDB's CDC feature on the `ingestion_jobs` and `ingestion_files` tables. Use the CDC log as an event source instead of (or in addition to) NATS publishing from application code.

**Why this matters:**
- **Single source of truth** — events are derived from actual DB mutations, not duplicated application-level publishes. Eliminates the risk of DB and NATS getting out of sync.
- **Replay-ability** — CDC log is persistent. New consumers can replay the full history of state changes.
- **Decoupled consumers** — any service can subscribe to ScyllaDB CDC without modifying the ingestion code. Analytics, auditing, billing — they all just tail the CDC log.
- **Simplifies activities** — the `_publish()` calls in `activities.py` become unnecessary. A CDC consumer handles all downstream notifications.

**How it fits:** ScyllaDB CDC writes changes to a `_scylla_cdc_log` table. A small consumer process (or a Temporal workflow) polls the CDC log and publishes to NATS JetStream, or consumers read the CDC log directly.

---

## 24. Valkey (Redis Fork) for Caching & Rate Limiting

**What:** Add Valkey (the community fork of Redis, post-license change) as a caching and coordination layer.

**Use cases:**
- **Embedding cache** — hash each chunk's text content, check Valkey before calling the embedding API. Identical chunks across documents skip the API call entirely. Saves real money at scale.
- **Rate limiting** — sliding window rate limits per tenant/source using Valkey's atomic operations. Protect the embedding API and Temporal from abuse.
- **Deduplication** — before starting a workflow, check if an identical file (by content hash) was already ingested into the same project. Return the existing job ID.
- **Session state** — if auth/multi-tenancy is added (idea #9), Valkey stores session tokens and API key lookups.

**Why Valkey over Redis:** Valkey is the BSD-licensed Redis fork maintained by the Linux Foundation after Redis's license change. Same protocol, same client libraries (`redis-py` works unchanged), no licensing concerns.

---

## 25. Weaviate or LanceDB as an Alternative Vector Store

**What:** Abstract the vector store behind an interface and support multiple backends — Qdrant (current), Weaviate, or LanceDB.

**Why this is interesting:**
- **LanceDB** — embedded, serverless vector DB built on Lance columnar format. No separate server needed. Great for development, edge deployments, or single-node setups. Supports hybrid search natively and is absurdly fast for disk-based search.
- **Weaviate** — has native multi-tenancy, built-in generative search modules, and automatic vectorization. If you wanted the vector DB to handle embedding instead of the application layer, Weaviate's `text2vec` modules do this out of the box.
- **Abstraction layer** — define a `VectorStore` protocol in `app/clients/` with `upsert()`, `search()`, `delete()` methods. Each backend implements the protocol. Select via config. Makes it trivial to benchmark different backends with the same data.

---

## 26. Workflow Visualization with Temporal Web UI

**What:** Add the Temporal Web UI and Temporal server to the docker-compose stack so the full workflow engine is self-hosted and inspectable.

**Why this matters:** Right now `docker-compose.yml` only has the infrastructure services. Temporal is assumed to be running externally. Self-hosting it means:
- **Full visibility** — inspect running/completed/failed workflows, see activity timelines, retry histories, and input/output payloads in the Temporal Web UI
- **Local development** — no external Temporal Cloud dependency for dev/test
- **Workflow replay** — Temporal's deterministic replay lets you debug failed workflows by replaying them with new code

**Docker additions:**
```yaml
temporal:
  image: temporalio/auto-setup:latest
  depends_on: [postgresql]  # or use SQLite for dev

temporal-ui:
  image: temporalio/ui:latest
  ports:
    - "8080:8080"
```

---

## 27. Apache Kafka / Redpanda as an Event Backbone

**What:** Replace or supplement NATS with Redpanda (Kafka-compatible, single-binary, no JVM) as the central event backbone.

**Why this could be interesting:**
- **Persistent event log** — every ingestion event, file status change, and job update is persisted with configurable retention. Unlike NATS core, events are never lost.
- **Consumer groups** — multiple services consume the same event stream independently at their own pace (WebSocket relay, analytics, audit log, billing).
- **Schema registry** — Redpanda includes a built-in schema registry. Define Avro/Protobuf schemas for events, get backward/forward compatibility guarantees as the event format evolves.
- **Backpressure** — consumers that fall behind don't lose events; they just have higher lag. Great for burst ingestion scenarios.
- **Redpanda over Kafka** — single Go binary, no ZooKeeper/JVM, 10x lower latency, drop-in Kafka API compatible. Runs in 512MB RAM.

**Trade-off:** NATS is simpler and already working well. Redpanda makes more sense if you're building a multi-service platform where many consumers need durable, replayable event streams. JetStream (idea #15) is the middle ground.

---

## 28. Fly.io / Cloudflare Workers for Edge Embedding

**What:** Deploy lightweight embedding proxy workers at the edge (Fly.io regions or Cloudflare Workers) that handle the embedding API calls closer to users, then push results to the central Qdrant instance.

**Why this is interesting:**
- Reduces embedding latency for geographically distributed users
- Can run quantized ONNX embedding models directly in Cloudflare Workers (via WebAssembly) for zero-API-cost embeddings at the edge
- Central Qdrant instance still serves as the single source of truth for search
- Edge workers could also handle document parsing for small files, only routing large/complex documents to the central GPU-equipped parse workers

---

## 29. DuckDB for Analytical Queries Over Ingestion Data

**What:** Periodically export ScyllaDB ingestion metadata to DuckDB (or query it directly via DuckDB's federation) for analytical workloads.

**Why this is interesting:** ScyllaDB is optimized for low-latency key-value lookups, not analytical queries. But questions like "what's the average ingestion time per file type over the last 30 days?" or "which projects have the highest failure rates?" are analytical. DuckDB:
- Runs in-process (no server), embeds directly into a Python analytics service
- Handles columnar scans over millions of rows in milliseconds
- Can read Parquet files exported from ScyllaDB, or use its postgres/ADBC scanner
- Powers the analytics dashboard from idea #7 without putting analytical load on ScyllaDB

---

## 30. Sigstore / Cosign for Document Provenance & Integrity

**What:** Sign each ingested document (or its content hash) using Sigstore's keyless signing. Store the signature and transparency log entry alongside the document metadata in ScyllaDB.

**Why this is interesting:**
- **Provenance** — cryptographic proof of when a document was ingested and by whom
- **Tamper detection** — verify that vector embeddings correspond to the original document, not a modified version
- **Audit compliance** — for regulated industries, prove that the knowledge base contains exactly what was ingested, unmodified
- **Keyless** — Sigstore's Fulcio CA issues short-lived certificates tied to OIDC identity (GitHub, Google). No key management burden.

---

## 31. WebAssembly (Wasm) Plugin Runtime for Custom Transforms

**What:** Instead of running custom transforms (idea #12) as Temporal activities in Python, run them as WebAssembly modules in a sandboxed runtime (Wasmtime, WasmEdge).

**Why this is interesting:**
- **Language-agnostic** — users write transforms in Rust, Go, C, AssemblyScript, whatever compiles to Wasm
- **Sandboxed execution** — Wasm modules can't access the filesystem, network, or other system resources unless explicitly granted. Safe to run user-provided code.
- **Near-native speed** — Wasm executes at close to native speed, unlike Python-based plugins
- **Hot-reloadable** — swap Wasm modules without restarting workers
- Could power a "marketplace" of community transforms (PII redactor, language detector, sentiment analyzer)

---

## 32. Embedded Vector Search with Turbopuffer

**What:** Use Turbopuffer as a serverless, pay-per-query vector store alternative to self-hosted Qdrant.

**Why this is interesting:**
- **Serverless** — no infrastructure to manage. Vectors are stored in object storage (S3/R2), queries execute on-demand.
- **Cost model** — pay per query, not per hour of running infrastructure. Great for bursty workloads where the knowledge base sits idle between queries.
- **Object storage-backed** — vectors are stored in a durable, cheap layer. Scales to billions of vectors without provisioning.
- Could be offered as a deployment option alongside self-hosted Qdrant — user picks based on their usage pattern.
