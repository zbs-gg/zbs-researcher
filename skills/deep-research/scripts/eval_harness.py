#!/usr/bin/env python3
"""Eval harness for investigate mode (R11): Beast vs a web-index baseline.

Runs the SAME question through two lenses and scores both on the user's own
data, three axes:

  depth            distinct primary threads that carry a quote AND a link
                   (dedup by normalized URL — a re-linked thread counts once)
  freshness_hours  median age of the items, in hours (None when unknown)
  social_coverage  distinct NATIVE social/community platforms reached
                   (x/twitter, telegram, reddit, threads, tiktok, instagram,
                   bluesky; plain web pages do not count)

The Beast side scores an EXISTING run directory (--beast-dir): the *.md
result files written by the investigate loop / --fire calls, plus the
manifest's sources and provenance freshness. The harness does not drive the
loop itself — it measures what a run produced.

The baseline side is a free web-index `site:` pass via the Brave Search API
(BRAVE_API_KEY or brave-key.txt in the secrets dir — same resolution as the
runner's KEYS["brave"]), standing in for "a web-index researcher". No key
configured -> the baseline row honestly reads "unavailable", the Beast side
still scores, nothing crashes, and no network I/O happens.

Every run appends one JSON row {ts, question, beast, baseline} to a local
eval-log.jsonl (in --out or the beast dir) so runs can be compared over time.

Stdlib only; Windows-safe; never logs key material or key-bearing URLs.

Usage:
    python3 eval_harness.py "<question>" --beast-dir DIR [--out FILE|DIR]
"""
import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "deep-research/2.0 (+https://github.com/zbs-gg/zbs-researcher)"
EVAL_LOG_FILENAME = "eval-log.jsonl"

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
BASELINE_PAGE_SIZE = 5
BASELINE_UNAVAILABLE_NO_KEY = "unavailable - no web-index key configured"

# --- Optional richer baseline: Parallel API (opt-in stub, NOT implemented) ---
# A key in PARALLEL_API_KEY signals the operator wants a richer paid baseline
# comparison someday. Deliberately unimplemented: the eval must run free, and
# a paid call may never become a prerequisite. When the env var is set, main()
# prints one honest note and still runs the free web-index baseline only.
PARALLEL_API_ENV_VAR = "PARALLEL_API_KEY"

# Native social/community platforms (the coverage axis). Keys are the tokens a
# source may arrive as — connector names, bare domains, or full URLs (hosts are
# extracted first). Anything unlisted is a plain web page and counts nothing.
_PLATFORM_TOKENS = {
    "grok": ("x",),
    "x": ("x",),
    "x.com": ("x",),
    "twitter": ("x",),
    "twitter.com": ("x",),
    "telegram": ("telegram",),
    "t.me": ("telegram",),
    "reddit": ("reddit",),
    "reddit.com": ("reddit",),
    "redd.it": ("reddit",),
    "threads": ("threads",),
    "threads.net": ("threads",),
    "threads.com": ("threads",),
    "tiktok": ("tiktok",),
    "tiktok.com": ("tiktok",),
    "instagram": ("instagram",),
    "instagram.com": ("instagram",),
    "tiktok-ig": ("tiktok", "instagram"),  # one connector, two platforms
    "bluesky": ("bluesky",),
    "bsky": ("bluesky",),
    "bsky.app": ("bluesky",),
}


# ---------------------------------------------------------------------------
# Scoring core — pure functions over parsed result sets (fully unit-tested)
# ---------------------------------------------------------------------------
_URL_RE = re.compile(r'https?://[^\s<>"\')\]]+')
# A "quote" is real voice next to a link: a blockquote line, an @author voice
# line (the github-issues comment format), or a quoted excerpt of >=10 chars.
_QUOTE_CHARS_RE = re.compile(r'["“][^"”]{10,}["”]')
_VOICE_RE = re.compile(r"^\s*(?:[-*]\s+)?(?:>\s+)?@[\w.\-]+[^:]{0,40}:\s*\S")
_BLOCKQUOTE_RE = re.compile(r"^\s*(?:[-*]\s+)?>\s+\S")


