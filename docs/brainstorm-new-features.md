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
