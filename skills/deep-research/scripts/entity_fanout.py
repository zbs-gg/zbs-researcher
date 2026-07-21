#!/usr/bin/env python3
"""entity_fanout.py — entity-fan-out deep research mode.

See docs/plans/2026-07-21-002-feat-entity-fanout-deep-mode-plan.md.

The single-query engine sends ONE blanket query per channel. That is broad
scan. This mode does deep research: (1) ENUMERATE the top-N entities for a
topic, (2) FAN OUT per entity across every selected channel, (3) AGGREGATE an
entity x channel dossier matrix, (4) hand the matrix to the agent to SYNTHESIZE
a landscape.

Reuse, don't rewrite (R11): this module reuses deep-research.py's registry,
channel_* callables, rank_items, gh_api, get_json and the arctic-shift helpers
through attach_runner() late-binding. deep-research.py has a hyphen in its
filename and is loaded both as a script and via importlib in tests, so a plain
`import` back into it is impossible — the connectors package solves this the
same way (see connectors/__init__.py). Lookups happen per call (late binding),
so tests that attach a fake runner dict are honored here.

Invariants (match the rest of the tool):
  - stdlib only; Windows-safe: concurrent.futures.ThreadPoolExecutor, no
    signal.SIGALRM / os.killpg / fcntl / pty / os.fork;
  - free channels run with zero paid keys; a failed (entity, channel) cell
    writes <channel>.ERROR.md and never aborts the matrix;
  - paid lenses only fire on the top-K entities (hybrid) and never exceed the
    paid budget without opt-in; no paid call is ever made without a key.
"""
import json
import re
import time
import urllib.parse
from pathlib import Path


# ---------------------------------------------------------------------------
# Runner injection (late binding; mirrors connectors/__init__.py)
# ---------------------------------------------------------------------------
_RUNNER = None


def attach_runner(runner_globals):
    """Register the live globals dict of the deep-research runner module."""
    global _RUNNER
    _RUNNER = runner_globals


def _r(name):
    """Resolve a runner helper at call time (late binding)."""
    if _RUNNER is None:
        raise RuntimeError(
            "entity_fanout is not wired: deep-research.py must call "
            "entity_fanout.attach_runner(globals()) before the mode runs"
        )
    return _RUNNER[name]


# ---------------------------------------------------------------------------
# Tiers, defaults, caps
# ---------------------------------------------------------------------------
# Free channels fan out on ALL entities. github repo stars/velocity is NOT a
# per-entity call — enumeration IS github-by-stars, so each entity already
# carries its repo facet (U0 spike: a bare per-entity github query mostly
# duplicates the enumeration and, for short names like "Zep", collides with
# zephyr / zeppelin). github-issues gives distinct per-entity user voice.
FREE_ENTITY_CHANNELS = ("hackernews", "github-issues", "reddit", "bluesky")
# Paid LLM lenses fan out on the top-K entities only (hybrid), budget-gated.
PAID_LENSES = ("grok", "gemini", "perplexity")

DEFAULT_N = 50
DEFAULT_K = 10
DEFAULT_CONCURRENCY = 6
HARD_N_CAP = 200
HARD_K_CAP = 200
HARD_CONCURRENCY_CAP = 16
# A free channel whose ERROR fraction exceeds this marks the whole run degraded
# (KTD7) so a rate-limit-hollow matrix is never presented as "complete".
FILL_RATE_DEGRADE_THRESHOLD = 0.5

# How many confidently topic-matching repos GitHub must yield before a topic is
# treated as repo-shaped. Below this, the topic is product/people-shaped and the
# LLM enumeration lens becomes required for good coverage (KTD2/R1).
REPO_SHAPED_MIN = 4

# Small curated seed alias map (normalized keys -> canonical normalized name).
# Augmented at enumeration time by LLM-derived aliases when a lens runs; without
# a lens, dedup is normalized-name-only and the claim is "normalized-name
# deduped", not "canonical" (KTD2).
SEED_ALIASES = {
    "memgpt": "letta",
    "gptresearcher": "gpt-researcher",
    "gpt-researcher": "gptresearcher",
}


