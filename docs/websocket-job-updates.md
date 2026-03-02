# WebSocket Job Updates

## Overview

The `/ws/jobs/{job_id}` WebSocket endpoint streams real-time ingestion job progress to clients. It combines a point-in-time snapshot from ScyllaDB with live updates from NATS pub/sub.

## Protocol

### Connection flow

1. Client connects to `ws://<host>/ws/jobs/{job_id}`
2. Server accepts and looks up the job in ScyllaDB
3. If the job doesn't exist, sends an error and closes with code `1008`
4. Server subscribes to NATS subject `jobs.{job_id}`
5. Server queries ScyllaDB for current file states
6. Server sends a `files_snapshot` message (all files in one payload)
7. Server sends a `job_update` message (current job status and counters)
8. If the job is already terminal (`completed` / `failed`), closes with code `1000`
9. Otherwise, relays live NATS messages until the job reaches a terminal status

### Message types

**`files_snapshot`** — sent once on connect, contains all file states:

```json
{
  "type": "files_snapshot",
  "job_id": "abc-123",
  "files": [
    { "file_id": "uuid-1", "filename": "report.pdf", "status": "completed" },
    { "file_id": "uuid-2", "filename": "notes.docx", "status": "in_progress" }
  ]
}
```

**`job_update`** — current job-level status and file counters:

```json
{
  "type": "job_update",
  "job_id": "abc-123",
  "status": "in_progress",
  "total_files": 5,
  "files_completed": 2,
  "files_failed": 0
}
```

**`file_update`** — live per-file status change (from NATS):

```json
{
  "type": "file_update",
  "job_id": "abc-123",
  "file_id": "uuid-2",
  "filename": "notes.docx",
  "status": "completed"
}
```

### Close codes

| Code | Reason | When |
|------|--------|------|
| `1000` | Job completed | Job reached `completed` or `failed` |
| `1008` | Job not found | `job_id` doesn't exist in ScyllaDB |

## The race condition (previous implementation)

The original implementation queried the DB for file states, sent them to the client, and **then** subscribed to NATS for live updates:

```
1. get_job()          — verify job exists
2. get_job_files()    — read file states from DB
3. send files         — send each file as an individual message
4. nats.subscribe()   — start listening for live updates
5. relay messages     — forward NATS messages to client
```

The problem is the gap between steps 2 and 4. Temporal activities publish file status changes to NATS as they happen. If a file transitions (e.g. `in_progress` -> `completed`) after the DB read in step 2 but before the NATS subscribe in step 4, that update is lost:

```
  Time
   |
   |  [step 2] DB query returns file X as "in_progress"
   |
   |  ~~~ gap ~~~
   |
   |  [activity] file X completes, publishes "completed" to NATS
   |             -> nobody is subscribed yet, message is dropped
   |
   |  ~~~ gap ~~~
   |
   |  [step 4] subscribe to NATS
   |            -> only future messages are received
   |
   v
```

The client sees file X stuck at `in_progress` forever. No further NATS message will be published for that file because it already reached its final state. The only way the client would see the correct status is by reconnecting.

This is more likely to happen under load — when many files are processing concurrently, the window between the DB read and the subscribe widens because sending N individual WebSocket messages (one per file) takes time.

## Subscribe-then-snapshot pattern (current implementation)

The fix reverses the order: subscribe to NATS **first**, then query the DB. The NATS callback pushes messages into an `asyncio.Queue` immediately, buffering them while the DB query and snapshot send are still in progress.

```
1. get_job()            — verify job exists
2. nats.subscribe()     — start buffering updates into asyncio.Queue
3. get_file_summaries() — read current state from DB
4. send snapshot        — client gets point-in-time state (single message)
5. drain queue          — relay any updates that arrived during steps 3-4
```

Now consider the same scenario:

```
  Time
   |
   |  [step 2] subscribe to NATS, messages go into queue
   |
   |  [step 3] DB query returns file X as "in_progress"
   |
   |  [activity] file X completes, publishes "completed" to NATS
   |             -> callback fires, message buffered in queue
   |
   |  [step 4] send snapshot (file X shown as "in_progress")
   |
   |  [step 5] drain queue, send the buffered "completed" update
   |            -> client sees file X transition to "completed"
   |
   v
```

The client may briefly see file X as `in_progress` from the snapshot, then immediately receive the `completed` update from the queue. This is correct behavior — the client converges to the right state.

Duplicates can occur if a file update lands both in the DB snapshot and in the queue (the activity published right before the DB read). This is harmless because status updates are idempotent — the client simply sees the same status twice and the UI doesn't change.

## Key files

| File | Role |
|------|------|
| `app/routes/jobs.py` | WebSocket endpoint, NATS subscription, message relay |
| `app/repositories/ingestion.py` | `get_job_file_summaries()` — lightweight query for WebSocket snapshot |
| `app/temporal/activities.py` | Publishes `file_update` and `job_update` messages to NATS |
| `app/clients/nats_client.py` | Singleton NATS client manager |
