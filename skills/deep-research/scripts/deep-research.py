#!/usr/bin/env python3
"""
Deep research raw-evidence runner: many channels in parallel.

Two channel families run concurrently and write one markdown file each:

  LLM channels (need an API key; each is a reasoning model with its own
  live access to a slice of the web):
    - gemini      Gemini 2.5 Pro + googleSearch grounding -> YouTube + web
    - grok        Grok-4 + x_search -> realtime X / Twitter
    - openai      gpt-5.4 (NON-Pro) + web_search -> Reddit / HN / GitHub / blogs
    - perplexity  Sonar online -> web + news, citation-first

  Tier 2 (R8): one OPENROUTER_API_KEY (or <secrets-dir>/openrouter-key.txt)
  drives gemini/grok/perplexity through OpenRouter when their direct keys are
  absent; direct keys always win. openai is NOT OpenRouter-routed (R17).

  Direct channels (zero-config, free; give STRUCTURAL signal an LLM
  won't hand you — raw numbers, odds, velocity):
    - hackernews  HN Algolia -> stories ranked by points/comments
    - hiring      HN "Who is hiring?" -> topic mentions and sample companies
    - polymarket  Gamma markets -> real-money odds on the topic
    - github      repo search -> stars, recent activity
    - github-issues  issue search -> top issues by reactions + comment
                  excerpts (real user voice; repo-scoped via `owner/repo`)
    - reddit      Arctic-Shift archive -> reaction-weighted posts (real
                  score+comments; reddit.com/search.json is dead)
    - bluesky     app.bsky searchPosts (best-effort)
    - launch-radar   what's shipping: Show HN + yc-oss + DevHunt (+Product
                  Hunt with a free read token) -> momentum + category velocity
    - revenue-radar  what's selling: Flippa sold prices + Substack bestseller
                  tiers (free; tiers rendered verbatim, never invented ARR)
    - meta-ads    who's PAYING to advertise: Meta Ad Library, EU scope
                  (free token required; auto-skipped without one)
    - telegram    Telegram channel posts + comments via a Telethon client
                  session (OPT-IN, hard-warning gate: separate account only;
                  Telethon is an optional lazy import, never a hard dep)
    - tiktok-ig   TikTok/IG posts + comments via a pay-per-use vendor
                  (OPT-IN + key-gated; every run costs vendor credits)
    - threads     Threads posts by keyword — official keyword_search with a
                  Threads token (free; Meta TOP order, no engagement counts;
                  Standard Access = own posts only until App Review) or the
                  ScrapeCreators vendor (pay-per-use, engagement-ranked)

The deep-research skill owns the higher-level workflow: it reserves one
project-local run with `--allocate-run`, writes `research-plan.md` before
connectors start, calls this runner with that exact `--output-dir`, then writes
`synthesis.md` and optionally renders `brief.html`. A direct topic invocation
is intentionally lower level: it writes raw channel reports and manifest.json,
not a research plan or synthesis.

Channels are independent; if one fails it writes <name>.ERROR.md and the
others continue. A manifest.json records what ran, what was skipped, and why.

Pro models (gpt-5.4-pro, gpt-5.5) are intentionally NOT used here — non-Pro
retrieval + citation is enough. Pro spend is reserved for emergency-pro.

Usage:
    # discover what's live (used by the plan step before any run)
    python3 deep-research.py --list-connectors

    # direct raw run (default = every available connector); output is uniquely
    # allocated beneath the launch project's research/ directory
    python3 deep-research.py "TOPIC"
    python3 deep-research.py "TOPIC" --only gemini,hackernews,polymarket
    python3 deep-research.py "TOPIC" --project-root /path/to/project
    python3 deep-research.py "TOPIC" --launch-cwd /captured/project/path

    # skill orchestration: reserve first, write research-plan.md, then run into
    # the exact reserved directory
    python3 deep-research.py "TOPIC" --allocate-run
    python3 deep-research.py "TOPIC" --output-dir /path/to/reserved-run --prepared-run

    # explicit raw-output override bypasses project-root allocation
    python3 deep-research.py "TOPIC" --output-dir ./scratch/run --skip reddit,bluesky

    # per-channel query aim
    python3 deep-research.py --topic T \\
        --q gemini:"YouTube talks on X" --q openai:"Reddit/HN on X"
    # legacy aliases still work: --gemini-q --grok-q --openai-q

    # render a shareable HTML brief from the synthesis markdown
    python3 deep-research.py --render-html DIR/synthesis.md --html-out DIR/brief.html
"""
import argparse
import html as html_mod
import importlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from output_paths import (
    allocate_run_directory,
    claim_prepared_run_directory,
    resolve_launch_directory,
    resolve_output_directory,
    resolve_project_root,
)

# Terminal UI (R4/R5): capability tiers, ZBS RESEARCHER banner, live board.
# In the plain tier (pipes, CI, NO_COLOR, TERM=dumb) the runner's stderr is
# byte-identical to the pre-banner format — pinned by the golden test.
import term_ui

# Market-radar connector modules (R22/KTD7) live in the connectors/ package.
# They reuse this module's HTTP + ranking helpers through a live-globals
# injection: lookups happen per call, so tests that patch attributes on this
# module are honored inside the connector modules too.
import connectors as _market_radar_pkg
from connectors import excerpt
from connectors.launch_radar import channel_launch_radar
from connectors.meta_ads import channel_meta_ads
from connectors.revenue_radar import channel_revenue_radar
from connectors.telegram import channel_telegram
from connectors.threads import channel_threads
from connectors.tiktok_ig import channel_tiktok_ig

_market_radar_pkg.attach_runner(globals())

# Where per-provider key files live. Defaults to a neutral XDG config dir
# (~/.config/zbs-research/secrets), overridable via DEEP_RESEARCH_SECRETS_DIR —
# or skip files entirely and use env vars (GEMINI_API_KEY, GROK_API_KEY,
# OPENAI_API_KEY, PERPLEXITY_API_KEY, OPENROUTER_API_KEY), which read_key()
# falls back to.
def _default_secrets_dir():
    """Neutral, XDG-friendly default for per-provider key files.
    Override with DEEP_RESEARCH_SECRETS_DIR, or skip files and use env vars."""
    override = os.environ.get("DEEP_RESEARCH_SECRETS_DIR")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(base).expanduser() / "zbs-research" / "secrets"
SECRETS = _default_secrets_dir()
UA = "deep-research/2.0 (+https://github.com/zbs-gg/zbs-research)"


def read_key(filenames, prefix_pattern, env_var=None):
    """Read an API key from the first of <secrets-dir>/<name> that
    exists (filenames is a list, tried in order), falling back to env_var.
    First regex match in the file wins so the file may hold either a bare
    key or a `KEY = sk-...` line."""
    if isinstance(filenames, str):
        filenames = [filenames]
    for filename in filenames:
        path = SECRETS / filename
        if path.exists():
            raw = path.read_text().strip()
            m = re.search(prefix_pattern, raw)
            if m:
                return m.group(0)
            if raw:
                return raw
    if env_var:
        env = os.environ.get(env_var, "").strip()
        if env:
            return env
    return ""


