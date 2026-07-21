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
  - stdlib only; Windows-safe: concurrent.futures.ThreadPoolExecutor for
    concurrency, no POSIX-only process/signal primitives (the selftest greps
    scripts/ for them);
  - free channels run with zero paid keys; a failed (entity, channel) cell
    writes <channel>.ERROR.md and never aborts the matrix;
  - paid lenses only fire on the top-K entities (hybrid) and never exceed the
    paid budget without opt-in; no paid call is ever made without a key.
"""
import html as _html
import json
import re
import threading
import time
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
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

# Rate-limit-prone hosts get per-host pacing + backoff (U4). Reddit and Bluesky
# already 403/429 under load; github (issues) and HN Algolia do not pace here.
THROTTLED_HOSTS = {"reddit": "reddit", "bluesky": "bluesky"}
BACKOFF_STATUS = (429, 403)
BACKOFF_RETRIES = 3
BACKOFF_BASE_SECONDS = 1.0

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


# ---------------------------------------------------------------------------
# Fan-out: per-entity, per-channel cells (U2)
# ---------------------------------------------------------------------------
class FanoutContext:
    """Shared state for a fan-out run: the topic, per-cell budget, the reddit
    topic-subreddits (discovered ONCE), an injectable sleep, per-host locks
    (U4), and a per-lens usage accumulator (U5). Thread-safe access to locks."""

    def __init__(self, topic, max_items, *, reddit_subs=None, sleep=None):
        self.topic = topic
        self.max_items = max_items
        self.reddit_subs = list(reddit_subs or [])
        self.sleep = sleep or time.sleep
        self.usage = {}  # channel -> list[usage dict] (U5)
        self._host_locks = {}
        self._guard = threading.Lock()

    def host_lock(self, host):
        """A process-wide lock per rate-limited host (reused by U4 pacing)."""
        with self._guard:
            return self._host_locks.setdefault(host, threading.Lock())

    def paced(self, host, thunk, *, retries=BACKOFF_RETRIES, base=BACKOFF_BASE_SECONDS):
        """Run `thunk` under per-host pacing + deterministic backoff (U4, R6).

        The host lock serializes this host's cells so N entity queries don't
        burst the same rate-limited endpoint. On HTTP 429/403 the call backs off
        `base * 2**attempt` (via the injectable clock) and retries up to
        `retries`, then re-raises so _run_cell degrades the cell to ERROR.md.
        Only 429/403 are retried — other errors surface immediately. Backoff is
        deterministic (no wall-clock randomness) so tests are stable. The reddit
        cell reuses the runner's _arctic_shift_json, which already retries a
        single 429; the retry cap here bounds the combined wait.
        """
        with self.host_lock(host):
            attempt = 0
            while True:
                try:
                    return thunk()
                except urllib.error.HTTPError as e:
                    if e.code not in BACKOFF_STATUS or attempt >= retries:
                        raise
                    self.sleep(base * (2 ** attempt))
                    attempt += 1


def discover_reddit_subs(topic):
    """Discover the topic's subreddits ONCE (KTD3) — reddit is topic-shaped, so
    a per-entity name query finds no eponymous subreddit. Degrades to [] on any
    failure so the reddit column is empty-but-honest, never an abort."""
    try:
        return _r("_arctic_shift_discover_subreddits")(topic)
    except Exception:  # noqa: BLE001 — reddit discovery never aborts the matrix
        return []


def _cell_query(entity, channel):
    """The per-entity query for a channel.

    github-issues resolves to the entity's repo (`owner/repo` => repo-scoped top
    issues, the strongest per-entity user-voice signal); every other channel
    uses the entity name. Name collisions on short names (the U0 "Zep" ->
    zephyr/zeppelin finding) are filtered downstream by rank_items' relevance
    floor against the entity name.
    """
    if channel == "github-issues" and entity.get("repo"):
        return entity["repo"]
    return entity["name"]


def _reddit_entity_cell(entity_name, ctx, out_path):
    """Per-entity reddit dossier: search each pre-discovered topic subreddit for
    the entity term, rank via rank_items (KTD3). Reuses the runner's
    arctic-shift helpers; `ctx.reddit_subs` was discovered once from the topic."""
    subs = ctx.reddit_subs
    lines = [f"# Reddit — posts mentioning: {entity_name}\n"]
    if not subs:
        lines.append(
            "_No topic subreddits discovered for this run; reddit fan-out "
            "skipped for this entity._\n"
        )
        out_path.write_text("\n".join(lines) + "\n")
        return 0

    arctic_json = _r("_arctic_shift_json")
    rank_items = _r("rank_items")
    base = _r("ARCTIC_SHIFT_BASE")
    pool_per_sub = _r("_REDDIT_POOL_PER_SUB")
    window_days = _r("_REDDIT_WINDOW_DAYS")

    after = time.strftime("%Y-%m-%d", time.gmtime(time.time() - window_days * 86400))
    posts, seen = [], set()
    for i, sub in enumerate(subs):
        if i:
            ctx.sleep(0.5)  # pace the "complex" text-search queries (U4 hardens)
        url = f"{base}/posts/search?" + urllib.parse.urlencode(
            {
                "query": entity_name,
                "subreddit": sub,
                "after": after,
                "limit": pool_per_sub,
                "sort": "desc",
                "sort_type": "created_utc",
                "fields": "id,title,score,num_comments,subreddit,created_utc,selftext,permalink",
            }
        )
        for p in arctic_json(url, timeout=30).get("data") or []:
            pid = p.get("id")
            if pid and pid in seen:
                continue
            seen.add(pid)
            p["_rank_text"] = f"{p.get('title') or ''} {(p.get('selftext') or '')[:400]}"
            posts.append(p)

    scope = ", ".join(f"r/{s}" for s in subs)
    lines.append(
        f"_Source: Arctic-Shift archive (free), last year. Scope: {scope}. "
        f"Query: {entity_name}._\n"
    )
    ranked = rank_items(
        posts,
        entity_name,
        text_key="_rank_text",
        engagement_key="score",
        comments_key="num_comments",
        max_items=ctx.max_items,
    )
    if not ranked.items:
        lines.append("_No posts found for this entity in the topic subreddits._\n")
    for p in ranked.items:
        lines.append(
            f"- **{p.get('title','?')}** — ▲{p.get('score',0)}, "
            f"{p.get('num_comments',0)} comments, r/{p.get('subreddit','?')}"
        )
        permalink = p.get("permalink")
        if permalink:
            lines.append(f"  - https://www.reddit.com{permalink}")
    out_path.write_text("\n".join(lines) + "\n")
    return len(ranked.items)


def _usage_total(usage):
    """Normalize a vendor usage block to a total token count (KTD6).

    Gemini direct returns `usageMetadata` (totalTokenCount / promptTokenCount /
    candidatesTokenCount); OpenAI/OpenRouter/Perplexity/xAI return `usage`
    (total_tokens / prompt_tokens / completion_tokens). Missing -> 0."""
    if not isinstance(usage, dict):
        return 0
    for key in ("total_tokens", "totalTokenCount"):
        val = usage.get(key)
        if isinstance(val, (int, float)):
            return int(val)
    prompt = usage.get("prompt_tokens") or usage.get("promptTokenCount") or 0
    completion = usage.get("completion_tokens") or usage.get("candidatesTokenCount") or 0
    return int((prompt or 0) + (completion or 0))


def _invoke_channel(channel, query, out_path, ctx, usage_sink=None):
    """Dispatch one non-reddit channel via the registry (R11). For paid lenses,
    an additive usage_sink captures real vendor token usage (KTD6); free
    channels take no sink and are called with the unchanged 3-arg signature."""
    fn = _r("CONNECTORS")[channel].fn
    if usage_sink is not None:
        return fn(query, out_path, ctx.max_items, usage_sink=usage_sink)
    return fn(query, out_path, ctx.max_items)


def _run_cell(cell, out_dir, ctx):
    """Execute one (entity, channel) cell; degrade to <channel>.ERROR.md on
    failure so a single cell never kills the matrix (mirrors run_connector)."""
    entity = cell["entity"]
    channel = cell["channel"]
    slug = entity_slug(entity["name"])
    cell_dir = Path(out_dir) / "entities" / slug
    cell_dir.mkdir(parents=True, exist_ok=True)
    out_path = cell_dir / f"{channel}.md"
    t0 = time.time()
    rec = {
        "entity": entity["name"],
        "slug": slug,
        "channel": channel,
        "tier": cell.get("tier", "free"),
        "rank": entity.get("rank"),
    }
    # Paid lens cells get a per-cell usage sink so real-vs-est token accounting
    # is exact (KTD6). Free cells take no sink.
    usage_sink = [] if channel in PAID_LENSES else None

    def _body():
        if channel == "reddit":
            return _reddit_entity_cell(entity["name"], ctx, out_path)
        return _invoke_channel(channel, _cell_query(entity, channel), out_path, ctx,
                               usage_sink=usage_sink)

    try:
        host = THROTTLED_HOSTS.get(channel)
        # Throttle-prone hosts pace per-host + back off (U4); others run direct.
        n = ctx.paced(host, _body) if host else _body()
        size = out_path.stat().st_size if out_path.exists() else 0
        rec.update(
            status="ok",
            items_or_chars=n,
            seconds=round(time.time() - t0, 2),
            output_size=size,
        )
        if channel in PAID_LENSES:
            if usage_sink:
                rec["tokens"] = sum(_usage_total(u) for u in usage_sink)
                rec["tokens_kind"] = "real"
            else:
                # vendor returned no usage block — honest size-based estimate
                rec["tokens"] = size // 4
                rec["tokens_kind"] = "est"
    except Exception as e:  # noqa: BLE001 — degrade, never kill sibling cells
        try:
            out_path.with_suffix(".ERROR.md").write_text(f"ERROR: {e}")
        except OSError:
            pass
        rec.update(status="error", error=str(e)[:200], seconds=round(time.time() - t0, 2))
    return rec


def build_free_cells(entities, channels=FREE_ENTITY_CHANNELS):
    """One free cell per (entity, channel) — free channels fan out on ALL
    entities (R3)."""
    return [
        {"entity": e, "channel": ch, "tier": "free"}
        for e in entities
        for ch in channels
    ]


# ---------------------------------------------------------------------------
# Tiering + paid-budget cap (U3)
# ---------------------------------------------------------------------------
def available_lenses(keys, lenses=PAID_LENSES):
    """Which paid lenses can actually run: a direct key, or the shared
    openrouter fallback (gemini/grok/perplexity all route through it). A lens
    with no usable key is absent and never counted toward the budget (R7).
    openai is deliberately excluded — opt-in only, no fallback (R17)."""
    keys = keys or {}
    out = []
    for lens in lenses:
        if keys.get(lens) or keys.get("openrouter"):
            out.append(lens)
    return out


def plan_cells(entities, keys, *, free_channels=FREE_ENTITY_CHANNELS,
               lenses=PAID_LENSES, k=DEFAULT_K, paid_all=False, paid_budget=None):
    """Build the full cell list under hybrid tiering (R3, R4, R7).

    Free channels fan out on ALL entities; paid lenses on the top-K only
    (`--paid-all` lifts them to all N *and* raises the budget so the opt-in is
    never trimmed back). A hard `paid_budget` (default K x available_lenses, or
    N x available_lenses under paid_all) trims excess paid cells keeping the
    highest-rank entities. Free cells are never gated.

    Entities are assumed rank-sorted (enumerate_entities returns them so).
    Returns (cells, report).
    """
    entities = list(entities)
    n = len(entities)
    k = max(0, min(int(k), min(n, HARD_K_CAP)))
    avail = available_lenses(keys, lenses)

    free_cells = [
        {"entity": e, "channel": ch, "tier": "free"}
        for e in entities
        for ch in free_channels
    ]

    paid_entities = entities if paid_all else entities[:k]
    if paid_budget is None:
        budget = (n if paid_all else k) * len(avail)
    else:
        budget = max(0, int(paid_budget))

    paid_cells = [
        {"entity": e, "channel": lens, "tier": "paid"}
        for e in paid_entities
        for lens in avail
    ]
    # rank order so a trim keeps the highest-rank entities' cells
    paid_cells.sort(key=lambda c: (c["entity"].get("rank", 0), avail.index(c["channel"])))
    trimmed = 0
    if len(paid_cells) > budget:
        trimmed = len(paid_cells) - budget
        paid_cells = paid_cells[:budget]

    report = {
        "n": n,
        "k": k,
        "available_lenses": avail,
        "free_channels": list(free_channels),
        "free_cells": len(free_cells),
        "paid_cells": len(paid_cells),
        "paid_budget": budget,
        "paid_all": bool(paid_all),
        "paid_trimmed": trimmed,
    }
    return free_cells + paid_cells, report


def run_matrix(cells, out_dir, ctx, *, concurrency=DEFAULT_CONCURRENCY):
    """Drain the (entity, channel) cell list with a bounded ThreadPoolExecutor
    (R5, Windows-safe: no fork/signal). Returns one record per cell in submit
    order. A cell that raises still returns an `error` record (per-cell degrade
    happens inside _run_cell)."""
    concurrency = max(1, min(int(concurrency), HARD_CONCURRENCY_CAP))
    if not cells:
        return []
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = [ex.submit(_run_cell, c, out_dir, ctx) for c in cells]
        return [f.result() for f in futures]


# ---------------------------------------------------------------------------
# Aggregation: entity x channel dossier matrix + honest cost/time (U5)
# ---------------------------------------------------------------------------
def aggregate_matrix(enum_result, records, *, topic, started, finished,
                     wall_seconds, plan_report):
    """Assemble per-entity dossiers + a cost/time manifest (KTD7, R9).

    Builds the entity x channel matrix (every cell, ok or error), per-channel
    fill_rate, a `degraded` flag when a free channel's ERROR fraction exceeds
    the threshold (so a rate-limit-hollow matrix is never called complete), and
    honest token accounting split real (vendor `usage`) vs est (size-based).
    Returns {matrix, manifest}."""
    entities = enum_result["entities"]
    cells_by_slug = {}
    for r in records:
        cells_by_slug.setdefault(r["slug"], {})[r["channel"]] = r

    matrix = []
    for e in entities:
        slug = entity_slug(e["name"])
        cells = cells_by_slug.get(slug, {})
        matrix.append(
            {
                "name": e["name"],
                "rank": e.get("rank"),
                "type": e.get("type"),
                "aliases": e.get("aliases", []),
                "sources": e.get("sources", []),
                "repo": e.get("repo"),
                "stars": e.get("stars"),
                "pushed": e.get("pushed"),
                "url": e.get("url"),
                "desc": e.get("desc"),
                "cells": {
                    ch: {
                        "status": c["status"],
                        "items_or_chars": c.get("items_or_chars"),
                        "seconds": c.get("seconds"),
                        "error": c.get("error"),
                        "tokens": c.get("tokens"),
                        "tokens_kind": c.get("tokens_kind"),
                        "path": (
                            f"entities/{slug}/{ch}.md"
                            if c["status"] == "ok"
                            else f"entities/{slug}/{ch}.ERROR.md"
                        ),
                    }
                    for ch, c in cells.items()
                },
            }
        )

    channels = {}
    for r in records:
        s = channels.setdefault(
            r["channel"], {"total": 0, "ok": 0, "error": 0, "tier": r["tier"]}
        )
        s["total"] += 1
        s["ok" if r["status"] == "ok" else "error"] += 1

    degraded = False
    for s in channels.values():
        s["fill_rate"] = round(s["ok"] / s["total"], 3) if s["total"] else 0.0
        error_fraction = (s["error"] / s["total"]) if s["total"] else 0.0
        s["error_fraction"] = round(error_fraction, 3)
        if s["tier"] == "free" and s["total"] and error_fraction > FILL_RATE_DEGRADE_THRESHOLD:
            degraded = True

    tokens_real = sum(r.get("tokens", 0) for r in records if r.get("tokens_kind") == "real")
    tokens_est = sum(r.get("tokens", 0) for r in records if r.get("tokens_kind") == "est")

    manifest = {
        "mode": "entity-fanout",
        "topic": topic,
        "started": started,
        "finished": finished,
        "wall_seconds": round(wall_seconds, 1),
        "entities": len(entities),
        "coverage": enum_result.get("coverage"),
        "enumeration_sources": enum_result.get("sources"),
        "plan": plan_report,
        "channels": channels,
        "cells_ok": sum(1 for r in records if r["status"] == "ok"),
        "cells_error": sum(1 for r in records if r["status"] == "error"),
        "paid_calls": sum(1 for r in records if r["tier"] == "paid"),
        "tokens_real": tokens_real,
        "tokens_est": tokens_est,
        "degraded": degraded,
    }
    return {"matrix": matrix, "manifest": manifest}


# ---------------------------------------------------------------------------
# Entity x channel HTML brief (U7) — reuses the runner's self-contained renderer
# ---------------------------------------------------------------------------
_BRIEF_EXCERPT_LINES = 8


def _cell_excerpt(out_dir, slug, channel, limit=_BRIEF_EXCERPT_LINES):
    """A bounded preview of a cell's markdown (drop its own H1 + blanks)."""
    path = Path(out_dir) / "entities" / slug / f"{channel}.md"
    if not path.exists():
        return []
    lines = [
        ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if ln.strip() and not ln.startswith("# ")
    ]
    return lines[:limit]