# ---------------------------------------------------------------------------
# Name normalization + dedup
# ---------------------------------------------------------------------------
def normalize_name(name, alias_map=None):
    """Fold a raw entity/repo name to a dedup key.

    Lowercase, drop an owner/ prefix, strip non-alphanumerics, then apply the
    alias map (seed + LLM-derived). "mem0ai/Mem0" and "Mem0" -> "mem0";
    "MemGPT" -> "letta" via the seed map.
    """
    n = (name or "").strip().lower()
    if "/" in n:
        n = n.rsplit("/", 1)[-1]
    n = re.sub(r"[^a-z0-9]+", "", n)
    if not n:
        return ""
    amap = alias_map if alias_map is not None else SEED_ALIASES
    # single hop is enough for our maps; guard against a->b->a cycles
    seen = set()
    while n in amap and n not in seen:
        seen.add(n)
        n = amap[n]
    return n


def _display_name(full_name):
    """Human-facing entity label from a repo full_name or raw name."""
    raw = (full_name or "").strip()
    if "/" in raw:
        return raw.rsplit("/", 1)[-1]
    return raw


def entity_slug(name):
    """Filesystem-safe per-entity directory slug (KTD3).

    Lowercase, non-alphanumerics -> '-', collapse, bounded length — so entity
    names like "owner/repo" or "C++" are safe path components.
    """
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    if not s:
        return "entity"
    return s[:60].rstrip("-") or "entity"


# ---------------------------------------------------------------------------
# Enumeration sources (each degrades independently — R1)
# ---------------------------------------------------------------------------
def _enum_github(topic, n):
    """Free source: GitHub top-repos-by-stars — already a ranked entity list."""
    gh_api = _r("gh_api")
    data = gh_api(
        "search/repositories?"
        + urllib.parse.urlencode({"q": topic, "sort": "stars", "per_page": min(max(n, 1), 100)})
    )
    ents = []
    for it in data.get("items", [])[:n]:
        full = it.get("full_name") or ""
        if not full:
            continue
        ents.append(
            {
                "name": _display_name(full),
                "type": "repo",
                "repo": full,
                "stars": int(it.get("stargazers_count") or 0),
                "pushed": (it.get("pushed_at") or "")[:10],
                "url": it.get("html_url") or "",
                "desc": (it.get("description") or "").strip(),
                "sources": ["github"],
            }
        )
    return ents


def _hn_search(topic, pool=50):
    """Raw HN Algolia story hits for the topic (reuses the runner's get_json)."""
    get_json = _r("get_json")
    url = "https://hn.algolia.com/api/v1/search?" + urllib.parse.urlencode(
        {"query": topic, "tags": "story", "hitsPerPage": pool}
    )
    return get_json(url, timeout=20).get("hits", [])


_SHOW_HN_RE = re.compile(r"show hn:\s*([^\-–—:(]+)", re.IGNORECASE)


def _enum_hn(topic):
    """Free source: HN mentions.

    Two roles: (a) name discovery via the 'Show HN: <Name> — ...' pattern;
    (b) a corpus of story titles used later to boost an entity's rank by how
    often it is mentioned. Returns (candidate_names, titles).
    """
    hits = _hn_search(topic)
    titles = [(h.get("title") or h.get("story_title") or "") for h in hits]
    candidates = []
    for t in titles:
        m = _SHOW_HN_RE.search(t)
        if m:
            name = m.group(1).strip()
            # keep short, name-like phrases only (avoid whole sentences)
            if name and len(name) <= 40 and len(name.split()) <= 4:
                candidates.append(name)
    return candidates, titles


def _llm_enum_prompt(topic, n):
    return (
        f"List the top {n} most important, widely-used {topic} — the actual "
        "named projects, products, tools, systems, and companies. Give the "
        "canonical name of each, most important first. Names only."
    )