def _is_quote_line(line):
    return bool(
        _QUOTE_CHARS_RE.search(line)
        or _VOICE_RE.match(line)
        or _BLOCKQUOTE_RE.match(line)
    )


def extract_evidence(md_text):
    """Parse a markdown result file into [{url, has_quote}, ...].

    A link "has a quote" when a quote-shaped line sits in a small window
    around it (the line before through two lines after — the connectors put
    voice lines directly under the link line). Deliberately simple: this is a
    scorer, not a markdown parser.
    """
    lines = (md_text or "").splitlines()
    items = []
    for i, line in enumerate(lines):
        urls = _URL_RE.findall(line)
        if not urls:
            continue
        window = lines[max(0, i - 1): i + 3]
        has_quote = any(_is_quote_line(w) for w in window)
        for url in urls:
            items.append({"url": url.rstrip(".,;:!?"), "has_quote": has_quote})
    return items


def normalize_url(url):
    """Dedup key: scheme dropped, host lowercased minus www., trailing slash
    and fragment stripped — http/https/www spellings of one thread collapse."""
    parts = urllib.parse.urlsplit(str(url or "").strip())
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path.rstrip("/")
    return host + path + ("?" + parts.query if parts.query else "")


def score_depth(items):
    """Distinct primary threads backed by a quote (dedup by normalized URL).
    A link without voice around it is a pointer, not evidence — not counted."""
    return len({
        normalize_url(it["url"])
        for it in items
        if it.get("has_quote") and it.get("url")
    })


def score_freshness(ages_hours):
    """Median item age in hours; None when no age is known. Unknown ages are
    skipped, never zeroed — a missing timestamp must not fake freshness."""
    known = sorted(
        float(age) for age in (ages_hours or []) if isinstance(age, (int, float))
    )
    if not known:
        return None
    mid = len(known) // 2
    if len(known) % 2:
        return known[mid]
    return (known[mid - 1] + known[mid]) / 2.0


def _platforms_for(source):
    """Map one source token (connector name, domain, or URL) to the native
    platform(s) it reaches; () for plain web pages."""
    token = str(source or "").strip().lower()
    if "://" in token:
        token = urllib.parse.urlsplit(token).netloc
    token = token.split("/", 1)[0]
    if token.startswith("www."):
        token = token[4:]
    candidates = [token]
    if "." in token:  # subdomain hosts (old.reddit.com) match their tail
        candidates.append(".".join(token.split(".")[-2:]))
    for candidate in candidates:
        platforms = _PLATFORM_TOKENS.get(candidate)
        if platforms:
            return platforms
    return ()


def score_social_coverage(sources):
    """Count distinct NATIVE social/community platforms among the sources.
    x.com and twitter.com are one platform; a blog or news page is zero."""
    reached = set()
    for source in sources or []:
        reached.update(_platforms_for(source))
    return len(reached)


def score_run(result_files, sources, ages_hours=None):
    """Score one result set: markdown files -> depth, sources -> coverage,
    known item ages -> freshness. Returns the three-axis dict."""
    items = []
    for path in result_files:
        items.extend(extract_evidence(Path(path).read_text(encoding="utf-8")))
    return {
        "depth": score_depth(items),
        "freshness_hours": score_freshness(ages_hours),
        "social_coverage": score_social_coverage(sources),
    }


# ---------------------------------------------------------------------------
# Beast side — score an existing run directory
# ---------------------------------------------------------------------------
def _manifest_sources_and_ages(beast_dir):
    """Pull (sources, ages_hours) out of manifest.json.

    Sources are the channels that actually ran ok (an errored channel reached
    nothing); ages come from the manifest's provenance freshness values when
    the run recorded them. No manifest -> (None, None) and the caller falls
    back to the result-file names.
    """
    manifest_path = Path(beast_dir) / "manifest.json"
    if not manifest_path.exists():
        return None, None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None
    channels = manifest.get("channels") or {}
    sources = [
        name for name, record in channels.items()
        if isinstance(record, dict) and record.get("status") == "ok"
    ] or list(manifest.get("connectors_run") or [])
    provenance = manifest.get("provenance") or {}
    records = provenance.values() if isinstance(provenance, dict) else provenance
    ages = []
    for record in records:
        if not isinstance(record, dict):
            continue
        age = record.get("freshness", record.get("newest_item_age_hours"))
        if isinstance(age, (int, float)):
            ages.append(age)
    return sources, ages


