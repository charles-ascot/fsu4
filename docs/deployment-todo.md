# fsu4 — Deployment To-Do

---

## PHASE 0 — Prerequisites

**Platform: Local machine**

- [ ] Install Google Cloud SDK (`gcloud`) and authenticate: `gcloud auth login`
- [ ] Set active project: `gcloud config set project chimera`
- [ ] Install Docker Desktop (required to test the image locally before push)
- [ ] Confirm you have Owner or Editor role on GCP project `chimera`

---

## PHASE 1 — Enable GCP APIs

**Platform: GCP Console → APIs & Services, or gcloud CLI**

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

- [ ] All 11 APIs confirmed active in Console → APIs & Services → Enabled APIs

---

## PHASE 2 — Gmail Account & OAuth2

**Platform: Google Account (chimera.data.in@gmail.com) + GCP Console**

### 2.1 Gmail account
- [ ] Confirm login access to `chimera.data.in@gmail.com`
- [ ] Enable IMAP: Settings → See all settings → Forwarding and POP/IMAP → Enable IMAP

### 2.2 OAuth2 credentials
- [ ] GCP Console → APIs & Services → Credentials → Create Credentials → **OAuth 2.0 Client ID**
  - Application type: **Desktop app**
  - Name: `chimera-gmail-oauth`
- [ ] Download the credentials JSON
- [ ] Note the values:
  - `client_id`: `____________________________`
  - `client_secret`: `____________________________`
  - `token_uri`: `https://oauth2.googleapis.com/token`

### 2.3 Generate OAuth token with refresh_token
- [ ] Run OAuth flow locally authorising `chimera.data.in@gmail.com` with scopes:
  - `https://www.googleapis.com/auth/gmail.readonly`
  - `https://www.googleapis.com/auth/gmail.modify`
- [ ] Confirm the token JSON contains a `refresh_token` field (if missing, revoke access in Google Account → Security → Third-party apps and re-run)
- [ ] Note the values:
  - `token`: `____________________________`
  - `refresh_token`: `____________________________`

---

## PHASE 3 — Google Secret Manager

**Platform: GCP Console → Security → Secret Manager, or gcloud CLI**
**Project: `chimera`**

### Secret 1: `anthropic-api-key`
- [ ] Create:
  ```bash
  echo -n "sk-ant-YOUR-KEY-HERE" | gcloud secrets create anthropic-api-key \
    --data-file=- --project=chimera
  ```

### Secret 2: `chimera-api-key`
- [ ] Choose a strong random string — this is the value clients send in the `X-Chimera-API-Key` header
- [ ] Create:
  ```bash
  echo -n "YOUR-CHIMERA-API-KEY" | gcloud secrets create chimera-api-key \
    --data-file=- --project=chimera
  ```
- [ ] Store this key safely — required for every authenticated API call

### Secret 3: `gmail-oauth-credentials`
- [ ] Build JSON from Phase 2.2 values:
  ```json
  {"client_id":"YOUR_CLIENT_ID","client_secret":"YOUR_CLIENT_SECRET","token_uri":"https://oauth2.googleapis.com/token"}
  ```
- [ ] Create:
  ```bash
  echo -n '{"client_id":"...","client_secret":"...","token_uri":"https://oauth2.googleapis.com/token"}' \
    | gcloud secrets create gmail-oauth-credentials --data-file=- --project=chimera
  ```

### Secret 4: `gmail-token`
- [ ] Build JSON from Phase 2.3 values:
  ```json
  {"token":"ACCESS_TOKEN","refresh_token":"REFRESH_TOKEN","token_uri":"https://oauth2.googleapis.com/token"}
  ```
- [ ] Create:
  ```bash
  echo -n '{"token":"...","refresh_token":"...","token_uri":"https://oauth2.googleapis.com/token"}' \
    | gcloud secrets create gmail-token --data-file=- --project=chimera
  ```

- [ ] Verify all 4 secrets visible in Console → Secret Manager

---

## PHASE 4 — GCP Infrastructure

**Platform: GCP Console / gcloud CLI**

### 4.1 Service Account
- [ ] Create:
  ```bash
  gcloud iam service-accounts create fsu4 \
    --display-name="fsu4 Cloud Run SA" \
    --project=chimera
  ```
- [ ] Grant all required roles:
  ```bash
  SA="fsu4@chimera.iam.gserviceaccount.com"

  gcloud projects add-iam-policy-binding chimera --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"
  gcloud projects add-iam-policy-binding chimera --member="serviceAccount:$SA" --role="roles/datastore.user"
  gcloud projects add-iam-policy-binding chimera --member="serviceAccount:$SA" --role="roles/storage.objectAdmin"
  gcloud projects add-iam-policy-binding chimera --member="serviceAccount:$SA" --role="roles/pubsub.subscriber"
  gcloud projects add-iam-policy-binding chimera --member="serviceAccount:$SA" --role="roles/logging.logWriter"
  gcloud projects add-iam-policy-binding chimera --member="serviceAccount:$SA" --role="roles/cloudtrace.agent"
  ```