def _enum_llm(topic, n, keys, tmpdir):
    """Optional/required LLM enumeration lens (KTD2).

    Reuses a lens channel_* function (no new vendor plumbing) with a list-style
    query, then extracts candidate names from the returned text. Picks the
    first lens whose key (direct or the shared openrouter fallback) is present.
    Returns (candidate_names, lens_name) or ([], None) when no lens is available.
    """
    lens = _pick_enum_lens(keys)
    if not lens:
        return [], None
    fn = _r("channel_" + lens)
    out = Path(tmpdir) / f"_enum_{lens}.md"
    try:
        fn(_llm_enum_prompt(topic, n), out, n)
        text = out.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 — enumeration lens failure degrades to no-LLM
        return [], None
    return _parse_entity_names(text), lens


def _pick_enum_lens(keys):
    """Which lens can run enumeration: a direct key, else the openrouter
    fallback (perplexity/gemini/grok all route through it)."""
    for lens in ("perplexity", "gemini", "grok"):
        if keys.get(lens):
            return lens
    if keys.get("openrouter"):
        return "perplexity"
    return None


_NAME_LINE_RES = (
    re.compile(r"^\s*\d+[.)]\s*\*{0,2}([^*\n:—–\-]+)"),   # "1. Name" / "1) **Name**"
    re.compile(r"^\s*[-*]\s*\*{0,2}([^*\n:—–]+)"),        # "- Name" / "* **Name**"
    re.compile(r"\*\*([^*\n]+)\*\*"),                       # **Name** anywhere
    re.compile(r"`([^`\n]+)`"),                             # `name`
)


def _parse_entity_names(text):
    """Tolerant extraction of candidate entity names from lens prose."""
    names, seen = [], set()
    for line in (text or "").splitlines():
        for rx in _NAME_LINE_RES:
            m = rx.search(line)
            if not m:
                continue
            name = m.group(1).strip().strip("*`").strip()
            name = re.split(r"\s[—–-]\s|:", name, maxsplit=1)[0].strip()
            if not name or len(name) > 40 or len(name.split()) > 5:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            names.append(name)
            break
    return names


# ---------------------------------------------------------------------------
# Merge / dedup / rank
# ---------------------------------------------------------------------------
def _topic_is_repo_shaped(gh_entities, topic):
    """True when GitHub yielded enough confidently topic-matching repos.

    Below the threshold the topic is product/people-shaped (leaders have no
    ranking repo) and the LLM lens becomes required for good coverage (KTD2).
    """
    relevance_score = _r("relevance_score")
    floor = _r("RELEVANCE_FLOOR")
    strong = 0
    for e in gh_entities:
        blob = f"{e.get('name','')} {e.get('desc','')}"
        if relevance_score(blob, topic) >= floor:
            strong += 1
    return strong >= REPO_SHAPED_MIN


def _blended_score(ent, titles):
    """Rank score: stars (log) + HN mentions (log) + LLM rank bonus."""
    engagement_score = _r("engagement_score")
    stars = ent.get("stars") or 0
    score = 2.0 * engagement_score(stars)
    name_l = (ent.get("name") or "").lower()
    if name_l and titles:
        mentions = sum(1 for t in titles if name_l in (t or "").lower())
        ent["hn_mentions"] = mentions
        score += 1.0 * engagement_score(mentions)
    llm_rank = ent.get("_llm_rank")
    if llm_rank is not None:
        score += 1.5  # simple, bounded LLM-presence bonus
    return score