def score_beast_dir(beast_dir):
    """Score a run directory: every *.md result file except the *.ERROR.md
    ones (an error is not evidence), sources + freshness from the manifest."""
    beast_dir = Path(beast_dir)
    files = sorted(
        p for p in beast_dir.glob("*.md") if not p.name.endswith(".ERROR.md")
    )
    sources, ages = _manifest_sources_and_ages(beast_dir)
    if sources is None:
        sources = [p.stem for p in files]
    return score_run(files, sources, ages_hours=ages)


# ---------------------------------------------------------------------------
# Baseline side — a free web-index `site:` pass (Brave Search)
# ---------------------------------------------------------------------------
def _default_secrets_dir():
    """Same resolution as the runner: DEEP_RESEARCH_SECRETS_DIR, else the
    neutral XDG config dir."""
    override = os.environ.get("DEEP_RESEARCH_SECRETS_DIR")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(base).expanduser() / "zbs-researcher" / "secrets"


def _read_brave_key():
    """Mirror the runner's KEYS["brave"] contract (file first, env fallback).
    Re-implemented locally on purpose: the runner's hyphenated filename cannot
    be imported by module name and this module stays import-clean standalone."""
    path = _default_secrets_dir() / "brave-key.txt"
    if path.exists():
        raw = path.read_text().strip()
        match = re.search(r"[A-Za-z0-9_\-]{12,}", raw)
        if match:
            return match.group(0)
        if raw:
            return raw
    return os.environ.get("BRAVE_API_KEY", "").strip()


def _get_json(url, headers=None, timeout=20):
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept": "application/json", **(headers or {})}
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read())


def _baseline_queries(question):
    """The question plain + `site:` variants aimed at the social surfaces a
    web-index researcher would try to reach through the index."""
    return [
        question,
        f"{question} site:twitter.com",
        f"{question} site:reddit.com",
        f"{question} site:news.ycombinator.com",
    ]


_RELATIVE_AGE_RE = re.compile(r"(\d+)\s*(minute|hour|day|week|month|year)s?\s+ago", re.I)
_AGE_UNIT_HOURS = {
    "minute": 1 / 60, "hour": 1.0, "day": 24.0,
    "week": 168.0, "month": 720.0, "year": 8760.0,
}


def _result_age_hours(result, now=None):
    """Age of one web result in hours: ISO `page_age` preferred, the relative
    `age` string ("3 days ago") second, None when the index gives neither."""
    now = now if now is not None else datetime.now(timezone.utc)
    page_age = str(result.get("page_age") or "").strip()
    if page_age:
        try:
            ts = datetime.fromisoformat(page_age)
        except ValueError:
            ts = None
        if ts is not None:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return max((now - ts).total_seconds() / 3600.0, 0.0)
    match = _RELATIVE_AGE_RE.search(str(result.get("age") or ""))
    if match:
        return float(match.group(1)) * _AGE_UNIT_HOURS[match.group(2).lower()]
    return None


