# FSU4 — Chimera Email Intelligence Service

**Version 1.0.0** · Python 3.12 · FastAPI · Cloud Run · `chimera-v4` · `europe-west2`

Transforms inbound emails at `chimera.data.in@gmail.com` into structured intelligence records via Gmail API → Pub/Sub → Claude AI → Firestore + GCS.

| | |
|---|---|
| **API** | `https://fsu4-950990732577.europe-west2.run.app` |
| **Management UI** | `https://fsu4.thync.online` |
| **GitHub** | `https://github.com/charles-ascot/fsu4` |
| **GCP Project** | `chimera-v4` |

---

## Quick Start

```bash
# Health check
curl https://fsu4-950990732577.europe-west2.run.app/health

# Query registry (authenticated)
curl -H "X-Chimera-API-Key: YOUR_KEY" \
  https://fsu4-950990732577.europe-west2.run.app/v1/registry?limit=10

# Manual ingest
curl -X POST \
  -H "X-Chimera-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message_id":"GMAIL_MESSAGE_ID"}' \
  https://fsu4-950990732577.europe-west2.run.app/v1/ingest/manual
```

---

## Architecture

```
chimera.data.in@gmail.com
        │  (new email)
        ▼
   Gmail API
        │  (push notification)
        ▼
   Pub/Sub topic: fsu4-trigger
        │  (HTTP push)
        ▼
   Cloud Run: fsu4  ──► Claude AI (claude-sonnet-4-20250514)
        │                     │
        ▼                     ▼
   Firestore              GCS Bucket
   fsu4-intelligence   chimera-ops-email-raw
```

**Processing pipeline per email:**
1. Pub/Sub push → decode historyId → Gmail History API → message IDs
2. Fetch full message from Gmail API
3. Parse headers, body text/HTML, attachments
4. Skip checks (ignore_senders, ignore_subjects)
5. Store raw artefacts to GCS
6. Extract text from attachments (PDF, DOCX, images via OCR, audio via STT)
7. AI tagging via Claude — title, summary, topics, intent, urgency, relevancy_score
8. Store processed record to GCS
9. Write intelligence record to Firestore

---

## Resource Reference

| Resource | Name |
|----------|------|
| GCP project | `chimera-v4` |
| Region | `europe-west2` |
| Cloud Run service | `fsu4` |
| Service account | `fsu4-runner@chimera-v4.iam.gserviceaccount.com` |
| GCS bucket | `chimera-ops-email-raw` |
| Firestore collection | `fsu4-intelligence` |
| Firestore sources collection | `fsu4-sources` |
| Firestore config doc | `chimera-fsu-config/fsu4-config` |
| Firestore system doc | `chimera-fsu-system/gmail-watch` |
| Pub/Sub topic | `fsu4-trigger` |
| Pub/Sub subscription | `fsu4-sub` |
| Gmail address | `chimera.data.in@gmail.com` |
| Claude model | `claude-sonnet-4-20250514` |

---

## Secrets (GCP Secret Manager — `chimera-v4`)

| Secret ID | Description |
|-----------|-------------|
| `anthropic-api-key` | Anthropic API key (`sk-ant-...`) |
| `chimera-api-key` | API key sent as `X-Chimera-API-Key` header by all clients |
| `gmail-oauth-credentials` | `{"client_id":"...","client_secret":"...","token_uri":"https://oauth2.googleapis.com/token"}` |
| `gmail-token` | `{"token":"...","refresh_token":"...","token_uri":"https://oauth2.googleapis.com/token"}` |

### Regenerating Gmail OAuth token

