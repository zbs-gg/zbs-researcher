#!/usr/bin/env bash
# Smoke test — calls NO paid APIs. Verifies deterministic unit behavior,
# packaged workflow/docs, metadata agreement, Windows portability, secret
# hygiene, free direct connectors, HTML, the Tier-0 zero-key wizard path,
# and (when the claude CLI is present) plugin manifest validity.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
SCRIPT="$HERE/deep-research.py"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT
export PYTHONDONTWRITEBYTECODE=1

echo "1/10 deterministic unit suite…"
python3 -m unittest discover \
    -s "$ROOT/skills/deep-research/tests" -p 'test_*.py'

echo "2/10 project-local documentation contract…"
python3 - "$ROOT" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
files = {
    "skill": root / "skills/deep-research/SKILL.md",
    "readme": root / "README.md",
    "cli": root / "skills/deep-research/scripts/deep-research.py",
}
texts = {name: path.read_text(encoding="utf-8") for name, path in files.items()}

forbidden = ("~/research", "~/elle", "/Users/nikshilov", "$HOME/research", "${HOME}/research")
problems = []
for name, text in texts.items():
    for value in forbidden:
        if value in text:
            problems.append(f"{files[name]} contains forbidden default {value}")

skill = texts["skill"]
for artifact in (
    "research-plan.md",
    "_topic.txt",
    ".raw-run.claim",
    "manifest.json",
    "gemini-youtube.md",
    "grok-x.md",
    "openai-social.md",
    "perplexity-web.md",
    "hackernews.md",
    "hiring.md",
    "polymarket.md",
    "github.md",
    "reddit.md",
    "bluesky.md",
    "synthesis.md",
    "brief.html",
):
    if artifact not in skill:
        problems.append(f"skill output contract is missing {artifact}")

required_markers = {
    "skill": (
        "--allocate-run",
        '--output-dir "$RUN_DIR"',
        "complete skill-authored bundle",
        "raw-evidence runner",
        "--prepared-run",
        "--launch-cwd",
        "supplied during skill discovery on Codex",
        'SCRIPT="$SKILL_DIR/scripts/deep-research.py"',
    ),
    "readme": ("complete skill-authored bundle", "raw-evidence runner", "--project-root"),
    "cli": ("raw-evidence runner", "not a research plan or synthesis"),
}
for name, markers in required_markers.items():
    lowered = texts[name].lower()
    for marker in markers:
        if marker.lower() not in lowered:
            problems.append(f"{files[name]} is missing contract marker: {marker}")

ordered_skill_markers = (
    "## STEP 0 — RESEARCH PLAN",
    "--allocate-run",
    "research-plan.md",
    '--output-dir "$RUN_DIR"',
    "synthesis.md",
)
positions = [skill.find(marker) for marker in ordered_skill_markers]
if any(position < 0 for position in positions) or positions != sorted(positions):
    problems.append(
        "skill must order STEP 0 as allocation -> research-plan.md -> "
        "raw-evidence runner -> synthesis.md"
    )

if "${CLAUDE_PLUGIN_ROOT}" in skill:
    problems.append("skill commands must not depend on CLAUDE_PLUGIN_ROOT")

output_module = root / "skills/deep-research/scripts/output_paths.py"
if not output_module.is_file():
    problems.append(f"packaged runner is missing sibling module: {output_module}")

if problems:
    raise SystemExit("\n".join(problems))
print("   packaged docs describe one complete skill bundle and a raw CLI boundary")
PY

PROJECT="$OUT/project"
SECRETS="$OUT/no-secrets"
mkdir -p "$PROJECT" "$SECRETS"
TOPIC="selftest prepared workflow"
RUN_DIR="$(cd "$OUT" && python3 "$SCRIPT" "$TOPIC" \
    --allocate-run --launch-cwd "$PROJECT")"
