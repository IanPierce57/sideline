#!/bin/bash
# Puts Sideline online with Google Cloud Run (Nov 8, 2026). Run it in Google Cloud Shell
# (console.cloud.google.com, the >_ button at the top right) with this one line:
#
#   git clone https://github.com/IanPierce57/sideline.git && sideline/hosting/deploy-cloud-run.sh
#
# You paste your .env file once (it never shows); it checks the keys, makes up an access code,
# turns on Cloud Run, builds the server from this repo, and prints the link. Run it again to update.
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

# The keys: paste the whole .env file once. Nothing you paste shows on screen.
ANTHROPIC="" GOOGLE="" GNEWS=""
take() {            # one line of the pasted .env: NAME=value
  local line="${1%$'\r'}" name value
  line="${line#export }"
  name="${line%%=*}"
  value="${line#*=}"
  value="${value//\"/}"
  value="${value//\'/}"
  value="${value//[[:space:]]/}"
  case "$name" in
    ANTHROPIC_API_KEY) ANTHROPIC="$value" ;;
    GOOGLE_TTS_KEY) GOOGLE="$value" ;;
    GNEWS_API_KEY) GNEWS="$value" ;;
  esac
}
# Once they work, the keys and the access code are saved privately in this Cloud Shell
# (only your Google account can see it), so running this again doesn't ask again.
SAVED="$HOME/.sideline-keys"
CODE=""
if [ -f "$SAVED" ]; then
  # shellcheck disable=SC1090
  . "$SAVED"
  echo "Using the keys you pasted before (saved privately in your Cloud Shell)."
else
  echo "YOUR KEYS: click on the TextEdit window with your .env file, press Cmd+A, then Cmd+C."
  echo "Then click back here in this black box, press Cmd+V, then Return."
  echo "(The keys won't show here. That's normal.)"
  trap 'stty echo </dev/tty 2>/dev/null' EXIT
  stty -echo </dev/tty
  line=""
  IFS= read -r line </dev/tty || true                                # waits for the paste
  take "$line"
  while IFS= read -r -t 2 line </dev/tty; do take "$line"; done      # the rest of the paste
  [ -n "$line" ] && take "$line"                                     # a last line with no Return
  stty echo </dev/tty
  echo
fi

if [[ "$ANTHROPIC" != sk-ant-* ]]; then
  echo "No Claude key found in what you pasted (the line that starts ANTHROPIC_API_KEY=sk-ant-)."
  echo "Run this again:  cd ~/sideline && hosting/deploy-cloud-run.sh"
  exit 1
fi
if [ "$(curl -s -o /dev/null -w '%{http_code}' https://api.anthropic.com/v1/models \
      -H "x-api-key: $ANTHROPIC" -H "anthropic-version: 2023-06-01")" != "200" ]; then
  echo "Claude didn't accept that key. Check it at console.anthropic.com, then run this again."
  exit 1
fi
echo "Claude key: works"
if [ -n "$GOOGLE" ]; then
  if [ "$(curl -s -o /dev/null -w '%{http_code}' "https://texttospeech.googleapis.com/v1/voices?languageCode=en-US&key=$GOOGLE")" = "200" ]; then
    echo "Google voices key: works"
  else
    echo "Google voices key: didn't work, so new segments will have subtitles only"
    GOOGLE=""
  fi
else
  echo "Google voices key: not found, so new segments will have subtitles only"
fi
[ -n "$GNEWS" ] && echo "GNews key: found" || echo "GNews key: not found, so the news ticker shows a placeholder"

# The access code for your professor: made up the first time, shown at the end
if [ -z "$CODE" ]; then
  WORDS=(tiger falcon comet rocket bison eagle maple harbor summit canyon river thunder)
  CODE="${WORDS[RANDOM % ${#WORDS[@]}]}-${WORDS[RANDOM % ${#WORDS[@]}]}-$((RANDOM % 900 + 100))"
fi
(umask 077 && printf 'ANTHROPIC=%q\nGOOGLE=%q\nGNEWS=%q\nCODE=%q\n' "$ANTHROPIC" "$GOOGLE" "$GNEWS" "$CODE" > "$SAVED")

VARS="^@^ANTHROPIC_API_KEY=$ANTHROPIC@SIDELINE_ACCESS_CODE=$CODE"
[ -n "$GOOGLE" ] && VARS="$VARS@GOOGLE_TTS_KEY=$GOOGLE"
[ -n "$GNEWS" ] && VARS="$VARS@GNEWS_API_KEY=$GNEWS"

echo
echo "Turning on Cloud Run and Cloud Build (the first time takes a minute)..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com --quiet

# Google's build robot needs permission to build and store the server (newer projects don't
# give it by default). Granting it is yours to do, once; this only checks.
NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
ROBOT="${NUMBER}-compute@developer.gserviceaccount.com"
if ! gcloud projects get-iam-policy "$PROJECT" --flatten='bindings[].members' \
     --filter="bindings.members:serviceAccount:$ROBOT" --format='value(bindings.role)' \
     | grep -qE 'roles/(run\.builder|editor|cloudbuild\.builds\.builder)'; then
  echo
  echo "ONE MORE STEP: Google's build robot needs permission to build Sideline. Paste this"
  echo "line, press Return, then run the setup again (cd ~/sideline && hosting/deploy-cloud-run.sh):"
  echo
  echo "  gcloud projects add-iam-policy-binding $PROJECT --member=serviceAccount:$ROBOT --role=roles/run.builder --condition=None --quiet"
  exit 1
fi

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