def render_entity_brief(out_dir, topic, agg):
    """Render brief.html entity-by-entity (KTD7), reusing the runner's
    self-contained markdown_to_html + HTML_TEMPLATE (no external deps, R11).
    Rows are entities; each shows its per-channel findings or an honest
    error/empty marker; a cost/time footer and a degraded banner keep it
    honest."""
    out_dir = Path(out_dir)
    matrix = agg["matrix"]
    m = agg["manifest"]
    summary = (
        f"{m['entities']} entities · {m['cells_ok']} cells ok / {m['cells_error']} error · "
        f"paid_calls={m['paid_calls']} · tokens real={m['tokens_real']} est={m['tokens_est']} · "
        f"{m['wall_seconds']}s"
    )
    md = [f"# Deep research — entity landscape: {topic}\n"]
    if m.get("coverage"):
        md.append(f"_{m['coverage']}_\n")
    md.append(f"_{summary}_\n")
    if m.get("degraded"):
        md.append(
            "**⚠ DEGRADED — one or more free channels were mostly rate-limited; "
            "the matrix below is incomplete.**\n"
        )

    for row in matrix:
        star = f" ★{row['stars']:,}" if row.get("stars") else ""
        repo = f" `{row['repo']}`" if row.get("repo") else ""
        md.append(f"## {(row.get('rank') or 0) + 1}. {row['name']}{star}{repo}\n")
        srcs = ", ".join(row.get("sources", []))
        if srcs:
            md.append(f"_sources: {srcs}_\n")
        if row.get("desc"):
            md.append(f"{row['desc']}\n")
        for ch in list(FREE_ENTITY_CHANNELS) + list(PAID_LENSES):
            cell = row["cells"].get(ch)
            if not cell:
                continue
            md.append(f"### {ch}\n")
            if cell["status"] != "ok":
                md.append(f"_⚠ {cell.get('error') or 'error'} — see {cell['path']}_\n")
                continue
            excerpt = _cell_excerpt(out_dir, entity_slug(row["name"]), ch)
            if excerpt:
                md.extend(excerpt)
                md.append("")
            else:
                md.append("_no signal_\n")

    md.append("\n---\n")
    md.append(f"_ZBS Researcher · entity-fanout · {summary}_")

    markdown_to_html = _r("markdown_to_html")
    template = _r("HTML_TEMPLATE")
    doc = template.format(
        title=_html.escape(f"Entity landscape: {topic}"),
        date=time.strftime("%Y-%m-%d"),
        content=markdown_to_html("\n".join(md)),
    )
    brief = out_dir / "brief.html"
    brief.write_text(doc, encoding="utf-8")
    return brief


