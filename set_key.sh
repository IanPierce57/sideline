#!/bin/bash
# set_key.sh: saves an API key into .env without showing it on screen.
#   ./set_key.sh          your Anthropic key (Claude)
#   ./set_key.sh gnews    your GNews key (the news ticker; free at gnews.io)
#   ./set_key.sh google   your Google Cloud Text-to-Speech key (the voices)
# A Mac pop-up box asks for the key; it's hidden as dots while you paste.
# Other keys already in .env are left alone.
cd "$(dirname "$0")"

WHICH="${1:-anthropic}"
if [ "$WHICH" = "gnews" ]; then
  NAME="GNEWS_API_KEY"; LABEL="GNews"; PATTERN='^[A-Za-z0-9]{20,64}$'; HINT="about 32 letters and numbers"
elif [ "$WHICH" = "google" ]; then
  NAME="GOOGLE_TTS_KEY"; LABEL="Google Cloud"; PATTERN='^AIza[0-9A-Za-z_-]{35}$'; HINT="it starts with AIza and is 39 characters"
else
  NAME="ANTHROPIC_API_KEY"; LABEL="Anthropic"; PATTERN='^sk-ant-[A-Za-z0-9_-]{60,}$'; HINT="it starts with sk-ant- and is about 100 characters"
fi

KEY="$(osascript \
  -e "set reply to display dialog \"Paste your $LABEL API key, then click Save.\" default answer \"\" with hidden answer buttons {\"Cancel\", \"Save\"} default button \"Save\" with title \"Sideline\"" \
  -e 'text returned of reply' 2>/dev/null)"

if [ $? -ne 0 ] || [ -z "$KEY" ]; then
  echo "Cancelled. Nothing was saved."
  exit 1
fi

# Remove any spaces or line breaks that came along with the paste.
KEY="$(printf '%s' "$KEY" | tr -d '[:space:]')"

if [[ ! "$KEY" =~ $PATTERN ]]; then
  echo "That doesn't look like a full $LABEL key ($HINT), so nothing was saved."
  echo "  - length: ${#KEY} characters"
  echo "Copy it again from the $LABEL website, then run this again."
  exit 1
fi

# Replace this key's line in .env (or add it), keeping every other line.
touch .env
grep -v "^$NAME=" .env > .env.tmp || true
printf '%s=%s\n' "$NAME" "$KEY" >> .env.tmp
mv .env.tmp .env
chmod 600 .env
echo "Saved. Your $LABEL key is in .env (${#KEY} characters), which git never commits."
