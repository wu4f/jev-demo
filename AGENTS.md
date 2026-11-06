# Working on Jev Lab

## App structure

- `app.py`: FastAPI routes, `.env` loading, input validation, origin checks, and
  server-side asynchronous TypeSafe SDK calls.
- `demos.py`: the five demo definitions, examples, and typed Choice/Score/Noul
  questions. Keep page descriptions and actual questions consistent here.
- `templates/`: Jinja pages. Static asset URLs must remain relative so the
  authenticated Cloud Run proxy can serve them.
- `static/app.js`: plain JavaScript for input editing, API calls, visualizations,
  previous-run comparison, and client-side decision thresholds.
- `static/style.css`: responsive styles; there is no frontend build step.
- `tests/test_app.py`: API and proxy behavior with a mocked TypeSafe SDK.
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
.venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Port 8000 intentionally supports access from another machine. Check for an
existing server before starting one; do not stop another session's process.
Local access is unauthenticated, so restrict network reachability.

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
evaluation requests return an explicit configuration error. Use these routes
for container smoke checks without spending credits. Also verify a custom
`PORT` when modifying the container startup command.

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
  invocation. Warn that visitors can use the paid key; capacity limits are not
  API spending quotas.

If adding runtime files, update the Dockerfile and both build-context
allowlists. `gcloud meta list-files-for-upload` checks the source upload without
deploying. A new Python import must also be copied into the runtime image.

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
- Retain exact origin checking. Cloud Run's trusted forwarding headers restore
  HTTPS; `JEV_PROXY_ORIGIN` permits one explicitly configured browser origin for
  an optional authenticated local proxy (not configured by default).
  Neither mechanism is a replacement for IAM or application authentication.
