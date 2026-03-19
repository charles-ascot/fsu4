# FSU Application Specification
## FSU4 — Email Intelligence Service
### Chimera Platform · Version 1.0.0

> This document is the canonical specification for FSU4 and serves as the **template for all future Chimera FSUs**. Sections marked `[FSU-TEMPLATE]` define the standard pattern that applies to every FSU. Sections marked `[FSU4-SPECIFIC]` are specific to this unit's domain.

---

## 1. FSU Framework Overview `[FSU-TEMPLATE]`

### 1.1 What is an FSU?

A **Fractional Services Unit (FSU)** is an autonomous, single-purpose microservice within the Chimera Platform. Each FSU:

- Has one clearly defined data acquisition or processing responsibility
- Exposes a standardised REST API
- Stores its output as structured **Intelligence Records** in a Firestore collection
- Archives raw and processed artefacts to GCS
- Is independently deployable to Cloud Run
- Is managed via a React/Cloudflare Pages UI

FSUs collectively form the **Chimera Data Acquisition Layer**, feeding structured intelligence into the Chimera Operations Data Lake.

### 1.2 FSU Naming Convention

| FSU | Domain |
|-----|--------|
| FSU1 | [Reserved] |
| FSU2 | [Reserved] |
| FSU3 | [Reserved] |
| FSU4 | Email Intelligence |
| FSU5 | [Future] |
| FSU6 | Lay Engine Signal Processing |
| FSUn | [Future domain] |

### 1.3 Standard FSU Technology Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12 |
| Framework | FastAPI + Uvicorn |
| AI | Claude (claude-sonnet-4-XXXXXXXX via Anthropic API) |
| Primary store | Google Cloud Firestore (Native mode) |
| Object store | Google Cloud Storage |
| Secrets | GCP Secret Manager |
| Compute | Google Cloud Run (europe-west2) |
| CI/CD | GitHub → Cloud Run Connect Repo |
| Management UI | React + Tailwind → Cloudflare Pages |
| GCP Project | chimera-v4 |

---

## 2. FSU4 — Service Definition `[FSU4-SPECIFIC]`

### 2.1 Purpose

FSU4 ingests emails forwarded to a dedicated Gmail inbox, processes them through Claude AI, and stores structured intelligence records for consumption by the Chimera Operations Data Lake and downstream services.

### 2.2 Data Sources

Emails forwarded to `chimera.data.in@gmail.com` from registered source accounts. Source accounts apply forwarding rules based on subject-line keywords relevant to Chimera operations.

### 2.3 Trigger Mechanism

Gmail push notifications via Google Pub/Sub. On new email arrival:
1. Gmail API sends notification to Pub/Sub topic `fsu4-trigger`
2. Pub/Sub pushes to Cloud Run endpoint `/v1/ingest/pubsub-push`
3. Service retrieves message via Gmail History API
4. Full processing pipeline executes synchronously within Cloud Run request

### 2.4 Output

- **Firestore** — structured Intelligence Record in `fsu4-intelligence`
- **GCS** — raw email artefacts + processed record in `chimera-ops-email-raw`

---

## 3. System Architecture `[FSU-TEMPLATE]`

### 3.1 Component Diagram

```
External Source
      │
      ▼
[Data Ingestion Layer]          ← FSU-specific (email, API, scrape, etc.)
      │
      ▼
[Cloud Run: FSU-n]
      │
      ├──► [AI Processing — Claude]
      │
      ├──► [Firestore: fsu-n-intelligence]    ← Primary intelligence store
      │
      └──► [GCS: chimera-ops-{domain}-raw]    ← Raw + processed artefacts
```

### 3.2 Processing Pipeline `[FSU-TEMPLATE]`

Every FSU follows this standard 9-step pipeline:

| Step | Name | Description |
|------|------|-------------|
| 1 | Idempotency check | Prevent duplicate processing of the same source record |
| 2 | Data fetch | Retrieve raw data from source |
| 3 | Parse | Extract structured fields from raw data |
| 4 | Skip check | Apply ignore rules (senders, keywords, etc.) |
| 5 | Raw storage | Store raw artefacts to GCS |
| 6 | Attachment/media processing | Extract text from PDFs, images, audio, etc. |
| 7 | AI tagging | Claude generates title, summary, topics, intent, urgency, relevancy |
| 8 | Processed storage | Store final record to GCS |
| 9 | Firestore write | Persist intelligence record |

### 3.3 Data Flow

