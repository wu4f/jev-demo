#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: bash scripts/cloud-run.sh {prepare|attach|deploy}" >&2
  echo "Set GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_REGION, K_SERVICE," >&2
  echo "TYPESAFE_SECRET, and TYPESAFE_SECRET_VERSION. Never pass the API key." >&2
  exit 1
}

[[ $# == 1 ]] || usage
mode=$1
case "$mode" in
  prepare|attach|deploy) ;;
  *) usage ;;
esac

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
: "${GOOGLE_CLOUD_REGION:?Set GOOGLE_CLOUD_REGION}"
: "${K_SERVICE:?Set K_SERVICE (for example jev-lab)}"
: "${TYPESAFE_SECRET:?Set TYPESAFE_SECRET to an existing secret name, not an API key}"
: "${TYPESAFE_SECRET_VERSION:?Set TYPESAFE_SECRET_VERSION to a numeric version}"

if [[ ! "$K_SERVICE" =~ ^[a-z]([a-z0-9-]{0,47}[a-z0-9])?$ ]]; then
  echo "K_SERVICE must be a Cloud Run service name of 1-49 characters." >&2
  exit 1
fi
if [[ ! "$TYPESAFE_SECRET" =~ ^[a-zA-Z0-9_-]{1,255}$ ]]; then
  echo "TYPESAFE_SECRET must be a secret name in the selected project, not a resource path." >&2
  exit 1
fi
if [[ ! "$TYPESAFE_SECRET_VERSION" =~ ^[1-9][0-9]*$ ]]; then
  echo "Pin TYPESAFE_SECRET_VERSION to a positive integer; latest is not supported." >&2
  exit 1
fi

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# Stable, service-specific account IDs stay within IAM's 30-character limit.
account_id="jev-$(printf '%s' "$K_SERVICE" | sha256sum | cut -c1-20)"
account="${account_id}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"
secret_binding="TYPESAFE_API_KEY=${TYPESAFE_SECRET}:${TYPESAFE_SECRET_VERSION}"
model="${TYPESAFE_DEFAULT_MODEL:-jev-latest}"
proxy_origin="${JEV_PROXY_ORIGIN:-http://127.0.0.1:8080}"

prepare() {
  gcloud services enable \
    run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
    secretmanager.googleapis.com iam.googleapis.com \
    --project="$GOOGLE_CLOUD_PROJECT" --quiet

  state=$(gcloud secrets versions describe "$TYPESAFE_SECRET_VERSION" \
    --secret="$TYPESAFE_SECRET" --project="$GOOGLE_CLOUD_PROJECT" \
    --format='value(state)')
  if [[ "$state" != ENABLED ]]; then
    echo "The selected Secret Manager version is not enabled." >&2
    exit 1
  fi

  existing=$(gcloud iam service-accounts list --project="$GOOGLE_CLOUD_PROJECT" \
    --filter="email=${account}" --format='value(email)')
  if [[ -z "$existing" ]]; then
    gcloud iam service-accounts create "$account_id" \
      --display-name="Jev Lab runtime ($K_SERVICE)" \
      --project="$GOOGLE_CLOUD_PROJECT" --quiet
  fi
  gcloud secrets add-iam-policy-binding "$TYPESAFE_SECRET" \
    --member="serviceAccount:${account}" --role=roles/secretmanager.secretAccessor \
    --condition=None --project="$GOOGLE_CLOUD_PROJECT" --quiet >/dev/null
}

attach() {
  gcloud run services update "$K_SERVICE" \
    --project="$GOOGLE_CLOUD_PROJECT" --region="$GOOGLE_CLOUD_REGION" \
    --service-account="$account" --update-secrets="$secret_binding" \
    --max-instances=2 --concurrency=8 --timeout=60 --quiet
}

deploy() {
  prepare
  gcloud run deploy "$K_SERVICE" --source="$root" \
    --project="$GOOGLE_CLOUD_PROJECT" --region="$GOOGLE_CLOUD_REGION" \
    --service-account="$account" --update-secrets="$secret_binding" \
    --set-env-vars="TYPESAFE_DEFAULT_MODEL=${model},JEV_PROXY_ORIGIN=${proxy_origin}" \
    --no-allow-unauthenticated --port=8080 --memory=512Mi --cpu=1 \
    --min-instances=0 --max-instances=2 --concurrency=8 --timeout=60 --quiet
}

case "$mode" in
  prepare) prepare ;;
  attach) attach ;;
  deploy) deploy ;;
esac
