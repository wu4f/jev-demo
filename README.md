# Jev Lab

A local-first FastAPI app for exploring TypeSafe's Jev model. Five individual
experiments cover ticket routing, review scoring, announcement completeness,
out-of-category inputs, and probability-driven automation.

[![Run on Google Cloud](https://deploy.cloud.run/button.svg)](https://deploy.cloud.run/?git_repo=https%3A%2F%2Fgithub.com%2Fwu4f%2Fjev-demo.git)

The button deploys [wu4f/jev-demo](https://github.com/wu4f/jev-demo) and requires
the prerequisites below. If you fork the project, update the button's
`git_repo` URL to point to your public fork.

## Run locally

Python 3.10 or later:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Create `.env` beside `app.py` (or use `.env.example` as a starting point):

```dotenv
TYPESAFE_API_KEY=your-key-here
TYPESAFE_DEFAULT_MODEL=jev-latest
```

```bash
.venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Open <http://127.0.0.1:8000> on this machine, or
`http://<this-machine-ip-or-hostname>:8000` from another machine.
The server listens on all IPv4 interfaces; allow inbound TCP port 8000 only
from trusted machines in your host or network firewall.
Restart the server after changing `.env`.
Existing process environment variables take precedence over `.env`.
For loopback-only access instead, use `--host 127.0.0.1` and forward port 8000
over SSH.

No frontend build, container, Google account, or Secret Manager setup is needed.
Only clicking **Run Jev** makes a paid API request. Each run batches the page's
questions in one call; automatic retries are disabled. Editing text, loading an
example, and moving policy sliders do not call the API.

## Explore

- **Support:** department Choice and urgency Noul.
- **Reviews:** three independent Scores on descriptive 0–2 rubrics.
- **Announcements:** separate Nouls for date, location, and action.
- **Nothing fits:** a forced Choice plus an independent fit Noul.
- **Automation:** adjustable probability thresholds applied locally to the
  most recent result. No real tickets are routed.

Each page includes editable input, examples, probability visualizations, the
returned confidence when available, request/response JSON, latency, and a
comparison with the previous successful run. Results retain the exact input
they evaluated and are marked out of date after edits.

Confidence summarizes the distribution, not a guarantee of accuracy. Noul has
no separate confidence field. Missing evidence can be an instructive failure:
inspect the probabilities rather than treating a Score as a fact.

## Run the container locally

```bash
docker build -t jev-lab .
docker run --rm -p 8000:8080 --env-file .env jev-lab
```

Open <http://127.0.0.1:8000>, or use the host's address from another machine.
Restrict inbound access as described above. `--env-file` injects the key at
runtime; it is **not** copied into the image. Protect access to the Docker
daemon, whose administrators can inspect container environment variables.

The image uses Python 3.12, runs as UID/GID 10001, listens on `0.0.0.0`, and
honors Cloud Run's `PORT` (8080 by default). `.dockerignore` and `.gcloudignore`
are allowlists: `.env`, Git metadata, virtual environments, and tests are
excluded from both build contexts. Docker runs only the application, not
development tooling. TLS forwarding headers are trusted in the container
because Cloud Run terminates HTTPS; use it behind a trusted ingress.

## Deploy to Cloud Run

### Prerequisites and Secret Manager

1. Select a Google Cloud project with billing enabled. Cloud Run, Cloud Build,
   Artifact Registry, and Secret Manager can incur charges.
2. In [Secret Manager](https://console.cloud.google.com/security/secret-manager),
   enable the API if prompted and create a secret named `typesafe-api-key`
   containing **only your TypeSafe API key**, not the contents of `.env`.
   Note the enabled numeric version (usually `1`).
3. Use a deploying identity permitted to enable APIs, build/deploy Cloud Run
   services, create service accounts and act as them, and change the selected
   secret's IAM policy. Google Cloud project administrators can grant these
   permissions; the runtime account does not need these administration roles.
   Source deployment also requires the project's Cloud Build service account
   to have the [Cloud Run Builder role](https://cloud.google.com/run/docs/deploying-source-code#required_roles).

The scripts create a deterministic, service-specific runtime account and grant
it `roles/secretmanager.secretAccessor` **on the selected secret only**.
Cloud Run injects the pinned version as `TYPESAFE_API_KEY` before starting an
instance. The app uses that environment variable exactly as it does locally:
no Google SDK, service-account key file, or runtime Secret Manager fetch is
necessary. If injection fails, Cloud Run cannot start the instance. Never
put the API key in `app.json`, build arguments, deployment URLs, or Git.

### Deploy with the button

Click **Run on Google Cloud** in the published repository's README. Choose
the same project containing your secret and a region, then supply:

| Prompt | Example | Meaning |
|---|---|---|
| `TYPESAFE_SECRET` | `typesafe-api-key` | Existing secret name, **not the API key** |
| `TYPESAFE_SECRET_VERSION` | `1` | Enabled, pinned numeric version; not `latest` |
| `TYPESAFE_DEFAULT_MODEL` | `jev-latest` | Jev model or alias |
| `JEV_PROXY_ORIGIN` | `http://127.0.0.1:8080` | Browser origin for the local authenticated proxy |

`app.json` configures the build and hooks. The `precreate` hook verifies the
secret version and prepares runtime IAM; `postcreate` attaches the secret and
runtime identity. The initial private revision has no API key until that
second step completes. Treat a failed hook as a failed deployment, not a
configured app.

The button is a [GoogleCloudPlatform community tool](https://github.com/GoogleCloudPlatform/cloud-run-button),
not an officially supported Google product. If it is unavailable or your
repository is private, use the CLI path below.

### Deploy from this directory with gcloud

Authenticate with the Google Cloud CLI, then:

```bash
gcloud auth login
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_REGION="us-central1"
export K_SERVICE="jev-lab"
export TYPESAFE_SECRET="typesafe-api-key"
export TYPESAFE_SECRET_VERSION="1"

bash scripts/cloud-run.sh deploy
```

This enables required APIs, prepares the account and secret access, uploads
the allowlisted source, builds the Dockerfile, and deploys a service requiring
Cloud Run IAM authentication. No local `.env` values are uploaded or read by
the deployment script. Runtime defaults are 512 MiB, one CPU, zero minimum
instances, at most two instances per revision, concurrency eight, and a
60-second request timeout.

No deploy command has been run against a real Google Cloud project as part
of this setup. Your identity and project policy determine deployment access;
resolve any IAM/build permission errors rather than granting broad runtime
permissions.

### Open the authenticated app

An IAM-protected service URL will not open directly in an ordinary browser.
With a signed-in identity that has `roles/run.invoker`, run:

```bash
gcloud run services proxy jev-lab \
  --project="$GOOGLE_CLOUD_PROJECT" \
  --region="$GOOGLE_CLOUD_REGION" \
  --port=8080
```

Open **http://127.0.0.1:8080** (use that exact hostname and port). Both deployment
paths configure this explicit proxy origin. Static assets use relative paths
so requests stay on the authenticated proxy. If you change the proxy's port
or hostname, update `JEV_PROXY_ORIGIN` on the service to match. It adds one
exact allowed browser origin; it does not disable origin checking or IAM.

For student access, prefer an authenticated gateway such as IAP. If you
deliberately want a public service, you can grant `allUsers` the
`roles/run.invoker` role on the service, subject to your organization's policy.
That makes **all API calls public too**; add access controls and durable quotas
before doing so. An obscure URL and the origin check are not authentication.

### Rotate the API key

Add a new secret version in Secret Manager, then pin the service to it:

```bash
export TYPESAFE_SECRET_VERSION="2"
bash scripts/cloud-run.sh prepare
bash scripts/cloud-run.sh attach
```

Use the same project, region, service, and secret variables as your deployment.
This creates a new revision with the new key; existing instances keep their
old environment until replaced. Don't disable the old version while revisions
still need it. `prepare` and `attach` also let you retry a failed button hook
without rebuilding the image.

## Development

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check app.py tests
bash -n scripts/cloud-run.sh
```

Tests mock the SDK and gcloud and never spend API credits or modify cloud
resources. Container smoke tests can use `/health` and the page routes without
calling Jev. Demo definitions and questions live in `demos.py`; the server,
templates, and plain JavaScript are in `app.py`,
`templates/`, and `static/`. The official `typesafe-sdk` validates and serializes
typed Jev responses. The server applies a 6,000-character input limit, a
20-second SDK timeout, and a 25-second overall call timeout. API errors are
shown explicitly without exposing upstream bodies or credentials.

## Cost and data safeguards

This version is for trusted **development testing**, not a public paid API proxy.
The local launch commands bind to all interfaces for access from another machine.
There is no authentication, durable rate limit, or shared spending quota:
anyone who can reach port 8000 can make calls using your paid API key.
Restrict development network access to trusted machines. Cloud Run deployments
default to IAM authentication. Instance/concurrency limits constrain capacity,
**not API spending**; add durable per-user quotas and a shared usage allowance
before opening the app to a class. Cloud billing budgets are alerts, not hard
spending caps, and TypeSafe API charges are separate.
Inputs go to TypeSafe; use fictional examples. The app does not persist inputs
or results, and its own logs exclude input text and upstream response bodies.
Avoid SDK debug logging, which can include request bodies.

The API key is server-only and `.env` is ignored by Git. It is never passed to
templates or JavaScript. Cloud Run injects `TYPESAFE_API_KEY` from Secret
Manager using the deployment scripts; it never becomes a build input.

References: [TypeSafe quickstart](https://docs.typesafe.ai/introduction/quickstart),
[primitives](https://docs.typesafe.ai/primitives), and
[confidence](https://docs.typesafe.ai/confidence).
