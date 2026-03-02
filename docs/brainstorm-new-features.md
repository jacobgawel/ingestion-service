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
