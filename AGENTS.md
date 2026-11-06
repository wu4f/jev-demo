# Working on Jev Lab

## App structure

- `app.py`: FastAPI routes, `.env` loading, client-IP allowlisting, origin checks, and
  server-side asynchronous TypeSafe SDK calls.
- `demos.py`: the four demo definitions, examples, and typed Choice/Score/Noul
  questions. Keep page descriptions and actual questions consistent here.
- `templates/`: Jinja pages. Keep static asset URLs relative to the request
  origin so direct Cloud Run and custom-domain access both work.
- `static/app.js`: plain JavaScript for input editing, API calls, visualizations,
  previous-run comparison, and client-side decision thresholds.
- `static/style.css`: responsive styles; there is no frontend build step.
- `tests/test_app.py`: API, IP filtering, and HTTPS origin behavior with a mocked
  TypeSafe SDK.
- `tests/test_deployment.py`: deployment scripts exercised with a fake gcloud.
- `Dockerfile`, `.dockerignore`, `.gcloudignore`: non-root runtime and
  allowlisted build/upload contexts.
- `app.json`: community Run on Google Cloud button prompts and lifecycle hooks.
- `scripts/cloud-run.sh`: `prepare`, `attach`, and `deploy` commands.

## Local development and checks

Use Python 3.10+ locally; the container uses Python 3.12.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 8000 --no-proxy-headers
```

Port 8000 intentionally supports access from another machine. Check for an
existing server before starting one; do not stop another session's process.
Local access is unauthenticated, so restrict network reachability.
The default allowed network is `131.252.0.0/16`. Pages remain public and show
the detected IP in green/red; TypeSafe calls outside the network return 403.
For loopback-only API testing, explicitly set `JEV_ALLOWED_NETWORK=127.0.0.0/8`
for that process. Do not weaken the deployment's default to make a local test pass.

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check app.py tests
bash -n scripts/cloud-run.sh
node --check static/app.js
```

Format changed Python files with Ruff. Keep tests focused on introduced
behavior. SDK and gcloud tests must remain mocked: ordinary checks must not
spend API credits or modify cloud resources.

```bash
docker build -t jev-lab .
docker run --rm -p 8001:8080 jev-lab
```

Without an injected key, `/health`, `/`, and all demo pages must work, while
evaluation requests return 403 outside the network or an explicit configuration
error inside it. Use these routes for container smoke checks without spending
credits. Also verify a custom `PORT` when modifying the container startup command.

## Secret handling and deployment

- Never read, print, commit, or bake the real `.env` into images. It contains
  the user's paid API key. `.env.example` contains placeholders only.
- Local `.env` loading must not override existing environment variables.
- Cloud Run injects a pinned Secret Manager version as `TYPESAFE_API_KEY`.
  This is native platform integration: do not add a Google SDK or service-account
  JSON key file merely to fetch the same secret at runtime.
- Deploy scripts receive secret **names and numeric versions**, not key values.
  The runtime account is service-specific and gets Secret Accessor on just the
  selected secret. Keep this least-privilege boundary.
- `app.json` runs `prepare` before service creation and `attach` afterward.
  The initial revision has no API key until attachment finishes.
  The CLI `deploy` path binds the secret in the initial deployment.
- The deploy button needs a published public repository; don't invent a Git
  remote or claim the button was deployed merely because local tests pass.
- Actual deployment changes cloud resources and can incur costs. Use the
  project, region, service, and secret explicitly chosen by the user.
- Deployment is intentionally public for direct browser access at the Cloud Run
  URL, as requested by the user. Both deployment paths must enable unauthenticated
  invocation. Only visitors in the app's allowed network can use the paid key;
  capacity limits are not API spending quotas.

If adding runtime files, update the Dockerfile and both build-context
allowlists. `gcloud meta list-files-for-upload` checks the source upload without
deploying. A new Python import must also be copied into the runtime image.

## Deployment target and custom domain

- Public repository: `https://github.com/wu4f/jev-demo`, default branch `main`.
- Cloud Run project: `pdx-cs-ai112`; region: `us-central1`; service: `jev-lab`.
- Custom domain mapping: `jev.oregonctf.org` routes to `jev-lab`.
- Authoritative DNS record: `jev.oregonctf.org. CNAME ghs.googlehosted.com.`
  The DNS zone uses `ns-cloud-d1.googledomains.com` through
  `ns-cloud-d4.googledomains.com`.