# ---------------------------------------------------------------------------
# Plan-first + orchestration entrypoint (U6)
# ---------------------------------------------------------------------------
def write_research_plan(out_dir, topic, enum_result, plan_report, free_channels):
    """Write research-plan.md BEFORE any fan-out fires (R13): the enumerated
    entity list, the per-entity channel plan, and the exact computed call
    budget. This is the plan-first contract for entity-fanout mode."""
    n = plan_report["n"]
    lenses = plan_report.get("available_lenses") or []
    lines = [
        f"# Research plan — entity fan-out: {topic}\n",
        f"_Mode: entity-fanout. {n} entities enumerated. "
        f"Coverage: {enum_result.get('coverage')}._\n",
        "## Call budget (computed before firing)\n",
        f"- free cells: **{plan_report['free_cells']}** "
        f"({n} entities x {len(free_channels)} free channels: {', '.join(free_channels)})",
        f"- paid cells: **{plan_report['paid_cells']}** "
        f"(lenses: {', '.join(lenses) or 'none'}; budget {plan_report['paid_budget']}; "
        f"paid_all={plan_report['paid_all']}; trimmed {plan_report['paid_trimmed']})",
        "\n## Enumeration sources\n",
    ]
    for src, status in (enum_result.get("sources") or {}).items():
        lines.append(f"- {src}: {status}")
    lines.append("\n## Entities (rank order)\n")
    if not enum_result["entities"]:
        lines.append("_No entities enumerated for this topic._")
    for e in enum_result["entities"]:
        star = f" ★{e['stars']:,}" if e.get("stars") else ""
        repo = f" `{e['repo']}`" if e.get("repo") else ""
        srcs = ", ".join(e.get("sources", []))
        lines.append(f"{e['rank'] + 1}. **{e['name']}**{repo}{star} — {srcs}")
    (Path(out_dir) / "research-plan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_entity_fanout(topic, out_dir, keys=None, *, n=DEFAULT_N, k=DEFAULT_K,
                      concurrency=DEFAULT_CONCURRENCY, paid_budget=None,
                      paid_all=False, max_items=10, dry_run=False,
                      free_channels=FREE_ENTITY_CHANNELS, lenses=PAID_LENSES):
    """Full entity-fanout run: enumerate -> plan (+ write research-plan.md) ->
    fan out -> aggregate. Writes research-plan.md (before firing), matrix.json,
    manifest.json, and brief.html into out_dir. Returns the aggregate dict.

    With dry_run=True it stops after writing research-plan.md (enumeration +
    computed call budget), firing no cells and no paid calls — a fast, free
    preview of what a full run would do.

    The run directory is caller-owned (the CLI self-allocates it); this function
    does not consume an agent-prepared run — that path stays single-mode only.
    """
    keys = keys or {}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    t0 = time.time()

    # dry-run enumerates without needing reddit subreddits (no fan-out).
    reddit_subs = (
        discover_reddit_subs(topic) if (not dry_run and "reddit" in free_channels) else []
    )
    ctx = FanoutContext(topic, max_items, reddit_subs=reddit_subs)

    enum = enumerate_entities(topic, n=n, keys=keys, tmpdir=str(out_dir))
    cells, plan_report = plan_cells(
        enum["entities"], keys, free_channels=free_channels, lenses=lenses,
        k=k, paid_all=paid_all, paid_budget=paid_budget,
    )
    # plan-first: the plan (with the exact call budget) lands before any cell.
    write_research_plan(out_dir, topic, enum, plan_report, free_channels)

    if dry_run:
        manifest = {
            "mode": "entity-fanout",
            "dry_run": True,
            "topic": topic,
            "started": started,
            "entities": len(enum["entities"]),
            "coverage": enum.get("coverage"),
            "enumeration_sources": enum.get("sources"),
            "plan": plan_report,
            "paid_calls": 0,
            "tokens_real": 0,
            "tokens_est": 0,
        }
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return {"matrix": [], "manifest": manifest}

    records = run_matrix(cells, out_dir, ctx, concurrency=concurrency)
    finished = time.strftime("%Y-%m-%dT%H:%M:%S")
    agg = aggregate_matrix(
        enum, records, topic=topic, started=started, finished=finished,
        wall_seconds=time.time() - t0, plan_report=plan_report,
    )
    (out_dir / "matrix.json").write_text(json.dumps(agg["matrix"], indent=2), encoding="utf-8")
    (out_dir / "manifest.json").write_text(json.dumps(agg["manifest"], indent=2), encoding="utf-8")
    _maybe_render_brief(out_dir, topic, agg)
    return agg


def _maybe_render_brief(out_dir, topic, agg):
    """Render brief.html when the U7 renderer is present (wired in U7)."""
    renderer = globals().get("render_entity_brief")
    if renderer is not None:
        try:
            renderer(out_dir, topic, agg)
        except Exception:  # noqa: BLE001 — a brief failure never fails the run
            pass


if __name__ == "__main__":  # pragma: no cover — manual smoke only
    import sys

    print("entity_fanout is a library module wired by deep-research.py "
          "(--mode entity-fanout). Direct args:", sys.argv[1:], file=sys.stderr)
