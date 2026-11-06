# Jev Lab

A local-first FastAPI app for exploring TypeSafe's Jev model. Five individual
experiments cover ticket routing, review scoring, the trolley problem,
LLM guardrails, and probability-driven automation.

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
JEV_ALLOWED_NETWORK=131.252.0.0/16
```

```bash
.venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 8000 --no-proxy-headers
```

Open <http://127.0.0.1:8000> on this machine, or
`http://<this-machine-ip-or-hostname>:8000` from another machine.
The server listens on all IPv4 interfaces; allow inbound TCP port 8000 only
from trusted machines in your host or network firewall.
Restart the server after changing `.env`.
Existing process environment variables take precedence over `.env`.
For loopback-only access instead, use `--host 127.0.0.1` and forward port 8000
over SSH.

Every page shows your detected IP and a green (allowed) or red (denied)
network indicator. Pages and examples remain accessible from any network,
but **only clients in `131.252.0.0/16` can call TypeSafe by default**.
The server returns HTTP 403 before creating the SDK client for other addresses,
even if someone manually enables the Run button or calls the API directly.
IPv6 addresses outside the IPv4 range are denied; IPv4-mapped IPv6 addresses
are checked as IPv4. Unknown or invalid client addresses are also denied.

Loopback is outside that default range. For local-only API testing, explicitly
override the single CIDR for that process:

```bash
JEV_ALLOWED_NETWORK=127.0.0.0/8 .venv/bin/python -m uvicorn app:app \
  --host 0.0.0.0 --port 8000 --no-proxy-headers
```

For testing from another machine, use a CIDR containing its actual source
address instead. Restart after changing `JEV_ALLOWED_NETWORK`; invalid CIDRs
fail at startup. Do not copy a development override into the Cloud Run service.

No frontend build, container, Google account, or Secret Manager setup is needed.
Only clicking **Run Jev** makes a paid API request. Each run batches the page's
questions in one call; automatic retries are disabled. Editing text, loading an
example, and moving policy sliders do not call the API.

## Explore

- **Support:** department Choice and urgency Noul.
- **Reviews:** three independent Scores on descriptive 0–2 rubrics.
- **Trolley problem:** a two-option Choice between pulling the lever and doing
  nothing, with classic, reversed, and uncertain fictional scenarios. Compare
  probabilities, not moral correctness; no real action is taken.
- **Automation:** adjustable probability thresholds applied locally to the
  most recent result. No real tickets are routed.
- **LLM guardrails:** four independent Noul risk signals for prompt injection,
  prompt-leaking attempts, jailbreaks, and data exfiltration. Compare attack,
  indirect-injection, and benign examples, then adjust a local flag-for-review
  threshold. This simulates screening only; it never calls a downstream LLM or
  accesses private data, and low probabilities do not guarantee safety.

Each page includes editable input, examples, probability visualizations, the
returned confidence when available, request/response JSON, latency, and a
comparison with the previous successful run. Results retain the exact input
they evaluated and are marked out of date after edits.

Confidence summarizes the distribution, not a guarantee of accuracy. Noul has
no separate confidence field. Missing evidence can be an instructive failure:
inspect the probabilities rather than treating a Score as a fact.

### Try the LLM guardrails demo

Open <http://127.0.0.1:8000/demos/guardrails> locally, or select **Explore LLM
guardrails** from the homepage. Pages and examples are readable from any
network; running Jev still requires the authorized network and a configured
server-side key.

Choose one of seven examples or write your own fictional input, then click
**Run Jev**. The four preset criteria are visible under **What are we asking
Jev?** Each returns an independent probability: an input can trigger multiple
risks, and the probabilities need not sum to 100%. Prompt leaking here means
an attempt to extract hidden instructions, not proof that a prompt was leaked.

The policy starts at 70% and flags an input for review when **any** risk is
at or above the threshold. Moving the slider recalculates the simulated
decision from the last successful run without calling Jev again. Editing the
input marks those results stale until the next successful run. Compare an
attack with the benign security-discussion example to explore false positives.

No example instructions are executed: the demo does not call tools, retrieve
private files, or forward input to a downstream LLM. Input text is sent to
TypeSafe for evaluation, so do not paste real secrets or confidential data.
This is a teaching simulation, not production guardrail enforcement or a
detection benchmark; low scores do not prove safety.

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
development tooling. Uvicorn proxy-header rewriting is disabled so the
application can apply its own client-IP trust rules.

### Client IP trust boundary

Locally (including plain Docker), the app checks the socket peer and ignores
forwarding headers. Always use `--no-proxy-headers`; otherwise Uvicorn can
replace that address before the app sees it.

