#!/usr/bin/env sh
set -eu

# Build static output for Cloudflare Pages in frontend/dist/
# Usage: API_BASE_URL="https://your-api.onrender.com/api/v1" ./build.sh

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
DIST_DIR="$SCRIPT_DIR/dist"

CF_PAGES_VAL="${CF_PAGES:-0}"
if [ "$CF_PAGES_VAL" = "1" ]; then
  API_URL="${API_BASE_URL:-}"
  if [ -z "$API_URL" ]; then
    echo "ERROR: API_BASE_URL must be set in Cloudflare Pages." >&2
    exit 1
  fi
else
  if [ "${API_BASE_URL+x}" = "x" ]; then
    API_URL="$API_BASE_URL"
  else
    API_URL="http://127.0.0.1:8000/api/v1"
  fi
fi

SAFE_CONFIG_JS="$(
  API_URL="$API_URL" CF_PAGES_VAL="$CF_PAGES_VAL" python3 - <<'PY'
import json
import os
import sys
from urllib.parse import urlsplit

api_url = os.environ["API_URL"]
cf_pages = os.environ["CF_PAGES_VAL"] == "1"

if not api_url:
    sys.stderr.write("ERROR: API_BASE_URL must not be empty.\n")
    sys.exit(1)

if any(ch.isspace() for ch in api_url) or any(
    ch in api_url for ch in ('"', "'", "`", ";", "\\", "\x00")
):
    sys.stderr.write("ERROR: API_BASE_URL contains invalid characters.\n")
    sys.exit(1)

parsed = urlsplit(api_url)
if parsed.scheme not in {"http", "https"} or not parsed.netloc:
    sys.stderr.write("ERROR: API_BASE_URL must be a valid HTTP(S) URL.\n")
    sys.exit(1)

if parsed.username or parsed.password or parsed.fragment:
    sys.stderr.write("ERROR: API_BASE_URL must not contain credentials or fragments.\n")
    sys.exit(1)

if cf_pages and parsed.scheme != "https":
    sys.stderr.write("ERROR: Production API_BASE_URL must use https://.\n")
    sys.exit(1)

encoded_url = json.dumps(api_url)
print("// Generated at build time by frontend/build.sh")
print("window.CMS_CONFIG = {")
print(f"  API_BASE_URL: {encoded_url},")
print("};")
PY
)"

rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

cp "$SCRIPT_DIR/index.html" "$DIST_DIR/"
cp "$SCRIPT_DIR/_redirects" "$DIST_DIR/"
cp -R "$SCRIPT_DIR/css" "$DIST_DIR/css"
cp -R "$SCRIPT_DIR/js" "$DIST_DIR/js"
if [ -d "$SCRIPT_DIR/assets" ]; then
  cp -R "$SCRIPT_DIR/assets" "$DIST_DIR/assets"
fi

printf '%s\n' "$SAFE_CONFIG_JS" > "$DIST_DIR/js/runtime-config.js"

BUILD_VER="$(printf '%s' "${CF_PAGES_COMMIT_SHA:-$(date +%s)}" | tr -cd '[:alnum:]_-' | cut -c1-12)"
if [ -n "$BUILD_VER" ]; then
  BUILD_VER="$BUILD_VER" DIST_INDEX="$DIST_DIR/index.html" python3 - <<'PY'
import os
from pathlib import Path

index_path = Path(os.environ["DIST_INDEX"])
ver = os.environ["BUILD_VER"]
html = index_path.read_text(encoding="utf-8")
index_path.write_text(html.replace("?v=5", f"?v={ver}"), encoding="utf-8")
PY
fi

echo "Static build complete in $DIST_DIR (API_BASE_URL=$API_URL)"
