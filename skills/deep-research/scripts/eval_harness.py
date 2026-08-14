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
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "deep-research/2.0 (+https://github.com/zbs-gg/zbs-researcher)"
EVAL_LOG_FILENAME = "eval-log.jsonl"

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
BASELINE_PAGE_SIZE = 5
BASELINE_UNAVAILABLE_NO_KEY = "unavailable - no web-index key configured"

# --- Optional richer baseline: Parallel API (OPT-IN, never a prerequisite) ---
# The eval must run free. A configured key is NOT consent to spend it, so the
# paid baseline fires only on an explicit `--baseline parallel`; the default
# stays the free web-index pass even when the key is right there. That rule is
# the whole reason this stayed a stub for a release, and it still holds.
PARALLEL_API_ENV_VAR = "PARALLEL_API_KEY"
PARALLEL_BASE_URL = "https://api.parallel.ai/v1"
PARALLEL_DEEP_PROCESSORS = ("pro", "pro-fast", "ultra", "ultra-fast")
# Published list price per single run, for the cost line printed BEFORE the
# call. Informational only — the vendor's bill is the source of truth.
PARALLEL_PRICE_USD = {
    "lite": 0.005, "base": 0.01, "core": 0.025,
    "pro": 0.10, "pro-fast": 0.10,
    "ultra": 0.30, "ultra-fast": 0.30,
}
# Parallel currently documents 5-25 minutes for ultra. Keep a wider hard stop
# for queue/polling slop, but never wait forever.
PARALLEL_POLL_SECONDS = 15
PARALLEL_DEADLINE_SECONDS = 45 * 60
PARALLEL_PRICING_SOURCE = "https://docs.parallel.ai/getting-started/pricing"
PARALLEL_PROCESSOR_SOURCE = (
    "https://docs.parallel.ai/task-api/guides/choose-a-processor"
)
BASELINE_KINDS = ("web-index", "parallel")

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
    # YouTube counts for the SPOKEN content the youtube connector reads: a web
    # index gets titles and descriptions, never what was said. Same judgement
    # the provenance table makes when it files youtube under "partial"; the two
    # modules must not disagree about which sources an index can reach.
    "youtube": ("youtube",),
    "youtube.com": ("youtube",),
    "youtu.be": ("youtube",),
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


# A platform's own documentation is not that platform's conversation.
# help.x.com is a corporate publication a web index has in full; counting it
# as "reached X natively" would credit reading the manual as reading the room.
_CORPORATE_SUBDOMAINS = frozenset({
    "help", "support", "about", "blog", "docs", "developer", "developers",
    "business", "status", "legal", "policy", "press", "careers", "investor",
})


def _platforms_for(source):
    """Map one source token (connector name, domain, or URL) to the native
    platform(s) it reaches; () for plain web pages."""
    token = str(source or "").strip().lower()
    if "://" in token:
        token = urllib.parse.urlsplit(token).netloc
    token = token.split("/", 1)[0]
    if token.startswith("www."):
        token = token[4:]
    head = token.split(".", 1)[0]
    if "." in token and head in _CORPORATE_SUBDOMAINS:
        return ()
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
        # provenance_record writes the age under "freshness_hours"; keep the
        # older aliases as fallbacks so pre-existing manifests still score.
        age = record.get("freshness_hours")
        if age is None:
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
# Paid baseline — Parallel deep research (opt-in only)
# ---------------------------------------------------------------------------
def _read_parallel_key():
    """Same file-then-env contract as every other key in this project."""
    path = _default_secrets_dir() / "parallel-key.txt"
    if path.exists():
        raw = path.read_text().strip()
        match = re.search(r"[A-Za-z0-9_\-]{12,}", raw)
        if match:
            return match.group(0)
        if raw:
            return raw
    return os.environ.get(PARALLEL_API_ENV_VAR, "").strip()


def parallel_price_note(processor):
    """One human line about what the next call costs, printed BEFORE it runs."""
    price = PARALLEL_PRICE_USD.get(processor)
    if price is None:
        return f"parallel baseline: processor {processor!r} — price unknown"
    # Enough decimals to state the real number: at two places a $0.005 run
    # prints as "$0.01", which is a lie about money, however small.
    amount = f"{price:.3f}".rstrip("0").rstrip(".")
    return (
        f"parallel baseline: one {processor} run, list price ${amount} "
        "(vendor bills successful runs only)"
    )