- Do not alter the separate `askcs.oregonctf.org` service or its DNS records.

The authenticated local proxy workflow was removed. Visitors open the Cloud Run
HTTPS URL or custom domain directly, without `gcloud run services proxy`, a
Google login, or an identity token. Both deployment paths enable unauthenticated
invocation (`allUsers` with `roles/run.invoker`) and ingress `all`. Do not
reintroduce IAM-protected invocation or a required local proxy.

Application-level network filtering, not Cloud Run IAM, gates paid TypeSafe
calls. Pages remain readable for denied visitors. Do not change that distinction
when adjusting deployment or DNS.

Keep shell commands on single lines in user-facing instructions: multiline
backslash continuations have caused copy/paste problems.

To rebuild an existing service while retaining its current Secret Manager
binding and runtime settings:

```bash
gcloud run deploy jev-lab --source=. --project=pdx-cs-ai112 --region=us-central1 --allow-unauthenticated --ingress=all
```

Run this from the repository directory. A Git push alone does not redeploy the
service. If gcloud reports `invalid_grant`, the user must refresh authentication
with `gcloud auth login` in their terminal before retrying; do not claim a failed
command changed the service.

Inspect custom-domain DNS requirements and certificate readiness with:

```bash
gcloud beta run domain-mappings describe --domain=jev.oregonctf.org --project=pdx-cs-ai112 --region=us-central1 --format="yaml(status.resourceRecords,status.conditions)"
```

Cloud Run domain mappings are Preview, supported in `us-central1`, and issue
Google-managed HTTPS certificates. Compare the returned `resourceRecords` with
authoritative DNS and public resolvers before changing records. A generic
"You must configure your DNS records" message can persist while certificate
issuance is pending even when the CNAME is correct. Check `DomainRoutable`,
`CertificateProvisioned`, and `Ready` separately. Provisioning typically takes
about 15 minutes but can take up to 24 hours; do not delete/recreate a correct
mapping just to restart issuance.

Do not claim the custom domain is ready until HTTPS and certificate status
have been checked. After domain or ingress changes, verify that the displayed
client IP and allowed/denied API behavior still match the actual visitor.

## Preserve learning and safety behavior

- Only explicit Run submissions call Jev; editing input, loading examples, and
  moving thresholds must not make API requests.
- Use typed SDK answers and preset server-side questions. Do not expose a
  generic arbitrary-question proxy by accident.
- Keep the 6,000-character input limit, bounded timeouts, disabled automatic
  retries, and sanitized error messages unless deliberately revising them.
- Do not log input text, API keys, or upstream bodies. Avoid SDK debug logs.
- Render student text and returned labels with `textContent`, never `innerHTML`.
- Keep results paired with their evaluated input. Edits mark results stale;
  failed requests must not look successful or replace results with fake data.
- Choice/Score confidence summarizes a distribution, not guaranteed accuracy.
  Noul returns a probability without a separate confidence field.
- Automation thresholds act on returned probabilities locally. They simulate
  routing; they never execute real customer actions.
- Retain exact same-origin checking for direct Cloud Run and custom-domain
  requests. The app restores HTTPS using Cloud Run's forwarding headers.
  Do not add a localhost browser-origin exception as a deployment requirement.
- Keep Uvicorn's proxy rewriting disabled (`--no-proxy-headers`). Local access
  checks the socket peer, ignoring forwarded headers. Direct Cloud Run ingress
  (`K_SERVICE` set by the platform) uses the rightmost appended forwarded IP,
  not a caller-supplied prefix. Missing/invalid addresses deny TypeSafe access.
  Reassess this trust model before adding any other proxy or load balancer.
- Use the same parsed IP/access result for the status banner and API enforcement.
  Never replace the server check with a disabled button. Keep pages readable
  when denied and their IP-specific responses private/no-store.
- Show the visitor's IP and access status, but never render the allowed CIDR
  in page text, embedded browser configuration, or API denial messages.