```
Source Event
    │
    ▼
/v1/ingest/[trigger-endpoint]
    │
    ├── Idempotency check (Firestore)
    ├── Fetch raw data
    ├── Parse into domain model
    ├── Apply skip rules
    ├── Store raw to GCS
    ├── Extract attachment text
    ├── AI tagging (Claude API)
    ├── Store processed to GCS
    └── Write to Firestore
```

---

## 4. API Specification `[FSU-TEMPLATE]`

All FSUs implement this standard API surface. Endpoint paths and request/response bodies vary by domain.

### 4.1 Authentication

All protected endpoints require:
```
X-Chimera-API-Key: <secret: chimera-api-key>
```

The key is stored in GCP Secret Manager and never committed to source control.

### 4.2 Response Envelope

All responses use the Chimera standard envelope:

```json
{
  "chimera_version": "1.0",
  "request_id": "string",
  "fsu": "fsu4",
  "status": "success | error",
  "timestamp": "ISO8601",
  "data": {},
  "errors": [],
  "meta": {
    "processing_time_ms": 0,
    "version": "1.0.0"
  }
}
```

### 4.3 Standard Endpoints

#### System (no auth)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness probe → `{"status":"ok"}` |
| GET | `/status` | Connectivity + stats snapshot |
| GET | `/version` | FSU version + build info |

#### Ingest

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/ingest/{trigger}` | None | Primary ingestion endpoint (called by trigger) |
| POST | `/v1/ingest/manual` | Yes | Manual trigger by source record ID |
| POST | `/v1/ingest/reprocess/{id}` | Yes | Re-run AI tagging on existing record |
| GET | `/v1/ingest/queue` | Yes | View pending records |

#### Registry

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/v1/registry` | Yes | Query intelligence records |
| GET | `/v1/registry/{id}` | Yes | Fetch single record |
| GET | `/v1/registry/metrics` | Yes | Processing statistics |
| POST | `/v1/registry/agent/query` | Yes | Natural language query via Claude |

Query parameters: `intent`, `urgency`, `topic`, `sender`, `min_relevancy`, `status`, `limit`, `offset`

#### Config

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/v1/config` | Yes | Get processing config |
| PUT | `/v1/config` | Yes | Update processing config |
| GET | `/v1/config/schema` | Yes | JSON schema for config |

#### Sources

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/v1/sources` | Yes | List registered data sources |
| POST | `/v1/sources` | Yes | Register a source |
| DELETE | `/v1/sources/{id}` | Yes | Remove a source |

---

## 5. Intelligence Record Schema `[FSU-TEMPLATE]`

The Intelligence Record is the standard output unit of every FSU.

### 5.1 Core Fields (all FSUs)

| Field | Type | Description |
|-------|------|-------------|
| `record_id` | string (UUID) | Primary key |
| `source_id` | string | Source-specific ID (message_id, thread_id, etc.) |
| `source_type` | string | FSU domain (email, api, scrape, etc.) |
| `received_at` | timestamp | When source data was received |
| `title` | string | AI-generated title |
| `summary` | string | AI-generated summary (2–5 sentences) |
| `topics` | array[string] | Extracted topic tags |
| `intent` | enum | `informational` · `actionable` · `alert` · `report` · `noise` |
| `urgency` | enum | `low` · `medium` · `high` · `critical` |
| `relevancy_score` | float (0.0–1.0) | Domain relevance score |
| `chimera_domain_tags` | array[string] | Chimera-specific classification tags |
| `gcs_raw_prefix` | string | GCS path to raw artefacts |
| `gcs_processed_prefix` | string | GCS path to processed record |
| `status` | enum | `processing` · `processed` · `skipped` · `error` |
| `processing_error` | string | Error detail if status=error |
| `created_at` | timestamp | Record creation time |
| `updated_at` | timestamp | Last update time |

### 5.2 FSU4-Specific Fields `[FSU4-SPECIFIC]`

| Field | Type | Description |
|-------|------|-------------|
| `message_id` | string | Gmail message ID |
| `thread_id` | string | Gmail thread ID |
| `from_address` | string | Sender email |
| `from_name` | string | Sender display name |
| `subject` | string | Email subject |
| `forwarded_from` | string | Original sender if forwarded |
| `gmail_labels` | array[string] | Gmail label IDs |
| `attachments` | array | Attachment metadata + extraction results |

### 5.3 Chimera Domain Tags `[FSU4-SPECIFIC]`

| Tag | Description |
|-----|-------------|
| `signal-intelligence` | Trading signals and alerts |
| `spread-control` | Spread management information |
| `racing-data` | Horse racing data and form |
| `betfair-signal` | Betfair-specific market signals |
| `strategy-update` | Strategy and system updates |
| `operational` | Operational and administrative |
| `market-data` | Market prices and data feeds |
| `risk-management` | Risk and exposure information |
| `reporting` | Reports and summaries |
| `alert` | Time-sensitive alerts |