KEYS = {
    "gemini": read_key(["gemini-key.txt"], r"AIza[A-Za-z0-9_\-]+", "GEMINI_API_KEY"),
    "grok": read_key(["grok-api-key.txt"], r"xai-[A-Za-z0-9_\-]+", "GROK_API_KEY"),
    "openai": read_key(
        ["openai-api-key.txt", "openai-key.txt", "openai.txt"],
        r"sk-(?:proj-)?[A-Za-z0-9_\-]+",
        "OPENAI_API_KEY",
    ),
    "perplexity": read_key(
        ["perplexity-key.txt", "perplexity.txt"],
        r"pplx-[A-Za-z0-9_\-]+",
        "PERPLEXITY_API_KEY",
    ),
    # Tier 2 (R8): ONE OpenRouter key covers the gemini/grok/perplexity lenses
    # when their direct keys are absent. Resolution contract mirrors
    # detect_state.py exactly (same file name, pattern, env var).
    "openrouter": read_key(["openrouter-key.txt"], r"sk-or-[A-Za-z0-9_\-]+", "OPENROUTER_API_KEY"),
    # Optional paid video sources — only wired if a key shows up.
    "scrapecreators": read_key(
        ["scrape_creators.txt", "scrapecreators-key.txt", "scrapecreators.txt"],
        r"[A-Za-z0-9_\-]{12,}",
        "SCRAPECREATORS_KEY",
    ),
    "brave": read_key(["brave-key.txt"], r"[A-Za-z0-9_\-]{12,}", "BRAVE_API_KEY"),
    # Media backend (R16): Groq Whisper transcription. Resolution contract
    # mirrors detect_state.py / media_backend.py (same file, pattern, env).
    "groq": read_key(["groq-key.txt"], r"gsk_[A-Za-z0-9_\-]+", "GROQ_API_KEY"),
    # Meta Ad Library (R6): money-signal connector, token-gated — with
    # requires=["meta_ads"] select_connectors auto-skips when absent and the
    # manifest records the missing key (the honest degrade).
    "meta_ads": read_key(["meta-ads-token.txt"], r"[A-Za-z0-9|]{20,}", "META_ADS_TOKEN"),
    # Threads (R23): official keyword_search token. Optional — the threads
    # connector declares fallback_key="scrapecreators", so either credential
    # keeps it available; without both, select_connectors skips it honestly.
    "threads": read_key(["threads-access-token.txt"], r"[A-Za-z0-9_\-]{20,}", "THREADS_ACCESS_TOKEN"),
}

OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = os.environ.get("OPENAI_RESEARCH_MODEL", "gpt-5.4")
PERPLEXITY_MODEL = os.environ.get("PERPLEXITY_RESEARCH_MODEL", "sonar")


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def post_json(url, body, headers, timeout=300):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "User-Agent": UA, **headers},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def get_json(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw)


def _extract_responses_text(data):
    """Pull assistant text out of an OpenAI/xAI Responses-API payload."""
    chunks = []
    for item in data.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") in ("output_text", "text"):
                    chunks.append(c.get("text", ""))
    return "\n\n".join(t for t in chunks if t).strip()


# ---------------------------------------------------------------------------
# LLM channels
#
# Each lens has two paths:
#   1. direct — the provider's own API with its own key (always preferred:
#      independent blast radius, provider-native response shape);
#   2. Tier 2 (R8) — no direct key but KEYS["openrouter"] present: the same
#      lens through OpenRouter's chat/completions with the provider's explicit
#      native grounding tool. NEVER the ":online" model suffix — that swaps in
#      OpenRouter's generic web plugin instead of provider-native retrieval.
# openai has NO Tier-2 path on purpose (R17: opt-in, direct key only).
# ---------------------------------------------------------------------------
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Model ids are literal constants on purpose: no suffix machinery exists, so a
# ":online" model can never be built (guarded by tests too).
OPENROUTER_MODELS = {
    "gemini": "google/gemini-2.5-pro",
    "grok": "x-ai/grok-4",
    "perplexity": "perplexity/sonar",
}


# Prompt text is shared between the direct and Tier-2 paths so a lens asks the
# same question no matter how it is routed.
def _gemini_prompt(query):
    return (
        "Search the web (especially YouTube) for the topic below. "
        "Find recent (2025-2026) videos / talks / tutorials. "
        "For each finding: title, channel/author, url, key claim "
        "(2-3 sentences). Flag contradictions with other sources. "
        "Conclude with a 5-7 line summary of recurring themes.\n\n"
        f"TOPIC: {query}"
    )


_GROK_SYSTEM = (
    "You search X / Twitter for honest user voice on technical topics. "
    "Quote actual posts when available. Note dates. Surface contradictions."
)


def _grok_user(query):
    return (
        f"Search X for posts (2025-2026) about: {query}\n\n"
        "Return: 1) 5-15 representative quotes (verbatim if possible) with "
        "author handle and date, 2) recurring complaints, 3) workarounds "
        "people share, 4) overall sentiment."
    )


_PERPLEXITY_SYSTEM = (
    "You are a citation-first research assistant. Answer with concrete, "
    "recent (2025-2026) findings and always attribute claims to sources. "
    "Surface disagreements between sources rather than smoothing them over."
)


def _perplexity_user(query):
    return (
        f"Research this topic and report key findings with dates and sources, "
        f"noting any contradictions: {query}"
    )


def openrouter_request_body(provider, query):
    """Build the OpenRouter chat/completions request body for one LLM lens.

    Pure function (no network) so tests pin the exact request shape. Grounding
    is provider-native and explicit — NEVER the ":online" model suffix.
    """
    if provider == "gemini":
        # KTD2: googleSearch is passed through in the provider-native schema
        # (OpenRouter forwards provider-specific fields). This passthrough is
        # NOT live-verified yet — the U4 smoke must confirm grounding evidence
        # (real search-backed citations in the response) before Tier 2 is
        # advertised for the gemini lens. Fallback if the smoke fails:
        # Tier 2 = Sonar-only; gemini stays direct-key.
        return {
            "model": OPENROUTER_MODELS["gemini"],
            "messages": [{"role": "user", "content": _gemini_prompt(query)}],
            "tools": [{"googleSearch": {}}],
        }
    if provider == "grok":
        # KTD2: same caveat as gemini — the x_search passthrough needs smoke
        # confirmation before Tier 2 is advertised for the grok lens.
        return {
            "model": OPENROUTER_MODELS["grok"],
            "messages": [
                {"role": "system", "content": _GROK_SYSTEM},
                {"role": "user", "content": _grok_user(query)},
            ],
            "tools": [{"type": "x_search"}],
        }
    if provider == "perplexity":
        # Sonar is grounded by construction — the model id IS the retrieval.
        # No tool field needed, so this lens is the safe Tier-2 baseline.
        return {
            "model": OPENROUTER_MODELS["perplexity"],
            "messages": [
                {"role": "system", "content": _PERPLEXITY_SYSTEM},
                {"role": "user", "content": _perplexity_user(query)},
            ],
            "max_tokens": 4000,
            "temperature": 0.3,
        }
    # openai (and anything else) is deliberately unrouted — R17.
    raise ValueError(f"no OpenRouter route for provider: {provider}")


def _channel_via_openrouter(provider, query, out_path):
    """Tier-2 execution: POST the pre-built body to OpenRouter, parse the
    OpenAI chat/completions shape, append citations/annotations if present.
    Errors propagate so run_connector writes <name>.ERROR.md."""
    body = openrouter_request_body(provider, query)
    data = post_json(
        OPENROUTER_URL,
        body,
        {"Authorization": f"Bearer {KEYS['openrouter']}"},
        timeout=600,
    )
    message, text = {}, ""
    try:
        message = data["choices"][0]["message"] or {}
        content = message.get("content")
        if isinstance(content, str):
            text = content.strip()
    except (KeyError, IndexError, TypeError):
        message = {}
    if not text:
        text = json.dumps(data, indent=2)[:5000]
    links = [c for c in (data.get("citations") or [])[:40] if isinstance(c, str)]
    for a in (message.get("annotations") or [])[:40]:
        u = a.get("url_citation") if isinstance(a, dict) else None
        if isinstance(u, dict) and u.get("url"):
            links.append(f"[{u.get('title') or u['url']}]({u['url']})")
    if links:
        text += "\n\n---\n## Citations\n" + "".join(f"- {c}\n" for c in links)
    out_path.write_text(text)
    return len(text)