### 4.2 GCS Bucket
- [ ] Create bucket `fsu4-raw`:
  ```bash
  gcloud storage buckets create gs://fsu4-raw \
    --project=chimera \
    --location=europe-west2 \
    --uniform-bucket-level-access
  ```

### 4.3 Firestore Database
- [ ] Create in Native mode, region `europe-west2`:
  ```bash
  gcloud firestore databases create \
    --location=europe-west2 \
    --project=chimera
  ```
  > Skip if a default Firestore database already exists in the project.
- [ ] Collection `fsu4-intelligence` is created automatically on first record write — no manual setup needed

### 4.4 Pub/Sub Topic
- [ ] Create topic:
  ```bash
  gcloud pubsub topics create fsu4-trigger --project=chimera
  ```
- [ ] Grant Gmail API permission to publish:
  ```bash
  gcloud pubsub topics add-iam-policy-binding fsu4-trigger \
    --member="serviceAccount:gmail-api-push@system.gserviceaccount.com" \
    --role="roles/pubsub.publisher" \
    --project=chimera
  ```

---

## PHASE 5 — GitHub & Cloud Build

**Platform: GitHub + GCP Console → Cloud Build**

### 5.1 GitHub repository
- [x] Create a new private GitHub repository named `fsu4`
- [ ] Push the project code to `main`:
  ```bash
  cd /Users/charles/Projects/fsu4
  git init
  git add .
  git commit -m "feat: initial build — fsu4 v1.0"
  git remote add origin git@github.com:chimeracloud/fsu4.git
  git push -u origin main
  ```
- [x] Confirm no real secrets are present anywhere in the repo (`.env.example` contains only comments)

### 5.2 Cloud Build trigger
- [ ] GCP Console → Cloud Build → Triggers → Connect Repository
  - Authorise GitHub and select `chimeracloud/fsu4`
- [ ] Create trigger:
  - Name: `fsu4-deploy`
  - Event: Push to branch `main`
  - Configuration: Cloud Build configuration file (`cloudbuild.yaml`)
  - Service account: `fsu4@chimera.iam.gserviceaccount.com`
- [ ] Grant Cloud Build service account the required roles:
  ```bash
  CB_SA="$(gcloud projects describe chimera --format='value(projectNumber)')@cloudbuild.gserviceaccount.com"

  gcloud projects add-iam-policy-binding chimera \
    --member="serviceAccount:$CB_SA" --role="roles/run.admin"

  gcloud projects add-iam-policy-binding chimera \
    --member="serviceAccount:$CB_SA" --role="roles/iam.serviceAccountUser"
  ```

---

## PHASE 6 — Initial Deployment

**Platform: gcloud CLI / GCP Console → Cloud Build**

- [ ] Trigger first build:
  ```bash
  cd /Users/charles/Projects/fsu4
  gcloud builds submit --config=cloudbuild.yaml --project=chimera
  ```
- [ ] Monitor in Console → Cloud Build → History — confirm successful completion
- [ ] Confirm Cloud Run service `fsu4` appears in Console → Cloud Run → `europe-west2`
- [ ] Note the deployed Cloud Run URL:
  - `https://fsu4-XXXXXXXX-nw.a.run.app`
  - Save this: `____________________________`

---

## PHASE 7 — Pub/Sub Push Subscription

**Platform: gcloud CLI**
> Requires Cloud Run URL from Phase 6

- [ ] Create push subscription:
  ```bash
  CLOUD_RUN_URL="https://fsu4-XXXXXXXX-nw.a.run.app"

  gcloud pubsub subscriptions create fsu4-sub \
    --topic=fsu4-trigger \
    --push-endpoint="${CLOUD_RUN_URL}/v1/ingest/pubsub-push" \
    --ack-deadline=300 \
    --project=chimera
  ```
- [ ] Verify subscription appears in Console → Pub/Sub → Subscriptions

---

## PHASE 8 — Gmail Watch Renewal Scheduler

**Platform: GCP Console → Cloud Scheduler**
> Requires Cloud Run URL from Phase 6

- [ ] Create scheduler job:
  ```bash
  CLOUD_RUN_URL="https://fsu4-XXXXXXXX-nw.a.run.app"

  gcloud scheduler jobs create http gmail-watch-renewal \
    --schedule="0 6 */6 * *" \
    --uri="${CLOUD_RUN_URL}/health" \
    --http-method=GET \
    --location=europe-west2 \
    --project=chimera
  ```

