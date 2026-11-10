#!/usr/bin/env bash
# Build the web app and publish it to the gh-pages branch (GitHub Pages).
# Live at https://<owner>.github.io/<repo>/ a minute or two after it runs.
set -euo pipefail
cd "$(dirname "$0")"
[ -d node_modules ] || npm install --silent
python3 build.py

REMOTE=$(git -C .. remote get-url origin)
SRC=$(git -C .. rev-parse --abbrev-ref HEAD)@$(git -C .. rev-parse --short HEAD)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
cp -r dist/. "$TMP/"
rm -f "$TMP/harness.html"
touch "$TMP/.nojekyll"          # serve files as-is (no Jekyll processing)

cd "$TMP"
git init -q -b gh-pages
git add -A
git -c user.name="$(git -C "$OLDPWD/.." log -1 --format=%an)" -c user.email="$(git -C "$OLDPWD/.." log -1 --format=%ae)" \
  commit -q -m "Publish Ascend web app from $SRC"
git push -f "$REMOTE" gh-pages
echo "Published. GitHub Pages will update in a minute or two."