def baseline_cost_disclosure(baseline, processor):
    """Durable cost context for one eval row; never pretend list price is bill."""
    if baseline != "parallel":
        return {
            "currency": "USD",
            "amount": None,
            "basis": "not reported for web-index baseline",
        }
    amount = PARALLEL_PRICE_USD.get(processor)
    return {
        "currency": "USD",
        "amount": amount,
        "basis": (
            "published list price per successful run"
            if amount is not None
            else "price unknown"
        ),
    }


def _post_json(url, payload, headers=None, timeout=60):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "User-Agent": UA,
            "Content-Type": "application/json",
            "Accept": "application/json",
            **(headers or {}),
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def _parallel_text(result):
    """Flatten Parallel's result into the markdown-ish text the scorer reads.

    Both output shapes are handled: `text` hands back a report with inline
    citations, `auto` hands back structured content plus a citations list. We
    append the citation URLs so a structured answer is not scored as evidence-
    free just because its links live in a sibling field.
    """
    if not isinstance(result, dict):
        return ""
    output = result.get("output")
    if isinstance(output, dict):
        content = output.get("content")
        basis = output.get("basis")
    else:
        content, basis = output, None
    parts = []
    if isinstance(content, str):
        parts.append(content)
    elif content is not None:
        parts.append(json.dumps(content, ensure_ascii=False, indent=2))
    for entry in basis or []:
        if not isinstance(entry, dict):
            continue
        for citation in entry.get("citations") or []:
            if not isinstance(citation, dict):
                continue
            url = citation.get("url")
            if not url:
                continue
            # The live API returns `excerpts` (a LIST). Reading only a singular
            # `excerpt` silently dropped every quote the opponent supplied and
            # scored them at zero depth — a rigged benchmark. Accept both.
            for excerpt in _citation_excerpts(citation):
                parts.append(f"- {url}\n  \"{excerpt}\"")
            if not _citation_excerpts(citation):
                parts.append(f"- {url}")
    return "\n".join(parts)


def _citation_excerpts(citation):
    """Quoted excerpts attached to one citation, whatever shape they arrive in.

    Parallel sends `excerpts: [...]`; a singular `excerpt` string is accepted
    too so neither spelling is silently ignored.
    """
    raw = citation.get("excerpts")
    if isinstance(raw, str):
        candidates = [raw]
    elif isinstance(raw, (list, tuple)):
        candidates = list(raw)
    else:
        candidates = []
    single = citation.get("excerpt")
    if isinstance(single, str):
        candidates.append(single)
    return [" ".join(str(c).split()) for c in candidates if str(c).strip()]


def _parallel_content_markdown(result):
    """Return only the human answer body, without synthesizing new claims."""
    if not isinstance(result, dict):
        return ""
    output = result.get("output")
    content = output.get("content") if isinstance(output, dict) else output
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    return json.dumps(content, ensure_ascii=False, indent=2)


def _parallel_citations(result):
    """Yield structured citations in provider order, preserving duplicates."""
    if not isinstance(result, dict) or not isinstance(result.get("output"), dict):
        return []
    citations = []
    for entry in result["output"].get("basis") or []:
        if not isinstance(entry, dict):
            continue
        citations.extend(
            citation for citation in (entry.get("citations") or [])
            if isinstance(citation, dict) and citation.get("url")
        )
    return citations


def normalize_parallel_evidence(result):
    """Create receipts showing exactly why each Parallel link did or did not
    affect a score. Structured citations are primary; additional inline answer
    links are retained so the receipt matches the scorer's complete input.
    """
    records = []
    for citation in _parallel_citations(result):
        excerpts = _citation_excerpts(citation)
        records.append({
            "url": str(citation.get("url")),
            "normalized_url": normalize_url(citation.get("url")),
            "excerpts": excerpts,
            "has_usable_excerpt": bool(excerpts),
            "source_shape": "structured_citation",
        })

    structured_urls = {record["normalized_url"] for record in records}
    for item in extract_evidence(_parallel_content_markdown(result)):
        normalized = normalize_url(item.get("url"))
        if normalized in structured_urls:
            continue
        records.append({
            "url": str(item.get("url")),
            "normalized_url": normalized,
            "excerpts": [],
            "has_usable_excerpt": bool(item.get("has_quote")),
            "source_shape": "inline_answer",
        })

    counted_urls = set()
    counted_platforms = set()
    for record in records:
        normalized = record["normalized_url"]
        has_quote = record["has_usable_excerpt"]
        if not has_quote:
            record["counted_depth"] = False
            record["exclusion_reason"] = "no_usable_excerpt"
        elif normalized in counted_urls:
            record["counted_depth"] = False
            record["exclusion_reason"] = "duplicate_url"
        else:
            record["counted_depth"] = True
            record["exclusion_reason"] = None
            counted_urls.add(normalized)

        platforms = sorted(set(_platforms_for(record["url"])))
        record["native_social_platforms"] = platforms
        newly_counted = [p for p in platforms if p not in counted_platforms]
        record["counted_social"] = bool(newly_counted)
        counted_platforms.update(platforms)
    return records