---

## 6. Configuration Schema `[FSU-TEMPLATE]`

Processing behaviour is controlled at runtime via the `/v1/config` endpoint, persisted in Firestore.

### 6.1 Standard Config Fields (all FSUs)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_relevancy_threshold` | float | 0.0 | Records below this score are skipped |
| `extra_domain_hints` | array[string] | [] | Additional context passed to Claude |

### 6.2 FSU4-Specific Config Fields `[FSU4-SPECIFIC]`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ignore_senders` | array[string] | [] | Email addresses to skip entirely |
| `ignore_subjects_containing` | array[string] | [] | Subject keywords that trigger skip |
| `max_attachment_size_mb` | int | 50 | Max attachment size to process |
| `enable_ocr` | bool | true | Image OCR via Vision API |
| `enable_transcription` | bool | true | Audio STT via Speech-to-Text API |
| `enable_pdf_extraction` | bool | true | PDF text extraction |
| `enable_docx_extraction` | bool | true | Word document extraction |
| `gmail_watch_expiry_buffer_hours` | int | 24 | Hours before watch expiry to renew |

---

## 7. GCS Storage Structure `[FSU-TEMPLATE]`

```
chimera-ops-{domain}-raw/
  raw/{year}/{month}/{day}/{source_id}/
    metadata.json          ← Source record metadata
    body.{ext}             ← Primary content
    attachments/           ← Raw attachment files
  processed/{record_id}/
    record.json            ← Final intelligence record
    extracted_texts/       ← Text extracted from attachments
    transcripts/           ← Audio transcriptions
  index/
    daily_manifest_{YYYY-MM-DD}.json   ← Daily processing log
```

---

## 8. Security `[FSU-TEMPLATE]`

### 8.1 Authentication & Authorisation

