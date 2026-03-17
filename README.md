# fsu4

**Chimera Platform — Email Data Collection FSU**
Cloud Run service · GCP project: `chimera` · Region: `europe-west2`

Transforms inbound emails at `chimera.data.in@gmail.com` into structured intelligence records via Gmail API → Pub/Sub → Claude AI → Firestore + GCS.

---

## GCP APIs to Enable

```
gmail.googleapis.com
pubsub.googleapis.com
run.googleapis.com
cloudbuild.googleapis.com
secretmanager.googleapis.com
storage.googleapis.com
firestore.googleapis.com
vision.googleapis.com
speech.googleapis.com
containerregistry.googleapis.com
cloudscheduler.googleapis.com
```

Enable all at once:
```bash
gcloud services enable \
  gmail.googleapis.com \
  pubsub.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  firestore.googleapis.com \
  vision.googleapis.com \
  speech.googleapis.com \
  containerregistry.googleapis.com \
  cloudscheduler.googleapis.com \
  --project=chimera
```

---

## Secrets to Create in Secret Manager

| Secret ID | Description |
|-----------|-------------|
| `anthropic-api-key` | Anthropic API key (`sk-ant-...`) |
| `chimera-api-key` | Value for `X-Chimera-API-Key` header used to auth all protected endpoints |
| `gmail-oauth-credentials` | JSON: `{"client_id":"...","client_secret":"...","token_uri":"https://oauth2.googleapis.com/token"}` |
| `gmail-token` | JSON: `{"token":"...","refresh_token":"...","token_uri":"https://oauth2.googleapis.com/token"}` |

Create each:
```bash
echo -n "your-value" | gcloud secrets create SECRET_ID \
  --data-file=- \
  --project=chimera
```

---

## GCP Resources to Create

### Service Account
```bash
gcloud iam service-accounts create fsu4 \
  --display-name="fsu4 Cloud Run SA" \
  --project=chimera

# Grant required roles
for ROLE in \
  roles/secretmanager.secretAccessor \
  roles/datastore.user \
  roles/storage.objectAdmin \
  roles/pubsub.subscriber \
  roles/logging.logWriter \
  roles/cloudtrace.agent; do
  gcloud projects add-iam-policy-binding chimera \
    --member="serviceAccount:fsu4@chimera.iam.gserviceaccount.com" \
    --role="$ROLE"
done
```

### GCS Bucket
```bash
gcloud storage buckets create gs://fsu4-raw \
  --project=chimera \
  --location=europe-west2 \
  --uniform-bucket-level-access
```

### Pub/Sub Topic + Subscription
```bash
gcloud pubsub topics create fsu4-trigger --project=chimera

# Grant Gmail permission to publish to the topic
gcloud pubsub topics add-iam-policy-binding fsu4-trigger \
  --member="serviceAccount:gmail-api-push@system.gserviceaccount.com" \
  --role="roles/pubsub.publisher" \
  --project=chimera

gcloud pubsub subscriptions create fsu4-sub \
  --topic=fsu4-trigger \
  --push-endpoint=https://fsu4-<HASH>-nw.a.run.app/v1/ingest/pubsub-push \
  --project=chimera
```

### Firestore Database
```bash
gcloud firestore databases create \
  --location=europe-west2 \
  --project=chimera
```

### Gmail Watch Renewal — Cloud Scheduler
Gmail watch() expires every 7 days. Create a scheduler job to call the service startup endpoint (which renews the watch):
```bash
gcloud scheduler jobs create http gmail-watch-renewal \
  --schedule="0 0 */6 * *" \
  --uri="https://fsu4-<HASH>-nw.a.run.app/health" \
  --http-method=GET \
  --location=europe-west2 \
  --project=chimera
```
The watch is renewed on every service startup via the lifespan handler. The scheduler job keeps the service warm and triggers renewal every 6 days.

---

## Gmail OAuth2 Setup

1. In Google Cloud Console, create OAuth 2.0 credentials (Desktop app type) for the `chimera` project
2. Download the credentials JSON
3. Run the OAuth flow locally to generate a token with the required scopes:
   ```
   https://www.googleapis.com/auth/gmail.readonly
   https://www.googleapis.com/auth/gmail.modify
   ```
4. Store the credentials JSON in `gmail-oauth-credentials` secret
5. Store the token JSON (including `refresh_token`) in `gmail-token` secret

---

## Deployment

All commits to `main` auto-deploy via Cloud Build. Connect the GitHub repository in Cloud Build console and point to `cloudbuild.yaml`.

### Initial manual deploy
```bash
gcloud builds submit --config=cloudbuild.yaml --project=chimera
```

---

## API Reference

### System (no auth)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/status` | Operational snapshot |
| GET | `/version` | Version info |

### All other endpoints require `X-Chimera-API-Key` header

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/ingest/pubsub-push` | Pub/Sub push receiver |
| POST | `/v1/ingest/manual` | Process a specific message ID |
| POST | `/v1/ingest/reprocess/{id}` | Re-run AI tagging on existing record |
| GET | `/v1/ingest/queue` | View pending records |
| GET | `/v1/registry` | Query registry (filterable) |
| GET | `/v1/registry/{record_id}` | Fetch single record |
| GET | `/v1/registry/metrics` | Processing stats |
| POST | `/v1/registry/agent/query` | AI agent integration |
| GET | `/v1/config` | Get processing config |
| PUT | `/v1/config` | Update processing config |
| GET | `/v1/config/schema` | JSON schema for config |
| GET | `/v1/sources` | List forwarding sources |
| POST | `/v1/sources` | Register a forwarding source |
| DELETE | `/v1/sources/{source_id}` | Remove a forwarding source |

---

## GCS Structure

```
fsu4-raw/
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
