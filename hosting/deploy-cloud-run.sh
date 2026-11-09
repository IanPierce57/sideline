#!/bin/bash
# Puts Sideline online with Google Cloud Run (Nov 8, 2026). Run it in Google Cloud Shell
# (console.cloud.google.com, the >_ button at the top right) with this one line:
#
#   git clone https://github.com/IanPierce57/sideline.git && sideline/hosting/deploy-cloud-run.sh
#
# It asks for your keys without showing them, turns on Cloud Run, builds the server from
# this repo, and prints the link. Run it again to update the code or change a key.
set -euo pipefail
cd "$(dirname "$0")/.."
trap 'echo; echo "Something went wrong above. Copy the last few lines and send them to Claude."' ERR

PROJECT="$(gcloud config get-value project 2>/dev/null || true)"
if [ -z "$PROJECT" ]; then
  echo "No project is selected. At the top of the Google Cloud console, pick the project you"
  echo "use for the Sideline voices, then run this again."
  exit 1
fi
REGION="us-east1"
echo "Putting Sideline online in project \"$PROJECT\"."
echo

secret() {          # read a key without showing it on screen
  local value
  read -rsp "$1: " value </dev/tty
  echo >&2
  printf '%s' "$value"
}

ANTHROPIC="$(secret "Claude (Anthropic) API key, required. Paste it and press Return (it won't show)")"
if [[ "$ANTHROPIC" != sk-ant-* ]]; then
  echo "That doesn't look like a Claude key (they start with sk-ant-). Run this again."
  exit 1
fi
GOOGLE="$(secret "Google Text-to-Speech key, for the voices. Paste it, or just press Return to skip")"
GNEWS="$(secret "GNews key, for the news ticker. Paste it, or just press Return to skip")"
read -rp "Make up an access code for your professor (letters, numbers, and dashes): " CODE </dev/tty
if ! [[ "$CODE" =~ ^[A-Za-z0-9-]{4,40}$ ]]; then
  echo "Use 4 to 40 letters, numbers, or dashes. Run this again."
  exit 1
fi

VARS="^@^ANTHROPIC_API_KEY=$ANTHROPIC@SIDELINE_ACCESS_CODE=$CODE"
[ -n "$GOOGLE" ] && VARS="$VARS@GOOGLE_TTS_KEY=$GOOGLE"
[ -n "$GNEWS" ] && VARS="$VARS@GNEWS_API_KEY=$GNEWS"

echo
echo "Turning on Cloud Run and Cloud Build (the first time takes a minute)..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com --quiet

# Let Google's build robot build and store the server (needed in newer projects)
NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
gcloud projects add-iam-policy-binding "$PROJECT" --condition=None --quiet \
  --member="serviceAccount:${NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/run.builder" >/dev/null 2>&1 || true

echo "Building and starting Sideline (about 5 minutes)..."
# One copy at most (it keeps segments in progress in memory), 2 GB of memory, and the CPU stays
# on between requests so a segment keeps working while the page waits. It shuts down when idle.
gcloud run deploy sideline --source . --region "$REGION" --allow-unauthenticated \
  --memory 2Gi --cpu 1 --no-cpu-throttling --min-instances 0 --max-instances 1 \
  --set-env-vars "$VARS" --quiet

URL="$(gcloud run services describe sideline --region "$REGION" --format='value(status.url)')"
echo
echo "Sideline is online: $URL"
echo "Access code: $CODE"
echo
echo "To take it offline later:  gcloud run services delete sideline --region $REGION"
