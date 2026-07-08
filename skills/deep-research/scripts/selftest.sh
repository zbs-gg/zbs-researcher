#!/usr/bin/env bash
# Smoke test — calls NO paid APIs. Verifies the script loads and the free
# direct connectors (Hacker News + hiring) return content, plus HTML render.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/deep-research.py"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

echo "1/3 connector list…"
python3 "$SCRIPT" --list-connectors | python3 -c "import sys,json; n=len(json.load(sys.stdin)['connectors']); print(f'   {n} connectors'); sys.exit(0 if n>=10 else 1)"

echo "2/3 free channels (hackernews + hiring)…"
python3 "$SCRIPT" "context engineering" --output-dir "$OUT" --only hackernews,hiring --max-items 3 >/dev/null 2>&1
test -s "$OUT/hackernews.md" || { echo "   FAIL: hackernews.md empty"; exit 1; }
test -s "$OUT/hiring.md"     || { echo "   FAIL: hiring.md empty"; exit 1; }
echo "   hackernews.md + hiring.md non-empty"

echo "3/3 HTML render…"
python3 "$SCRIPT" --render-html "$OUT/hackernews.md" --html-out "$OUT/brief.html" >/dev/null 2>&1
test -s "$OUT/brief.html" || { echo "   FAIL: brief.html empty"; exit 1; }
grep -qE 'src=|href="http[^"]*\.css|@import' "$OUT/brief.html" && { echo "   FAIL: brief.html not self-contained"; exit 1; }
echo "   brief.html self-contained"

echo "OK — selftest passed (no paid APIs called)"
