#!/usr/bin/env bash
# Build and deploy the web app to Netlify.
#   NETLIFY_AUTH_TOKEN=... ./webapp/deploy.sh   (token optional when a proxy injects it)
# The site id is remembered in webapp/.netlify-site (create on first run).
set -euo pipefail
cd "$(dirname "$0")"
API=https://api.netlify.com/api/v1
AUTH=()
[ -n "${NETLIFY_AUTH_TOKEN:-}" ] && AUTH=(-H "Authorization: Bearer $NETLIFY_AUTH_TOKEN")
NAME=${NETLIFY_SITE_NAME:-ascend-quests-$(head -c3 /dev/urandom | od -An -tx1 | tr -d ' \n')}

[ -d node_modules ] || npm install --silent
python3 build.py

if [ ! -f .netlify-site ]; then
  curl -fsS "${AUTH[@]}" -H "Content-Type: application/json" -d "{\"name\":\"$NAME\"}" "$API/sites" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['id']); print(d['ssl_url'], file=sys.stderr)" > .netlify-site
fi
SITE=$(cat .netlify-site)

rm -f /tmp/ascend-dist.zip
(cd dist && zip -qr /tmp/ascend-dist.zip .)
DEPLOY=$(curl -fsS "${AUTH[@]}" -H "Content-Type: application/zip" --data-binary @/tmp/ascend-dist.zip "$API/sites/$SITE/deploys" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
for _ in $(seq 1 60); do
  STATE=$(curl -fsS "${AUTH[@]}" "$API/deploys/$DEPLOY" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['state'], d.get('ssl_url') or d.get('url'))")
  case "$STATE" in ready*) echo "live: ${STATE#ready }"; exit 0 ;; error*) echo "deploy failed: $STATE"; exit 1 ;; esac
  sleep 3
done
echo "deploy still processing: $DEPLOY"
