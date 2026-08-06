"""Coverage-provenance helper for the deep-research runner (R6, R7).

Answers one question per fired source: "could a web-index researcher have
reached this content?" — from a static per-connector reachability table plus
a freshness override for live-social sources (an X post 3h old exists nowhere
a crawler has been yet). provenance_record packages the answer with the query,
item count and fetch time into the record coverage-receipts render from: every
"a web index can't see this" marker in a report traces back to one of these
records, never to inference. Two honesty rules:

  1. Never over-claim un-reachability: an unknown source defaults to "yes"
     (web-reachable) — the delta we report is only what the table proves.
  2. A record is built from what actually happened (real item count, real
     fetch time); an empty result carries no freshness claim at all.

The coverage-receipts renderers (coverage_markers, coverage_summary,
render_coverage_section) turn a run manifest's accumulated records into the
report's Coverage section under the same rules: a "yes" record never yields
a marker, and a manifest with no provenance yields NO section — never a
fabricated one.

Pure classification + record-building + markdown rendering; stdlib only,
no network, Windows-safe.
"""
from datetime import datetime, timezone

# Static reachability table: source -> ("yes" | "partial" | "no", reason).
# "yes" = fully crawlable public web; "partial" = the native channel holds
# meaningfully more than any web index surfaces; "no" = no web footprint.
# Anything NOT listed here is treated as "yes" (rule 1 above).
_REACHABILITY = {
    "telegram": ("no",
                 "client-session Telegram communities leave no web footprint"),
    "grok": ("partial",
             "live X content — a web index sees only the indexed scraps"),
    "reddit": ("partial",
               "Arctic-Shift full archive vs the top-of-Google slice "
               "a web index surfaces"),
    "github": ("yes", "public GitHub content, fully web-indexed"),
    "github-issues": ("yes", "public GitHub issues, fully web-indexed"),
    "hackernews": ("yes", "public Hacker News threads, fully web-indexed"),
    "bluesky": ("yes", "public Bluesky posts, web-indexed"),
    "youtube": ("partial",
                "spoken content inside videos — a web index reads titles and "
                "descriptions, not what was actually said"),
    "gemini": ("yes", "LLM lens grounded in the public web index"),
    "perplexity": ("yes", "LLM lens grounded in the public web index"),
}

_UNKNOWN_REASON = ("unknown source — assumed web-reachable "
                   "(never over-claim un-reachability)")

# Live-social "partial" sources where a fresh item flips to "no": content this
# new predates any crawl. Telegram is already "no"; Reddit's "partial" is an
# archive-depth story, not a pre-index one, so it stays put.
_LIVE_SOCIAL = ("grok",)
PRE_INDEX_WINDOW_HOURS = 48


def _format_hours(hours):
    """3.0 -> "3", 3.5 -> "3.5" — keeps the reason readable."""
    if isinstance(hours, float) and hours == int(hours):
        hours = int(hours)
    return str(hours)


def web_index_reachable(source, newest_item_age_hours=None, self_sourced=False,
                        self_sourced_items=0, items=0):
    """Classify one source: ("yes"|"partial"|"no", human-readable reason).

    `self_sourced` says the run MANUFACTURED some of the evidence (transcribing
    a video's audio itself, say) — text that provably exists in no index. That
    is a fact about what we did, not a heuristic about a platform, so it
    outranks the table. But it only earns a flat "no" when it covers EVERY
    item: with 1 self-produced transcript among 5 results, calling the whole
    source unreachable would relabel four rows a web index can read perfectly
    well. A partial claim stays "partial" and says the real ratio.

    Otherwise applies the static table, then the freshness override: a
    live-social "partial" source whose newest item is under
    PRE_INDEX_WINDOW_HOURS old flips to "no" — that item is not yet in any web
    index. An unknown age (None) never triggers the override.
    """
    if self_sourced:
        produced = max(1, int(self_sourced_items or 0))
        total = max(produced, int(items or 0))
        if produced >= total:
            return "no", ("produced by this run (own transcription) — this "
                          "text exists in no web index")
        return "partial", (
            f"{produced} of {total} items produced by this run (own "
            "transcription) — that text exists in no web index; the rest is "
            "as reachable as the table says"
        )
    tag, reason = _REACHABILITY.get(source, ("yes", _UNKNOWN_REASON))
    if (
        tag == "partial"
        and source in _LIVE_SOCIAL
        and newest_item_age_hours is not None
        and newest_item_age_hours < PRE_INDEX_WINDOW_HOURS
    ):
        return "no", (f"posted {_format_hours(newest_item_age_hours)}h ago "
                      "— not yet web-indexed")
    return tag, reason