def run_baseline(question, fetch=None):
    """Run the free web-index pass and score it on the same three axes.

    Returns the scores dict, or an honest "unavailable - ..." string when no
    key is configured (no network I/O then) or every query failed. A search
    snippet counts as the result's quote — that IS what the index hands you.
    Failure strings never echo the request URL (it carries no key for Brave,
    but the invariant is blanket: no URL material in error surfaces).
    """
    key = _read_brave_key()
    if not key:
        return BASELINE_UNAVAILABLE_NO_KEY
    fetch = fetch if fetch is not None else _get_json
    items, ages, urls, failures = [], [], [], []
    for query in _baseline_queries(question):
        url = BRAVE_ENDPOINT + "?" + urllib.parse.urlencode(
            {"q": query, "count": BASELINE_PAGE_SIZE}
        )
        try:
            data = fetch(url, headers={"X-Subscription-Token": key})
        except Exception as exc:  # noqa: BLE001 — one query down, others go on
            failures.append(type(exc).__name__)
            continue
        for result in (data.get("web") or {}).get("results") or []:
            result_url = result.get("url") or ""
            if not result_url:
                continue
            items.append({
                "url": result_url,
                "has_quote": bool((result.get("description") or "").strip()),
            })
            ages.append(_result_age_hours(result))
            urls.append(result_url)
    if not items and failures:
        return "unavailable - web-index queries failed (" + ", ".join(sorted(set(failures))) + ")"
    return {
        "depth": score_depth(items),
        "freshness_hours": score_freshness(ages),
        "social_coverage": score_social_coverage(urls),
    }


# ---------------------------------------------------------------------------
# Comparison + eval log
# ---------------------------------------------------------------------------
def run_eval(question, beast_dir, fetch=None):
    """Score both sides; return the eval row {ts, question, beast, baseline}."""
    return {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "question": question,
        "beast": score_beast_dir(beast_dir),
        "baseline": run_baseline(question, fetch=fetch),
    }


def _fmt(value):
    if value is None:
        return "unknown"
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


def format_table(row):
    """Compact three-axis comparison table for stdout."""
    beast = row["beast"]
    baseline = row["baseline"]
    base_scores = baseline if isinstance(baseline, dict) else None
    lines = [
        "Eval — Beast vs web-index baseline",
        f"question: {row['question']}",
        "",
        f"{'axis':<30}{'beast':>10}{'web-index':>12}",
    ]
    axes = [
        ("depth (quoted threads)", "depth"),
        ("freshness (median hours)", "freshness_hours"),
        ("social coverage (native)", "social_coverage"),
    ]
    for label, key in axes:
        base_value = _fmt(base_scores[key]) if base_scores is not None else "-"
        lines.append(f"{label:<30}{_fmt(beast[key]):>10}{base_value:>12}")
    if base_scores is None:
        lines.append("")
        lines.append(f"baseline: {baseline}")
    return "\n".join(lines)


def _append_jsonl_line(path, entry):
    """Append one JSON line; O_APPEND single-write mirrors signals.py's care."""
    line = (json.dumps(entry, ensure_ascii=False) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(descriptor, line)
    finally:
        os.close(descriptor)


def resolve_ledger_path(out_arg, beast_dir):
    """--out names the ledger file (*.jsonl) or a directory to hold it;
    default is eval-log.jsonl next to the scored run (public-repo-safe: the
    row lands where the run already lives, never in a personal home path)."""
    if out_arg:
        target = Path(out_arg).expanduser()
        if target.suffix == ".jsonl":
            return target
        return target / EVAL_LOG_FILENAME
    return Path(beast_dir) / EVAL_LOG_FILENAME


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Score a Beast run vs a free web-index baseline (three axes)."
    )
    ap.add_argument("question", help="the research question both sides answer")
    ap.add_argument(
        "--beast-dir", required=True,
        help="run directory to score (*.md result files + manifest.json)",
    )
    ap.add_argument(
        "--out", default=None,
        help="eval-log destination: a *.jsonl file or a directory "
             "(default: eval-log.jsonl inside --beast-dir)",
    )
    args = ap.parse_args(argv)

    beast_dir = Path(args.beast_dir).expanduser()
    if not beast_dir.is_dir():
        ap.error(f"--beast-dir is not a directory: {beast_dir}")

    row = run_eval(args.question, beast_dir)
    ledger = resolve_ledger_path(args.out, beast_dir)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    _append_jsonl_line(ledger, row)

    print(format_table(row))
    print(f"\neval row appended: {ledger}")
    if os.environ.get(PARALLEL_API_ENV_VAR, "").strip():
        print(
            "note: PARALLEL_API_KEY is set, but the Parallel richer baseline "
            "is not implemented yet — opt-in hook only, never required."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
