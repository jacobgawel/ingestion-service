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

---
---

# AI-Native Integrations & Agent Ecosystem

Ideas for making the knowledge base accessible to AI agents, LLM toolchains, and emerging protocols.

---

## 33. MCP Server (Model Context Protocol)

**What:** Expose the knowledge base as an MCP server so any MCP-compatible AI client (Claude Desktop, Cursor, Claude Code, Windsurf, etc.) can search and retrieve documents as tool calls.

**Why this is interesting:** MCP is becoming the standard protocol for giving AI models access to external data. Instead of building a custom UI, you build once and every AI client can use it. Tools to expose:
- `search_knowledge_base(query, project_id?, top_k?)` — semantic search
- `get_document(file_id)` — retrieve full document text
- `list_projects()` — enumerate available projects
- `ingest_url(url, project_id)` — trigger ingestion from an AI conversation
- `get_job_status(job_id)` — check ingestion progress

The MCP server is a thin wrapper around the existing API. Could be a separate Python process using the `mcp` SDK, or served over SSE/stdio.

---

## 34. OpenAI-Compatible `/v1/embeddings` Proxy

**What:** Expose an OpenAI-compatible embeddings API endpoint that routes to your local GPU embedding server (Infinity/TEI from idea #17) or to the actual OpenAI API, transparently.

**Why this is interesting:**
- Any tool that supports OpenAI embeddings (LangChain, LlamaIndex, Haystack, custom apps) can point at your service and get embeddings without code changes
- You control the routing — dev environments hit the local GPU, production hits OpenAI, and the caller doesn't know or care
- Add transparent caching (idea #24) behind this proxy and every consumer benefits
- Metrics and cost tracking in one place

---

## 35. LangChain / LlamaIndex Retriever Plugin

**What:** Publish a Python package (`nexus-retriever`) that implements the LangChain `BaseRetriever` and LlamaIndex `BaseRetriever` interfaces, backed by your Qdrant knowledge base.

**Why this is interesting:** Anyone building a RAG app with LangChain or LlamaIndex can `pip install nexus-retriever` and immediately use your knowledge base as a retrieval source. Turns your ingestion pipeline into a reusable building block for the broader ecosystem.

```python
from nexus_retriever import NexusRetriever

retriever = NexusRetriever(base_url="http://localhost:8065", project_id="my-project")
docs = retriever.invoke("how does authentication work?")
```

---

## 36. AI Agent Tool Use — Function Calling Interface

**What:** Build a standalone "research agent" service that uses LLM function calling (tool use) to orchestrate multi-step research over the knowledge base:
- Break a complex question into sub-queries
- Search the knowledge base for each sub-query
- Cross-reference results across documents
- Synthesize a final answer with citations and confidence scores

**Why this is interesting:** Simple RAG (embed question → top-K → LLM) fails on complex questions that require reasoning across multiple documents. An agent loop with tool use handles "Compare the security policies across all three vendor proposals" by issuing multiple targeted searches and synthesizing the results.

---

## 37. Slack / Discord Bot

**What:** A bot that sits in a Slack or Discord channel and answers questions from the knowledge base. Users `@mention` the bot with a question, it queries the RAG service, and posts the answer with source citations.

**Why this is interesting:** Meets people where they already work. No need to context-switch to a separate app. Could also support:
- `/ingest <url>` slash command to trigger URL ingestion from chat
- Threaded follow-up questions with conversation memory
- Channel-specific project scoping (bot in `#engineering` only searches the engineering project)

---
---

# Developer Experience & API Design

---

## 38. CLI Tool (`nexus-cli`)

**What:** A command-line tool for interacting with the ingestion service:
```bash
nexus ingest ./docs/ --project my-project --source jake
nexus ingest https://docs.example.com --depth 2
nexus status ingest-abc-123
nexus search "how does auth work?" --project my-project --top-k 5
nexus jobs --source jake --status failed
nexus watch ingest-abc-123  # live progress, like docker logs -f
```

**Why this is interesting:** Power users and CI/CD pipelines want a CLI, not a REST API. The `watch` command streams job progress via SSE/WebSocket. Could be built with `typer` + `httpx` in a separate repo, published to PyPI.

---

## 39. Python SDK (`nexus-sdk`)

**What:** A typed Python client library with async support:
```python
from nexus_sdk import NexusClient

async with NexusClient("http://localhost:8065") as client:
    job = await client.ingest(files=["report.pdf"], project_id="my-project")
    async for event in client.watch(job.job_id):
        print(f"{event.filename}: {event.status}")
    results = await client.search("quarterly revenue", project_id="my-project")
```

**Why this is interesting:** Removes the friction of hand-writing HTTP requests. Typed models for all request/response objects, async iteration over WebSocket/SSE events, automatic retry with backoff. Makes it trivial for other services in the Nexus platform to integrate with ingestion.

---

## 40. gRPC API Alongside REST

**What:** Add a gRPC interface for the ingestion and query endpoints, running on a separate port.

**Why this is interesting:**
- **Streaming** — gRPC server-streaming is a natural fit for job progress updates (like SSE, but with strong typing via Protobuf)
- **Performance** — binary Protobuf serialization is 5-10x smaller than JSON for embedding vectors and document chunks
- **Code generation** — clients in any language get auto-generated typed stubs from the `.proto` files
- **Internal service mesh** — gRPC is the default for service-to-service communication in Kubernetes. If Nexus grows to multiple services, gRPC between them is natural.
- Qdrant already uses gRPC (`QDRANT_PREFER_GRPC` is in your settings). Temporal uses gRPC internally. Adding gRPC to the API layer completes the picture.

---

## 41. Batch / Async API with Callback Webhooks

**What:** Add a batch ingestion endpoint that accepts a list of files or URLs, returns a batch ID immediately, and calls a user-provided webhook URL when the batch completes (or on each file completion).

```json
POST /ingestion/batch
{
  "urls": ["https://example.com/doc1.pdf", "https://example.com/doc2.pdf"],
  "project_id": "my-project",
  "callback_url": "https://myapp.com/hooks/ingestion-complete",
  "callback_events": ["job_completed", "job_failed", "file_completed"]
}
```

**Why this is interesting:** Not every consumer wants to hold a WebSocket open. Webhooks are the standard pattern for async integrations. The callback payload matches the existing NATS event format, so it's just a new consumer that POSTs to the registered URL.

---

## 42. OpenAPI Spec + Generated Docs Portal

**What:** FastAPI already auto-generates OpenAPI specs. Take it further:
- Host a polished docs portal (Scalar, Redoc, or Stoplight Elements) at `/docs`
- Add rich examples, request/response samples, and error code documentation
- Generate SDKs from the OpenAPI spec using `openapi-generator` for TypeScript, Go, Rust, etc.
- Publish the spec to a registry so consumers can auto-generate clients

**Why this is interesting:** The existing FastAPI `/docs` is functional but minimal. A proper API portal with examples, guides, and multi-language SDK generation makes the service approachable for teams outside your immediate circle.

---
---

# Deployment, IaC & DevOps

---

## 43. Terraform / Pulumi for Infrastructure as Code

**What:** Define the entire infrastructure stack (Qdrant, MinIO, ScyllaDB, NATS, Temporal) as Terraform or Pulumi modules. Support multiple deployment targets: local Docker, AWS, GCP.

**Why this is interesting:**
- One command to spin up the full stack in any environment
- Separate modules for each service — compose only what you need
- Cloud-specific variants (Qdrant Cloud, Amazon S3 instead of MinIO, ScyllaDB Cloud, etc.)
- State management and drift detection

---

## 44. GitOps with ArgoCD or FluxCD

**What:** Deploy the Kubernetes manifests via GitOps. Push to `main`, ArgoCD syncs the cluster.

**Why this is interesting:** Combined with Dockerfiles (#21), KEDA (#22), and Terraform (#43), this completes the deployment story. Changes to worker configuration, scaling policies, or infrastructure are all version-controlled and auditable.

---

## 45. Nix Flake for Reproducible Dev Environment

**What:** Define a `flake.nix` that provisions the exact Python version, `uv`, system dependencies (poppler, tesseract for Docling), and all tooling in a single `nix develop` command.

**Why this is interesting:** New contributors clone the repo, run `nix develop`, and have everything. No "works on my machine." Especially valuable because this project has heavy system dependencies (CUDA, torch, Docling's native parsers).

---
---

# Data Processing & Intelligence

---

## 46. Chunking Strategy Experimentation Framework

**What:** Currently chunks are created by `MarkdownNodeParser` with default settings. Build a framework to experiment with different strategies:
- Fixed-size token windows with overlap
- Semantic chunking (split on topic boundaries using embeddings)
- Hierarchical chunking (paragraph → section → document, with parent-child relationships in Qdrant)
- Late chunking (embed the full document, then split — preserves cross-chunk context)

Store chunks from different strategies in separate Qdrant collections. Run the same queries against each and compare retrieval quality.

**Why this is interesting:** Chunking is the single biggest lever on RAG quality and there's no one-size-fits-all answer. A framework for A/B testing strategies against real queries is extremely valuable.

---

## 47. Code-Aware Ingestion

**What:** Detect source code files and use AST parsing instead of Markdown conversion:
- Parse Python, TypeScript, Go, Rust, etc. into AST
- Extract functions, classes, docstrings, type signatures as separate chunks
- Preserve call graphs and import relationships as metadata
- Embed function-level chunks with rich context (file path, class, signature)

**Why this is interesting:** Docling treats code as plain text, which loses structural information. AST-aware chunking means a search for "authentication middleware" returns the actual function definition, not a random line that mentions auth. Could use `tree-sitter` for multi-language AST parsing.

---

## 48. Synthetic Question Generation

**What:** After ingesting documents, use an LLM to generate synthetic questions that each chunk should be able to answer. Store the questions alongside the chunks in Qdrant as additional embedding targets.

**Why this is interesting:**
- Bridges the vocabulary gap — documents use formal language, users ask casual questions. The synthetic questions are phrased how a user would ask.
- Dramatically improves retrieval recall for chunks that contain answers but don't use the same words as the query
- The synthetic questions can also serve as a test suite for measuring retrieval quality — "does the system return the right chunk for this question?"

---

## 49. Cross-Lingual / Multilingual Embedding

**What:** Use multilingual embedding models (Cohere `embed-multilingual-v3.0`, or multilingual E5) so documents in any language are searchable from queries in any other language.

**Why this is interesting:** A company with docs in English, German, and Japanese could search across all of them with a single English query. The multilingual model maps semantically equivalent text to nearby vectors regardless of language. Could be an opt-in per-project setting.

---

## 50. Document Lineage & Dependency Graph

**What:** Track which documents reference or depend on other documents. When a source document is re-ingested or deleted, identify all downstream documents that may be affected.

**Why this is interesting:** In regulated environments (healthcare, finance, legal), you need to know: "if this policy document changes, which other documents cite it?" Temporal workflows can trigger cascading re-ingestion when a dependency changes. Store lineage as edges in ScyllaDB or the knowledge graph from idea #6.

---
---

# Bleeding-Edge Tech Stack Alternatives

Replacements or upgrades for current stack components. Each section explains what it replaces, why you'd switch, and what you'd learn.

---

## 51. Restate instead of Temporal (Durable Execution)

**Replaces:** Temporal

**What:** Restate is a newer durable execution engine (open source, written in Rust) that embeds directly into your application as a library instead of requiring a separate server cluster. You write regular async Python functions with Restate's SDK and it handles retries, state, and exactly-once execution.

**Why it's interesting to learn:**
- **No separate infrastructure** — Restate runs as a single binary sidecar or embedded server, vs Temporal requiring a full server + database (Postgres/Cassandra) + UI. Massively simpler ops.
- **RPC-native** — services call each other like normal function calls; Restate intercepts and makes them durable. No task queues, no workflow vs activity distinction.
- **Virtual objects** — built-in keyed state that survives restarts. The ingestion job state could live in Restate itself instead of ScyllaDB.
- **Written in Rust** — single binary, tiny footprint, sub-millisecond overhead.

**Trade-off:** Temporal has a much larger ecosystem, better docs, and battle-tested scale. Restate is newer but architecturally cleaner for many use cases.

```python
# What your ingestion workflow could look like with Restate
from restate import Service, Context

ingestion = Service("ingestion")

@ingestion.handler()
async def ingest(ctx: Context, request: IngestionRequest):
    files = await ctx.run("parse", parse_files, request)
    await ctx.run("embed", embed_markdown, files)
    await ctx.run("finalize", finalize_job, request.job_id)
```

---

## 52. Meilisearch or Typesense instead of Qdrant (Hybrid Search)

**Replaces:** Qdrant (partially — for hybrid keyword + vector search)

**What:** Meilisearch and Typesense are search engines primarily built for typo-tolerant full-text search, but both have added vector search capabilities. They combine keyword and semantic search in a single engine.

**Why it's interesting:**
- **Hybrid search in one engine** — no need to run Qdrant for vectors AND Elasticsearch for keywords. One service does both.
- **Meilisearch** — Rust-based, sub-50ms search, built-in faceting, typo tolerance, and now hybrid vector search with auto-embedding. Dead simple to operate (single binary, zero config).
- **Typesense** — C++-based, supports vector search with HNSW, embedded ML model inference, built-in geosearch. More feature-rich for structured data.
- **When to use:** If your retrieval strategy needs exact keyword matching (product names, error codes, IDs) alongside semantic search, a hybrid engine gives you both without query-time orchestration.

**Trade-off:** Neither matches Qdrant's vector-specific optimizations (quantization, multi-vector, sparse vectors, GPU indexing). Best when keyword search is equally important as semantic search.

---

## 53. SurrealDB instead of ScyllaDB (Multi-Model Database)

**Replaces:** ScyllaDB (and potentially the knowledge graph DB from idea #6)

**What:** SurrealDB is a multi-model database that supports document, graph, key-value, and relational query patterns in a single engine with a SQL-like query language (SurrealQL).

**Why it's interesting:**
- **Graph + document in one** — the ingestion jobs table AND the knowledge graph (idea #6) live in the same DB. Query document metadata and traverse entity relationships without a second database.
- **Record links** — first-class relationships between records. `ingestion_files` can link directly to `ingestion_jobs` without JOIN-like queries.
- **Real-time LIVE queries** — subscribe to changes on any table. Could replace NATS for job status updates — `LIVE SELECT * FROM ingestion_jobs WHERE job_id = $id` pushes changes to connected clients.
- **Built-in auth** — row-level security with `PERMISSIONS` clauses. Multi-tenancy enforcement at the DB layer.

**Trade-off:** ScyllaDB is purpose-built for high-throughput, low-latency writes at massive scale. SurrealDB is more versatile but hasn't been battle-tested at the same scale. Good for projects that value flexibility over raw throughput.

---

## 54. Tigris instead of MinIO (S3-Compatible Object Storage)

**Replaces:** MinIO

**What:** Tigris is a globally distributed, S3-compatible object storage built on FoundationDB. It's designed for modern applications that need multi-region data with zero replication configuration.

**Why it's interesting:**
- **Global distribution** — objects are automatically cached in the region closest to the reader. Useful if ingestion happens in one region but queries come from everywhere.
- **Metadata search** — query object metadata directly without a separate index. Find all PDFs in a project without listing the entire bucket.
- **FoundationDB core** — learning FoundationDB's architecture is valuable. It's the most interesting distributed database design in existence (used by Apple at massive scale).

**Alternative to consider: SeaweedFS** — a simpler, high-performance distributed file system with S3 API, FUSE mount, and built-in Filer for metadata. Better for self-hosted deployments where you want raw throughput.

---

## 55. ClickHouse instead of ScyllaDB for Analytics

**Replaces:** ScyllaDB (for analytical/read-heavy workloads, not for transactional writes)

**What:** Use ScyllaDB for the transactional job/file tracking but add ClickHouse as a dedicated analytical store for ingestion metrics, usage analytics, and corpus-level queries.

**Why it's interesting:**
- **Column-oriented** — scans over millions of rows in milliseconds. "Average ingestion time by file type over 90 days" is instant.
- **Materialized views** — pre-compute aggregations (hourly ingestion counts, failure rates per project) that refresh automatically.
- **SQL interface** — familiar query language, unlike CQL's restrictions.
- **chDB** — embedded ClickHouse that runs in-process as a Python library, like DuckDB but with ClickHouse's engine. No server needed for dev.

---

## 56. Rust Sidecar for CPU-Heavy Parsing (PyO3)

**Replaces:** Python-based Docling parsing (partially)

**What:** Write performance-critical parsing logic (PDF text extraction, chunking, content hashing) as a Rust library exposed to Python via PyO3/maturin.

**Why it's interesting:**
- **10-100x speedup** — Rust processes raw bytes and text much faster than Python. Chunking large documents, hashing, and Markdown manipulation are all CPU-bound and benefit enormously.
- **Memory safety** — no GIL contention, no memory leaks from long-running worker processes.
- **PyO3 + maturin** — build a Rust crate that compiles to a Python-importable `.so` file. Call Rust functions from Python as if they're native. `pip install` just works.
- **Incremental adoption** — don't rewrite everything. Start with the hottest path (chunking + hashing) and measure.

```toml
# Cargo.toml for the Rust sidecar
[lib]
name = "nexus_native"
crate-type = ["cdylib"]

[dependencies]
pyo3 = { version = "0.22", features = ["extension-module"] }
```

---

## 57. Deno / Bun Workers for Lightweight Transform Functions

**Replaces:** Python-based transform plugins (idea #12)

**What:** Run user-defined transforms as Deno or Bun scripts in isolated V8 sandboxes instead of Python or Wasm.

**Why it's interesting:**
- **TypeScript/JavaScript** — larger pool of developers than Rust/Wasm. Most teams can write a transform function in TypeScript immediately.
- **Deno's permission model** — granular capabilities (`--allow-net`, `--allow-read`). Run user code without worrying about filesystem or network access.
- **Sub-millisecond startup** — V8 isolates spin up nearly instantly, unlike Python subprocess or container spin-up.
- **Bun** — if raw speed matters, Bun's runtime is significantly faster than Deno/Node for text processing workloads.

---

## 58. CockroachDB or TiDB instead of ScyllaDB (Distributed SQL)

**Replaces:** ScyllaDB

**What:** Use a distributed SQL database instead of a wide-column NoSQL store.

**Why it's interesting:**
- **SQL** — no CQL restrictions. JOINs, subqueries, window functions, CTEs. The query patterns in `ingestion.py` (filtering by source AND project_id, counting file statuses) would be simpler and more flexible.
- **CockroachDB** — Postgres-compatible wire protocol. Every Postgres library works. Distributed ACID transactions. No materialized views needed for secondary access patterns.
- **TiDB** — MySQL-compatible. Built-in HTAP (hybrid transactional + analytical). Query real-time analytics AND transactional data in the same DB, no separate ClickHouse/DuckDB needed.
- **Serializable isolation** — no more worrying about concurrent status updates causing inconsistencies.

**Trade-off:** ScyllaDB has lower write latency at extreme scale. CockroachDB/TiDB are better when query flexibility matters more than raw write throughput.

---
---

# New Companion Services to Build

Complete service ideas that complement the ingestion pipeline. Each includes a recommended tech stack.

---

## 59. Nexus Query Service (Standalone RAG API)

**What it does:** Handles all retrieval and generation — semantic search, hybrid search, RAG with streaming LLM responses, conversation history.

**Recommended stack:**
- **Language:** Python (FastAPI) or Rust (Axum) for lower latency
- **Vector search:** Qdrant (shared instance with ingestion)
- **LLM:** OpenAI / Anthropic Claude via API, or local inference with vLLM
- **Conversation state:** Valkey (short-lived conversation turns) or SurrealDB
- **Streaming:** SSE for streaming LLM token output
- **Caching:** Semantic cache in Qdrant (idea #13) + Valkey for exact-match dedup

**Why a separate service:** Ingestion is CPU/GPU-bound and bursty. Retrieval is latency-sensitive and steady-state. Mixing them in one process means a large ingestion batch starves query latency. Separate services scale independently.

---

## 60. Nexus Gateway (API Gateway / BFF)

**What it does:** A single entry point that sits in front of the ingestion service, query service, and any future services. Handles auth, rate limiting, request routing, and API versioning.

**Recommended stack:**
- **Option A: Kong or Traefik** — mature API gateways with plugin ecosystems. Kong has rate limiting, JWT auth, and request transformation built in. Traefik integrates natively with Docker and Kubernetes service discovery.
- **Option B: Hono on Cloudflare Workers** — if you want something modern and lightweight. Hono is a fast web framework for edge runtimes. Handles auth, routing, and rate limiting at the edge before traffic hits your origin.
- **Option C: Custom FastAPI gateway** — if you want full control. A thin FastAPI service that validates JWTs, applies rate limits (via Valkey), and proxies to backend services. Simpler than it sounds.

**Why build this:** Right now the ingestion service has no auth and `allow_origins=["*"]`. Before adding more services, centralize auth and rate limiting in one place.

---

## 61. Nexus Evaluation Service (RAG Quality Benchmarking)

**What it does:** An automated evaluation pipeline that measures retrieval quality:
- Run a suite of test queries against the knowledge base
- Measure precision, recall, MRR (Mean Reciprocal Rank), and NDCG
- Compare different embedding models, chunking strategies, and search parameters
- Generate reports showing retrieval quality trends over time
- Integrate with CI — fail a PR if retrieval quality degrades after a code change

**Recommended stack:**
- **Framework:** RAGAS or DeepEval for RAG evaluation metrics
- **Test data:** Synthetic questions from idea #48, or manually curated Q&A pairs
- **Storage:** ClickHouse for evaluation results (time-series analytical queries)
- **Orchestration:** Temporal (reuse existing infra) for scheduled evaluation runs
- **Visualization:** Grafana dashboards showing quality metrics over time

---

## 62. Nexus Embedding Service (Centralized Embedding Infrastructure)

**What it does:** A standalone, high-throughput embedding service that any other service (ingestion, query, analytics) calls for embeddings. Centralizes model management, batching, and caching.

**Recommended stack:**
- **Inference server:** vLLM (GPU), or Hugging Face TEI (Text Embeddings Inference) for production. Supports dynamic batching, quantization, and multi-GPU.
- **API:** OpenAI-compatible `/v1/embeddings` endpoint (idea #34)
- **Caching:** Valkey for content-hash → embedding cache
- **Queue:** NATS JetStream for async batch embedding requests
- **Models:** Host multiple models simultaneously (OpenAI text-embedding-3-small, mxbai-embed-large-v1, multilingual models) and route per-request

**Why a separate service:** Embeddings are used everywhere — ingestion, search, semantic caching, analytics clustering. A central service avoids duplicating model loading, GPU allocation, and caching logic across every consumer.

---

## 63. Nexus Document Processing Service (Heavy Compute)

**What it does:** Offloads the heaviest compute — OCR, table extraction, image description, audio transcription — from the ingestion pipeline into a dedicated service optimized for GPU throughput.

**Recommended stack:**
- **OCR / Parsing:** Docling (current), Marker (faster PDF-to-Markdown), or Unstructured.io
- **Vision:** Florence-2 or Qwen2.5-VL for describing images/diagrams (runs locally on GPU, no API cost)
- **Audio:** Whisper large-v3 via faster-whisper (CTranslate2 backend, 4x faster than OpenAI Whisper)
- **GPU management:** NVIDIA Triton Inference Server for multi-model serving on shared GPUs
- **Queue:** Temporal task queue (dedicated `PARSE_QUEUE` from idea #16)

**Why a separate service:** GPU resources are expensive. A dedicated processing service with its own scaling policy (idea #22) prevents GPU-bound parsing from blocking I/O-bound embedding or trivial DB writes.

---

## 64. Nexus Notification Service (Webhooks, Email, Chat)

**What it does:** A general-purpose notification service that other services publish events to. It routes notifications to the right channel based on user preferences.

**Recommended stack:**
- **Event intake:** NATS JetStream consumer (subscribe to `jobs.>`, `alerts.>`, etc.)
- **Delivery channels:** Webhook (httpx), Slack (Bolt SDK), Email (resend.com or SES), Discord (discord.py)
- **Preference storage:** Valkey or SurrealDB (user -> channels -> filters)
- **Retry/DLQ:** Temporal workflow per notification (auto-retry with backoff on webhook failures)
- **Template engine:** Jinja2 for email/message templates

**Why a separate service:** Notification logic (retry policies, rate limiting, template rendering, channel routing) is orthogonal to business logic. Every future service benefits from publishing a single NATS event and letting the notification service handle delivery.

---
---

# Performance Recommendations

Concrete performance improvements for the current codebase based on what's in the code today.

---

## P1. Batch Embedding Calls

**Current:** `VectorStoreIndex` in `embed_markdown()` embeds nodes one at a time via LlamaIndex's default behavior.

**Improvement:** Use OpenAI's batch embedding endpoint directly. Send chunks in batches of 100-2048 texts per API call instead of one at a time. The OpenAI embeddings API supports up to 2048 inputs per request.

```python
# Instead of LlamaIndex's VectorStoreIndex handling embedding internally,
# batch-embed explicitly:
response = await self.openai_client.embeddings.create(
    model="text-embedding-3-small",
    input=[node.text for node in batch],
    dimensions=1536,
)
```

**Impact:** 10-50x fewer API round trips. Massive latency reduction for large documents.

---

## P2. Streaming File Uploads to MinIO

**Current:** The ingestion route reads entire file contents into memory (`file.file.read()`) before uploading to MinIO.

**Improvement:** Stream file uploads directly to MinIO using `put_object()` with the file stream, avoiding loading the full file into memory. For large files (100MB+ PDFs, video files), this prevents OOM.

```python
# Stream directly instead of reading into memory
await asyncio.to_thread(
    minio.put_object,
    bucket_name="nexus-uploads",
    object_name=object_name,
    data=file.file,
    length=-1,  # unknown length, MinIO handles chunked upload
    part_size=10 * 1024 * 1024,  # 10MB parts
)
```

---

## P3. Prepared Statement Warming

**Current:** `ScyllaService._prepare()` lazily prepares statements on first use, which means the first request to each query pattern pays a latency penalty.

**Improvement:** Pre-warm all known prepared statements during `initialize_scylla()`. The query strings are all known at compile time (they're in `IngestionRepository`). Prepare them all at startup.

---

## P4. Connection Pooling for OpenAI / Embedding API

**Current:** `AsyncOpenAI` uses default httpx connection pool settings.

**Improvement:** Configure the connection pool explicitly for high-concurrency embedding:

```python
import httpx
client = AsyncOpenAI(
    api_key=config.OPENAI_KEY,
    http_client=httpx.AsyncClient(
        limits=httpx.Limits(
            max_connections=50,
            max_keepalive_connections=20,
        ),
        timeout=httpx.Timeout(60.0),
    ),
)
```

**Impact:** Prevents connection exhaustion during burst embedding. Default httpx limits are conservative (100 total / 20 keepalive).

---

## P5. Qdrant Batch Upsert with `wait=False`

**Current:** `VectorStoreIndex` upserts points to Qdrant via LlamaIndex's default behavior (likely sequential).

**Improvement:** Use Qdrant's native batch upsert with `wait=False` for fire-and-forget writes when durability is handled by the workflow retry:

```python
await self.qdrant_client.upsert(
    collection_name="nexus_knowledge_base",
    points=batch_of_points,
    wait=False,  # Don't wait for WAL flush — 2-3x faster writes
)
```

**Impact:** 2-3x write throughput improvement. The Temporal retry policy already handles failures, so waiting for each WAL flush is unnecessary.

---

## P6. Enable gRPC for Qdrant

**Current:** `QDRANT_PREFER_GRPC` defaults to `False`.

**Improvement:** Set it to `True`. Qdrant's gRPC interface is 2-5x faster than REST for batch operations because Protobuf serialization is more efficient than JSON for vectors (arrays of 1536 floats).

---

## P7. Worker Concurrency Tuning

**Current:** `asyncio.Semaphore(4)` is hardcoded in `parse_files`.

**Improvement:** Make this configurable via environment variable. Optimal concurrency depends on hardware:
- GPU worker with 24GB VRAM: semaphore of 2-4 (Docling is memory-hungry)
- CPU-only worker: semaphore of 1-2
- Embed-only worker (API calls): semaphore of 20-50 (I/O-bound)

---

## P8. ScyllaDB Token-Aware Load Balancing

**Current:** Default `Cluster` configuration uses round-robin routing.

**Improvement:** Enable token-aware routing so queries go directly to the node that owns the partition:

```python
from cassandra.policies import TokenAwarePolicy, DCAwareRoundRobinPolicy

Cluster(
    contact_points=contact_points,
    load_balancing_policy=TokenAwarePolicy(DCAwareRoundRobinPolicy()),
    connection_class=AsyncioConnection,
)
```

**Impact:** Eliminates coordinator hops. Especially impactful as you scale beyond a single ScyllaDB node.

---
---

# Big Tech Infrastructure & Patterns Worth Learning

Tech and patterns used at NVIDIA, Anthropic, Google, Meta, Apple, Netflix, Uber, Cloudflare, and others. Each maps to something you can apply to this project or build as a new service.

---

## 65. NVIDIA Triton Inference Server (Multi-Model GPU Serving)

**Used by:** NVIDIA, AWS (SageMaker), Azure, most ML platform teams

**What:** Triton is NVIDIA's production inference server. It serves multiple models (PyTorch, TensorFlow, ONNX, TensorRT, vLLM) on shared GPUs with dynamic batching, model ensembles, and automatic GPU memory management.

**How it applies to your project:** Instead of loading Docling + embedding models + vision models in separate Python processes each claiming a full GPU, Triton multiplexes them on shared GPU memory. It dynamically batches requests — if 20 embedding requests arrive within 5ms, Triton fuses them into a single GPU kernel call.

**What you'd learn:**
- Model repository patterns (versioned model configs)
- Dynamic batching and request scheduling on GPU
- TensorRT optimization (quantize models for 3-5x inference speedup)
- gRPC + shared-memory transport between client and server (zero-copy inference)
- Ensemble pipelines (chain OCR → NER → embedding in a single Triton request)

**Language to write clients in:** Python (tritonclient), C++ for custom backends
**Infrastructure:** Docker with NVIDIA Container Toolkit, or Kubernetes with NVIDIA GPU Operator

---

## 66. Anthropic-Style Prompt Caching & Context Management

**Used by:** Anthropic (Claude API)

**What:** Anthropic's prompt caching lets you cache long system prompts and reuse them across requests, paying only for the incremental tokens. This pattern generalizes: any RAG system can separate "static context" from "dynamic query" and cache the static part.

**How it applies:** When your Query Service does RAG, the retrieved documents form a context window. If multiple users query the same corpus (same project), the document context is identical — only the user question changes. Cache the document context prefix and reuse it.

**What you'd learn:**
- KV-cache management for transformer inference
- Prefix-sharing across requests (vLLM's automatic prefix caching does this)
- Cost optimization — Anthropic charges 90% less for cached tokens. At scale, this is the single biggest cost lever for RAG.
- Designing retrieval to maximize cache hits (sort retrieved chunks deterministically so the same documents produce the same token prefix)

---

## 67. Google Colossus / Apple FoundationDB (Distributed Storage Layers)

**Used by:** Google (Colossus underpins BigTable, Spanner, GFS), Apple (FoundationDB underpins iCloud, CloudKit)

**What:** Both are distributed storage layers that provide strong consistency guarantees and are used as the foundation for higher-level databases. FoundationDB is open source; Colossus is not.

**How it applies:** FoundationDB's "layer" concept is worth studying. It's a minimal ordered key-value store, and everything else (document DB, graph DB, spatial index) is built as a layer on top. Tigris (idea #54) is a FoundationDB layer. You could build your own:

**What you'd learn:**
- **FoundationDB** — ACID transactions across a distributed cluster with serializable isolation. The testing methodology (deterministic simulation testing) is legendary — they simulate network partitions, disk failures, and clock skew to find bugs before production.
- **Layer concept** — build a purpose-built storage layer for your exact access patterns. Instead of adapting your queries to ScyllaDB's data model, build a layer that matches your domain model exactly.
- **Deterministic simulation testing** — Antithesis (founded by FoundationDB creators) sells this as a product. Write your service, Antithesis finds bugs by simulating every possible failure mode. Restate (idea #51) also uses this approach.

**Language:** FoundationDB itself is C++. Client bindings in Python, Go, Rust, Java.

---

## 68. Meta FAISS + Product Quantization (Billion-Scale Vector Search)

**Used by:** Meta (Facebook AI), Spotify, Pinterest, Instacart

**What:** FAISS (Facebook AI Similarity Search) is Meta's library for billion-scale nearest neighbor search. It's not a database — it's a library that runs in-process. Combined with Product Quantization (PQ), it compresses 1536-dim float32 vectors down to ~64 bytes while maintaining >95% recall.

**How it applies:** If Qdrant becomes a bottleneck at scale, or if you want sub-millisecond search for a hot path, FAISS running in-process eliminates network round-trips entirely.

**What you'd learn:**
- **IVF (Inverted File Index)** — partition the vector space into Voronoi cells, only search nearby cells. 10-100x faster than brute force.
- **Product Quantization** — compress vectors from 6KB to 64 bytes. Fit 1 billion vectors in ~64GB RAM.
- **GPU FAISS** — run search on GPU for another 10-50x speedup. NVIDIA builds custom CUDA kernels for this.
- **Hybrid search architecture** — use FAISS for hot data (recent 30 days) and Qdrant for the full corpus. Two-tier like Google's search index.

**Language:** C++ core with Python bindings. GPU variant needs CUDA.

---

## 69. Netflix Zuul / Envoy Proxy (Service Mesh & Intelligent Routing)

**Used by:** Netflix (Zuul), Google/Lyft (Envoy), Uber, every large microservices org

**What:** Envoy is an L7 proxy written in C++ that handles service-to-service communication. It provides load balancing, circuit breaking, rate limiting, observability, and mTLS — all without modifying application code.

**How it applies:** As you add more services (query, embedding, notification, processing), you need service-to-service communication that handles failures gracefully. Envoy as a sidecar proxy gives you:
- **Circuit breaking** — if the embedding service is overloaded, Envoy stops sending requests instead of cascading the failure to ingestion.
- **Automatic retries** with jitter (replaces manual retry logic)
- **Distributed tracing** — Envoy injects trace headers so you can see a request flow from Gateway → Ingestion → Processing → Embedding → Qdrant.
- **gRPC load balancing** — HTTP/2-aware, unlike standard L4 load balancers that pin all streams to one connection.

**Alternative:** Linkerd (Rust-based, simpler than Envoy/Istio). Or skip the mesh and use NATS for service communication (request-reply pattern).

**Infrastructure:** Kubernetes with Istio (Envoy-based) or Linkerd. Or standalone Envoy in Docker Compose.

---

## 70. Uber Cadence → Temporal Patterns (Advanced Workflow Techniques)

**Used by:** Uber (Cadence, Temporal's predecessor), Stripe, Netflix, Snap, Datadog

**What:** Since you already use Temporal, here are advanced patterns that big companies use:

- **Saga pattern** — long-running transactions across services. If embedding fails after parsing succeeded, run compensating actions (delete parsed data, update status, notify user). Uber uses this for ride booking (reserve driver → charge payment → if charge fails, release driver).
- **Continue-as-new** — for workflows processing unbounded data (streaming ingestion, continuous crawling). Instead of one workflow growing forever, snapshot state and start a new execution. Prevents history size from exploding.
- **Child workflows** — your current monolithic workflow could spawn child workflows per file. If one file hangs, it doesn't block others. Each child has independent retry/timeout policies.
- **Schedules** — built-in cron. Trigger re-indexing, cleanup, or evaluation runs on a schedule without an external cron system.
- **Update/Signal handlers** — let external systems inject data into a running workflow. A user cancels a job? Signal the workflow. Priority change? Update the workflow in-flight.

---

## 71. Cloudflare Workers + R2 + D1 (Edge-Native Architecture)

**Used by:** Cloudflare, Vercel, Shopify, Discord

**What:** Run compute at the edge (200+ global PoPs). Workers run V8 isolates that cold-start in <5ms. R2 is S3-compatible storage with zero egress fees. D1 is SQLite at the edge.

**How it applies:** Build the Gateway (idea #60) and Query Service (idea #59) on Cloudflare:
- **Workers** — handle auth, rate limiting, and request routing at the edge. Requests that fail auth never reach your origin servers.
- **R2** — replace MinIO for file storage. Zero egress fees means serving files to users costs nothing. S3-compatible API so your boto3 code works unchanged.
- **Vectorize** — Cloudflare's edge vector database. Store a lightweight index at the edge for low-latency similarity search, backed by Qdrant for the full corpus.
- **D1** — SQLite at the edge for user preferences, API keys, rate limit counters.
- **Queues** — Cloudflare Queues for async work dispatch from edge to origin.

**What you'd learn:** Edge computing patterns, V8 isolate model, globally distributed state. This is where the industry is heading — compute moves to the user, not the other way around.

**Language:** TypeScript/JavaScript (Workers), Python (limited support via Pyodide)

---

## 72. Google Spanner-Style Global Consistency (TrueTime)

**Used by:** Google (Spanner), CockroachDB (approximation)

**What:** Google Spanner achieves globally consistent reads using GPS-synced atomic clocks (TrueTime). CockroachDB approximates this with NTP + hybrid logical clocks. The insight: if you know the uncertainty bound on your clock, you can wait out the uncertainty window and guarantee consistency.

**How it applies:** If your system goes multi-region (idea #20), you face the question: "user uploads in US-East, queries in EU-West — does the query see the upload?" With ScyllaDB's eventual consistency, maybe not. With Spanner/CockroachDB, yes — always.

**What you'd learn:**
- **Hybrid logical clocks** — how CockroachDB guarantees consistency without atomic clocks
- **Linearizability vs serializability** — the two strongest consistency models and when you need each
- **Multi-region replication topologies** — active-active vs active-passive vs consensus-based

**Infrastructure:** CockroachDB multi-region cluster or Google Cloud Spanner (managed)

---

## 73. Meta PyTorch + CUDA Custom Kernels (GPU Programming)

**Used by:** NVIDIA, Meta, OpenAI, Anthropic, every AI lab

**What:** Write custom CUDA kernels for operations that PyTorch doesn't optimize well. Or use Triton (the language, not the server — confusingly same name) to write GPU kernels in Python.

**How it applies:** Your embedding pipeline's bottleneck will eventually be GPU throughput. Custom kernels for:
- **Fused attention** — FlashAttention (by Tri Dao, used by everyone) fuses the attention computation into a single kernel, 2-4x faster than naive PyTorch.
- **Quantized inference** — run embedding models in INT8 or INT4 with custom kernels. NVIDIA's TensorRT and Meta's FBGEMM do this.
- **Batch preprocessing** — tokenize + pad + embed in a single GPU pipeline instead of CPU tokenize → GPU embed.

**What you'd learn:**
- **OpenAI Triton** (the language) — write GPU kernels in Python. Much easier than raw CUDA. This is what Anthropic and OpenAI use for custom training kernels.
- **CUDA programming model** — threads, blocks, warps, shared memory, memory coalescing
- **Model optimization pipeline** — PyTorch → ONNX → TensorRT for production inference

**Language:** Python (Triton language), CUDA C++ for raw kernels

---

## 74. Netflix Data Mesh + Apache Iceberg (Lakehouse Architecture)

**Used by:** Netflix, Apple, Airbnb, Uber, LinkedIn

**What:** Apache Iceberg is a table format for huge datasets (petabyte-scale) that supports ACID transactions, time travel, schema evolution, and partition pruning. It sits on top of object storage (S3/MinIO/R2) and is queried by engines like Spark, Trino, DuckDB, or ClickHouse.

**How it applies:** As your document corpus grows, you'll need an analytical layer:
- Store all ingested document metadata, embeddings, and processing metrics in Iceberg tables on MinIO
- Query with DuckDB locally or Trino in production
- Time travel: "show me the corpus as it existed on January 15th" — useful for debugging retrieval regressions
- Schema evolution: add columns to metadata tables without rewriting data

**What you'd learn:**
- **Lakehouse architecture** — combine the flexibility of a data lake with the reliability of a data warehouse
- **Parquet + Iceberg** — columnar storage with metadata layers
- **Apache Spark** — distributed compute for batch processing millions of documents
- **Data mesh** — organizational pattern where each team owns their data as a product. Your ingestion service publishes Iceberg tables that other teams consume.

**Infrastructure:** MinIO (you already have it) + Iceberg + DuckDB (dev) / Trino (prod) / Spark (batch)

---

## 75. Anthropic Constitutional AI Patterns (Self-Improving Pipelines)

**Used by:** Anthropic, OpenAI, Google DeepMind

**What:** Constitutional AI uses an LLM to evaluate and improve its own outputs against a set of principles. Apply this pattern to your ingestion pipeline — use an LLM to evaluate and improve the quality of parsed/chunked content.

**How it applies:**
- **Chunk quality evaluation** — after chunking, run a fast model (Claude Haiku / GPT-4o-mini) to score each chunk: "Does this chunk contain a coherent, self-contained idea? Score 1-5." Discard or re-chunk low-scoring chunks.
- **Parsing quality checks** — compare Docling's Markdown output against the original PDF. "Does the Markdown preserve all information from page 3? List anything missing." Automatically re-parse pages that fail.
- **Embedding quality validation** — embed a chunk, then use the embedding to retrieve the original chunk. If it doesn't come back in top-3, the embedding or chunk has quality issues.
- **Continuous improvement loop** — log quality scores, identify failure patterns, fine-tune parsing/chunking strategies automatically.

**What you'd learn:** LLM-as-judge patterns, RLHF/RLAIF concepts, self-improving system design

---

## 76. Google Borg / Kubernetes Operators (Custom Infrastructure Automation)

**Used by:** Google (Borg → Kubernetes), every cloud-native company

**What:** Write a Kubernetes Operator that automates your entire platform's lifecycle — deploying services, scaling based on queue depth, provisioning Qdrant collections, managing database migrations.

**How it applies:** Instead of manually `docker compose up`, build an operator that:
- Watches a `NexusProject` CRD (Custom Resource Definition) — when a user creates one, the operator provisions a Qdrant collection, ScyllaDB keyspace, MinIO bucket, and NATS subjects
- Auto-scales Temporal workers based on queue depth (KEDA + Temporal metrics)
- Runs canary deployments — deploy new embedding model to 10% of traffic, compare quality metrics, auto-promote or rollback
- Manages GPU node pools — scale GPU nodes to zero when no processing jobs are queued

**What you'd learn:**
- **Kubernetes Operator pattern** — the same pattern Google uses internally to manage all their infrastructure
- **Custom Resource Definitions** — extend Kubernetes with your own API objects
- **Reconciliation loops** — the core of Kubernetes: continuously observe actual state, compare to desired state, take action
- **KEDA** — event-driven autoscaling based on NATS queue depth, Temporal task count, etc.

**Language:** Go (kubebuilder/operator-sdk) or Python (kopf)
**Infrastructure:** Kubernetes (k3s for dev, EKS/GKE for prod), KEDA, Prometheus

---

## 77. Uber H3 + PostGIS (Geospatial Indexing for Documents)

**Used by:** Uber, Foursquare, Snap, Google Maps

**What:** H3 is Uber's hexagonal hierarchical geospatial indexing system. PostGIS extends PostgreSQL with spatial operations.

**How it applies:** If your corpus includes location-aware documents (real estate listings, city permits, restaurant menus, travel guides), add geospatial search:
- Tag documents with lat/lng during ingestion
- "Find similar documents within 5km of this location" — combine H3 spatial filtering with Qdrant vector similarity
- Spatial clustering — group documents by geographic region for better retrieval

**Language:** Python (h3-py), SQL (PostGIS)
**Infrastructure:** PostgreSQL + PostGIS (or CockroachDB which has spatial support built in)

---

## 78. Meta LLaMA + LoRA Fine-Tuning (Custom Embedding Models)

**Used by:** Meta, Anthropic, Google, every AI team doing domain-specific tasks

**What:** Fine-tune open-source embedding models on your specific domain data using LoRA (Low-Rank Adaptation) — a technique that trains only ~1% of model parameters, making fine-tuning feasible on a single GPU.

**How it applies:**
- Fine-tune `mxbai-embed-large-v1` or `bge-large-en-v1.5` on your domain's vocabulary
- Generate training pairs from your corpus: (query, positive_chunk, negative_chunk)
- A fine-tuned model can improve retrieval quality by 10-30% on domain-specific queries
- Serve the fine-tuned model via HuggingFace TEI or Triton

**What you'd learn:**
- **LoRA / QLoRA** — parameter-efficient fine-tuning. Train on a single A100 or even a 3090.
- **Contrastive learning** — the training objective for embedding models (pull similar pairs together, push dissimilar pairs apart)
- **Matryoshka embeddings** — train models that produce useful embeddings at any dimension (256, 512, 1024, 1536). Use short embeddings for fast filtering, full-length for re-ranking.
- **Evaluation** — MTEB benchmark, BEIR datasets, custom test suites

**Language:** Python (transformers, sentence-transformers, peft)
**Infrastructure:** Single GPU (24GB+ VRAM), Weights & Biases for experiment tracking

---

## 79. Apple Private Cloud Compute Pattern (Confidential Computing)

**Used by:** Apple, Microsoft (Azure Confidential Computing), Google (Confidential VMs)

**What:** Process sensitive data in hardware-isolated enclaves where even the cloud provider cannot see the data. Apple's Private Cloud Compute uses this for on-device AI that needs server-side processing.

**How it applies:** If you ingest sensitive documents (medical records, legal contracts, financial data):
- Run parsing and embedding inside a TEE (Trusted Execution Environment) — AMD SEV-SNP or Intel TDX
- The encryption keys never leave the hardware enclave
- Remote attestation proves to clients that their data is processed in a secure environment
- Even if the host is compromised, enclave data is protected

**What you'd learn:**
- **TEE architecture** — how hardware enclaves work (AMD SEV, Intel SGX/TDX, ARM CCA)
- **Remote attestation** — cryptographic proof that code is running in a genuine enclave
- **Confidential containers** — run Docker containers inside enclaves (Kata Containers, Azure Confidential Containers)
- **Threat modeling** — what confidential computing protects against vs what it doesn't

**Infrastructure:** AMD EPYC servers (SEV-SNP), Azure Confidential VMs, or GCP Confidential Computing

---

## 80. Stripe-Style Idempotency Keys (Exactly-Once Ingestion)

**Used by:** Stripe, AWS, Google Cloud APIs

**What:** Every API call includes an idempotency key. If the same key is seen twice, the server returns the cached result instead of re-processing. Stripe pioneered this pattern for payment APIs.

**How it applies:** Your ingestion endpoint should be idempotent:
- Client sends `Idempotency-Key: abc123` header with the upload
- Server checks Valkey/Redis for that key. If found, return the existing job.
- If not found, process the upload and cache the result with the key.
- This prevents duplicate ingestion when clients retry on timeout.

**What you'd learn:**
- Distributed idempotency with key expiry
- The CAP implications — what happens if the idempotency cache is unavailable?
- Stripe's approach: store idempotency records in the same transaction as the business operation (no cache — database-backed)

---

## 81. Netflix Chaos Engineering (Resilience Testing)

**Used by:** Netflix (Chaos Monkey), AWS (Fault Injection Service), Gremlin

**What:** Intentionally inject failures into production systems to find weaknesses before they cause outages.

**How it applies:**
- **Kill a Temporal worker** mid-activity — does the workflow recover and retry on another worker?
- **Partition Qdrant** — what happens when the vector DB is unreachable during embedding? Does the workflow retry or corrupt state?
- **Slow down MinIO** — inject 5-second latency on `put_object`. Does the ingestion timeout cascade to WebSocket clients?
- **Fill ScyllaDB disk** — does the schema creation handle write failures gracefully?

**What you'd learn:**
- **Steady-state hypothesis** — define "normal" (e.g., "jobs complete within 60s with <1% failure rate"), then inject faults and verify the hypothesis still holds
- **Blast radius control** — start with one request, not all traffic
- **Game days** — scheduled chaos exercises where the team practices incident response

**Tools:** Chaos Mesh (Kubernetes-native), Litmus (CNCF), or just `tc` and `iptables` for network faults
**Language:** Go (Chaos Mesh controllers) or Python (custom fault injection scripts)

---

## 82. Cloudflare Durable Objects (Stateful Edge Compute)

**Used by:** Cloudflare, Discord (message storage), Canva

**What:** Durable Objects are single-threaded, stateful JavaScript objects that live at the edge. Each object has a unique ID, persistent storage, and guaranteed single-execution (no concurrency issues). Think of them as lightweight actors.

**How it applies:**
- **Job coordination** — each ingestion job is a Durable Object. It tracks file status, handles WebSocket connections, and coordinates between parse/embed/finalize stages. No need for ScyllaDB for job state or NATS for pubsub — the Durable Object IS the coordination layer.
- **Rate limiting** — per-user Durable Objects that track request counts with zero-latency reads (state is co-located with compute).
- **Real-time collaboration** — if multiple users watch the same job's progress, they connect to the same Durable Object which broadcasts updates.

**What you'd learn:**
- **Actor model** — single-threaded, message-passing concurrency (same model as Erlang/Elixir, which powers WhatsApp and Discord)
- **Edge-native state management** — state lives where the user is, not in a central datacenter
- **Conflict-free coordination** — single-writer pattern eliminates race conditions without locks

**Language:** TypeScript
**Infrastructure:** Cloudflare Workers platform

---
---

# Expanded Companion Services with Full Stack Recommendations

Detailed service blueprints with language choices, infrastructure, and reasoning for each.

---

## 83. Nexus Auth Service

**What it does:** Centralized authentication and authorization. JWT issuance, API key management, OAuth2/OIDC, RBAC, and row-level access control for multi-tenant document isolation.

**Recommended language:** **Go**
- Auth services are latency-critical (every request passes through them) and Go compiles to a single binary with sub-millisecond response times
- Excellent JWT/crypto libraries (golang-jwt)
- Built-in HTTP server is production-ready (no framework needed)

**Infrastructure:**
- **Database:** PostgreSQL (ACID for user/role data, not eventually consistent)
- **Session/token cache:** Valkey (formerly Redis) — store revoked tokens, rate limit counters, session data
- **OIDC provider:** Use Ory Hydra (open source, Go-based) or Zitadel if you want a full identity platform
- **Secret management:** HashiCorp Vault or SOPS for API key encryption at rest
- **Deploy:** Single Docker container, <50MB image, <10MB RAM

---

## 84. Nexus Search & Retrieval Service (Production RAG)

**What it does:** The read path — semantic search, hybrid search, re-ranking, RAG generation with streaming, conversation memory, and citation tracking.

**Recommended language:** **Rust (Axum framework)**
- P99 latency matters for search — users wait for every millisecond
- Axum is async-native, compiles to a single binary, uses ~5MB RAM idle
- Rust's ownership model prevents the memory leaks that plague long-running Python services
- If Rust is too steep: **Go (Fiber/Echo)** for similar performance with easier onboarding

**Infrastructure:**
- **Vector DB:** Qdrant (gRPC, shared cluster with ingestion)
- **Re-ranking:** Cohere Rerank API, or self-hosted cross-encoder via Triton
- **LLM:** Anthropic Claude / OpenAI via API. For self-hosted: vLLM on GPU nodes
- **Conversation memory:** Valkey with TTL (ephemeral) + ScyllaDB (persistent history)
- **Caching:** Two-tier — Valkey for exact query cache, Qdrant for semantic similarity cache (idea #13)
- **Streaming:** Server-Sent Events (SSE) for token streaming to clients
- **Deploy:** Kubernetes with HPA scaling on request latency P95

---

## 85. Nexus Real-Time Streaming Pipeline

**What it does:** Continuous ingestion from streaming sources — Kafka topics, webhook events, database CDC (Change Data Capture), RSS/Atom feeds, file system watchers.

**Recommended language:** **Rust or Go**
- Streaming pipelines need consistent low-latency processing with minimal GC pauses
- Rust: use `rdkafka` crate (librdkafka wrapper) for Kafka, `tokio` for async I/O
- Go: use `confluent-kafka-go` or Sarama, goroutines for concurrent stream processing

**Infrastructure:**
- **Message broker:** Apache Kafka or Redpanda (Kafka-compatible, written in C++, no JVM, 10x lower latency). Redpanda is the bleeding-edge choice.
- **CDC:** Debezium for capturing database changes as events
- **Stream processing:** Use native consumers (avoid Spark Streaming / Flink unless you're at massive scale). For complex event processing, consider Arroyo (Rust-based stream processor with SQL).
- **Schema registry:** Confluent Schema Registry or Buf (for Protobuf schemas)
- **Deploy:** Redpanda cluster (3 nodes minimum) + consumer containers

**Why Redpanda over Kafka:**
- Single C++ binary, no JVM, no ZooKeeper
- 10x lower tail latency
- S3-compatible tiered storage built in
- Kafka API compatible — your Kafka libraries work unchanged

---

## 86. Nexus Observability Stack

**What it does:** Unified logging, metrics, tracing, and alerting across all services. Not a service you write, but an infrastructure stack you deploy.

**Recommended stack (all open source):**

| Layer | Tool | Why |
|-------|------|-----|
| **Metrics** | VictoriaMetrics | Prometheus-compatible, 10x less RAM, long-term storage. Drop-in replacement. |
| **Logs** | Grafana Loki | Log aggregation designed for Kubernetes. Index-free — stores compressed log streams, queries by label. 10-100x cheaper than Elasticsearch. |
| **Traces** | Grafana Tempo | Distributed tracing backend. Stores traces in object storage (MinIO!). Integrates with OpenTelemetry. |
| **Visualization** | Grafana | Dashboards for all three signal types in one UI. |
| **Alerting** | Grafana Alerting | Alert on metrics, logs, or trace-derived SLOs. Routes to Slack/PagerDuty/email. |
| **Instrumentation** | OpenTelemetry | Vendor-neutral SDK. One instrumentation → export to any backend. |

**Language for instrumentation:** Python (opentelemetry-python), auto-instrumented for FastAPI, httpx, and Temporal
**Infrastructure:** Docker Compose for dev, Kubernetes with Helm charts for prod. All components store data in MinIO (object storage you already run).

**What you'd learn:** OpenTelemetry is becoming the universal standard. Every big company (Google, Microsoft, AWS, Uber, Stripe) is converging on it. Learning OTel now means you understand observability everywhere.

---

## 87. Nexus Admin Dashboard

**What it does:** Web UI for monitoring ingestion jobs, browsing the document corpus, testing search queries, managing projects/users, and viewing system health.

**Recommended language:** **TypeScript (Next.js or SvelteKit)**
- Next.js: React-based, biggest ecosystem, great for data-heavy dashboards. Used by Netflix, Twitch, Notion.
- SvelteKit: Simpler, faster, less boilerplate. Better developer experience. Used by Apple (some internal tools), Vercel.

**Infrastructure:**
- **Backend:** The dashboard calls your existing services via REST/gRPC. No new backend needed.
- **Auth:** Clerk or Auth0 for managed auth, or your Nexus Auth Service (idea #83)
- **Real-time:** Connect to the existing NATS WebSocket for live job updates
- **Charts:** Recharts (React) or LayerChart (Svelte) for ingestion metrics visualization
- **Hosting:** Vercel (zero-config Next.js), Cloudflare Pages (SvelteKit), or self-hosted in Docker
- **State management:** TanStack Query (React) or SvelteKit's built-in load functions for server-state

**What you'd learn:** Modern full-stack TypeScript, SSR/streaming, edge rendering, real-time WebSocket UIs

---

## 88. Nexus CLI Tool

**What it does:** A command-line tool for developers to interact with the platform — upload files, check job status, query the knowledge base, manage projects, and configure settings.

**Recommended language:** **Rust (clap crate) or Go (cobra)**
- Both compile to a single static binary — `curl | install` just works, no runtime needed
- Rust with `clap`: beautiful auto-generated help, shell completions, typed arguments
- Go with `cobra`: same pattern, used by kubectl, gh (GitHub CLI), docker CLI

```
nexus upload ./docs/ --project my-project --source cli
nexus jobs list --project my-project --status processing
nexus search "how does authentication work" --project my-project --top-k 5
nexus status abc-123-def
```

**Infrastructure:**
- **Distribution:** GitHub Releases with cross-compiled binaries (linux/mac/windows). Use GoReleaser (Go) or cargo-dist (Rust) for automated releases.
- **Auth:** Store API key in `~/.nexus/config.toml`
- **Output:** JSON (for piping to jq) and human-readable table format (default)

---

## 89. Nexus Data Sync Service (Connectors)

**What it does:** Pull documents from external sources — Google Drive, Notion, Confluence, SharePoint, Slack, GitHub repos, S3 buckets — and continuously sync them into the ingestion pipeline.

**Recommended language:** **Python (FastAPI or plain async)**
- Connector logic is I/O-bound (API calls to external services), Python's async is perfect
- Most third-party SDKs are Python-first (google-api-python-client, notion-client, atlassian-python-api)
- Low compute, high I/O — Python's speed doesn't matter here

**Infrastructure:**
- **Orchestration:** Temporal (reuse existing). Each connector is a workflow with a schedule (e.g., sync Google Drive every 15 minutes).
- **OAuth token storage:** HashiCorp Vault or encrypted PostgreSQL column
- **Change detection:** Store file hashes/ETags in ScyllaDB. Only re-ingest changed files.
- **Queue:** NATS JetStream for dispatching sync events to the ingestion service
- **Rate limiting:** Respect external API rate limits with Temporal's activity heartbeats + sleep

**What you'd learn:** OAuth2 flows, webhook receivers, incremental sync patterns, backpressure handling

---

## 90. Nexus Model Registry & A/B Testing Service

**What it does:** Manage multiple embedding models, chunking strategies, and retrieval configurations. Run A/B tests to compare them in production.

**Recommended language:** **Go**
- Routing decisions (which model serves this request) must be fast and consistent
- Go's simplicity makes the routing logic easy to audit
- Excellent concurrency for handling traffic splitting

**Infrastructure:**
- **Config store:** etcd (the same thing Kubernetes uses for configuration) — strongly consistent, watchable key-value store
- **Traffic splitting:** Envoy proxy with weighted routes, or application-level routing in the Gateway
- **Metrics:** OpenTelemetry metrics tagged by experiment variant → VictoriaMetrics → Grafana
- **Statistical analysis:** Python notebook (Jupyter) or automated with scipy for significance testing
- **Model storage:** MinIO for model artifacts (LoRA adapters, ONNX files)

---

## Language Recommendation Summary

| Service | Language | Reason |
|---------|----------|--------|
| Ingestion (current) | Python | Correct choice — ML libraries, Docling, LlamaIndex all Python-first |
| Auth | Go | Latency-critical, single binary, great crypto libs |
| Search / RAG | Rust (Axum) | P99 latency matters, memory safety for long-running processes |
| Streaming Pipeline | Rust or Go | Consistent latency, no GC pauses, high throughput |
| Data Sync / Connectors | Python | I/O-bound, best third-party SDK support |
| Admin Dashboard | TypeScript (Next.js/SvelteKit) | Full-stack web, real-time UIs, SSR |
| CLI Tool | Rust or Go | Single binary distribution, shell completions |
| Model Registry / A/B | Go | Simple routing logic, fast, auditable |
| GPU Processing | Python + Rust (PyO3) | Python for ML frameworks, Rust for CPU-hot paths |
| Gateway | Go (or Hono/TypeScript for edge) | High-throughput proxy, minimal overhead |

---

## Infrastructure Platform Recommendation

If you're building the full Nexus platform, here's the infrastructure stack:

| Layer | Tool | Why |
|-------|------|-----|
| **Container orchestration** | Kubernetes (k3s for dev) | Industry standard, required for GPU scheduling |
| **GPU scheduling** | NVIDIA GPU Operator + MIG | Multi-instance GPU — one A100 serves 7 isolated workloads |
| **Service mesh** | Linkerd (simpler) or Istio (more features) | mTLS, circuit breaking, traffic splitting |
| **Autoscaling** | KEDA | Scale on NATS queue depth, Temporal task count, custom metrics |
| **CI/CD** | GitHub Actions + ArgoCD | GitOps — push to git, ArgoCD syncs to cluster |
| **Secret management** | HashiCorp Vault | Dynamic secrets, auto-rotation, PKI |
| **DNS/TLS** | Cloudflare (proxy) + cert-manager | Automatic HTTPS, DDoS protection |
| **Object storage** | MinIO (self-hosted) or R2 (cloud) | You already run MinIO |
| **Package registry** | GitHub Container Registry (ghcr.io) | Free for public, integrated with GitHub Actions |

---
---

# Drop-In Bleeding-Edge Tech You Can Actually Use

Not patterns to study — actual technology you can swap into your stack today. Each entry maps directly to a component in your current `docker-compose.yml`, `pyproject.toml`, or `app/clients/`. Organized by what they replace.

---

## REPLACE: LlamaIndex Embedding Pipeline → Direct OpenAI Batch + Custom Chunker

**What you currently have:** LlamaIndex `VectorStoreIndex` + `MarkdownNodeParser` + `OpenAIEmbedding` in `embed_markdown()`. LlamaIndex wraps OpenAI calls, manages node→vector→Qdrant insertion, but adds abstraction overhead and limits control over batching.

**Replace with:** Call OpenAI and Qdrant directly. You already have both clients as singletons. Cut out the middleman.

```python
# app/service/ingestion.py — replace the LlamaIndex VectorStoreIndex path

from llama_index.core.node_parser import MarkdownNodeParser  # keep just the parser
from qdrant_client.models import PointStruct
import uuid

async def embed_and_store(
    documents: list[Document],
    qdrant: AsyncQdrantClient,
    openai: AsyncOpenAI,
    collection: str,
    project_id: str,
    source: str,
    batch_size: int = 512,
) -> int:
    parser = MarkdownNodeParser()
    nodes = parser.get_nodes_from_documents(documents)

    total_stored = 0
    for i in range(0, len(nodes), batch_size):
        batch = nodes[i : i + batch_size]
        texts = [node.get_content() for node in batch]

        # Single API call for entire batch — 50x fewer round trips
        response = await openai.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
            dimensions=1536,
        )

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=emb.embedding,
                payload={
                    "text": texts[j],
                    "source": source,
                    "project_id": project_id,
                    "node_id": batch[j].node_id,
                },
            )
            for j, emb in enumerate(response.data)
        ]

        # Fire-and-forget — Temporal retries handle durability
        await qdrant.upsert(
            collection_name=collection,
            points=points,
            wait=False,
        )
        total_stored += len(points)

    return total_stored
```

**What you gain:**
- Remove `llama-index-core`, `llama-index-embeddings-openai`, `llama-index-vector-stores-qdrant` from `pyproject.toml` — that's **hundreds of transitive deps** gone
- 50x fewer API calls (batch 512 texts per request instead of 1)
- Direct control over Qdrant point payloads (add any metadata you want)
- `wait=False` for 2-3x write throughput
- ~200MB smaller Docker image without LlamaIndex's dependency tree

**What you keep:** `MarkdownNodeParser` is genuinely useful. You can vendor just that one file (~200 lines) if you want to fully drop LlamaIndex.

---

## REPLACE: Docling → Marker (Faster PDF→Markdown)

**What you currently have:** `docling>=2.73.1` converts documents to Markdown. It works but it's heavy (pulls in PyTorch vision models, ~2GB of model weights).

**Replace with:** **Marker** by VikParuchuri — purpose-built for high-speed, high-quality PDF→Markdown conversion. Created by the developer behind Surya OCR. Used by many AI companies for document processing pipelines.

```toml
# pyproject.toml — swap docling for marker
dependencies = [
    "marker-pdf>=1.6.0",  # replaces docling
    # ...
]
```

```python
# app/service/ingestion.py — swap the converter
from marker.converters.pdf import PdfConverter
from marker.config.parser import ConfigParser

config_parser = ConfigParser({"output_format": "markdown"})
converter = PdfConverter(config=config_parser)

async def parse_document(file_stream: BytesIO, filename: str) -> str:
    rendered = await asyncio.to_thread(converter, file_stream)
    return rendered.markdown
```

**Why Marker is bleeding edge:**
- **2-3x faster** than Docling for PDF processing
- **Better table extraction** — uses a dedicated table recognition model
- **Better equation handling** — converts LaTeX equations correctly
- **Surya OCR engine** — state-of-the-art open-source OCR, competitive with commercial solutions
- **Smaller memory footprint** — optimized model loading

**Trade-off:** Docling supports more formats (Word, Excel, PowerPoint). Marker is PDF-only but does PDF significantly better. Use both — Marker for PDFs, Docling as fallback for non-PDF formats.

---

## REPLACE: OpenAI Embeddings → Jina AI Embeddings v3

**What you currently have:** `text-embedding-3-small` via OpenAI API (1536 dimensions, $0.02/1M tokens).

**Add or replace with:** **Jina Embeddings v3** — supports 8192 token context (vs OpenAI's 8191), built-in **Matryoshka representation** (truncate to any dimension without quality loss), and **task-specific LoRA adapters** (retrieval.query, retrieval.passage, separation, classification).

```python
# app/clients/jina_client.py
import httpx

class JinaEmbeddingClient:
    def __init__(self, api_key: str) -> None:
        self.client = httpx.AsyncClient(
            base_url="https://api.jina.ai/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )

    async def embed(
        self,
        texts: list[str],
        task: str = "retrieval.passage",  # or retrieval.query for search
        dimensions: int = 1024,
    ) -> list[list[float]]:
        response = await self.client.post(
            "/embeddings",
            json={
                "model": "jina-embeddings-v3",
                "input": texts,
                "task": task,
                "dimensions": dimensions,  # Matryoshka — use 256 for fast, 1024 for quality
            },
        )
        data = response.json()
        return [item["embedding"] for item in data["data"]]
```

**Why Jina v3 is bleeding edge:**
- **Task-specific adapters** — tell the model whether the text is a query or a passage. Retrieval quality jumps 5-10% because the model optimizes the embedding space for each role.
- **Matryoshka dimensions** — store 256-dim vectors for fast filtering (4x less storage, 4x faster search), then re-rank with 1024-dim. One model, two tiers.
- **Late chunking** — Jina's API can accept a long document and embed overlapping chunks in a single call, preserving cross-chunk context. No external chunking needed.
- **Multilingual** — 89 languages out of the box.

**Also consider:** **Cohere Embed v4** (multimodal — embeds text AND images in the same vector space, so diagrams are searchable) or **Voyage AI 3.5** (best-in-class code embedding, if your corpus includes source code).

---

## REPLACE: NATS → NATS JetStream (Already Have NATS, Just Enable Persistence)

**What you currently have:** NATS core pub/sub — fire-and-forget messaging in `nats_client.py`. If a subscriber isn't connected when a message is published, the message is lost.

**Upgrade to:** **NATS JetStream** — adds persistence, replay, exactly-once delivery, and consumer groups. Zero new infrastructure — JetStream is built into the NATS binary you're already running.

```yaml
# docker-compose.yml — just add the -js flag
nats:
  image: nats:latest
  command: ["-js", "-m", "8222"]  # enable JetStream + monitoring
  ports:
    - "4222:4222"
    - "8222:8222"  # monitoring dashboard
```

```python
# app/clients/nats_client.py — upgrade to JetStream
async def initialize(self) -> None:
    self._nc = await nats.connect(config.NATS_URL)
    self._js = self._nc.jetstream()

    # Create a stream for job events — persisted to disk
    await self._js.add_stream(
        name="JOBS",
        subjects=["jobs.>"],
        retention="limits",
        max_age=86400 * 7,  # 7 day retention
        storage="file",
    )

async def publish(self, subject: str, data: bytes) -> None:
    # Guaranteed delivery — JetStream acks after persistence
    await self._js.publish(subject, data)

async def subscribe(self, subject: str) -> nats.js.JetStreamContext.PushSubscription:
    # Durable consumer — resumes from where it left off after disconnect
    return await self._js.subscribe(
        subject,
        durable="job-watcher",
        deliver_policy="last_per_subject",
    )
```

**What you gain:**
- **Message replay** — new WebSocket connections can replay all events for a job, not just future ones. Fixes the subscribe-then-snapshot race condition entirely.
- **Guaranteed delivery** — if a subscriber disconnects and reconnects, it gets all missed messages. No lost updates.
- **Consumer groups** — scale WebSocket handlers horizontally. NATS distributes messages across consumers.
- **Key-value store** — JetStream includes a built-in KV store. Could replace ScyllaDB for simple job status lookups:
  ```python
  kv = await js.key_value("job_status")
  await kv.put(f"jobs.{job_id}", status_json)
  entry = await kv.get(f"jobs.{job_id}")
  ```
- **Object store** — JetStream can store large objects (files). Could supplement MinIO for small files.

---

## ADD: Valkey (Redis Fork by Linux Foundation)

**What you currently don't have:** No caching layer. Every request hits ScyllaDB and Qdrant directly.

**Add:** **Valkey** — the Linux Foundation's community fork of Redis, created after Redis relicensed. Fully Redis-compatible. AWS, Google, Oracle, Ericsson, and Snap all back it.

```yaml
# docker-compose.yml
valkey:
  image: valkey/valkey:latest
  ports:
    - "6379:6379"
  command: ["valkey-server", "--save", "60", "1000", "--maxmemory", "512mb", "--maxmemory-policy", "allkeys-lru"]
```

```python
# app/clients/valkey_client.py
import valkey.asyncio as valkey

class ValkeyManager:
    _instance: "ValkeyManager | None" = None
    _client: valkey.Valkey | None = None

    async def initialize(self) -> None:
        self._client = valkey.Valkey(
            host=config.VALKEY_HOST,
            port=config.VALKEY_PORT,
            decode_responses=True,
        )

    async def get(self, key: str) -> str | None:
        return await self._client.get(key)

    async def set(self, key: str, value: str, ttl: int = 3600) -> None:
        await self._client.set(key, value, ex=ttl)

    async def cache_embedding(self, content_hash: str, embedding: list[float]) -> None:
        """Cache embedding by content hash — avoid re-embedding identical chunks."""
        import json
        await self._client.set(
            f"emb:{content_hash}",
            json.dumps(embedding),
            ex=86400 * 7,  # 7 day TTL
        )
```

**Use cases in your project:**
- **Embedding cache** — hash chunk text → cache embedding. If the same text appears in multiple documents (boilerplate, headers, legal disclaimers), skip the OpenAI API call entirely. 10-40% of chunks are often duplicates.
- **Job status cache** — `GET /jobs/{job_id}` reads from Valkey first (1ms) before hitting ScyllaDB (5-10ms).
- **Rate limiting** — sliding window counters per API key/source.
- **Idempotency keys** — prevent duplicate ingestion (idea #80).

**Why Valkey over Redis:** Identical API, fully open source (BSD license), backed by Linux Foundation. No licensing risk. AWS ElastiCache already runs Valkey.

---

## REPLACE: ScyllaDB Driver → ScyllaDB Rust Driver via PyO3

**What you currently have:** `scylla-driver>=3.27.2` (Python Cassandra driver with async wrapper). Your `ScyllaService._await_future()` manually bridges Cassandra's `ResponseFuture` to asyncio — this works but adds overhead per query.

**Bleeding edge alternative:** **scylla-rust-driver** exposed to Python via PyO3. The Rust driver is ScyllaDB's official next-gen driver — shard-aware routing, prepared statement caching, and token-aware load balancing are all built in.

The community project `scyllaft` wraps the Rust driver for Python:

```toml
# pyproject.toml
dependencies = [
    "scyllaft>=0.3.0",  # Rust-based ScyllaDB driver via PyO3
]
```

```python
# app/clients/scylla_client.py — native async, no ResponseFuture bridging
from scyllaft import Scylla, InlineBatch

class ScyllaManager:
    async def initialize(self) -> None:
        self._client = Scylla(
            contact_points=[config.SCYLLA_HOSTS],
            keyspace=config.SCYLLA_KEYSPACE,
        )
        await self._client.startup()

    async def execute(self, query: str, params: list | None = None) -> list[dict]:
        result = await self._client.execute(query, params or [])
        return result.all_rows()  # native async — no Future bridging needed
```

**Why this is better:**
- **Shard-aware routing** — requests go directly to the CPU core that owns the partition. The Python driver routes to nodes, but the Rust driver routes to specific shards within nodes. This is ScyllaDB's killer feature and the Python driver doesn't support it.
- **Native async** — no `asyncio.Future` bridging, no thread pool overhead
- **Connection pooling per shard** — optimal throughput on multi-core ScyllaDB nodes
- **2-5x lower latency** at P99

---

## ADD: Turbopuffer (Serverless Vector Database)

**What you currently have:** Self-hosted Qdrant (great for control, needs ops).

**Add as a secondary option:** **Turbopuffer** — a serverless vector database built on object storage. Created by ex-Cloudflare engineers. The key insight: store vectors on S3/R2 and use aggressive caching + custom indexing to make it fast.

**Why it's interesting:**
- **10x cheaper** than hosted Qdrant/Pinecone at scale — object storage costs pennies per GB vs SSD-backed databases
- **Infinite scale** — storage is S3, so you never run out of disk. Index 10 billion vectors without provisioning anything.
- **Namespace isolation** — each project gets its own namespace. Multi-tenancy without collection-per-tenant overhead.
- **Attribute filtering** — fast metadata filtering built into the index (not post-filter). Filter by project_id + source while doing vector search, without scanning irrelevant vectors.

```python
# app/clients/turbopuffer_client.py
import turbopuffer as tpuf

ns = tpuf.Namespace("nexus_knowledge_base")

# Upsert with metadata
ns.upsert(
    ids=[...],
    vectors=[...],
    attributes={
        "project_id": [...],
        "source": [...],
        "text": [...],
    },
)

# Search with metadata filter
results = ns.query(
    vector=query_embedding,
    top_k=10,
    filters={"project_id": ["Eq", "my-project"]},
    include_attributes=["text", "source"],
)
```

**Use case:** Keep Qdrant for self-hosted/dev and offer Turbopuffer as the production backend. The interface is similar enough to abstract behind a common protocol.

---

## REPLACE: boto3 for MinIO → Native MinIO SDK (or rclone for Transfers)

**What you currently have:** `boto3>=1.42.49` for S3 operations. boto3 is AWS's SDK — it works with MinIO but it's massive (70MB+), pulls in botocore, has complex auth, and wasn't designed for MinIO.

**Replace with:** The **native MinIO Python SDK** — purpose-built, much lighter, supports MinIO-specific features.

```toml
# pyproject.toml — you already have minio, just drop boto3
dependencies = [
    "minio>=7.2.20",  # you already have this!
    # "boto3>=1.42.49",  # remove — 70MB+ savings
]
```

```python
# app/clients/minio_client.py — you may already be using this for some ops
from minio import Minio

client = Minio(
    config.MINIO_HOST.replace("http://", ""),
    access_key=config.MINIO_ACCESS_KEY,
    secret_key=config.MINIO_SECRET_KEY,
    secure=False,
)

# Streaming upload — no memory buffering
client.put_object(
    "ingestion-bucket",
    object_name,
    data=file.file,  # stream directly from upload
    length=-1,
    part_size=10 * 1024 * 1024,
)
```

**What you gain:**
- Drop boto3 + botocore + s3transfer (~70MB of deps)
- MinIO-specific features: server-side encryption, bucket notifications, object locking
- Simpler API (no `resource` vs `client` confusion)

**Bleeding edge addition:** For bulk transfers (migrating data between MinIO and S3/R2/GCS), use **rclone** — a single Go binary that supports 50+ cloud storage backends with parallel transfers, bandwidth limiting, and checksumming.

---

## ADD: Granian (Replace Uvicorn)

**What you currently have:** Uvicorn as your ASGI server (via `fastapi[standard]`).

**Replace with:** **Granian** — a Rust-based ASGI/WSGI server. 2-3x higher throughput than Uvicorn for FastAPI apps, with lower memory usage.

```toml
# pyproject.toml
dependencies = [
    "granian>=2.2.0",
]
```

```python
# main.py
if __name__ == "__main__":
    from granian import Granian
    from granian.constants import Interfaces

    server = Granian(
        "main:app",
        address=config.HOST,
        port=config.PORT,
        interface=Interfaces.ASGI,
        workers=4,
        threading_mode="runtime",  # Rust tokio runtime per worker
    )
    server.serve()
```

**Why Granian is bleeding edge:**
- **Rust HTTP parser** — the HTTP layer runs in Rust, only calling into Python for your application code. Parsing, routing, and connection management are all native speed.
- **Tokio runtime** — each worker gets a Rust async runtime. Fewer Python threads, less GIL contention.
- **RSGIs** — Granian's own protocol (Rust Server Gateway Interface), even faster than ASGI for Rust-aware frameworks.
- **2-3x throughput** on benchmarks vs Uvicorn for typical FastAPI workloads.
- **Used by:** Pydantic (their docs site), various AI startups for inference APIs.

---

## ADD: Redpanda (Replace or Supplement NATS for Heavy Streaming)

**What you currently have:** NATS for pub/sub.

**Add for streaming workloads:** **Redpanda** — a Kafka-compatible streaming platform written in C++. No JVM, no ZooKeeper, single binary, 10x lower tail latency than Kafka.

```yaml
# docker-compose.yml
redpanda:
  image: redpandadata/redpanda:latest
  command:
    - redpanda start
    - --smp 1
    - --memory 1G
    - --mode dev-container
    - --kafka-addr 0.0.0.0:9092
    - --schema-registry-addr 0.0.0.0:8081
  ports:
    - "9092:9092"   # Kafka API
    - "8081:8081"   # Schema Registry
    - "9644:9644"   # Admin API
```

**Why Redpanda over Kafka:**
- **No JVM** — single C++ binary, starts in 2 seconds, uses 10x less memory
- **Kafka API compatible** — use `aiokafka` or `confluent-kafka-python`, no new client library
- **Built-in Schema Registry** — Avro/Protobuf/JSON schema management included
- **Tiered storage** — automatically offload old data to S3/MinIO. Keep hot data on SSD, cold data on object storage.
- **Data transforms** — run Wasm functions inside the broker to transform data in-flight (filter, enrich, route). No external stream processor needed.
- **Used by:** Cisco, HP Enterprise, Palo Alto Networks, and hundreds of companies replacing Kafka.

**When to use Redpanda vs NATS:**
- NATS JetStream: lightweight pub/sub, job events, WebSocket relay (your current use case)
- Redpanda: high-throughput ordered event streams, CDC ingestion, audit logs, cross-service event sourcing

---

## ADD: DuckDB (In-Process Analytics)

**No separate server needed.** DuckDB is an in-process OLAP database (like SQLite but for analytics). Runs inside your Python process.

```toml
# pyproject.toml
dependencies = [
    "duckdb>=1.2.0",
]
```

```python
# Query your ScyllaDB data analytically — without a separate analytics DB
import duckdb

async def get_ingestion_analytics(scylla_service: ScyllaService) -> dict:
    # Pull data from ScyllaDB
    jobs = await scylla_service.execute("SELECT * FROM ingestion_jobs")

    # Analyze with SQL — joins, window functions, aggregations
    conn = duckdb.connect()
    conn.register("jobs", jobs)

    result = conn.sql("""
        SELECT
            source,
            project_id,
            status,
            COUNT(*) as job_count,
            AVG(files_completed) as avg_files_completed,
            SUM(files_failed) as total_failures,
            DATE_TRUNC('hour', created_at) as hour
        FROM jobs
        GROUP BY source, project_id, status, hour
        ORDER BY hour DESC
    """).fetchall()

    return result
```

**Why DuckDB is cool:**
- **Zero infrastructure** — no server, no container, no port. It's a Python import.
- **Reads Parquet from MinIO directly** — `SELECT * FROM read_parquet('s3://ingestion-bucket/*.parquet')` with MinIO credentials.
- **Vectorized execution** — columnar engine processes millions of rows in milliseconds.
- **Used by:** MotherDuck (serverless DuckDB), Google (BigQuery migration tool), dbt Labs, and practically every data team.

---

## ADD: Hatchet (Next-Gen Task Queue / Workflow Engine)

**What you currently have:** Temporal for workflow orchestration.

**Add or evaluate:** **Hatchet** — a newer workflow engine built specifically for AI workloads. Written in Go, with a Python SDK that feels more Pythonic than Temporal's.

```python
from hatchet_sdk import Hatchet, Context

hatchet = Hatchet()

@hatchet.workflow(on_events=["ingestion:start"])
class IngestionWorkflow:

    @hatchet.step(timeout="10m", retries=5)
    async def parse(self, context: Context) -> dict:
        job_id = context.workflow_input()["job_id"]
        # ... parse logic
        return {"documents": docs}

    @hatchet.step(parents=["parse"], timeout="10m")
    async def embed(self, context: Context) -> dict:
        docs = context.step_output("parse")["documents"]
        # ... embed logic
        return {"count": len(docs)}

    @hatchet.step(parents=["embed"], timeout="30s")
    async def finalize(self, context: Context) -> None:
        # ... finalize logic
        pass
```

**Why Hatchet is interesting:**
- **DAG-based** — steps declare parent dependencies, engine resolves execution order. More flexible than Temporal's sequential activity model for AI pipelines.
- **Built-in rate limiting** — limit per-tenant or per-model API calls at the engine level. No application-level semaphores.
- **Concurrency control** — max N concurrent workflows per key (per-project, per-user). Replace your `asyncio.Semaphore(4)`.
- **Event-driven** — workflows trigger on events, not just RPC calls. Publish an event, all matching workflows run.
- **Sticky workers** — route workflows to workers with specific capabilities (GPU, high-memory). No Temporal task queue configuration needed.
- **Newer, lighter** — single Go binary + Postgres. No Cassandra/Elasticsearch like Temporal requires.

**Trade-off:** Temporal is battle-tested at Uber/Netflix/Stripe scale. Hatchet is newer but architecturally better suited for AI pipelines specifically.

---

## ADD: Quickwit (Log-Optimized Search Engine)

**What you currently have:** No full-text search or log aggregation.

**Add:** **Quickwit** — a cloud-native search engine built on Tantivy (Rust). Stores indexes on object storage (MinIO!). 10x cheaper than Elasticsearch.

```yaml
# docker-compose.yml
quickwit:
  image: quickwit/quickwit:latest
  command: ["run"]
  ports:
    - "7280:7280"
  environment:
    QW_S3_ENDPOINT: http://minio:9000
    AWS_ACCESS_KEY_ID: ${MINIO_ACCESS_KEY}
    AWS_SECRET_ACCESS_KEY: ${MINIO_SECRET_KEY}
  volumes:
    - ./quickwit-config:/quickwit/config
```

**Use cases:**
- **Full-text search over ingested documents** — Qdrant handles semantic search, Quickwit handles keyword/exact match. Combine results for hybrid retrieval.
- **Ingestion pipeline logs** — aggregate logs from FastAPI, Temporal workers, and activities. Query with sub-second latency.
- **Audit trail** — index every ingestion event (who uploaded what, when, what happened). Quickwit's object-storage backend means retention is essentially free.

**Why it's bleeding edge:**
- **Tantivy** (Rust search engine) — 5-10x faster indexing than Elasticsearch's Lucene
- **Object storage native** — indexes live on MinIO/S3. No SSD provisioning, no disk management.
- **Kafka/Redpanda native** — ingest directly from Kafka topics with exactly-once semantics.
- **OpenTelemetry native** — accepts OTLP traces and logs directly, no Logstash/Fluentd.
- **Used by:** various observability and log analytics companies replacing Elasticsearch.

---

## ADD: Litestar (Alternative to FastAPI)

**What you currently have:** FastAPI — excellent, widely used, but some rough edges (dependency injection is limited, no built-in DTO layer, OpenAPI generation can be slow).

**Consider for new services:** **Litestar** — a FastAPI alternative by ex-Starlite team. Same ASGI foundation, but more opinionated and feature-rich.

**Why it's interesting:**
- **Msgspec** instead of Pydantic for serialization — 5-10x faster JSON encoding/decoding (uses C extensions). Optional — Pydantic also works.
- **Built-in DTO layer** — control what fields are exposed per-endpoint without separate request/response models.
- **Dependency injection** — proper DI container (like .NET or Spring), not just FastAPI's `Depends()` chain.
- **Channels** — built-in WebSocket channel layer (like Django Channels). Your NATS→WebSocket relay could be simplified.
- **Rate limiting** — built-in middleware, no external library needed.
- **OpenAPI generation** — faster and more correct than FastAPI's.

**Trade-off:** FastAPI has a much larger ecosystem and community. Litestar is better-engineered but smaller. Perfect for new companion services where you're starting fresh.

---

## ADD: Modal (Serverless GPU Compute)

**What you currently have:** GPU compute tied to your Docker host or a provisioned GPU server.

**Add for burst GPU workloads:** **Modal** — serverless GPU functions. Write Python, Modal runs it on GPUs that spin up in seconds and bill per-second.

```python
import modal

app = modal.App("nexus-parser")

@app.function(
    gpu="A100",
    image=modal.Image.debian_slim().pip_install("marker-pdf", "torch"),
    timeout=600,
)
async def parse_pdf_gpu(file_bytes: bytes) -> str:
    from marker.converters.pdf import PdfConverter
    from marker.config.parser import ConfigParser
    from io import BytesIO

    config = ConfigParser({"output_format": "markdown"})
    converter = PdfConverter(config=config)
    rendered = converter(BytesIO(file_bytes))
    return rendered.markdown
```

**Why Modal is bleeding edge:**
- **Cold start in 1-3 seconds** — vs 5+ minutes to provision a GPU VM.
- **Per-second billing** — parse a PDF, release the GPU. No idle GPU costs.
- **Container snapshots** — Modal snapshots your container after model loading. Next invocation starts from the snapshot (models already in memory). Feels instant.
- **Distributed dict** — share data between functions without external storage.
- **Volume mounts** — persistent storage for model weights. Download once, use forever.
- **Used by:** Ramp, Suno (AI music), Hex, many AI startups. Anthropic and OpenAI use similar internal infrastructure.

**When to use:** Burst GPU workloads — large batch ingestions, OCR, fine-tuning. Keep your always-on Temporal worker for lightweight tasks and dispatch GPU-heavy work to Modal.

---

## ADD: Buf + ConnectRPC (Modern gRPC Alternative)

**What you currently have:** REST APIs (FastAPI).

**Add for service-to-service communication:** **ConnectRPC** — a simpler alternative to gRPC by the Buf team. Supports gRPC, gRPC-Web, and a simple HTTP/JSON protocol from a single Protobuf definition. Works in browsers without a proxy.

```protobuf
// proto/ingestion/v1/ingestion.proto
syntax = "proto3";

service IngestionService {
  rpc IngestFiles(IngestRequest) returns (IngestResponse);
  rpc GetJobStatus(GetJobRequest) returns (JobStatus);
  rpc WatchJob(WatchJobRequest) returns (stream JobUpdate);  // server streaming
}
```

**Why ConnectRPC is bleeding edge:**
- **Triple protocol** — one server handles gRPC (binary, fast), gRPC-Web (browser-compatible), and Connect (simple HTTP/JSON with `curl`). You get REST-like debuggability AND gRPC performance.
- **Buf CLI** — linting, breaking change detection, code generation. `buf generate` produces type-safe clients for Python, TypeScript, Go, Rust.
- **Schema-first** — Protobuf is the contract between services. Add a field? `buf breaking` tells you if it's backwards-compatible.
- **Server streaming** — `WatchJob` replaces your WebSocket for job updates. gRPC streaming is bidirectional and has built-in flow control.
- **Used by:** Buf itself, but the gRPC ecosystem broadly is used by Google, Netflix, Uber, Cloudflare (inter-service).

---

## ADD: Polar Signals Parca (Continuous Profiling)

**What you currently have:** No profiling infrastructure.

**Add:** **Parca** — open-source continuous profiling. It tells you WHERE your CPU time and memory are going, in production, always-on, with <1% overhead.

```yaml
# docker-compose.yml
parca:
  image: ghcr.io/parca-dev/parca:latest
  ports:
    - "7070:7070"
  volumes:
    - ./parca.yaml:/etc/parca/parca.yaml
```

**Why this matters for your project:**
- See exactly which line of Docling/Marker code is burning CPU during parsing
- Find memory leaks in your long-running Temporal worker (PyTorch models not being freed)
- Compare flame graphs before and after optimization — proof that your change actually helped
- **eBPF-based** — no code instrumentation needed. Parca Agent attaches to your process via eBPF and samples the stack. Works with Python, Rust, Go, C++.
- **Used by:** Polar Signals (founded by Prometheus co-founders), Frederic Branczyk (ex-Red Hat, Prometheus maintainer). Same approach Google uses internally (Google-Wide Profiling).

---

## Summary: Recommended Stack Upgrades

Priority order for maximum impact with minimum effort:

| Priority | Change | Impact | Effort |
|----------|--------|--------|--------|
| 1 | Drop LlamaIndex, batch embed directly | 50x fewer API calls, remove ~200 deps | Medium |
| 2 | Enable NATS JetStream | Guaranteed delivery, message replay | Low (flag flip) |
| 3 | Add Valkey for caching | Skip re-embedding duplicates, faster reads | Low |
| 4 | Switch to Granian | 2-3x HTTP throughput | Low (swap import) |
| 5 | Enable Qdrant gRPC | 2-5x faster vector ops | Low (env var) |
| 6 | Add DuckDB for analytics | SQL analytics with zero infra | Low |
| 7 | Swap Docling → Marker for PDFs | 2-3x faster PDF parsing | Medium |
| 8 | Add Jina v3 or Cohere v4 embeddings | Better retrieval quality, Matryoshka dims | Medium |
| 9 | Use Modal for burst GPU | No idle GPU costs, 1s cold start | Medium |
| 10 | Add Quickwit for full-text + logs | Hybrid search, cheap log storage on MinIO | Medium |
| 11 | Use Hatchet for AI workflows | Better concurrency control, rate limiting | High |
| 12 | Add ConnectRPC for inter-service | Type-safe, streaming, browser-compatible | High |
| 13 | Replace ScyllaDB driver with Rust driver | Shard-aware routing, native async | High |
| 14 | Add Parca continuous profiling | Find real bottlenecks, not guessed ones | Low |