---

## PHASE 9 — Smoke Tests

**Platform: Terminal (curl or Postman)**

Replace `XXXXXXXX` and `YOUR-CHIMERA-API-KEY` throughout.

- [ ] **Health check** — expect `{"status":"ok"}`:
  ```bash
  curl https://fsu4-XXXXXXXX-nw.a.run.app/health
  ```

- [ ] **Version endpoint**:
  ```bash
  curl https://fsu4-XXXXXXXX-nw.a.run.app/version
  ```

- [ ] **Status endpoint** — confirm `"firestore": "ok"`:
  ```bash
  curl https://fsu4-XXXXXXXX-nw.a.run.app/status
  ```

- [ ] **Registry query** (authenticated):
  ```bash
  curl -H "X-Chimera-API-Key: YOUR-CHIMERA-API-KEY" \
    https://fsu4-XXXXXXXX-nw.a.run.app/v1/registry
  ```

- [ ] **Manual ingest test** — send a test email to `chimera.data.in@gmail.com`, find the Gmail message ID, then:
  ```bash
  curl -X POST \
    -H "X-Chimera-API-Key: YOUR-CHIMERA-API-KEY" \
    -H "Content-Type: application/json" \
    -d '{"message_id":"GMAIL_MESSAGE_ID"}' \
    https://fsu4-XXXXXXXX-nw.a.run.app/v1/ingest/manual
  ```

- [ ] **Verify Firestore record** — Console → Firestore → collection `fsu4-intelligence` → confirm new document
- [ ] **Verify GCS artefacts** — Console → Cloud Storage → `fsu4-raw` → `raw/` → confirm uploaded files

---

## PHASE 10 — End-to-End Live Test

**Platform: Gmail + GCP Console**

- [ ] Forward a real operational email to `chimera.data.in@gmail.com`
- [ ] Confirm Pub/Sub message received: Console → Pub/Sub → Subscriptions → `fsu4-sub` → Metrics
- [ ] Confirm new intelligence record in Firestore collection `fsu4-intelligence` within ~30 seconds
- [ ] Check Cloud Run logs: Console → Cloud Run → `fsu4` → Logs
- [ ] Query the record and confirm AI fields populated (title, summary, topics, relevancy_score, intent):
  ```bash
  curl -H "X-Chimera-API-Key: YOUR-CHIMERA-API-KEY" \
    "https://fsu4-XXXXXXXX-nw.a.run.app/v1/registry?limit=5"
  ```

---

## PHASE 11 — Register Forwarding Sources & Config

**Platform: API**

- [ ] Register each source email address:
  ```bash
  curl -X POST \
    -H "X-Chimera-API-Key: YOUR-CHIMERA-API-KEY" \
    -H "Content-Type: application/json" \
    -d '{"email_address":"source@example.com","display_name":"Source Name","description":"What this source sends"}' \
    https://fsu4-XXXXXXXX-nw.a.run.app/v1/sources
  ```

- [ ] Configure forwarding on each source account (Gmail, Outlook, Workspace — see spec Section 8.1)

- [ ] Set `ignore_senders` to filter newsletters and noise:
  ```bash
  curl -X PUT \
    -H "X-Chimera-API-Key: YOUR-CHIMERA-API-KEY" \
    -H "Content-Type: application/json" \
    -d '{"ignore_senders":["noreply@newsletter.com"]}' \
    https://fsu4-XXXXXXXX-nw.a.run.app/v1/config
  ```

---

## PHASE 12 — Monitoring

**Platform: GCP Console → Cloud Monitoring / Logging**

- [ ] Set up a Cloud Monitoring alert for Cloud Run error rate > 5% on service `fsu4`
- [ ] Set up a log-based alert for log entries containing `"Gmail watch setup failed"`
- [ ] Bookmark Cloud Run logs URL for `fsu4` in `europe-west2`
- [ ] Check `/v1/registry/metrics` weekly to confirm records are flowing

---

## Quick Reference — Resource Names

| Resource | Name |
|----------|------|
| Cloud Run service | `fsu4` |
| Container image | `gcr.io/chimera/fsu4` |
| Service account | `fsu4@chimera.iam.gserviceaccount.com` |
| GCS bucket | `fsu4-raw` |
| Firestore collection | `fsu4-intelligence` |
| Pub/Sub topic | `fsu4-trigger` |
| Pub/Sub subscription | `fsu4-sub` |
| Cloud Build trigger | `fsu4-deploy` |
| Secret: API key | `chimera-api-key` |
| Secret: Anthropic | `anthropic-api-key` |
| Secret: Gmail creds | `gmail-oauth-credentials` |
| Secret: Gmail token | `gmail-token` |