def channel_gemini(query, out_path, max_items):
    if not KEYS["gemini"]:
        # Tier 2: no direct key — route through OpenRouter (KTD2).
        return _channel_via_openrouter("gemini", query, out_path)
    body = {
        "contents": [{"role": "user", "parts": [{"text": _gemini_prompt(query)}]}],
        "tools": [{"googleSearch": {}}],
        "generationConfig": {"maxOutputTokens": 8000, "temperature": 0.4},
    }
    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/gemini-2.5-pro:generateContent?key={KEYS['gemini']}"
    )
    data = post_json(url, body, {})
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"no candidates: {json.dumps(data)[:500]}")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts)
    meta = candidates[0].get("groundingMetadata", {})
    if meta:
        text += "\n\n---\n## Grounding sources\n"
        for c in meta.get("groundingChunks", [])[:30]:
            w = c.get("web", {})
            text += f"- [{w.get('title','?')}]({w.get('uri','?')})\n"
    out_path.write_text(text)
    return len(text)


def channel_grok(query, out_path, max_items):
    if not KEYS["grok"]:
        # Tier 2: no direct key — route through OpenRouter (KTD2).
        return _channel_via_openrouter("grok", query, out_path)
    body = {
        "model": "grok-4.20-reasoning",
        "input": [
            {"role": "system", "content": _GROK_SYSTEM},
            {"role": "user", "content": _grok_user(query)},
        ],
        "tools": [{"type": "x_search"}],
    }
    data = post_json(
        "https://api.x.ai/v1/responses",
        body,
        {"Authorization": f"Bearer {KEYS['grok']}"},
        timeout=600,
    )
    text = _extract_responses_text(data) or json.dumps(data, indent=2)[:5000]
    out_path.write_text(text)
    return len(text)


def channel_openai(query, out_path, max_items):
    body = {
        "model": OPENAI_MODEL,
        "input": [
            {
                "role": "system",
                "content": (
                    "You investigate community sentiment on technical topics. "
                    "Search Reddit, Hacker News, GitHub Issues, and dev blogs. "
                    "Quote real users with subreddit/thread URLs. Note recurring complaints."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{query}\n\n"
                    "Check relevant subreddits, Hacker News (news.ycombinator.com), and "
                    "GitHub Issues. For each finding: source URL, quote, why relevant. "
                    "Conclude with consensus and outlier views."
                ),
            },
        ],
        "tools": [{"type": "web_search"}],
        "max_output_tokens": 6000,
    }
    data = post_json(
        f"{OPENAI_BASE_URL}/responses",
        body,
        {"Authorization": f"Bearer {KEYS['openai']}"},
        timeout=600,
    )
    text = _extract_responses_text(data) or json.dumps(data, indent=2)[:5000]
    out_path.write_text(text)
    return len(text)


def channel_perplexity(query, out_path, max_items):
    if not KEYS["perplexity"]:
        # Tier 2: no direct key — route through OpenRouter (KTD2).
        return _channel_via_openrouter("perplexity", query, out_path)
    body = {
        "model": PERPLEXITY_MODEL,
        "messages": [
            {"role": "system", "content": _PERPLEXITY_SYSTEM},
            {"role": "user", "content": _perplexity_user(query)},
        ],
        "max_tokens": 4000,
        "temperature": 0.3,
    }
    data = post_json(
        "https://api.perplexity.ai/chat/completions",
        body,
        {"Authorization": f"Bearer {KEYS['perplexity']}"},
        timeout=300,
    )
    text = ""
    try:
        text = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError):
        text = json.dumps(data, indent=2)[:5000]
    cites = data.get("citations") or []
    if cites:
        text += "\n\n---\n## Citations\n" + "".join(f"- {c}\n" for c in cites[:40])
    out_path.write_text(text)
    return len(text)


# ---------------------------------------------------------------------------
# Ranking (R21): comment-evidence + relevance floor
#
# Raw vote-count ranking lets an off-topic viral item bury on-topic results
# for niche topics. The shared helper below fixes that with three rules:
#   1. relevance floor — an item must match enough distinctive topic tokens
#      before engagement counts at all; below-floor items rank strictly
#      below every above-floor item regardless of votes;
#   2. bounded engagement — log-scale, so 10k votes can't dominate purely
#      on votes;
#   3. "too clean" penalty — like-heavy/comment-light items (a common bot
#      signature) are penalized when comment data is available.
# Pure functions, no network: connectors fetch a pool and rank it here.
# ---------------------------------------------------------------------------
_RANK_STOPWORDS = frozenset(
    "a an and are as at be but by can do for from has have how i if in is it its "
    "my of on or our so that the their there these they this to was we what when "
    "where which who why will with you your".split()
)
RELEVANCE_FLOOR = 0.34  # fraction of distinctive topic tokens that must appear


def _rank_tokens(text):
    """Lowercase word tokens minus stopwords (stopword-light, not a full NLP
    pass — enough to make 'context engineering' distinctive)."""
    words = re.findall(r"[a-z0-9][a-z0-9+#.\-]*", (text or "").lower())
    return [w for w in words if w not in _RANK_STOPWORDS and len(w) >= 2]


def relevance_score(text, topic):
    """0..1: fraction of the topic's distinctive tokens present in text.
    A topic with no distinctive tokens gates nothing (returns 1.0)."""
    topic_tokens = set(_rank_tokens(topic))
    if not topic_tokens:
        return 1.0
    text_tokens = set(_rank_tokens(text))
    return len(topic_tokens & text_tokens) / len(topic_tokens)


def engagement_score(votes, comments=None):
    """Bounded (log10) engagement. Comments count as corroborating evidence;
    a high-vote / near-zero-comment signature gets halved (bot smell).
    `comments=None` means "no comment data" — no bonus, no penalty."""
    votes = max(float(votes or 0), 0.0)
    score = math.log10(1.0 + votes)
    if comments is not None:
        comments = max(float(comments or 0), 0.0)
        score += 0.5 * math.log10(1.0 + comments)
        if votes >= 50 and comments <= max(1.0, votes / 200.0):
            score *= 0.5
    return score


class RankResult:
    """Ranked items plus an optional degrade note the caller can surface."""

    __slots__ = ("items", "note")

    def __init__(self, items, note=None):
        self.items = items
        self.note = note


def rank_items(items, topic, *, text_key, engagement_key, comments_key=None,
               max_items=None):
    """Order dict items by (relevance floor, then engagement+relevance).

    Deterministic and stable: pure function of the input; exact ties keep
    input order. When NO item clears the relevance floor the order is
    best-effort (relevance, then engagement) and `note` explains that.
    """
    scored = []
    for it in items:
        rel = relevance_score(str(it.get(text_key) or ""), topic)
        comments = it.get(comments_key) if comments_key else None
        eng = engagement_score(it.get(engagement_key), comments)
        tier = 0 if rel >= RELEVANCE_FLOOR else 1
        scored.append((tier, -(eng + 1.5 * rel), -rel, it))
    scored.sort(key=lambda row: row[:3])  # stable: ties keep input order
    ranked = [row[3] for row in scored]
    note = None
    if ranked and all(row[0] == 1 for row in scored):
        note = (
            "no result cleared the topic-relevance floor; "
            "order is best-effort (may be off-topic)"
        )
    if max_items is not None:
        ranked = ranked[:max_items]
    return RankResult(ranked, note)


