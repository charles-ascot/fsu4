# fsu4 — Deployment To-Do
### Browser & GitHub only — no local CLI required

> **Last updated: 2026-03-18**
> ✅ = already done | [ ] = still to do
>
> **How to run CLI commands without a local terminal:** Every command in this doc can be run in **GCP Cloud Shell** — the browser-based terminal built into GCP Console. Open it by clicking the `>_` icon in the top-right of any GCP Console page. It is already authenticated to `chimera-v4` — no login or config needed.

---

## Quick Reference — Resource Names

| Resource | Name |
|----------|------|
| GCP project | `chimera-v4` |
| Cloud Run service | `fsu4` |
| Cloud Run region | `europe-west2` |
| Container image | `gcr.io/chimera-v4/fsu4` |
| Service account | `fsu4@chimera-v4.iam.gserviceaccount.com` |
| GCS bucket | `chimera-ops-email-raw` |
| Firestore collection | `fsu4-intelligence` |
| Pub/Sub topic | `fsu4-trigger` |
| Pub/Sub subscription | `fsu4-sub` |
| Cloud Build trigger | `fsu4-deploy` |
| Gmail address | `chimera.data.in@gmail.com` |
| Secret: Anthropic key | `anthropic-api-key` |
| Secret: API key | `chimera-api-key` |
| Secret: Gmail creds | `gmail-oauth-credentials` |
| Secret: Gmail token | `gmail-token` |

---

## PHASE 1 — Enable GCP APIs

**Where: GCP Console Cloud Shell (`>_` icon, top-right) — project `chimera-v4`**

Open Cloud Shell and paste this single command:

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
  --project=chimera-v4
```

- [ ] All 11 APIs confirmed active: Console → APIs & Services → Enabled APIs

---

## PHASE 2 — Gmail Account & OAuth2

### 2.1 Gmail account
**Where: Browser — logged into `chimera.data.in@gmail.com`**

- ✅ `chimera.data.in@gmail.com` account exists (Chimera CERP)
- [ ] Enable IMAP: Gmail → Settings (gear icon) → See all settings → Forwarding and POP/IMAP → **Enable IMAP** → Save Changes

### 2.2 Create OAuth2 credentials
**Where: GCP Console → `chimera-v4` → APIs & Services → Credentials**

1. Click **+ Create Credentials → OAuth 2.0 Client ID**
2. If prompted to configure consent screen first:
   - User type: **Internal**
   - App name: `fsu4`
   - Save and continue through all steps (no scopes needed here)
3. Back in Credentials → Create OAuth 2.0 Client ID:
   - Application type: **Desktop app**
   - Name: `chimera-gmail-oauth`
   - Click **Create**
4. A popup shows your credentials — note these values:
   - `client_id`: `____________________________`
   - `client_secret`: `____________________________`
   - `token_uri`: `https://oauth2.googleapis.com/token`
5. Click **Download JSON** and save the file somewhere safe