topic_marker="$(<"$RUN_DIR/_topic.txt")"
test "$topic_marker" = "$TOPIC"
printf '# Selftest research plan\n' > "$RUN_DIR/research-plan.md"
# Unset OPENROUTER_API_KEY too: gemini now declares fallback_key="openrouter",
# so a host/CI exporting it would route --only gemini to a live billed
# OpenRouter call — silently, while the test still "passes". Keeping the step
# key-free preserves the "calls NO paid APIs" contract (R17 budget invariant).
env -u GEMINI_API_KEY -u OPENROUTER_API_KEY DEEP_RESEARCH_SECRETS_DIR="$SECRETS" \
    python3 "$SCRIPT" "$TOPIC" --output-dir "$RUN_DIR" \
    --prepared-run --launch-cwd "$PROJECT" --only gemini >/dev/null 2>&1
test -s "$RUN_DIR/research-plan.md"
test -s "$RUN_DIR/manifest.json"
runs=("$PROJECT"/research/deep-research-*)
test "${#runs[@]}" -eq 1
echo "   prepared plan-first handoff reused exactly one run"

echo "3/10 plugin metadata agreement…"
python3 - "$ROOT" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
plugin = json.loads((root / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
marketplace = json.loads((root / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
listed = next(item for item in marketplace["plugins"] if item["name"] == plugin["name"])
expected = "0.3.0"
if plugin["version"] != expected or listed["version"] != expected:
    raise SystemExit(
        f"version mismatch: plugin={plugin['version']} marketplace={listed['version']} expected={expected}"
    )
changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
if f"## {expected}" not in changelog or "project-local" not in changelog.lower():
    raise SystemExit("changelog is missing the 0.3.0 entry or the project-local behavior marker")
lowered_changelog = changelog.lower()
for marker in ("ambiguous or malformed", "--only", "--skip", "blank explicit paths"):
    if marker not in lowered_changelog:
        raise SystemExit(f"changelog is missing CLI compatibility marker: {marker}")
print(f"   plugin + marketplace = {expected}; changelog entry present")
PY

echo "4/10 Windows portability — banned POSIX-only symbols…"
# Guarded os.chmod is allowed (telegram session 0600 behind an os.name
# check); the symbols below have no Windows implementation and must never
# appear anywhere in scripts/ (connectors/ included).
if grep -rnE '\b(signal\.SIGALRM|os\.killpg|os\.setsid|fcntl|pty|termios|os\.fork)\b' \
    --include='*.py' --exclude-dir=__pycache__ "$HERE"; then
    echo "   FAIL: POSIX-only symbol found in scripts/ (breaks Windows)"; exit 1
fi
echo "   no POSIX-only symbols in scripts/ Python (guarded os.chmod allowed)"

echo "5/10 secret scan — no key material in tracked source…"
# Real key bodies are long runs of [A-Za-z0-9_-] right after the provider
# prefix; the read_key() regex literals in source put a "[" there instead,
# so they can never match. Any hit below is a leaked (or planted) key.
if grep -rnE '(sk-or-|xai-|gsk_|pplx-)[A-Za-z0-9_-]{20,}|sk-(proj-)?[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{30,}|[0-9]{6,}\|[A-Za-z0-9_-]{20,}' \
    --exclude-dir=__pycache__ \
    "$ROOT/skills" "$ROOT/hooks" "$ROOT/.claude-plugin"; then
    echo "   FAIL: key-material pattern found in tracked source"; exit 1
fi
echo "   no key-material patterns in skills/, hooks/, .claude-plugin/"

echo "6/10 connector list…"
python3 "$SCRIPT" --list-connectors | python3 -c "import sys,json; n=len(json.load(sys.stdin)['connectors']); print(f'   {n} connectors'); sys.exit(0 if n>=10 else 1)"

echo "7/10 free channels (hackernews + hiring)…"
RAW_OUT="$OUT/raw"
python3 "$SCRIPT" "context engineering" --output-dir "$RAW_OUT" --only hackernews,hiring --max-items 3 >/dev/null 2>&1
test -s "$RAW_OUT/hackernews.md" || { echo "   FAIL: hackernews.md empty"; exit 1; }
test -s "$RAW_OUT/hiring.md"     || { echo "   FAIL: hiring.md empty"; exit 1; }
echo "   hackernews.md + hiring.md non-empty"

echo "8/10 HTML render…"
python3 "$SCRIPT" --render-html "$RAW_OUT/hackernews.md" --html-out "$OUT/brief.html" >/dev/null 2>&1
test -s "$OUT/brief.html" || { echo "   FAIL: brief.html empty"; exit 1; }
grep -qE 'src=|href="http[^"]*\.css|@import' "$OUT/brief.html" && { echo "   FAIL: brief.html not self-contained"; exit 1; }
echo "   brief.html self-contained"

echo "9/10 Tier-0 wizard dry-run (zero keys)…"
# The scripted half of the onboarding wizard: a fresh install with NO keys
# must still detect state honestly, pass the doctor offline, and produce a
# real free-connector report + self-contained brief. Conversation ordering
# (pitch-inside-question, proof-before-key-ask) is the manual checklist in
# SKILL.md.
WIZ_OUT="$OUT/tier0-run"
WIZ_SECRETS="$OUT/tier0-secrets"
mkdir -p "$WIZ_SECRETS"
TIER0=(env -u GEMINI_API_KEY -u GROK_API_KEY -u OPENAI_API_KEY \
    -u PERPLEXITY_API_KEY -u OPENROUTER_API_KEY -u GROQ_API_KEY \
    -u SCRAPECREATORS_KEY -u BRAVE_API_KEY -u META_ADS_TOKEN \
    -u THREADS_ACCESS_TOKEN \
    -u PRODUCTHUNT_TOKEN -u APIFY_TOKEN -u TELEGRAM_API_ID -u TELEGRAM_API_HASH \
    DEEP_RESEARCH_SECRETS_DIR="$WIZ_SECRETS")
"${TIER0[@]}" python3 "$HERE/detect_state.py" | python3 -c '
import json, sys
state = json.load(sys.stdin)
providers = state.get("providers")
assert isinstance(providers, dict) and providers, f"bad providers: {providers!r}"
on = [name for name, flag in providers.items() if flag is not False]
assert not on, f"providers unexpectedly configured in isolated env: {on}"
assert state.get("telegram_session") is False, "telegram_session must be false"
assert state.get("wizard_done") is False, "wizard_done must be false"
print("   detect_state: valid JSON, all providers false")
'
"${TIER0[@]}" python3 "$SCRIPT" --diagnose >/dev/null
echo "   --diagnose exits 0 offline"
"${TIER0[@]}" python3 "$SCRIPT" "context engineering" --output-dir "$WIZ_OUT" \
    --only hackernews,hiring --max-items 3 >/dev/null 2>&1
test -s "$WIZ_OUT/hackernews.md" || { echo "   FAIL: tier-0 hackernews.md empty"; exit 1; }
test -s "$WIZ_OUT/hiring.md"     || { echo "   FAIL: tier-0 hiring.md empty"; exit 1; }
"${TIER0[@]}" python3 "$SCRIPT" --render-html "$WIZ_OUT/hackernews.md" \
    --html-out "$WIZ_OUT/brief.html" >/dev/null 2>&1
test -s "$WIZ_OUT/brief.html" || { echo "   FAIL: tier-0 brief.html empty"; exit 1; }
grep -qE 'src=|href="http[^"]*\.css|@import' "$WIZ_OUT/brief.html" \
    && { echo "   FAIL: tier-0 brief.html not self-contained"; exit 1; }
echo "   zero-key run produced a real report + self-contained brief"

echo "10/10 claude plugin validate…"
if command -v claude >/dev/null 2>&1; then
    (cd "$ROOT" && claude plugin validate .)
else
    echo "   SKIP (claude CLI not found)"
fi

echo "OK — selftest passed (no paid APIs called)"