def _iso_utc(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _parallel_run_outcome(*, processor, state, reason, run_id, started_at,
                          finished_at, duration_seconds, raw_response=None,
                          answer_markdown="", evidence=None):
    evidence = list(evidence or [])
    scores = None
    if state == "completed":
        scores = {
            "depth": sum(1 for item in evidence if item["counted_depth"]),
            "freshness_hours": None,
            "social_coverage": len({
                platform
                for item in evidence
                for platform in item["native_social_platforms"]
            }),
        }
    amount = PARALLEL_PRICE_USD.get(processor)
    return {
        "schema_version": 1,
        "provider": "parallel",
        "processor": processor,
        "state": state,
        "available": state == "completed",
        "reason": reason,
        "run_id": run_id,
        "started_at": _iso_utc(started_at),
        "finished_at": _iso_utc(finished_at),
        "duration_seconds": round(max(float(duration_seconds), 0.0), 3),
        "cost": {
            "currency": "USD",
            "amount": amount,
            "basis": (
                f"published list price per successful Task API run for {processor}; "
                "actual vendor billing is authoritative"
                if amount is not None else "published price unavailable"
            ),
            "source": PARALLEL_PRICING_SOURCE,
            "processor_source": PARALLEL_PROCESSOR_SOURCE,
        },
        "scores": scores,
        "raw_response": raw_response,
        "answer_markdown": answer_markdown,
        "evidence": evidence,
    }


def run_parallel_task(question, processor="ultra", post=None, fetch=None,
                      sleep=None, deadline_seconds=None, now=None, utc_now=None,
                      announce=None):
    """Run one paid task and return its complete audit outcome.

    Unlike the compatibility wrapper below, this function retains provider
    identity, timestamps, the raw response, readable answer and evidence
    receipts. It still degrades to a serializable unavailable outcome.
    """
    now = now if now is not None else time.monotonic
    utc_now = utc_now if utc_now is not None else (
        lambda: datetime.now(timezone.utc)
    )
    started_at = utc_now()
    started_mono = now()

    def finish(state, reason, run_id=None, raw_response=None,
               answer_markdown="", evidence=None):
        return _parallel_run_outcome(
            processor=processor,
            state=state,
            reason=reason,
            run_id=run_id,
            started_at=started_at,
            finished_at=utc_now(),
            duration_seconds=now() - started_mono,
            raw_response=raw_response,
            answer_markdown=answer_markdown,
            evidence=evidence,
        )

    if processor not in PARALLEL_DEEP_PROCESSORS:
        return finish(
            "unavailable",
            "unavailable - parallel processor is not an allowed priced "
            f"deep-research choice ({processor})",
        )
    key = _read_parallel_key()
    if not key:
        return finish(
            "unavailable",
            "unavailable - no parallel key configured "
            f"(parallel-key.txt or {PARALLEL_API_ENV_VAR})",
        )
    post = post if post is not None else _post_json
    fetch = fetch if fetch is not None else _get_json
    sleep = sleep if sleep is not None else time.sleep
    announce = announce if announce is not None else (
        lambda message: print(message, file=sys.stderr)
    )
    deadline_seconds = (
        PARALLEL_DEADLINE_SECONDS if deadline_seconds is None else deadline_seconds
    )
    headers = {"x-api-key": key}

    announce(parallel_price_note(processor))
    try:
        created = post(
            f"{PARALLEL_BASE_URL}/tasks/runs",
            {
                "input": question,
                "processor": processor,
                "task_spec": {"output_schema": {"type": "text"}},
            },
            headers=headers,
        )
    except Exception as exc:  # noqa: BLE001
        return finish(
            "unavailable",
            f"unavailable - parallel run could not start ({type(exc).__name__})",
        )

    run_id = (created or {}).get("run_id") or (created or {}).get("id")
    if not run_id:
        return finish("unavailable", "unavailable - parallel returned no run id")

    stop_at = started_mono + deadline_seconds
    result = None
    while True:
        try:
            result = fetch(
                f"{PARALLEL_BASE_URL}/tasks/runs/{run_id}/result", headers=headers
            )
            break
        except Exception as exc:  # noqa: BLE001
            if now() >= stop_at:
                return finish(
                    "unavailable",
                    "unavailable - parallel did not finish within "
                    f"{int(deadline_seconds / 60)} min ({type(exc).__name__})",
                    run_id=run_id,
                )
            sleep(PARALLEL_POLL_SECONDS)

    answer = _parallel_text(result)
    if not answer.strip():
        return finish(
            "unavailable",
            "unavailable - parallel returned an empty result",
            run_id=run_id,
            raw_response=result,
        )
    evidence = normalize_parallel_evidence(result)
    return finish(
        "completed", None, run_id=run_id, raw_response=result,
        answer_markdown=answer, evidence=evidence,
    )


def run_parallel_baseline(question, processor="ultra", post=None, fetch=None,
                          sleep=None, deadline_seconds=None, now=None,
                          announce=None):
    """Run ONE Parallel deep-research task and score it on the same three axes.

    Returns the scores dict, or an honest "unavailable - ..." string. Never
    raises: a baseline that fell over must not take the Beast side down with
    it. The key travels in the x-api-key header only — never in a URL, never
    in a failure string.
    """
    outcome = run_parallel_task(
        question, processor=processor, post=post, fetch=fetch, sleep=sleep,
        deadline_seconds=deadline_seconds, now=now, announce=announce,
    )
    if outcome["state"] == "completed":
        return outcome["scores"]
    return outcome["reason"]


_PERSONAL_PATH_RE = re.compile(
    r"(?<!https:)(?<!http:)/(?:Users|home)/[^\s\"']+|"
    r"[A-Za-z]:\\Users\\[^\s\"']+"
)


def _sanitize_artifact(value, secrets=()):
    """Redact credentials and personal absolute paths from persisted data."""
    if isinstance(value, dict):
        return {str(k): _sanitize_artifact(v, secrets) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_artifact(v, secrets) for v in value]
    if not isinstance(value, str):
        return value
    clean = value
    for secret in secrets:
        if secret:
            clean = clean.replace(str(secret), "[REDACTED]")
    return _PERSONAL_PATH_RE.sub("[REDACTED_ABSOLUTE_PATH]", clean)


def _atomic_write_private(path, payload):
    """Atomically replace one artifact with a mode-0600 regular file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        os.chmod(path.parent, 0o700)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        os.chmod(temporary, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if os.name == "posix":
            os.chmod(path, 0o600)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _private_json(path, value):
    _atomic_write_private(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def persist_parallel_artifacts(outcome, artifact_dir):
    """Write one self-contained Parallel audit bundle and return only paths
    relative to that bundle. `parallel-outcome.json` is written last and acts
    as the bundle's commit marker after the other atomic files are durable.
    """
    artifact_dir = Path(artifact_dir).expanduser()
    artifacts = {
        "raw_response": "parallel-raw.json",
        "answer": "parallel-answer.md",
        "evidence": "parallel-evidence.json",
        "outcome": "parallel-outcome.json",
    }
    secrets = tuple(filter(None, (
        os.environ.get(PARALLEL_API_ENV_VAR, "").strip(),
        _read_parallel_key(),
    )))
    safe_raw = _sanitize_artifact(outcome.get("raw_response"), secrets)
    safe_answer = _sanitize_artifact(outcome.get("answer_markdown") or "", secrets)
    safe_evidence = _sanitize_artifact(outcome.get("evidence") or [], secrets)

    _private_json(artifact_dir / artifacts["raw_response"], safe_raw)
    _atomic_write_private(
        artifact_dir / artifacts["answer"],
        safe_answer.rstrip() + ("\n" if safe_answer.strip() else ""),
    )
    _private_json(
        artifact_dir / artifacts["evidence"],
        {
            "schema_version": 1,
            "evidence": safe_evidence,
            "counted_depth": sum(
                1 for item in safe_evidence if item.get("counted_depth")
            ),
            "counted_native_social_platforms": sorted({
                platform
                for item in safe_evidence
                for platform in item.get("native_social_platforms", [])
            }),
        },
    )
    public_outcome = {
        key: value for key, value in outcome.items()
        if key not in {"raw_response", "answer_markdown", "evidence"}
    }
    public_outcome["artifacts"] = {
        key: value for key, value in artifacts.items() if key != "outcome"
    }
    _private_json(
        artifact_dir / artifacts["outcome"],
        _sanitize_artifact(public_outcome, secrets),
    )
    return artifacts


# ---------------------------------------------------------------------------
# Comparison + eval log
# ---------------------------------------------------------------------------
def run_eval(question, beast_dir, fetch=None, baseline="web-index",
             processor="ultra", post=None, artifact_dir=None, sleep=None,
             now=None, utc_now=None, announce=None):
    """Score both sides; return the eval row {ts, question, beast, baseline}.

    `baseline` selects which opponent runs. It defaults to the FREE web-index
    pass; "parallel" is opt-in and spends money, so nothing but an explicit
    caller choice may select it.
    """
    baseline_run = None
    baseline_artifacts = None
    if artifact_dir is not None and baseline != "parallel":
        raise ValueError("artifact_dir is available only for the Parallel baseline")
    if baseline == "parallel" and artifact_dir is not None:
        outcome = run_parallel_task(
            question, processor=processor, post=post, fetch=fetch, sleep=sleep,
            now=now, utc_now=utc_now, announce=announce,
        )
        opponent = (
            outcome["scores"]
            if outcome["state"] == "completed"
            else outcome["reason"]
        )
        baseline_artifacts = persist_parallel_artifacts(outcome, artifact_dir)
        baseline_run = {
            key: outcome[key]
            for key in (
                "provider", "processor", "state", "available", "reason",
                "run_id", "started_at", "finished_at", "duration_seconds",
            )
        }
    elif baseline == "parallel":
        opponent = run_parallel_baseline(
            question, processor=processor, post=post, fetch=fetch
        )
    else:
        opponent = run_baseline(question, fetch=fetch)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "question": question,
        "baseline_kind": baseline,
        "baseline_processor": processor if baseline == "parallel" else None,
        "baseline_cost": baseline_cost_disclosure(baseline, processor),
        "beast": score_beast_dir(beast_dir),
        "baseline": opponent,
    }
    if baseline_run is not None:
        row["baseline_run"] = baseline_run
        row["baseline_artifacts"] = baseline_artifacts
    return row


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
    # Name the opponent that actually ran — a table headed "web-index" while a
    # paid Parallel run produced the numbers would misread at a glance.
    kind = row.get("baseline_kind") or "web-index"
    lines = [
        f"Eval — Beast vs {kind} baseline",
        f"question: {row['question']}",
        "",
        f"{'axis':<30}{'beast':>10}{kind:>12}",
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
    cost = row.get("baseline_cost")
    if kind == "parallel" and isinstance(cost, dict):
        amount = cost.get("amount")
        amount_text = "unknown" if amount is None else f"${amount:g}"
        lines.append(f"parallel list price: {amount_text} ({cost.get('basis')})")
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
    ap.add_argument(
        "--baseline", choices=BASELINE_KINDS, default="web-index",
        help="which opponent to run: 'web-index' is free (default); "
             "'parallel' SPENDS MONEY on the Parallel deep-research API and "
             "is never selected just because a key is configured",
    )
    ap.add_argument(
        "--processor", choices=PARALLEL_DEEP_PROCESSORS, default="ultra",
        help="Parallel processor for --baseline parallel (default: ultra)",
    )
    ap.add_argument(
        "--artifact-dir", default=None,
        help="private audit bundle directory for --baseline parallel: raw JSON, "
             "readable answer, evidence receipts, run/timing/cost metadata",
    )
    args = ap.parse_args(argv)

    beast_dir = Path(args.beast_dir).expanduser()
    if not beast_dir.is_dir():
        ap.error(f"--beast-dir is not a directory: {beast_dir}")
    if args.artifact_dir and args.baseline != "parallel":
        ap.error("--artifact-dir requires --baseline parallel")

    row = run_eval(
        args.question, beast_dir,
        baseline=args.baseline, processor=args.processor,
        artifact_dir=args.artifact_dir,
    )
    ledger = resolve_ledger_path(args.out, beast_dir)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    _append_jsonl_line(ledger, row)

    print(format_table(row))
    print(f"\neval row appended: {ledger}")
    if args.baseline != "parallel" and _read_parallel_key():
        print(
            "note: a Parallel key is configured but was NOT used — the eval "
            "stays free unless you pass --baseline parallel."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