# ---------------------------------------------------------------------------
# Direct channels (structural signal)
# ---------------------------------------------------------------------------
def channel_hackernews(query, out_path, max_items):
    # Pull a pool larger than max_items so the relevance/engagement ranker
    # has something to choose from (Algolia's own order is match-based).
    pool = min(50, max(30, max_items * 3))
    url = (
        "https://hn.algolia.com/api/v1/search?"
        + urllib.parse.urlencode({"query": query, "tags": "story", "hitsPerPage": pool})
    )
    data = get_json(url, timeout=20)
    hits = [
        {**h, "_rank_text": h.get("title") or h.get("story_title") or ""}
        for h in data.get("hits", [])
    ]
    ranked = rank_items(
        hits,
        query,
        text_key="_rank_text",
        engagement_key="points",
        comments_key="num_comments",
        max_items=max_items,
    )
    lines = [f"# Hacker News — top stories for: {query}\n"]
    if ranked.note:
        lines.append(f"_Note: {ranked.note}._\n")
    if not ranked.items:
        lines.append("_No stories found._\n")
    for h in ranked.items:
        title = h.get("title") or h.get("story_title") or "?"
        obj = h.get("objectID", "")
        u = h.get("url") or f"https://news.ycombinator.com/item?id={obj}"
        pts = h.get("points", 0)
        ncom = h.get("num_comments", 0)
        when = (h.get("created_at") or "")[:10]
        hn = f"https://news.ycombinator.com/item?id={obj}"
        lines.append(f"- **{title}** — {pts} pts, {ncom} comments, {when}")
        lines.append(f"  - link: {u}")
        lines.append(f"  - discussion: {hn}")
    out_path.write_text("\n".join(lines) + "\n")
    return len(ranked.items)


def channel_hiring(query, out_path, max_items):
    """Job-market hotness: search the latest monthly HN 'Who is hiring?'
    thread for the topic. Count of matching postings = how hot the topic
    is on the hiring market (e.g. RAG/agents/context-engineering spike).
    Free, zero-config (HN Algolia)."""
    surl = "https://hn.algolia.com/api/v1/search_by_date?" + urllib.parse.urlencode(
        {"tags": "story,author_whoishiring", "query": "hiring", "hitsPerPage": 5}
    )
    stories = [
        h for h in get_json(surl, timeout=20).get("hits", [])
        if "who is hiring" in (h.get("title", "") or "").lower()
    ]
    if not stories:
        raise RuntimeError("no 'Who is hiring?' thread found")
    thread = stories[0]
    tid, ttitle = thread["objectID"], thread.get("title", "")
    curl = "https://hn.algolia.com/api/v1/search?" + urllib.parse.urlencode(
        {"tags": f"comment,story_{tid}", "query": query, "hitsPerPage": max_items}
    )
    cd = get_json(curl, timeout=20)
    nb = cd.get("nbHits", 0)
    lines = [
        f'# Hiring signal — HN "{ttitle}"\n',
        f"**{nb} postings** in this month's thread mention: _{query}_\n",
        f"(discussion: https://news.ycombinator.com/item?id={tid})\n",
    ]
    if not cd.get("hits"):
        lines.append("_No matching postings — topic is not (yet) a hiring driver here._\n")
    for h in cd.get("hits", [])[:max_items]:
        txt = " ".join(html_mod.unescape(re.sub(r"<[^>]+>", " ", h.get("comment_text", "") or "")).split())
        lines.append(f"- {txt[:260]}")
        lines.append(f"  - https://news.ycombinator.com/item?id={h.get('objectID')}")
    out_path.write_text("\n".join(lines) + "\n")
    return nb


def channel_polymarket(query, out_path, max_items):
    # Gamma's /markets endpoint has no text filter and caps at 100 by
    # volume (dominated by whatever's hot). /public-search IS a real
    # full-text search over events — use it. Honest "0 markets" when the
    # topic isn't a forecastable event.
    url = "https://gamma-api.polymarket.com/public-search?" + urllib.parse.urlencode(
        {"q": query, "limit_per_type": max_items, "events_status": "active"}
    )
    data = get_json(url, timeout=25)
    events = data.get("events", []) if isinstance(data, dict) else []
    lines = [f"# Polymarket — real-money odds for: {query}\n"]
    if not events:
        lines.append("_No active prediction markets matched this topic._\n")
    for ev in events[:max_items]:
        title = ev.get("title", "?")
        slug = ev.get("slug", "")
        vol = ev.get("volume") or 0
        end = (ev.get("endDate") or "")[:10]
        try:
            vol_s = f"${float(vol):,.0f}"
        except (TypeError, ValueError):
            vol_s = str(vol)
        lines.append(f"- **{title}** — volume {vol_s}, ends {end}")
        lines.append(f"  - https://polymarket.com/event/{slug}")
        # show the priced outcomes inside the event (Yes-probability)
        for m in ev.get("markets", [])[:6]:
            label = m.get("groupItemTitle") or m.get("question", "")
            prices = m.get("outcomePrices")
            outcomes = m.get("outcomes")
            try:
                pr = json.loads(prices) if isinstance(prices, str) else prices
                oc = json.loads(outcomes) if isinstance(outcomes, str) else outcomes
                if pr and oc:
                    yes = float(pr[0]) * 100
                    lines.append(f"    - {label}: {oc[0]} ≈{yes:.0f}%")
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
    out_path.write_text("\n".join(lines) + "\n")
    return len(events)


def gh_api(path):
    """GitHub REST GET (path relative to the API root). Prefers the authed
    `gh` CLI when installed (higher rate limit); falls back to unauthenticated
    api.github.com. Shared by channel_github and channel_github_issues."""
    if shutil.which("gh"):
        r = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            return json.loads(r.stdout)
    return get_json("https://api.github.com/" + path, timeout=25)


def channel_github(query, out_path, max_items):
    """Repo search: stars + push recency. Issue/PR signal moved to the
    dedicated github-issues connector (R11) — the old "Recent issues / PRs"
    section here was duplicate signal (review decision)."""
    repos = gh_api(
        "search/repositories?" + urllib.parse.urlencode({"q": query, "sort": "stars", "per_page": max_items})
    )
    items = repos.get("items", [])[:max_items]
    lines = [f"# GitHub — for: {query}\n", "## Top repositories (by stars)\n"]
    if not items:
        lines.append("_No repositories found._\n")
    for r in items:
        lines.append(
            f"- **{r.get('full_name')}** — ★{r.get('stargazers_count',0):,}, "
            f"pushed {(r.get('pushed_at') or '')[:10]}"
        )
        if r.get("description"):
            lines.append(f"  - {r['description']}")
        lines.append(f"  - {r.get('html_url')}")
    lines.append(
        "\n_Issue + comment evidence lives in the github-issues connector "
        "(github-issues.md)._"
    )
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(items)


_GH_REPO_RE = re.compile(r"^[\w.-]+/[\w.-]+$")
_GH_ISSUES_COMMENT_ISSUES = 5      # top issues that get comment excerpts
_GH_ISSUES_COMMENTS_PER_ISSUE = 5  # comment excerpts per issue
_GH_ISSUES_COMMENT_CHARS = 280     # excerpt truncation length


def _gh_reactions(obj):
    """total_count from a GitHub `reactions` sub-object (search issue items
    and comment bodies both carry one)."""
    return (obj.get("reactions") or {}).get("total_count") or 0


