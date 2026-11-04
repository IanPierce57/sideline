#!/bin/bash
# set_key.sh: saves your Anthropic API key into .env without showing it on screen.
# A Mac pop-up box asks for the key; it's hidden as dots while you paste.
cd "$(dirname "$0")"

KEY="$(osascript \
  -e 'set reply to display dialog "Paste your Anthropic API key (it starts with sk-ant-), then click Save." default answer "" with hidden answer buttons {"Cancel", "Save"} default button "Save" with title "The Receipts"' \
  -e 'text returned of reply' 2>/dev/null)"

if [ $? -ne 0 ] || [ -z "$KEY" ]; then
  echo "Cancelled. Nothing was saved."
  exit 1
fi

# Remove any spaces or line breaks that came along with the paste.
KEY="$(printf '%s' "$KEY" | tr -d '[:space:]')"

if [[ ! "$KEY" =~ ^sk-ant-[A-Za-z0-9_-]{60,}$ ]]; then
  echo "That doesn't look like a full key, so nothing was saved. What the paste looked like:"
  echo "  - length: ${#KEY} characters (a full key is about 100)"
  if [[ "$KEY" == sk-ant-* ]]; then echo "  - starts with sk-ant-: yes"; else echo "  - starts with sk-ant-: NO"; fi
  ODD="$(printf '%s' "$KEY" | LC_ALL=C tr -d 'A-Za-z0-9_-' | LC_ALL=C tr -c '.*\n' '?' | fold -w1 | sort -u | tr -d '\n')"
  if [ -n "$ODD" ]; then echo "  - has characters a real key never has: $ODD  (dots or stars mean a shortened, masked copy)"; fi
  echo "Create a new key in the Console, click its Copy button, then run this again."
  exit 1
fi

printf '# Paste your Anthropic API key right after the = sign, with no spaces or quotes.\nANTHROPIC_API_KEY=%s\n' "$KEY" > .env
chmod 600 .env
echo "Saved. Your key is in .env (${#KEY} characters), which git never commits."