def enumerate_entities(topic, n=DEFAULT_N, keys=None, *, tmpdir=None):
    """Merge free sources (+ optional/required LLM) into a ranked entity list.

    Each source degrades independently: a failure is recorded in `sources` and
    skipped — enumeration proceeds on survivors and zero entities is a clean
    empty result, never an exception (R1). Dedup is by normalized name + alias
    map; without an LLM lens, dedup is normalized-name-only and `coverage`
    carries the repo-shaped-only caveat for non-repo topics.

    Returns a dict:
      {topic, entities: [entity...], sources: {github, hn, llm}, coverage}
    where each entity is
      {name, type, rank, sources, aliases, repo?, stars?, pushed?, url?, desc?}
    """
    keys = keys or {}
    n = max(1, min(int(n), HARD_N_CAP))
    tmpdir = tmpdir or "."
    sources = {}
    by_key = {}
    alias_map = dict(SEED_ALIASES)

    def _add(cand, source):
        key = normalize_name(cand.get("name"), alias_map)
        if not key:
            return None
        existing = by_key.get(key)
        if existing is None:
            cand.setdefault("sources", [])
            if source not in cand["sources"]:
                cand["sources"].append(source)
            cand.setdefault("aliases", [])
            by_key[key] = cand
            return cand
        # merge: prefer richer github facet, union sources/aliases
        if source not in existing["sources"]:
            existing["sources"].append(source)
        for field in ("repo", "stars", "pushed", "url", "desc"):
            if not existing.get(field) and cand.get(field):
                existing[field] = cand[field]
        disp = cand.get("name")
        if disp and disp != existing.get("name") and disp not in existing["aliases"]:
            existing["aliases"].append(disp)
        return existing

    # (a) GitHub — free primary
    gh_entities = []
    try:
        gh_entities = _enum_github(topic, n)
        for e in gh_entities:
            _add(e, "github")
        sources["github"] = "ok"
    except Exception as exc:  # noqa: BLE001 — per-source degrade (R1)
        sources["github"] = f"error: {type(exc).__name__}"

    # (b) HN — free: Show HN name discovery + mention corpus
    titles = []
    try:
        hn_names, titles = _enum_hn(topic)
        for name in hn_names:
            _add({"name": name, "type": "unknown"}, "hn")
        sources["hn"] = "ok"
    except Exception as exc:  # noqa: BLE001
        sources["hn"] = f"error: {type(exc).__name__}"

    # topic shape decides whether the LLM lens is merely optional or required
    repo_shaped = _topic_is_repo_shaped(gh_entities, topic)

    # (c) LLM enumeration — optional for repo-shaped, required otherwise
    llm_names, lens = _enum_llm(topic, n, keys, tmpdir)
    if lens:
        for i, name in enumerate(llm_names):
            ent = _add({"name": name, "type": "unknown"}, "llm")
            if ent is not None and ent.get("_llm_rank") is None:
                ent["_llm_rank"] = i
            # LLM-derived aliases feed the dedup map for later adds
            alias_map.setdefault(normalize_name(name, alias_map), normalize_name(name, alias_map))
        sources["llm"] = f"ok ({lens})"
    elif _pick_enum_lens(keys):
        sources["llm"] = "error"
    else:
        sources["llm"] = "absent"

    # coverage honesty (KTD2 / Product Contract)
    if not repo_shaped and not lens:
        coverage = (
            "repo-shaped entities only — no LLM enumeration lens available; "
            "coverage may miss closed-source products and people"
        )
    elif not repo_shaped:
        coverage = f"product/people-shaped topic — enriched via the {lens} lens"
    else:
        coverage = "repo-shaped topic — GitHub + HN enumeration" + (
            f" (+{lens} lens)" if lens else ""
        )

    # rank + cap
    entities = list(by_key.values())
    for e in entities:
        e["_score"] = _blended_score(e, titles)
        e.pop("_llm_rank", None)
    entities.sort(key=lambda e: (-e["_score"], e.get("name", "")))
    entities = entities[:n]
    for rank, e in enumerate(entities):
        e["rank"] = rank
        e.pop("_score", None)

    return {"topic": topic, "entities": entities, "sources": sources, "coverage": coverage}


if __name__ == "__main__":  # pragma: no cover — manual smoke only
    import sys

    print("entity_fanout is a library module wired by deep-research.py "
          "(--mode entity-fanout). Direct args:", sys.argv[1:], file=sys.stderr)
