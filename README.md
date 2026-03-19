# FSU4 — Chimera Email Intelligence Service
**Version 1.0.0** · Cloud Run · `chimera-v4` · `europe-west2`

Transforms inbound emails at `chimera.data.in@gmail.com` into structured intelligence records using Gmail API → Pub/Sub → Claude AI → Firestore + GCS.

**Live URL:** `https://fsu4-950990732577.europe-west2.run.app`
**Management UI:** `https://fsu4.thync.online`

---

## Resource Reference

| Resource | Name |
|----------|------|
| GCP project | `chimera-v4` |
| Cloud Run service | `fsu4` |
| Region | `europe-west2` |
| Service account | `fsu4-runner@chimera-v4.iam.gserviceaccount.com` |
| GCS bucket | `chimera-ops-email-raw` |
| Firestore collection | `fsu4-intelligence` |
| Firestore sources collection | `fsu4-sources` |
| Pub/Sub topic | `fsu4-trigger` |
| Pub/Sub subscription | `fsu4-sub` |
| Gmail address | `chimera.data.in@gmail.com` |
| Claude model | `claude-sonnet-4-20250514` |
| GitHub repo | `https://github.com/charles-ascot/fsu4` |

---

## CI/CD

Push to `main` → Cloud Run auto-deploys via the **Connect repo** integration in GCP Console → Cloud Run → Connect repo.

No manual deploy steps required.

---

## Secrets (GCP Secret Manager — project: `chimera-v4`)

| Secret ID | Value |
|-----------|-------|
| `anthropic-api-key` | Anthropic API key (`sk-ant-...`) |
| `chimera-api-key` | Random 32-char string — sent as `X-Chimera-API-Key` header on all authenticated calls |
| `gmail-oauth-credentials` | `{"client_id":"...","client_secret":"...","token_uri":"https://oauth2.googleapis.com/token"}` |
| `gmail-token` | `{"token":"...","refresh_token":"...","token_uri":"https://oauth2.googleapis.com/token"}` |

### Generating Gmail OAuth credentials

1. GCP Console → `chimera-v4` → APIs & Services → Credentials → **Create OAuth 2.0 Client ID**
   - Application type: **Web application**
   - Authorised redirect URI: `https://developers.google.com/oauthplayground`
2. Note the `client_id` and `client_secret`
3. Go to [OAuth 2.0 Playground](https://developers.google.com/oauthplayground)
   - Gear icon → check **Use your own OAuth credentials** → enter `client_id` and `client_secret`
   - Scope: `https://www.googleapis.com/auth/gmail.modify`
   - Authorise APIs → sign in as `chimera.data.in@gmail.com`
   - Exchange authorisation code for tokens → copy `access_token` and `refresh_token`
4. Store in Secret Manager as shown above

---

## GCP Infrastructure

All of the below is already provisioned in `chimera-v4`. This section documents what exists and how to recreate it if needed.

### APIs enabled
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

### Pub/Sub topic
```bash
gcloud pubsub topics create fsu4-trigger --project=chimera-v4

gcloud pubsub topics add-iam-policy-binding fsu4-trigger \
  --member="serviceAccount:gmail-api-push@system.gserviceaccount.com" \
  --role="roles/pubsub.publisher" --project=chimera-v4
```

### Pub/Sub push subscription
Create after first deploy once the Cloud Run URL is known:
```bash
gcloud pubsub subscriptions create fsu4-sub \
  --topic=fsu4-trigger \
  --push-endpoint=https://fsu4-950990732577.europe-west2.run.app/v1/ingest/pubsub-push \
  --ack-deadline=300 \
  --project=chimera-v4
```

### Firestore
Native mode, `europe-west2`. Collections created automatically on first write.

### GCS bucket
`chimera-ops-email-raw` — `europe-west2`, Standard, uniform access, public access prevented.

---

## Integration Guide

### Authentication
All protected endpoints require the header:
```
X-Chimera-API-Key: <value of chimera-api-key secret>
```

### Base URL
```
https://fsu4-950990732577.europe-west2.run.app
```

### API Endpoints

#### System (no auth required)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness probe — returns `{"status":"ok"}` |
| GET | `/status` | Operational snapshot including Firestore connectivity |
| GET | `/version` | Version and build info |

#### Ingest
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/ingest/pubsub-push` | Pub/Sub push receiver (called by GCP, not directly) |
| POST | `/v1/ingest/manual` | Process a specific Gmail message ID |
| POST | `/v1/ingest/reprocess/{id}` | Re-run AI tagging on an existing record |
| GET | `/v1/ingest/queue` | View pending records |

**Manual ingest example:**
```bash
curl -X POST \
  -H "X-Chimera-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message_id":"GMAIL_MESSAGE_ID"}' \
  https://fsu4-950990732577.europe-west2.run.app/v1/ingest/manual
```

#### Registry
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/registry` | Query intelligence records (filterable) |
| GET | `/v1/registry/{record_id}` | Fetch a single record |
| GET | `/v1/registry/metrics` | Processing stats |
| POST | `/v1/registry/agent/query` | AI agent query integration |

**Query example:**
```bash
curl -H "X-Chimera-API-Key: YOUR_KEY" \
  "https://fsu4-950990732577.europe-west2.run.app/v1/registry?limit=10"
```

#### Config
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/config` | Get current processing config |
| PUT | `/v1/config` | Update processing config |
| GET | `/v1/config/schema` | JSON schema for config object |

**Filter out noise (example):**
```bash
curl -X PUT \
  -H "X-Chimera-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"ignore_senders":["noreply@newsletter.com"]}' \
  https://fsu4-950990732577.europe-west2.run.app/v1/config
```

#### Sources
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/sources` | List registered forwarding sources |
| POST | `/v1/sources` | Register a forwarding source |
| DELETE | `/v1/sources/{source_id}` | Remove a source |

**Register a forwarding source:**
```bash
curl -X POST \
  -H "X-Chimera-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email_address":"source@example.com","display_name":"Source Name","description":"What this source sends"}' \
  https://fsu4-950990732577.europe-west2.run.app/v1/sources
```

### Intelligence Record Schema
Each processed email produces a Firestore document in `fsu4-intelligence` with:

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | AI-generated title |
| `summary` | string | AI-generated summary |
| `topics` | array | Extracted topic tags |
| `relevancy_score` | float | 0.0–1.0 relevance to Chimera domain |
| `intent` | string | Classified intent of the email |
| `sender` | string | From address |
| `subject` | string | Original subject line |
| `received_at` | timestamp | When email was received |
| `gcs_path` | string | Path to raw artefacts in `chimera-ops-email-raw` |

---

## GCS Structure

```
chimera-ops-email-raw/
  raw/{year}/{month}/{day}/{message_id}/
    email_metadata.json
    body.txt
    body.html
    attachments/
  processed/{record_id}/
    record.json
    extracted_texts/
    transcripts/
  index/
    daily_manifest_{date}.json
```

---

## Email Forwarding Setup

For each email account that should feed FSU4:
1. Set up a forwarding rule based on subject keywords to `chimera.data.in@gmail.com`
2. Register the source via the `/v1/sources` endpoint (see above)

Gmail forwarding: Settings → See all settings → Forwarding and POP/IMAP → Add a forwarding address → `chimera.data.in@gmail.com`