When Cloud Run sets `K_SERVICE`, the app uses the **rightmost** forwarded
address appended by direct Cloud Run ingress, never the untrusted leftmost
value supplied by a caller. Duplicate header fields are processed in order;
a missing or invalid final address fails closed. HTTPS forwarding is handled
in the app for same-origin validation. Don't manually set `K_SERVICE` on an
internet-exposed local container.

This trust model targets the direct Cloud Run endpoint. If you add another
load balancer, CDN, or reverse proxy, review and test its forwarding chain
before relying on the filter; do not simply select an earlier header entry.
After deploying, check the displayed IP from campus and off-campus, including
a request with a forged `X-Forwarded-For: 131.252.1.1`. The forged prefix must
not change the detected connecting IP or grant access.

This is an application-level filter, not a network firewall. Rejected requests
still reach the container and can incur Cloud Run charges, but do not call
TypeSafe. Page responses use `Cache-Control: private, no-store` so one visitor's
IP/access indicator is not cached for another. Reload after connecting a VPN.

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

`app.json` configures the build and hooks. The `precreate` hook verifies the
secret version and prepares runtime IAM; `postcreate` attaches the secret and
runtime identity and enables public invocation. The initial revision has no API key until that
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
the allowlisted source, builds the Dockerfile, and deploys a publicly accessible
service. No local `.env` values are uploaded or read by
the deployment script. Runtime defaults are 512 MiB, one CPU, zero minimum
instances, at most two instances per revision, concurrency eight, and a
60-second request timeout.

No deploy command has been run against a real Google Cloud project as part
of this setup. Your identity and project policy determine deployment access;
resolve any IAM/build permission errors rather than granting broad runtime
permissions.

### Open the app directly

Open the HTTPS service URL printed by Cloud Run in an ordinary browser.
No login, local proxy, or identity token is required. Deployments allow
unauthenticated invocation (`allUsers` with `roles/run.invoker`).

Anyone can read the pages, but **only clients in `131.252.0.0/16` can submit
experiments using your paid API key** by default. Off-campus clients need a
VPN whose internet traffic exits through that range. The key stays server-side,
but this app has no per-user quota or hard spending cap. Instance limits do
not cap TypeSafe charges. Rebuild and redeploy to apply this Python filter to
an existing service; changing IAM alone does not install it.

If you already deployed the earlier private version, enable direct access
without rebuilding (replace the project, region, and service as needed):

```bash
gcloud run services update jev-lab \
  --project="$GOOGLE_CLOUD_PROJECT" \
  --region="$GOOGLE_CLOUD_REGION" \
  --ingress=all
gcloud run services add-iam-policy-binding jev-lab \
  --project="$GOOGLE_CLOUD_PROJECT" \
  --region="$GOOGLE_CLOUD_REGION" \
  --member=allUsers \
  --role=roles/run.invoker
```

Organization policies may prohibit granting access to `allUsers`. If the
command is rejected, ask your project administrator about permitted public
access; don't treat a failed IAM update as a successful public deployment.
Same-origin checks remain enabled for direct HTTPS browser requests.

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
.venv/bin/python -m ruff format --check app.py demos.py tests
bash -n scripts/cloud-run.sh
node --check static/app.js
node --test tests/test_guardrails.js
```

Tests mock the SDK and gcloud and never spend API credits or modify cloud
resources. The guardrail UI tests use Node.js's built-in test runner with a
mocked DOM and API; no npm dependencies or frontend build are needed. They
check threshold boundaries, overlapping risk signals, no calls while editing
or moving sliders, stale-input handling, and failed-run result preservation.
Container smoke tests can use `/health` and the page routes without
calling Jev. Demo definitions and questions live in `demos.py`; the server,
templates, and plain JavaScript are in `app.py`,
`templates/`, and `static/`. The official `typesafe-sdk` validates and serializes
typed Jev responses. The server applies a 6,000-character input limit, a
20-second SDK timeout, and a 25-second overall call timeout. API errors are
shown explicitly without exposing upstream bodies or credentials.

## Cost and data safeguards

This is a teaching demo, not a production service with spending controls.
The local launch commands bind to all interfaces for access from another machine.
There is no user authentication, durable rate limit, or shared spending quota:
anyone in the configured allowed network can make calls using your paid API key.
Restrict development network access to trusted machines. Cloud Run deployments
are public for direct browser access, with TypeSafe calls restricted by the
application's CIDR check. Instance/concurrency limits constrain capacity,
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