def channel_github_issues(query, out_path, max_items):
    """Issues + comment bodies as product/competitor evidence (R11).

    Two modes:
      - topic (default): search issues everywhere sorted by reactions, then
        rank client-side via rank_items (reactions = engagement, comment
        count = corroboration, relevance floor vs the topic);
      - owner/repo (query matches `owner/repo`): top issues of that repo by
        reactions, server order kept — there is no topic to rank against.

    For the top few issues the comment bodies are pulled (capped + truncated)
    so the report carries actual user voice, not just titles. A failed
    comment fetch degrades that one issue (note line), never the siblings.
    Zero-config Tier 0: authed `gh` preferred, anonymous fallback; a hard
    search failure (e.g. HTTP 403 rate limit) propagates so run_connector
    writes ERROR.md."""
    topic = query.strip()
    repo_mode = bool(_GH_REPO_RE.match(topic))
    q = f"repo:{topic} is:issue" if repo_mode else f"{topic} is:issue"
    pool = max_items if repo_mode else min(30, max(15, max_items * 3))
    found = gh_api(
        "search/issues?"
        + urllib.parse.urlencode({"q": q, "sort": "reactions", "order": "desc", "per_page": pool})
    )
    items = found.get("items", [])
    note = None
    if repo_mode:
        issues = items[:max_items]
    else:
        for it in items:
            it["_rank_text"] = f"{it.get('title') or ''} {(it.get('body') or '')[:400]}"
            it["_reactions"] = _gh_reactions(it)
        ranked = rank_items(
            items,
            topic,
            text_key="_rank_text",
            engagement_key="_reactions",
            comments_key="comments",
            max_items=max_items,
        )
        issues, note = ranked.items, ranked.note

    scope = (
        f"repo {topic} — top issues by reactions (server order)"
        if repo_mode
        else "issue search ranked by reactions + comment corroboration"
    )
    lines = [f"# GitHub issues — for: {query}\n", f"_Scope: {scope}._\n"]
    if note:
        lines.append(f"_Note: {note}._\n")
    if not issues:
        lines.append("_No issues found._\n")
    for pos, it in enumerate(issues):
        lines.append(
            f"- **{it.get('title') or '?'}** — {it.get('state') or '?'}, "
            f"👍{_gh_reactions(it)} reactions, {it.get('comments') or 0} comments, "
            f"updated {(it.get('updated_at') or '')[:10]}"
        )
        lines.append(f"  - {it.get('html_url')}")
        if pos >= _GH_ISSUES_COMMENT_ISSUES or not it.get("comments"):
            continue
        repo_path = (it.get("repository_url") or "").rsplit("/repos/", 1)[-1]
        number = it.get("number")
        if not repo_path or number is None:
            continue
        try:
            comments = gh_api(
                f"repos/{repo_path}/issues/{number}/comments?"
                + urllib.parse.urlencode({"per_page": _GH_ISSUES_COMMENTS_PER_ISSUE})
            )
        except Exception as e:  # noqa: BLE001 — one issue's comments never kill siblings
            lines.append(f"  - _comments unavailable: {str(e)[:120]}_")
            continue
        for c in comments[:_GH_ISSUES_COMMENTS_PER_ISSUE]:
            author = (c.get("user") or {}).get("login") or "?"
            body = excerpt(c.get("body"), _GH_ISSUES_COMMENT_CHARS)
            lines.append(f"  - @{author} (👍{_gh_reactions(c)}): {body}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(issues)


ARCTIC_SHIFT_BASE = "https://arctic-shift.photon-reddit.com/api"
_REDDIT_MAX_SUBS = 4        # subreddits searched per run (rate-limit friendly)
_REDDIT_POOL_PER_SUB = 25   # posts pulled per subreddit before ranking
_REDDIT_WINDOW_DAYS = 365   # recency window
_ARCTIC_SHIFT_RETRY_SLEEP = 3.0  # seconds before the single 429 retry


def _arctic_shift_json(url, timeout=30):
    """GET with ONE polite retry on 429 — Arctic-Shift rate-limits complex
    queries (observed live: 'Too many complex queries. Please slow down.').
    A persistent 429 or any other error propagates so the run_connector
    wrapper writes ERROR.md."""
    try:
        return get_json(url, timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code != 429:
            raise
        time.sleep(_ARCTIC_SHIFT_RETRY_SLEEP)
        return get_json(url, timeout=timeout)


def _arctic_shift_discover_subreddits(query, limit=_REDDIT_MAX_SUBS):
    """Arctic-Shift's free-text post search REQUIRES a subreddit (or author)
    filter — verified live 2026-07-17: 400 \"'query' query parameter requires
    one of: author, subreddit\". So: prefix-match distinctive topic tokens
    against the subreddit index, keep the candidates whose name/description
    actually relate to the topic, best (relevance, subscribers) first."""
    candidates = {}
    joined_topic = "".join(_rank_tokens(query))  # "prompt engineering" -> "promptengineering"
    for token in _rank_tokens(query)[:5]:
        if len(token) < 3:
            continue
        url = f"{ARCTIC_SHIFT_BASE}/subreddits/search?" + urllib.parse.urlencode(
            {"subreddit_prefix": token, "limit": 10}
        )
        for row in _arctic_shift_json(url, timeout=25).get("data") or []:
            name = row.get("display_name") or ""
            if not name or name in candidates:
                continue
            about = " ".join(
                str(row.get(k) or "")
                for k in ("display_name", "title", "public_description")
            )
            rel = relevance_score(about, query)
            # CamelCase names tokenize to one word ("PromptEngineering") and
            # would score 0 — a name that IS the topic concatenated is the
            # strongest possible signal.
            if joined_topic and joined_topic in name.lower():
                rel = 1.0
            candidates[name] = (rel, row.get("subscribers") or 0)
    ordered = sorted(candidates.items(), key=lambda kv: (-kv[1][0], -kv[1][1], kv[0]))
    return [name for name, _ in ordered[:limit]]


def channel_reddit(query, out_path, max_items):
    """Reaction-weighted Reddit via the free Arctic-Shift archive (the old
    reddit.com/search.json path is dead — Reddit throttles unauthenticated
    JSON). Real `score` + `num_comments` confirmed in the live API. No
    server-side score sort exists (sort_type: default|created_utc only), so
    posts are pulled recent-first and ranked here via rank_items. Comment
    bodies are NOT pulled: /api/comments/search 422s (\"Timeout. Maybe slow
    down a bit\") — too expensive for a Tier-0 pass."""
    subs = _arctic_shift_discover_subreddits(query)
    lines = [f"# Reddit — top posts for: {query}\n"]
    if not subs:
        lines.append(
            "_No posts pulled: Arctic-Shift text search requires a subreddit "
            "filter and no candidate subreddit matched this topic's tokens._\n"
        )
        out_path.write_text("\n".join(lines) + "\n")
        return 0

    after = time.strftime(
        "%Y-%m-%d", time.gmtime(time.time() - _REDDIT_WINDOW_DAYS * 86400)
    )
    posts, seen = [], set()
    for i, sub in enumerate(subs):
        if i:  # pace the "complex" text-search queries a little
            time.sleep(0.5)
        url = f"{ARCTIC_SHIFT_BASE}/posts/search?" + urllib.parse.urlencode(
            {
                "query": query,
                "subreddit": sub,
                "after": after,
                "limit": _REDDIT_POOL_PER_SUB,
                "sort": "desc",
                "sort_type": "created_utc",
                "fields": "id,title,score,num_comments,subreddit,created_utc,selftext",
            }
        )
        for p in _arctic_shift_json(url, timeout=30).get("data") or []:
            pid = p.get("id")
            if pid and pid in seen:
                continue
            seen.add(pid)
            p["_rank_text"] = f"{p.get('title') or ''} {(p.get('selftext') or '')[:400]}"
            posts.append(p)

    scope = ", ".join(f"r/{s}" for s in subs)
    lines.append(f"_Source: Arctic-Shift archive (free), last year. Scope: {scope}._\n")

    if posts and not any("score" in p for p in posts):
        lines.append(
            "_Degraded: Arctic-Shift returned posts without score fields — "
            "engagement ranking unavailable, order is relevance-only._\n"
        )
    ranked = rank_items(
        posts,
        query,
        text_key="_rank_text",
        engagement_key="score",
        comments_key="num_comments",
        max_items=max_items,
    )
    if ranked.note:
        lines.append(f"_Note: {ranked.note}._\n")
    if not ranked.items:
        lines.append("_No posts found._\n")
    for p in ranked.items:
        lines.append(
            f"- **{p.get('title','?')}** — ▲{p.get('score',0)}, "
            f"{p.get('num_comments',0)} comments, r/{p.get('subreddit','?')}"
        )
        permalink = p.get("permalink")
        if permalink:
            lines.append(f"  - https://www.reddit.com{permalink}")
        else:
            lines.append(
                f"  - https://www.reddit.com/r/{p.get('subreddit','?')}/comments/{p.get('id','')}"
            )
    out_path.write_text("\n".join(lines) + "\n")
    return len(ranked.items)


def channel_bluesky(query, out_path, max_items):
    """Best-effort public AppView search (no auth)."""
    url = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?" + urllib.parse.urlencode(
        {"q": query, "limit": max_items, "sort": "top"}
    )
    data = get_json(url, timeout=20)
    posts = data.get("posts", [])
    lines = [f"# Bluesky — top posts for: {query}\n"]
    if not posts:
        lines.append("_No posts found._\n")
    for p in posts:
        author = p.get("author", {}).get("handle", "?")
        text = (p.get("record", {}).get("text", "") or "").replace("\n", " ")
        likes = p.get("likeCount", 0)
        reposts = p.get("repostCount", 0)
        uri = p.get("uri", "")
        rkey = uri.split("/")[-1] if uri else ""
        lines.append(f"- @{author} — ♥{likes}, ⟲{reposts}: {text[:240]}")
        if rkey:
            lines.append(f"  - https://bsky.app/profile/{author}/post/{rkey}")
    out_path.write_text("\n".join(lines) + "\n")
    return len(posts)


# ---------------------------------------------------------------------------
# Connector registry
# ---------------------------------------------------------------------------
class Connector:
    def __init__(self, name, kind, fn, source, requires=(), default=True, fallback_key=None):
        self.name = name
        self.kind = kind  # 'llm' | 'direct'
        self.fn = fn
        self.source = source
        self.requires = list(requires)
        self.default = default
        # Tier 2 (R8): a key that satisfies `requires` when the direct key is
        # absent (the channel itself still prefers the direct key).
        self.fallback_key = fallback_key

    def missing_keys(self):
        missing = [k for k in self.requires if not KEYS.get(k)]
        if missing and self.fallback_key and KEYS.get(self.fallback_key):
            return []
        return missing

    def available(self):
        return not self.missing_keys()


CONNECTORS = {
    c.name: c
    for c in [
        Connector("gemini", "llm", channel_gemini, "YouTube + web (Gemini grounding)", ["gemini"], fallback_key="openrouter"),
        Connector("grok", "llm", channel_grok, "X / Twitter live (Grok x_search)", ["grok"], fallback_key="openrouter"),
        # openai is OFF by default: it bills the OpenAI API per token. Web/social
        # is covered by gemini+grok+perplexity (not OpenAI/Anthropic) + direct
        # channels. Opt in explicitly with --only openai when you want a GPT lens.
        # NO OpenRouter fallback here either — openai stays direct-key only (R17).
        Connector("openai", "llm", channel_openai, "Reddit/HN/GitHub/blogs (gpt-5.4 web_search) — OPT-IN, bills OpenAI API", ["openai"], default=False),
        Connector("perplexity", "llm", channel_perplexity, "web + news, citation-first (Sonar)", ["perplexity"], fallback_key="openrouter"),
        Connector("hackernews", "direct", channel_hackernews, "HN Algolia — points/comments", []),
        Connector("hiring", "direct", channel_hiring, "HN Who-is-hiring — job-market hotness for a topic", []),
        Connector("polymarket", "direct", channel_polymarket, "real-money prediction odds", []),
        Connector("github", "direct", channel_github, "repo stars + velocity", []),
        Connector("github-issues", "direct", channel_github_issues, "issues + comment evidence (free)", []),
        Connector("reddit", "direct", channel_reddit, "top posts via Arctic-Shift archive (free, score+comments)", []),
        Connector("bluesky", "direct", channel_bluesky, "top posts (best-effort)", []),
        Connector("launch-radar", "direct", channel_launch_radar, "what's shipping: Show HN + yc-oss + DevHunt (+PH with token)", []),
        Connector("revenue-radar", "direct", channel_revenue_radar, "what's selling: Flippa sold + Substack leaderboards (free)", []),
        Connector("meta-ads", "direct", channel_meta_ads, "who's paying to advertise: Meta Ad Library, EU scope (free token)", ["meta_ads"]),
        # telegram is OFF by default (R9): it drives a real client session and
        # is additionally gated at run time by DEEP_RESEARCH_TELEGRAM_ACK +
        # a *.session file in the secrets dir. Opt in with --only telegram.
        Connector("telegram", "direct", channel_telegram, "Telegram channels + comments via client session (opt-in, moat)", [], default=False),
        # tiktok-ig is OFF by default AND key-gated (R10): pay-per-use vendor,
        # every run costs credits. Opt in with --only tiktok-ig.
        Connector("tiktok-ig", "direct", channel_tiktok_ig, "TikTok/IG posts+comments via pay-per-use vendor (opt-in)", ["scrapecreators"], default=False),
        # threads (R23): official token preferred (free, Meta TOP order, no
        # engagement counts); fallback_key keeps it available with ONLY the
        # ScrapeCreators key — the channel then routes to the vendor path.
        Connector("threads", "direct", channel_threads, "Threads posts by keyword (official token or ScrapeCreators)", ["threads"], fallback_key="scrapecreators"),
    ]
}

OUTPUT_NAMES = {
    "gemini": "gemini-youtube.md",
    "grok": "grok-x.md",
    "openai": "openai-social.md",
    "perplexity": "perplexity-web.md",
    "hackernews": "hackernews.md",
    "hiring": "hiring.md",
    "polymarket": "polymarket.md",
    "github": "github.md",
    "github-issues": "github-issues.md",
    "reddit": "reddit.md",
    "bluesky": "bluesky.md",
    "launch-radar": "launch-radar.md",
    "revenue-radar": "revenue-radar.md",
    "meta-ads": "meta-ads.md",
    "telegram": "telegram.md",
    "tiktok-ig": "tiktok-ig.md",
    "threads": "threads.md",
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run_connector(conn, query, out_dir, max_items, manifest, lock, announce=True):
    """Run one connector; record its outcome in the manifest.

    ``announce`` controls the per-channel stderr prints: True in the plain
    tier (today's byte-compatible line-per-event output), False when the
    animated board renders instead (KTD4 — the board replaces these lines
    and the final summary is printed once after board teardown).
    """
    t0 = time.time()
    out_path = out_dir / OUTPUT_NAMES[conn.name]
    try:
        n = conn.fn(query, out_path, max_items)
        dt = time.time() - t0
        with lock:
            manifest["channels"][conn.name] = {"status": "ok", "items_or_chars": n, "seconds": round(dt, 1)}
        if announce:
            print(f"[{conn.name}] OK {dt:.1f}s ({n})", file=sys.stderr)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:800]
        out_path.with_suffix(".ERROR.md").write_text(f"HTTP {e.code}\n{detail}")
        with lock:
            manifest["channels"][conn.name] = {"status": "error", "error": f"HTTP {e.code}"}
        if announce:
            print(f"[{conn.name}] HTTP {e.code}: {detail[:160]}", file=sys.stderr)
    except Exception as e:  # noqa: BLE001 — degrade, never kill siblings
        out_path.with_suffix(".ERROR.md").write_text(f"ERROR: {e}")
        with lock:
            manifest["channels"][conn.name] = {"status": "error", "error": str(e)[:200]}
        if announce:
            print(f"[{conn.name}] ERROR: {e}", file=sys.stderr)


_BOARD_FRAME_SECONDS = 0.1  # ~10 fps


def _board_loop(board, manifest, lock, stop_event):
    """Board render thread: snapshot manifest state under the lock, write
    frames at ~10 fps. ``render()`` stays pure — this thread only snapshots
    and writes. One final frame is drawn after stop is requested so the last
    visible state is complete (every completion/error/skip row present)
    before the caller erases it and prints the one-time summary."""
    skipped = manifest["connectors_skipped"]  # written once, before threads
    while True:
        stopping = stop_event.wait(_BOARD_FRAME_SECONDS)
        with lock:
            state = dict(manifest["channels"])
        board.clear_and_write(state, skipped)
        if stopping:
            return


def select_connectors(only, skip):
    if only:
        want = [c.strip() for c in only.split(",") if c.strip()]
        unknown = [c for c in want if c not in CONNECTORS]
        if unknown:
            print(f"error: unknown connector(s): {', '.join(unknown)}", file=sys.stderr)
            sys.exit(2)
        chosen = [CONNECTORS[c] for c in want]
    else:
        skipset = {c.strip() for c in (skip or "").split(",") if c.strip()}
        unknown = sorted(skipset.difference(CONNECTORS))
        if unknown:
            print(f"error: unknown connector(s): {', '.join(unknown)}", file=sys.stderr)
            sys.exit(2)
        chosen = [c for c in CONNECTORS.values() if c.default and c.name not in skipset]
    # drop LLM channels whose key is missing (record the skip)
    live, skipped = [], []
    for c in chosen:
        (live if c.available() else skipped).append(c)
    return live, skipped


def parse_query_overrides(args):
    overrides = {}
    for spec in args.q:
        if ":" not in spec:
            raise ValueError(f"invalid --q value (expected name:query): {spec}")
        name, query = (part.strip() for part in spec.split(":", 1))
        if not name or not query:
            raise ValueError(f"invalid --q value (expected name:query): {spec}")
        if name not in CONNECTORS:
            raise ValueError(f"unknown connector in --q: {name}")
        overrides[name] = query

    for name, value in (
        ("gemini", args.gemini_q),
        ("grok", args.grok_q),
        ("openai", args.openai_q or args.openai_q_legacy),
    ):
        if value:
            overrides[name] = value
    return overrides


# ---------------------------------------------------------------------------
# HTML brief renderer (no external deps)
# ---------------------------------------------------------------------------
def _md_inline(s):
    s = html_mod.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"(?<!\")(https?://[^\s<]+)", r'<a href="\1">\1</a>', s)
    return s


