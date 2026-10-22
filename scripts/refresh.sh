#!/usr/bin/env bash
# Rebuild and encrypt every client page.
# Usage: REPORT_PASSWORD_<SLUG>=... scripts/refresh.sh <data_dir>
#   <SLUG> is the client slug upper-cased with - turned into _ (auditor-alpha -> AUDITOR_ALPHA).
# Plaintext pages stay in <data_dir>/out and are never committed.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
DATA="$1"
python3 "$REPO/scripts/build.py" "$DATA" "$REPO" "$DATA/out"
command -v staticrypt >/dev/null || npm i -g staticrypt@3 >/dev/null 2>&1
SALT="$(python3 -c "import json;print(json.load(open('$REPO/clients.json'))['_salt'])")"
for f in "$DATA"/out/*.html; do
  slug="$(basename "$f" .html)"
  var="REPORT_PASSWORD_$(echo "$slug" | tr 'a-z-' 'A-Z_')"
  pw="${!var:-}"
  if [ -z "$pw" ]; then echo "missing $var, skipping $slug" >&2; continue; fi
  mkdir -p "$REPO/$slug"
  staticrypt "$f" -p "$pw" --salt "$SALT" --short --remember 30 \
    --template-title "My Growth report" \
    --template-instructions "Enter the password shared by My Growth." \
    --template-button "Open report" --template-placeholder "Password" \
    --template-color-primary "#2f6fde" --template-color-secondary "#f7f6f2" \
    -d "$DATA/enc" >/dev/null
  mv "$DATA/enc/$slug.html" "$REPO/$slug/index.html"
  echo "encrypted $slug"
done