1. GCP Console → `chimera-v4` → APIs & Services → Credentials → OAuth client **FSU4 - Chimera Email Ingest**
2. Copy `client_id` and `client_secret`
3. Open [OAuth 2.0 Playground](https://developers.google.com/oauthplayground)
   - Gear icon → **Use your own OAuth credentials** → enter `client_id` and `client_secret`
   - Scope: `https://www.googleapis.com/auth/gmail.modify`
   - Authorise → sign in as `chimera.data.in@gmail.com`
   - Exchange authorisation code for tokens
4. Update secrets `gmail-oauth-credentials` and `gmail-token` in Secret Manager

---

## CI/CD

Push to `main` → Cloud Run auto-deploys via the **Connect repo** integration.

GCP Console → Cloud Run → `fsu4` → **Edit & Deploy** → Source tab shows connected repo.

No `cloudbuild.yaml` or manual deploy steps required.

---

## API Reference

### Authentication

All protected endpoints require:
```
X-Chimera-API-Key: <chimera-api-key secret value>
```

### Base URL
```
https://fsu4-950990732577.europe-west2.run.app
```

### Endpoints

#### System — no auth required

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness probe → `{"status":"ok"}` |
| GET | `/status` | Firestore connectivity + registry stats |
| GET | `/version` | Version and build info |

#### Ingest

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/v1/ingest/pubsub-push` | None | Pub/Sub push receiver — called by GCP only |
| POST | `/v1/ingest/manual` | Yes | Process a specific Gmail message ID |
| POST | `/v1/ingest/reprocess/{id}` | Yes | Re-run AI tagging on existing record |
| GET | `/v1/ingest/queue` | Yes | View records in pending status |

#### Registry

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/v1/registry` | Yes | Query records — filterable by intent, urgency, sender, topic, relevancy |
| GET | `/v1/registry/{record_id}` | Yes | Fetch a single record |
| GET | `/v1/registry/metrics` | Yes | Processing statistics |
| POST | `/v1/registry/agent/query` | Yes | Natural language query via Claude agent |

**Query parameters:** `intent`, `urgency`, `topic`, `sender`, `min_relevancy`, `status`, `limit` (default 20), `offset`

#### Config

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/v1/config` | Yes | Get current processing config |
| PUT | `/v1/config` | Yes | Update processing config |
| GET | `/v1/config/schema` | Yes | JSON schema for config object |

**Config fields:** `ignore_senders`, `ignore_subjects_containing`, `min_relevancy_threshold`, `max_attachment_size_mb`, `enable_ocr`, `enable_transcription`, `enable_pdf_extraction`, `enable_docx_extraction`, `extra_domain_hints`

#### Sources

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/v1/sources` | Yes | List registered forwarding sources |
| POST | `/v1/sources` | Yes | Register a forwarding source |
| DELETE | `/v1/sources/{source_id}` | Yes | Remove a source |

---

## Intelligence Record Schema

Each processed email produces a Firestore document in `fsu4-intelligence`:

| Field | Type | Description |
|-------|------|-------------|
| `record_id` | string | UUID — primary key |
| `message_id` | string | Gmail message ID (idempotency key) |
| `thread_id` | string | Gmail thread ID |
| `from_address` | string | Sender email address |
| `from_name` | string | Sender display name |
| `subject` | string | Email subject line |
| `received_at` | timestamp | When email was received |
| `forwarded_from` | string | Original sender if forwarded |
| `title` | string | AI-generated title |
| `summary` | string | AI-generated summary |
| `topics` | array[string] | Extracted topic tags |
| `intent` | enum | `informational` · `actionable` · `alert` · `report` · `noise` |
| `urgency` | enum | `low` · `medium` · `high` · `critical` |
| `relevancy_score` | float | 0.0–1.0 relevance to Chimera domain |
| `chimera_domain_tags` | array[string] | Domain-specific tags |
| `attachments` | array | Attachment metadata + GCS paths |
| `gcs_raw_prefix` | string | GCS path to raw email artefacts |
| `gcs_processed_prefix` | string | GCS path to processed record |
| `status` | enum | `processing` · `processed` · `skipped` · `error` |
| `processing_error` | string | Error message if status=error |
| `created_at` | timestamp | Record creation time |
| `updated_at` | timestamp | Last update time |

---

## GCS Structure

```
chimera-ops-email-raw/
  raw/{year}/{month}/{day}/{message_id}/
    email_metadata.json
    body.txt
    body.html
    attachments/{filename}
  processed/{record_id}/
    record.json
    extracted_texts/{filename}.txt
    transcripts/{filename}.txt
  index/
    daily_manifest_{YYYY-MM-DD}.json
```

---

## Email Forwarding Setup

1. For each source account, create a forwarding rule to `chimera.data.in@gmail.com`
   - Gmail: Settings → Forwarding and POP/IMAP → Add forwarding address
   - Filter by subject keywords relevant to Chimera operations
2. Register the source via the API:
```bash
curl -X POST \
  -H "X-Chimera-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email_address":"source@example.com","display_name":"Source Name","description":"What this source sends"}' \
  https://fsu4-950990732577.europe-west2.run.app/v1/sources
```

---

## GCP Infrastructure — Provisioning Reference

All resources are already provisioned. Commands below are for recreation only.

### APIs
```bash
gcloud services enable \
  run.googleapis.com cloudbuild.googleapis.com containerregistry.googleapis.com \
  secretmanager.googleapis.com firestore.googleapis.com pubsub.googleapis.com \
  storage.googleapis.com gmail.googleapis.com cloudscheduler.googleapis.com \
  --project=chimera-v4
```

### Service account
```bash
gcloud iam service-accounts create fsu4-runner \
  --display-name="fsu4 Cloud Run SA" --project=chimera-v4

SA="fsu4-runner@chimera-v4.iam.gserviceaccount.com"
for ROLE in roles/secretmanager.secretAccessor roles/datastore.user \
  roles/storage.objectAdmin roles/pubsub.subscriber \
  roles/logging.logWriter roles/cloudtrace.agent; do
  gcloud projects add-iam-policy-binding chimera-v4 \
    --member="serviceAccount:$SA" --role="$ROLE" --condition=None
done
```

### Pub/Sub
```bash
gcloud pubsub topics create fsu4-trigger --project=chimera-v4

gcloud pubsub topics add-iam-policy-binding fsu4-trigger \
  --member="serviceAccount:gmail-api-push@system.gserviceaccount.com" \
  --role="roles/pubsub.publisher" --project=chimera-v4

gcloud pubsub subscriptions create fsu4-sub \
  --topic=fsu4-trigger \
  --push-endpoint=https://fsu4-950990732577.europe-west2.run.app/v1/ingest/pubsub-push \
  --ack-deadline=300 \
  --project=chimera-v4
```

### Firestore
Native mode, `europe-west2`. All collections created automatically on first write.

### GCS bucket
`chimera-ops-email-raw` — `europe-west2`, Standard storage, uniform access control, public access prevented.