def markdown_to_html(md):
    out, i, lines = [], 0, md.split("\n")
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(html_mod.escape(lines[i]))
                i += 1
            i += 1
            out.append("<pre><code>" + "\n".join(buf) + "</code></pre>")
            continue
        m = re.match(r"(#{1,4})\s+(.*)", line)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{_md_inline(m.group(2))}</h{lvl}>")
            i += 1
            continue
        if re.match(r"^\s*(-{3,}|\*{3,})\s*$", line):
            out.append("<hr>")
            i += 1
            continue
        # table
        if "|" in line and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", lines[i + 1]):
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            th = "".join(f"<th>{_md_inline(c)}</th>" for c in header)
            trs = "".join(
                "<tr>" + "".join(f"<td>{_md_inline(c)}</td>" for c in r) + "</tr>" for r in rows
            )
            out.append(f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>")
            continue
        # list
        if re.match(r"^\s*[-*]\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                indent = len(lines[i]) - len(lines[i].lstrip())
                content = re.sub(r"^\s*[-*]\s+", "", lines[i])
                items.append((indent, _md_inline(content)))
                i += 1
            out.append("<ul>" + "".join(f'<li style="margin-left:{d//2}px">{c}</li>' for d, c in items) + "</ul>")
            continue
        # paragraph (gather until blank)
        buf = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^\s*([-*#|]|```)", lines[i]):
            buf.append(lines[i])
            i += 1
        out.append("<p>" + _md_inline(" ".join(buf)) + "</p>")
    return "\n".join(out)


HTML_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root{{--bg:#0d1117;--panel:#161b22;--fg:#c9d1d9;--muted:#8b949e;--accent:#58a6ff;--border:#30363d}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);
 font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
 line-height:1.6;font-size:16px}}
.wrap{{max-width:820px;margin:0 auto;padding:48px 24px 96px}}
h1,h2,h3,h4{{line-height:1.25;font-weight:650}}
h1{{font-size:1.9rem;margin:0 0 .2em;border-bottom:1px solid var(--border);padding-bottom:.3em}}
h2{{font-size:1.35rem;margin:1.8em 0 .5em;color:#e6edf3}}
h3{{font-size:1.1rem;margin:1.4em 0 .4em}}
a{{color:var(--accent);text-decoration:none}}a:hover{{text-decoration:underline}}
code{{font-family:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
 background:var(--panel);padding:.15em .4em;border-radius:5px;font-size:.88em}}
pre{{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:14px 16px;overflow-x:auto}}
pre code{{background:none;padding:0}}
hr{{border:none;border-top:1px solid var(--border);margin:2em 0}}
ul{{padding-left:1.3em}}li{{margin:.25em 0}}
table{{border-collapse:collapse;width:100%;margin:1em 0;display:block;overflow-x:auto}}
th,td{{border:1px solid var(--border);padding:8px 12px;text-align:left;vertical-align:top}}
th{{background:var(--panel);font-weight:600}}
.meta{{color:var(--muted);font-size:.85rem;margin-top:.4em}}
</style></head>
<body><div class="wrap">
<div class="meta">deep-research brief · {date}</div>
{content}
</div></body></html>"""


def render_html(md_path, html_path):
    md = Path(md_path).read_text()
    title = "Deep Research Brief"
    for ln in md.split("\n"):
        m = re.match(r"#\s+(.*)", ln)
        if m:
            title = m.group(1).strip()
            break
    date = time.strftime("%Y-%m-%d")
    doc = HTML_TEMPLATE.format(
        title=html_mod.escape(title), date=date, content=markdown_to_html(md)
    )
    Path(html_path).write_text(doc)
    print(f"[html] wrote {html_path} ({len(doc)} bytes)", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def list_connectors_json():
    rows = []
    for c in CONNECTORS.values():
        row = {
            "name": c.name,
            "kind": c.kind,
            "source": c.source,
            "default": c.default,
            "available": c.available(),
            "requires": c.requires,
            "missing_keys": c.missing_keys(),
        }
        if c.fallback_key:
            row["fallback_key"] = c.fallback_key
        rows.append(row)
    print(json.dumps({"connectors": rows}, indent=2))


def _import_sibling(name):
    """Import a sibling module from scripts/ (no hyphen, so a plain import
    works when this file runs as a script and scripts/ is sys.path[0]); fall
    back to an explicit path insert for importlib-loaded copies of this
    module."""
    try:
        return importlib.import_module(name)
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        return importlib.import_module(name)


def main():
    process_cwd = Path.cwd().resolve()
    ap = argparse.ArgumentParser(
        description="Deep research raw-evidence runner: multi-channel parallel pull"
    )
    ap.add_argument("topic", nargs="?", help="Topic to research")
    ap.add_argument("--topic", dest="topic2")
    ap.add_argument(
        "--output-dir",
        help="explicit raw-output directory (bypasses project-local allocation)",
    )
    ap.add_argument(
        "--project-root",
        help="project that owns default research output (default: Git root or launch cwd)",
    )
    ap.add_argument(
        "--launch-cwd",
        help="captured launch directory for project ownership and relative output paths",
    )
    ap.add_argument("--only", help="comma list: run ONLY these connectors")
    ap.add_argument("--skip", help="comma list: skip these connectors")
    ap.add_argument("--max-items", type=int, help="items per direct channel (default 10)")
    ap.add_argument(
        "--prepared-run",
        action="store_true",
        help="require --output-dir to be the untouched run reserved by the skill",
    )
    ap.add_argument("--q", action="append", default=[], metavar="name:query",
                    help="per-channel query override, repeatable (e.g. --q gemini:\"...\")")
    ap.add_argument(
        "--no-banner",
        action="store_true",
        help="suppress the ZBS RESEARCHER banner art",
    )
    modes = ap.add_mutually_exclusive_group()
    modes.add_argument("--list-connectors", action="store_true", help="print connector availability as JSON and exit")
    modes.add_argument("--render-html", metavar="MD", help="render a markdown file to a shareable HTML brief")
    modes.add_argument(
        "--allocate-run",
        action="store_true",
        help="reserve a project-local run directory, print it, and exit",
    )
    modes.add_argument(
        "--diagnose",
        action="store_true",
        help="print an offline doctor report (providers, profile, onboarding state)",
    )
    modes.add_argument(
        "--signal",
        metavar="KIND",
        help="record a demand signal (want-paid | host-for-me) and exit",
    )
    ap.add_argument("--html-out", metavar="HTML", help="output path for --render-html")
    # legacy aliases
    ap.add_argument("--gemini-q")
    ap.add_argument("--grok-q")
    ap.add_argument("--openai-q")
    ap.add_argument("--gpt-q", dest="openai_q_legacy", help=argparse.SUPPRESS)
    args = ap.parse_args()

    # Terminal capabilities: probed once per process, on stderr (R5/KTD3).
    # plain tier => byte-compatible output, no banner, no board.
    caps = term_ui.ansi_caps()
    show_banner = caps.tier != "plain" and not args.no_banner

    try:
        launch_cwd = resolve_launch_directory(args.launch_cwd, process_cwd)
    except ValueError as exc:
        ap.error(str(exc))

    if args.html_out and not args.render_html:
        ap.error("--html-out requires --render-html")

    if args.list_connectors:
        list_connectors_json()
        return

    if args.diagnose:
        # Banner in ansi/unicode tiers only — piped/plain doctor output stays
        # exactly today's report (selftest pipes it; logs must stay clean).
        if show_banner:
            print(term_ui.banner(caps), file=sys.stderr)
        detect_state = _import_sibling("detect_state")
        print(detect_state.doctor_report())
        return

    if args.signal:
        signals = _import_sibling("signals")
        profile = os.environ.get("DEEP_RESEARCH_PROFILE", "").strip() or "client"
        try:
            result = signals.record_signal(args.signal, profile=profile)
        except (ValueError, OSError) as exc:
            ap.error(str(exc))
        print(signals.signal_message(args.signal, result.notified))
        return

    if args.render_html:
        out = args.html_out or str(Path(args.render_html).with_suffix(".html"))
        render_html(args.render_html, out)
        return

    if args.topic and args.topic2:
        ap.error("provide topic either positionally or with --topic, not both")
    topic = args.topic or args.topic2
    if not topic or not topic.strip():
        ap.error("topic required (positional or --topic)")
    topic = topic.strip()

    if args.only and args.skip:
        ap.error("--only and --skip cannot be used together")

    if args.prepared_run and args.output_dir is None:
        ap.error("--prepared-run requires --output-dir")

    if args.allocate_run:
        if args.output_dir is not None:
            ap.error("--allocate-run cannot be combined with --output-dir")
        if any(
            (
                args.only,
                args.skip,
                args.q,
                args.gemini_q,
                args.grok_q,
                args.openai_q,
                args.openai_q_legacy,
                args.max_items is not None,
                args.prepared_run,
            )
        ):
            ap.error("--allocate-run cannot be combined with connector options")
        try:
            project_root = resolve_project_root(launch_cwd, args.project_root)
            out_dir = allocate_run_directory(project_root, topic)
            (out_dir / "_topic.txt").write_text(topic + "\n", encoding="utf-8")
        except (OSError, ValueError) as exc:
            ap.error(str(exc))
        print(out_dir)
        return

    try:
        overrides = parse_query_overrides(args)
    except ValueError as exc:
        ap.error(str(exc))

    # Validate connector selection before creating a default run directory.
    live, skipped = select_connectors(args.only, args.skip)

    if args.output_dir is not None:
        try:
            out_dir = resolve_output_directory(args.output_dir, launch_cwd)
            if args.prepared_run:
                claim_prepared_run_directory(out_dir, topic)
            else:
                out_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, ValueError) as exc:
            ap.error(str(exc))
    else:
        try:
            project_root = resolve_project_root(launch_cwd, args.project_root)
            out_dir = allocate_run_directory(project_root, topic)
        except (OSError, ValueError) as exc:
            ap.error(str(exc))

    try:
        (out_dir / "_topic.txt").write_text(topic + "\n", encoding="utf-8")
    except OSError as exc:
        ap.error(str(exc))

    max_items = args.max_items if args.max_items is not None else 10

    manifest = {
        "topic": topic,
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "connectors_run": [c.name for c in live],
        "connectors_skipped": {c.name: f"missing keys: {c.missing_keys()}" for c in skipped},
        "channels": {},
    }

    if show_banner:
        print(term_ui.banner(caps), file=sys.stderr)

    # Animated tier: the live board replaces the per-event prints (KTD4).
    # Otherwise (plain, or color-without-TTY via FORCE_COLOR) today's
    # line-per-event output stays the sole output — byte-compatible.
    if not caps.animate:
        for c in skipped:
            print(f"[{c.name}] SKIP — missing keys: {c.missing_keys()}", file=sys.stderr)

    lock = threading.Lock()
    run_start = time.time()
    board = board_stop = board_thread = None
    if caps.animate:
        registry_order = {name: i for i, name in enumerate(CONNECTORS)}
        requested = sorted(
            (c.name for c in live + skipped),
            key=lambda name: registry_order.get(name, len(registry_order)),
        )
        board = term_ui.LiveBoard(requested, caps, run_start, stream=sys.stderr)
        board_stop = threading.Event()
        board_thread = threading.Thread(
            target=_board_loop,
            args=(board, manifest, lock, board_stop),
            daemon=True,
        )
        board_thread.start()

    threads = [
        threading.Thread(
            target=run_connector,
            args=(c, overrides.get(c.name, topic), out_dir, max_items, manifest, lock),
            kwargs={"announce": not caps.animate},
        )
        for c in live
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if board is not None:
        board_stop.set()
        board_thread.join()
        board.stop()
        # Final per-channel summary — printed exactly once, in board order,
        # in the same format as the plain tier's line-per-event output.
        for name in board.channel_names:
            reason = manifest["connectors_skipped"].get(name)
            if reason is not None:
                print(f"[{name}] SKIP — {reason}", file=sys.stderr)
                continue
            record = manifest["channels"].get(name) or {}
            if record.get("status") == "ok":
                seconds = record.get("seconds")
                seconds = seconds if isinstance(seconds, (int, float)) else 0.0
                print(
                    f"[{name}] OK {seconds:.1f}s ({record.get('items_or_chars')})",
                    file=sys.stderr,
                )
            else:
                error = term_ui.sanitize(record.get("error", "?"))
                print(f"[{name}] ERROR: {error}", file=sys.stderr)

    manifest["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"\nAll channels done. Output: {out_dir}", file=sys.stderr)
    for f in sorted(out_dir.iterdir()):
        if f.is_file():
            print(f"  {f.name}: {f.stat().st_size} bytes", file=sys.stderr)


if __name__ == "__main__":
    main()
