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
3. Parse headers, body text/HTML, attachments; detect original sender if forwarded
4. Skip checks (ignore_senders, ignore_subjects)
5. Store raw artefacts to GCS
6. Extract text from attachments (PDF, DOCX, images via OCR, audio via STT)
7. AI tagging via Claude — title, summary, topics, entities, intent, urgency, sentiment, relevancy_score
8. If sender is `mark.insley@ascotwm.com` → classify email type → SCN/SDR process or simple acknowledgement
9. Store processed record to GCS
10. Write intelligence record to Firestore

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
| Firestore SCN records | `chimera-scn-records` |
| Firestore SDR records | `chimera-sdr-records` |
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
| GET | `/v1/registry` | Yes | Query records — filterable by intent, urgency, sender, topic, domain_tag, relevancy |
| GET | `/v1/registry/{record_id}` | Yes | Fetch a single record |
| GET | `/v1/registry/metrics` | Yes | Processing statistics |
| POST | `/v1/registry/agent/query` | Yes | Natural language query via Claude agent |

**Query parameters:** `intent`, `urgency`, `topic`, `domain_tag`, `sender`, `min_relevancy`, `status`, `limit` (default 50, max 200), `offset`

#### Config

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/v1/config` | Yes | Get current processing config |
| PUT | `/v1/config` | Yes | Update processing config |
| GET | `/v1/config/schema` | Yes | JSON schema for config object |

**Config fields:** `ignore_senders`, `ignore_subjects_containing`, `min_relevancy_threshold`, `max_attachment_size_mb`, `enable_ocr`, `enable_transcription`, `enable_pdf_extraction`, `enable_docx_extraction`, `cloud_run_timeout_seconds`, `gmail_watch_expiry_buffer_hours`, `extra_domain_hints`

#### Sources

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/v1/sources` | Yes | List registered forwarding sources |
| POST | `/v1/sources` | Yes | Register a forwarding source |
| DELETE | `/v1/sources/{source_id}` | Yes | Remove a source |

#### Actions

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/v1/actions` | Yes | List all pending SCN and SDR action items, newest first |
| GET | `/v1/actions/{ref}` | Yes | Fetch a single action item by reference (e.g. `SCN-20260323-001`) |

**Query parameters:** `limit` (default 50, max 200)

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
| `gmail_labels` | array[string] | Gmail labels on the message |
| `title` | string | AI-generated title (max 80 chars) |
| `summary` | string | AI-generated summary |
| `topics` | array[string] | Extracted topic tags |
| `entities` | object | Extracted entities — `people`, `organisations`, `race_venues`, `horse_names`, `monetary_values` |
| `intent` | enum | `informational` · `action_required` · `data_payload` · `alert` · `report` |
| `urgency` | enum | `low` · `medium` · `high` · `critical` |
| `sentiment` | enum | `neutral` · `positive` · `negative` |
| `relevancy_score` | float | 0.0–1.0 relevance to Chimera domain |
| `relevancy_reasoning` | string | AI explanation of relevancy score |
| `chimera_domain_tags` | array[string] | Domain-specific tags |
| `action_items` | array[string] | Action items extracted from the email |
| `contains_pii` | bool | Whether PII was detected |
| `chimera_ref` | string | SCN or SDR reference if raised (e.g. `SCN-20260323-001`) |
| `attachments` | array | Attachment metadata + GCS paths |
| `gcs_raw_prefix` | string | GCS path to raw email artefacts |
| `gcs_processed_prefix` | string | GCS path to processed record |
| `status` | enum | `pending` · `processing` · `complete` · `failed` · `skipped` |
| `processing_error` | string | Error message if status=failed |
| `ai_model_used` | string | Claude model used for tagging |
| `processing_time_ms` | int | End-to-end processing duration |
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

## Mark Insley SCN/SDR Workflow

Emails from `mark.insley@ascotwm.com` trigger an additional classification and automated response workflow on top of standard AI tagging.

### Email Classification

Claude classifies each Mark email into one of four types:

| Type | Description |
|------|-------------|
| `strategy_instruction` | Specific parameter change or direct instruction for the live trading engine (odds bands, stakes, rule overrides). Triggers **SCN process**. |
| `strategy_development` | Exploratory idea, test/backtest request, or new rule proposal needing research before going live. Triggers **SDR process**. |
| `strategy_discussion` | Thinking out loud, sharing analysis/research, reflecting on performance. Triggers simple acknowledgement. |
| `general_correspondence` | Brief conversational message with no strategy content. Triggers simple acknowledgement. |

### Strategy Change Notice (SCN)

A `strategy_instruction` email triggers the full SCN process:

1. A sequential reference is generated: `SCN-YYYYMMDD-NNN`
2. A 5-step formal reply is sent to Mark confirming receipt, reference, no-changes-yet, sign-off required, and any self-commitments extracted from the email
3. A record is written to `chimera-scn-records` in Firestore
4. `chimera_ref` on the intelligence record is set to the SCN reference
5. The SCN item appears in `/v1/actions` until resolved

### Strategy Development Request (SDR)

A `strategy_development` email triggers the SDR process:

1. A sequential reference is generated: `SDR-YYYYMMDD-NNN`
2. A 3-step reply is sent to Mark confirming receipt, reference, and that it is queued for development
3. A record is written to `chimera-sdr-records` in Firestore
4. `chimera_ref` on the intelligence record is set to the SDR reference
5. The SDR item appears in `/v1/actions` until resolved

### Self-Note Extraction

For both SCN and SDR emails, the pipeline extracts self-directed commitments from Mark's message body (phrases beginning with "I will have to", "I need to", "I should", etc.) and includes them in the reply and the Firestore record under `self_notes`.

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


## Changelog

### 2026-03-30 — Domain migration prep
- Replaced hardcoded `thync.online` domain references with environment variables
- `ALLOWED_ORIGINS` env var (Cloud Run) now controls CORS allowed origins — set as comma-separated list, e.g. `https://service.newdomain.com,https://service.newdomain.com`
- Default falls back to `http://localhost:5173` for local development
- See `domain-migration-register.md` at the root of /Users/charles/Projects for the complete list of Cloud Run env vars to set per service