def provenance_record(source, query, items, newest_item_age_hours=None,
                      fetched_at=None, self_sourced=False,
                      self_sourced_items=0):
    """Build the truthful per-fire provenance record (pure, no network).

    `items` is the fired result — a list (counted) or an already-known int
    count. `fetched_at` is an ISO string, injectable for tests, defaulting to
    now (UTC). `freshness_hours` is None when the age is unknown or the
    result is empty — an empty run makes no freshness claim, so it cannot
    trigger the pre-index override either. `self_sourced` is set by channels
    that produced evidence themselves; an EMPTY result can never claim it.
    """
    count = items if isinstance(items, int) else len(items or [])
    freshness = newest_item_age_hours if count else None
    tag, reason = web_index_reachable(
        source, freshness,
        self_sourced=bool(self_sourced) and bool(count),
        self_sourced_items=self_sourced_items,
        items=count,
    )
    if fetched_at is None:
        fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "source": source,
        "query": query,
        "items": count,
        "fetched_at": fetched_at,
        "freshness_hours": freshness,
        "web_index_reachable": tag,
        "reason": reason,
    }


# Display names for coverage markers: grok is the X lens, so its marker names
# the platform a reader knows. Anything unlisted renders under its own name.
_DISPLAY = {"grok": "grok/X"}


def _display_name(source):
    return _DISPLAY.get(source, source or "?")


def _dedupe_by_source(provenance_list):
    """One record per source, last fire wins (mirrors the manifest's
    channels last-write-wins); first-seen order is preserved."""
    rows = {}
    for record in provenance_list or []:
        if isinstance(record, dict) and record.get("source"):
            rows[record["source"]] = record
    return list(rows.values())


def coverage_markers(provenance_list):
    """Human marker strings for the records a web index can NOT fully reach.

    Only "no"/"partial" records yield a marker — a "yes" record never does
    (rule 1: the delta we report is only what the records prove). The marker
    text is the record's own reason, verbatim, never re-inferred prose;
    identical repeated fires collapse to one marker. No records -> [].
    """
    markers, seen = [], set()
    for record in provenance_list or []:
        if not isinstance(record, dict):
            continue
        tag = record.get("web_index_reachable")
        if tag not in ("no", "partial"):
            continue
        reason = record.get("reason") or f"web-index reachability: {tag}"
        marker = f"{_display_name(record.get('source'))} — {reason}"
        if marker not in seen:
            seen.add(marker)
            markers.append(marker)
    return markers


def coverage_summary(provenance_list):
    """One honest line: how much of this run a web index could not reach.

    Counts DISTINCT sources (a source fired twice is still one source). A
    yes-only run says "0 of M" out loud instead of hiding it; the freshest
    known signal age is appended only when a record actually carries one.
    Empty input -> "".
    """
    rows = _dedupe_by_source(provenance_list)
    if not rows:
        return ""
    total = len(rows)
    unreached = sum(
        1 for r in rows if r.get("web_index_reachable") in ("no", "partial")
    )
    if not unreached:
        return (f"0 of {total} sources web-index-unreachable or partial — "
                "this run's evidence is web-index-reachable")
    line = f"{unreached} of {total} sources web-index-unreachable or partial"
    ages = [
        r["freshness_hours"]
        for r in provenance_list
        if isinstance(r, dict)
        and isinstance(r.get("freshness_hours"), (int, float))
    ]
    if ages:
        line += f"; freshest signal ~{_format_hours(min(ages))}h old"
    return line


def render_coverage_section(manifest):
    """The full markdown Coverage section from a run manifest dict, or ""
    when the manifest carries no provenance records — a run without real
    records gets NO section, never a fabricated one.

    Shape: heading, summary line, inline markers (unreachable sources only),
    then a per-source source|reachability|reason table covering EVERY fired
    source. Plain pipe-table markdown — the runner's markdown_to_html renders
    it with no external references, so brief.html stays self-contained.
    """
    prov = manifest.get("provenance") if isinstance(manifest, dict) else None
    if not isinstance(prov, list):
        return ""
    records = [r for r in prov if isinstance(r, dict)]
    if not records:
        return ""
    lines = [
        "## Coverage — what a web-index researcher would miss",
        "",
        coverage_summary(records),
        "",
    ]
    markers = coverage_markers(records)
    if markers:
        lines.extend(f"- {marker}" for marker in markers)
        lines.append("")
    lines.append("| source | reachability | reason |")
    lines.append("| --- | --- | --- |")
    for record in _dedupe_by_source(records):
        lines.append(
            f"| {_display_name(record.get('source'))} "
            f"| {record.get('web_index_reachable')} "
            f"| {record.get('reason')} |"
        )
    return "\n".join(lines)