### 2.3 Generate OAuth token with refresh_token
**Where: Browser — [Google OAuth 2.0 Playground](https://developers.google.com/oauthplayground) — no local tools needed**

> This is the browser-based alternative to running a local Python script.

1. Open [https://developers.google.com/oauthplayground](https://developers.google.com/oauthplayground)
2. Click the **gear icon** (top-right of the page) → check **"Use your own OAuth credentials"**
   - Enter your `client_id` and `client_secret` from Phase 2.2
3. In the left panel, find **"Gmail API v1"** and select these two scopes:
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.modify`
4. Click **Authorise APIs** — a Google sign-in popup appears
   - **Sign in as `chimera.data.in@gmail.com`** (not your personal account)
   - Grant the requested permissions
5. You are returned to the Playground — click **Exchange authorisation code for tokens**
6. The response JSON appears on the right. Note these values:
   - `access_token`: `____________________________`
   - `refresh_token`: `____________________________`

> ⚠️ If `refresh_token` is missing: go to [Google Account → Security → Third-party apps](https://myaccount.google.com/connections) while logged in as `chimera.data.in@gmail.com`, remove the OAuth app, then repeat steps 3–6.

---

## PHASE 3 — Google Secret Manager

**Where: GCP Console → `chimera-v4` → Security → Secret Manager**

> All secrets are created via the Console UI — no CLI needed. For each secret below: click **+ Create Secret**, enter the name, paste the value into the **Secret value** field, leave all other settings as default, click **Create Secret**.

### Secret 1: `anthropic-api-key`
- [ ] Name: `anthropic-api-key`
- [ ] Value: your `sk-ant-...` Anthropic API key

### Secret 2: `chimera-api-key`
- [ ] Generate a strong random string (e.g. use [passwordsgenerator.net](https://passwordsgenerator.net) — 32 chars, no symbols)
- [ ] Name: `chimera-api-key`
- [ ] Value: the random string you generated
- [ ] **Save this key somewhere safe** — you will need it for every authenticated API call

### Secret 3: `gmail-oauth-credentials`
- [ ] Name: `gmail-oauth-credentials`
- [ ] Value: paste this JSON, filled in with your Phase 2.2 values:
  ```json
  {"client_id":"YOUR_CLIENT_ID","client_secret":"YOUR_CLIENT_SECRET","token_uri":"https://oauth2.googleapis.com/token"}
  ```

### Secret 4: `gmail-token`
- [ ] Name: `gmail-token`
- [ ] Value: paste this JSON, filled in with your Phase 2.3 values:
  ```json
  {"token":"YOUR_ACCESS_TOKEN","refresh_token":"YOUR_REFRESH_TOKEN","token_uri":"https://oauth2.googleapis.com/token"}
  ```

- [ ] All 4 secrets visible in Console → Secret Manager

---

## PHASE 4 — GCP Infrastructure

### 4.1 Service Account
**Where: GCP Console Cloud Shell (`>_`) — project `chimera-v4`**

```bash
# Create the service account
gcloud iam service-accounts create fsu4 \
  --display-name="fsu4 Cloud Run SA" \
  --project=chimera-v4

# Grant all required roles
SA="fsu4@chimera-v4.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding chimera-v4 --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"
gcloud projects add-iam-policy-binding chimera-v4 --member="serviceAccount:$SA" --role="roles/datastore.user"
gcloud projects add-iam-policy-binding chimera-v4 --member="serviceAccount:$SA" --role="roles/storage.objectAdmin"
gcloud projects add-iam-policy-binding chimera-v4 --member="serviceAccount:$SA" --role="roles/pubsub.subscriber"
gcloud projects add-iam-policy-binding chimera-v4 --member="serviceAccount:$SA" --role="roles/logging.logWriter"
gcloud projects add-iam-policy-binding chimera-v4 --member="serviceAccount:$SA" --role="roles/cloudtrace.agent"
```

- [ ] Service account `fsu4@chimera-v4.iam.gserviceaccount.com` created and all 6 roles granted
- [ ] Verify: Console → IAM & Admin → Service Accounts → `fsu4` appears

### 4.2 GCS Bucket
- ✅ Bucket `chimera-ops-email-raw` created in `chimera-v4`, region `europe-west2`, Standard, public access prevented, Uniform access control

### 4.3 Firestore Database
**Where: GCP Console → `chimera-v4` → Firestore**

1. Console → Firestore → **Create Database**
2. Select **Native mode** → click **Continue**
3. Location: **europe-west2 (London)** → click **Create Database**

> Skip entirely if a default Firestore database already exists in `chimera-v4`

- [ ] Firestore database created in `europe-west2`, Native mode
- [ ] Note: collection `fsu4-intelligence` is created automatically on first record write — no manual setup needed

### 4.4 Pub/Sub Topic
**Where: GCP Console Cloud Shell (`>_`) — project `chimera-v4`**

```bash
# Create the topic
gcloud pubsub topics create fsu4-trigger --project=chimera-v4

# Grant Gmail API permission to publish to it
gcloud pubsub topics add-iam-policy-binding fsu4-trigger \
  --member="serviceAccount:gmail-api-push@system.gserviceaccount.com" \
  --role="roles/pubsub.publisher" \
  --project=chimera-v4
```

- [ ] Topic `fsu4-trigger` visible in Console → Pub/Sub → Topics

---

## PHASE 5 — GitHub & Cloud Build

### 5.1 GitHub repository
**Where: GitHub.com + VS Code (your normal workflow)**

- [ ] Create a new **private** GitHub repository — suggested name: `fsu4` or `chimera-fsu4`
- [ ] In VS Code, open the project at `/Users/charles/Projects/fsu4`
- [ ] Open the VS Code terminal and run:
  ```bash
  git remote add origin git@github.com:YOUR-ORG/fsu4.git
  git push -u origin main
  ```
  > If the repo already has a remote, replace `add origin` with `set-url origin`
- [ ] Confirm in GitHub that all files are present and **no secrets are in the repo**

### 5.2 Connect Cloud Build to GitHub
**Where: GCP Console → `chimera-v4` → Cloud Build → Triggers**

1. Click **Connect Repository**
2. Select **GitHub (Cloud Build GitHub App)** → click **Continue**
3. Authorise GitHub and select your `fsu4` repository → click **Connect**
4. Click **Create a trigger** (or go to Triggers → **+ Create Trigger**):
   - Name: `fsu4-deploy`
   - Event: **Push to a branch**
   - Branch: `^main$`
   - Configuration: **Cloud Build configuration file** → location: `cloudbuild.yaml`
   - Service account: `fsu4@chimera-v4.iam.gserviceaccount.com`
   - Click **Save**

- [ ] Trigger `fsu4-deploy` saved in Console → Cloud Build → Triggers

### 5.3 Grant Cloud Build service account permissions
**Where: GCP Console Cloud Shell (`>_`)**

```bash
CB_SA="$(gcloud projects describe chimera-v4 --format='value(projectNumber)')@cloudbuild.gserviceaccount.com"

gcloud projects add-iam-policy-binding chimera-v4 \
  --member="serviceAccount:$CB_SA" --role="roles/run.admin"

gcloud projects add-iam-policy-binding chimera-v4 \
  --member="serviceAccount:$CB_SA" --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding chimera-v4 \
  --member="serviceAccount:$CB_SA" --role="roles/storage.admin"
```

- [ ] Cloud Build SA has `run.admin`, `iam.serviceAccountUser`, `storage.admin`

---

## PHASE 6 — Initial Deployment

**Where: VS Code → GitHub push (triggers Cloud Build automatically)**

- [ ] Make any small change in VS Code (e.g. update the version comment in `main.py`) or simply push the current state
- [ ] Push to `main` branch in GitHub
- [ ] Monitor build: Console → `chimera-v4` → Cloud Build → History
  - Build should take ~3–5 minutes
  - Green checkmark = success | Red X = click it and read the logs
- [ ] Confirm Cloud Run service `fsu4` appears: Console → Cloud Run → filter region `europe-west2`
- [ ] Click the service to get the URL:
  - Format: `https://fsu4-XXXXXXXX-nw.a.run.app`
  - **Save this URL: `____________________________`** — needed for Phases 7, 8, and 9

---

## PHASE 7 — Pub/Sub Push Subscription

**Where: GCP Console Cloud Shell (`>_`)**
> Requires the Cloud Run URL from Phase 6

```bash
CLOUD_RUN_URL="https://fsu4-XXXXXXXX-nw.a.run.app"   # ← paste your real URL

gcloud pubsub subscriptions create fsu4-sub \
  --topic=fsu4-trigger \
  --push-endpoint="${CLOUD_RUN_URL}/v1/ingest/pubsub-push" \
  --ack-deadline=300 \
  --project=chimera-v4
```

- [ ] Subscription `fsu4-sub` visible in Console → Pub/Sub → Subscriptions

---

## PHASE 8 — Gmail Watch Renewal Scheduler

**Where: GCP Console Cloud Shell (`>_`)**
> Requires the Cloud Run URL from Phase 6. Gmail watch expires every 7 days — this job pings the service every 6 days to keep it renewed.

```bash
CLOUD_RUN_URL="https://fsu4-XXXXXXXX-nw.a.run.app"   # ← paste your real URL

gcloud scheduler jobs create http gmail-watch-renewal \
  --schedule="0 6 */6 * *" \
  --uri="${CLOUD_RUN_URL}/health" \
  --http-method=GET \
  --location=europe-west2 \
  --project=chimera-v4
```

- [ ] Job `gmail-watch-renewal` visible in Console → Cloud Scheduler

---

## PHASE 9 — Smoke Tests

**Where: GCP Console Cloud Shell (`>_`) or any browser-based API tool (e.g. Postman web)**

Replace `XXXXXXXX` with your real URL suffix and `YOUR-CHIMERA-API-KEY` with your Phase 3 Secret 2 value.

```bash
URL="https://fsu4-XXXXXXXX-nw.a.run.app"
KEY="YOUR-CHIMERA-API-KEY"
```

**Health check** — expect `{"status":"ok"}`:
```bash
curl $URL/health
```
- [ ] Returns `{"status":"ok"}`

**Version endpoint**:
```bash
curl $URL/version
```
- [ ] Returns version JSON

**Status endpoint** — confirm Firestore connectivity:
```bash
curl $URL/status
```
- [ ] Returns `"firestore": "ok"`

**Registry query** (authenticated):
```bash
curl -H "X-Chimera-API-Key: $KEY" $URL/v1/registry
```
- [ ] Returns valid JSON (empty array is fine at this stage)

**Manual ingest test:**
1. Send a test email to `chimera.data.in@gmail.com` from any address
2. Open Gmail as `chimera.data.in@gmail.com`, find the email, open it
3. The message ID is in the URL: `.../#inbox/` **`THIS_IS_THE_MESSAGE_ID`**
4. Run:
```bash
curl -X POST \
  -H "X-Chimera-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"message_id":"GMAIL_MESSAGE_ID"}' \
  $URL/v1/ingest/manual
```
- [ ] Returns success response
- [ ] Firestore record created: Console → Firestore → collection `fsu4-intelligence` → new document appears
- [ ] GCS artefact uploaded: Console → Cloud Storage → `chimera-ops-email-raw` → `raw/` folder → file present

---

## PHASE 10 — End-to-End Live Test

**Where: Gmail + GCP Console**

- [ ] Forward a real operational email to `chimera.data.in@gmail.com`
- [ ] Confirm Pub/Sub message received: Console → Pub/Sub → Subscriptions → `fsu4-sub` → **Metrics tab**
- [ ] Confirm new document in Firestore collection `fsu4-intelligence` within ~30 seconds
- [ ] Check Cloud Run logs: Console → Cloud Run → `fsu4` → **Logs tab**
- [ ] Query and confirm AI fields are populated (title, summary, topics, relevancy_score, intent):
  ```bash
  curl -H "X-Chimera-API-Key: $KEY" "$URL/v1/registry?limit=5"
  ```
- [ ] `title`, `summary`, `topics`, `relevancy_score`, `intent` all present and non-empty

---

## PHASE 11 — Register Forwarding Sources & Config

**Where: Cloud Shell or any API client**

Register each email address that will forward to `chimera.data.in@gmail.com`:

```bash
curl -X POST \
  -H "X-Chimera-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"email_address":"source@example.com","display_name":"Source Name","description":"What this source sends"}' \
  $URL/v1/sources
```

- [ ] All forwarding sources registered

Configure email forwarding on each source account (Gmail: Settings → Forwarding → Add forwarding address → `chimera.data.in@gmail.com`):
- [ ] All source accounts configured to forward to `chimera.data.in@gmail.com`

Optionally filter newsletters/noise:
```bash
curl -X PUT \
  -H "X-Chimera-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"ignore_senders":["noreply@newsletter.com"]}' \
  $URL/v1/config
```

---

## PHASE 12 — Monitoring

**Where: GCP Console → `chimera-v4` → Cloud Monitoring / Logging**

- [ ] Cloud Monitoring alert: Console → Monitoring → Alerting → **Create Policy** → Cloud Run → request error rate > 5% → service `fsu4`
- [ ] Log-based alert for `"Gmail watch setup failed"`: Console → Logging → Log-based Metrics → create metric → alert on it
- [ ] Bookmark: Console → Cloud Run → `fsu4` → Logs (for day-to-day checks)
- [ ] Scheduled weekly check: hit `GET $URL/v1/registry/metrics` to confirm records flowing
