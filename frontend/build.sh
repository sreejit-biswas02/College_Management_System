#!/usr/bin/env sh
set -eu

# Build static output for Cloudflare Pages in frontend/dist/
# Usage: API_BASE_URL="https://your-api.onrender.com/api/v1" ./build.sh

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
DIST_DIR="$SCRIPT_DIR/dist"

API_URL="${API_BASE_URL:-http://127.0.0.1:8000/api/v1}"

if [ "${CF_PAGES:-0}" = "1" ] && [ -z "${API_BASE_URL:-}" ]; then
  echo "ERROR: API_BASE_URL must be set in Cloudflare Pages environment variables." >&2
  exit 1
fi

rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

cp "$SCRIPT_DIR/index.html" "$DIST_DIR/"
cp "$SCRIPT_DIR/_redirects" "$DIST_DIR/"
cp -R "$SCRIPT_DIR/css" "$DIST_DIR/css"
cp -R "$SCRIPT_DIR/js" "$DIST_DIR/js"
if [ -d "$SCRIPT_DIR/assets" ]; then
  cp -R "$SCRIPT_DIR/assets" "$DIST_DIR/assets"
fi

cat > "$DIST_DIR/js/runtime-config.js" <<EOF
// Generated at build time by frontend/build.sh
window.CMS_CONFIG = {
  API_BASE_URL: "${API_URL}",
};
EOF

echo "Static build complete in $DIST_DIR (API_BASE_URL=$API_URL)"