- API key authentication via `X-Chimera-API-Key` header
- Key stored in GCP Secret Manager, never in code or environment variables
- Cloud Run service account (`fsu-n-runner`) has minimum required IAM roles only
- Pub/Sub push endpoint is unauthenticated (Google's push SA authenticates at topic level)

### 8.2 IAM Roles — Service Account

| Role | Purpose |
|------|---------|
| `roles/secretmanager.secretAccessor` | Read secrets |
| `roles/datastore.user` | Read/write Firestore |
| `roles/storage.objectAdmin` | Read/write GCS |
| `roles/pubsub.subscriber` | Subscribe to Pub/Sub |
| `roles/logging.logWriter` | Write Cloud Logging |
| `roles/cloudtrace.agent` | Write Cloud Trace |

### 8.3 Secrets Management

All credentials are stored in GCP Secret Manager and accessed at runtime. No secrets in:
- Source code
- Environment variables in Cloud Run config
- Docker images
- GitHub repository

### 8.4 CORS

Management UI domain is explicitly allowlisted in the FastAPI CORS middleware. No wildcard origins.

---

## 9. Deployment `[FSU-TEMPLATE]`

### 9.1 CI/CD Pipeline

```
Developer pushes to main
        │
        ▼
GitHub (charles-ascot/fsu-n)
        │  (webhook)
        ▼
Cloud Run — Connect Repo integration
        │  (builds container, deploys revision)
        ▼
Cloud Run Service — new revision serving 100% traffic
```

### 9.2 Containerisation

- Base image: `python:3.12-slim`
- Dependencies: `requirements.txt`
- Entry point: `uvicorn main:app --host 0.0.0.0 --port 8080`
- No root privileges — runs as default non-root user

### 9.3 Cloud Run Configuration

| Parameter | Value |
|-----------|-------|
| Region | `europe-west2` |
| Min instances | 0 (scale to zero) |
| Max instances | 10 |
| Request timeout | 300s |
| Concurrency | 80 |
| Memory | 512Mi (default) |
| Authentication | Allow unauthenticated (API key auth in app) |

### 9.4 Prerequisites for New FSU Deployment

1. Enable required GCP APIs
2. Create service account `fsu-n-runner` with standard IAM roles
3. Create required secrets in Secret Manager
4. Create Firestore database (if not already exists in project)
5. Create GCS bucket `chimera-ops-{domain}-raw`
6. Create Pub/Sub topic + grant Gmail API publish permission
7. Create GitHub repo, push code
8. Connect repo in Cloud Run → Connect repo
9. After first deploy: create Pub/Sub push subscription with Cloud Run URL

---

## 10. Observability `[FSU-TEMPLATE]`

### 10.1 Health Endpoints

| Endpoint | Expected Response |
|----------|------------------|
| `/health` | `{"status":"ok"}` — always 200 if service is running |
| `/status` | Firestore=ok + registry stats |

### 10.2 Logging

Structured logging via Python `logging` module. All logs captured by Cloud Logging.

Key log events:
- Service startup + Gmail watch established
- Each processed record: `Processed message {id} → record {id} (status={s}, relevancy={r})`
- Skip events with reason
- AI tagging failures (non-fatal — falls back to default tags)
- Pub/Sub decode errors

### 10.3 Metrics

Available via `/v1/registry/metrics`:
```json
{
  "total_records": 0,
  "by_status": {},
  "by_intent": {},
  "by_urgency": {}
}
```

---

## 11. Management UI `[FSU-TEMPLATE]`

Each FSU ships with a React management interface deployed to Cloudflare Pages.

### 11.1 Standard Pages

| Page | Path | Description |
|------|------|-------------|
| Dashboard | `/` | Service health, record counts, recent activity |
| Registry | `/registry` | Browse and search intelligence records |
| Record Detail | `/registry/{id}` | Full record view |
| Sources | `/sources` | Manage registered data sources |
| Config | `/config` | Edit processing configuration |
| Manual Ingest | `/ingest` | Trigger manual processing |
| Agent | `/agent` | Natural language query interface |

### 11.2 Authentication

Google OAuth (restricted to `ascotwm.com` organisation accounts).

### 11.3 Environment Variables (Cloudflare Pages)

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE` | Cloud Run service URL |
| `VITE_API_KEY` | Chimera API key |
| `VITE_GOOGLE_CLIENT_ID` | OAuth client ID (`.apps.googleusercontent.com`) |

---

## 12. Future FSU Generation Guide `[FSU-TEMPLATE]`

To generate a new FSU from this template:

### 12.1 What changes per FSU

| Item | Change |
|------|--------|
| FSU number/name | `fsu4` → `fsu-n` |
| Domain | Email → [new domain] |
| Ingest trigger | Gmail/Pub/Sub → [API poll / webhook / scrape / etc.] |
| Source-specific fields | Gmail fields → domain fields |
| Domain hints | Racing/betting tags → [domain tags] |
| GCS bucket | `chimera-ops-email-raw` → `chimera-ops-{domain}-raw` |
| Secrets | Gmail OAuth → [domain credentials] |
| Config fields | Gmail-specific → [domain-specific] |

### 12.2 What stays the same

- FastAPI structure and router layout
- Standard 9-step processing pipeline
- Intelligence Record core fields
- API response envelope
- `/health`, `/status`, `/version` endpoints
- Registry, Config, Sources endpoints
- AI tagging via Claude (same prompt structure, different domain hints)
- GCS folder structure
- IAM roles and service account pattern
- CI/CD pattern (GitHub → Cloud Run Connect Repo)
- Management UI structure and pages
- Cloudflare Pages deployment
- GCP project (`chimera-v4`)

### 12.3 AI Generation Prompt Template

When generating a new FSU via AI:

```
Create a new Chimera FSU following the FSU4 template at docs/fsu-app-specification.md.

FSU details:
- FSU number: [n]
- Domain: [domain name]
- Purpose: [one sentence]
- Data source: [where data comes from]
- Trigger mechanism: [how ingestion is triggered]
- Source-specific fields: [list of domain-specific record fields]
- Domain hints for Claude: [list of domain-specific tags]
- GCS bucket: chimera-ops-[domain]-raw
- Additional secrets: [any domain-specific credentials]

Follow all FSU-TEMPLATE sections exactly. Replace all FSU4-SPECIFIC sections
with the domain-specific equivalents above.
```

---

## Appendix A — Compliance Notes

- All data stored in `europe-west2` (London) — EU data residency
- Secrets never in code, logs, or environment variables
- Service accounts follow principle of least privilege
- No persistent credentials in container images
- Pub/Sub push endpoint does not require bearer tokens (Google authenticates at topic level via IAM)
- Cloud Run scales to zero when idle — no persistent compute cost

## Appendix B — Known Limitations (v1.0.0)

- Gmail OAuth token stored as a static secret — will expire if refresh token is revoked. Mitigate by ensuring `chimera.data.in@gmail.com` is not removed from the OAuth app's test users list
- Gmail watch must be renewed every 7 days — handled by startup renewal on each Cloud Run instance restart; Cloud Scheduler job (`gmail-watch-renewal`) provides additional renewal via `/health` ping
- Firestore `query_records` performs client-side filtering for array fields (topics, domain_tags) due to Firestore composite index limitations — acceptable at current scale
