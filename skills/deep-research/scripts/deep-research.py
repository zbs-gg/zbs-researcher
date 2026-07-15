#!/usr/bin/env python3
"""
Deep research orchestrator: many channels in parallel + synthesis.

Two channel families run concurrently and write one markdown file each:

  LLM channels (need an API key; each is a reasoning model with its own
  live access to a slice of the web):
    - gemini      Gemini 2.5 Pro + googleSearch grounding -> YouTube + web
    - grok        Grok-4 + x_search -> realtime X / Twitter
    - openai      gpt-5.4 (NON-Pro) + web_search -> Reddit / HN / GitHub / blogs
    - perplexity  Sonar online -> web + news, citation-first

  Direct channels (zero-config, free; give STRUCTURAL signal an LLM
  won't hand you — raw numbers, odds, velocity):
    - hackernews  HN Algolia -> stories ranked by points/comments
    - polymarket  Gamma markets -> real-money odds on the topic
    - github      repo search -> stars, recent activity, top issues
    - reddit      search.json -> top posts by upvotes (best-effort; Reddit
                  throttles unauthenticated JSON, degrades to ERROR.md)
    - bluesky     app.bsky searchPosts (best-effort)

Claude (the caller) does synthesis after channels return, reading the
report files, then optionally renders a shareable HTML brief via
`--render-html`.

Channels are independent; if one fails it writes <name>.ERROR.md and the
others continue. A manifest.json records what ran, what was skipped, and why.

Pro models (gpt-5.4-pro, gpt-5.5) are intentionally NOT used here — non-Pro
retrieval + citation is enough. Pro spend is reserved for emergency-pro.

Usage:
    # discover what's live (used by the plan step before any run)
    python3 deep-research.py --list-connectors

    # run (default = every available connector)
    python3 deep-research.py "TOPIC" --output-dir DIR
    python3 deep-research.py "TOPIC" --output-dir DIR --only gemini,hackernews,polymarket
    python3 deep-research.py "TOPIC" --output-dir DIR --skip reddit,bluesky

    # per-channel query aim
    python3 deep-research.py --topic T --output-dir D \\
        --q gemini:"YouTube talks on X" --q openai:"Reddit/HN on X"
    # legacy aliases still work: --gemini-q --grok-q --openai-q

    # render a shareable HTML brief from the synthesis markdown
    python3 deep-research.py --render-html DIR/synthesis.md --html-out DIR/brief.html
"""
import argparse
import hashlib
import html as html_mod
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Where per-provider key files live. Defaults to ~/.openclaw/secrets (the
# author's setup) but is overridable so anyone can point it elsewhere — or
# skip files entirely and use env vars (GEMINI_API_KEY, GROK_API_KEY,
# OPENAI_API_KEY, PERPLEXITY_API_KEY), which read_key() falls back to.
SECRETS = Path(os.environ.get("DEEP_RESEARCH_SECRETS_DIR", str(Path.home() / ".openclaw" / "secrets"))).expanduser()
UA = "deep-research/2.0 (+https://github.com/nkkmnk/deep-research-skill)"


def read_key(filenames, prefix_pattern, env_var=None):
    """Read an API key from the first of ~/.openclaw/secrets/<name> that
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
    # Optional paid video sources — only wired if a key shows up.
    "scrapecreators": read_key(["scrapecreators-key.txt"], r"[A-Za-z0-9_\-]{12,}", "SCRAPECREATORS_KEY"),
    "brave": read_key(["brave-key.txt"], r"[A-Za-z0-9_\-]{12,}", "BRAVE_API_KEY"),
}

OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = os.environ.get("OPENAI_RESEARCH_MODEL", "gpt-5.4")
PERPLEXITY_MODEL = os.environ.get("PERPLEXITY_RESEARCH_MODEL", "sonar")

RUN_PREFIX = "deep-research-"
RESEARCH_DIR_NAME = "research"
FALLBACK_NAME_MAX = 255


# ---------------------------------------------------------------------------
# Project-local output paths
# ---------------------------------------------------------------------------
def _launch_relative_path(value, launch_cwd):
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path(launch_cwd) / path
    return path.resolve()


def resolve_output_directory(output_dir, launch_cwd):
    """Resolve an explicit output override from the captured launch cwd."""
    return _launch_relative_path(output_dir, launch_cwd)


def resolve_project_root(launch_cwd, explicit_root=None):
    """Resolve explicit root, Git top-level, or the captured cwd in that order."""
    launch_cwd = Path(launch_cwd).resolve()
    if explicit_root is not None:
        root = _launch_relative_path(explicit_root, launch_cwd)
        if not root.is_dir():
            raise ValueError(f"project root is not an existing directory: {root}")
        return root

    try:
        result = subprocess.run(
            ["git", "-C", str(launch_cwd), "rev-parse", "--show-toplevel"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (FileNotFoundError, OSError):
        return launch_cwd

    if result.returncode == 0 and result.stdout.strip():
        root = Path(result.stdout.strip()).resolve()
        if root.is_dir():
            return root
    return launch_cwd


def topic_slug(topic):
    """Return a normalized, deterministic directory slug for a topic."""
    normalized = unicodedata.normalize("NFKC", topic).casefold()
    parts = []
    pending_separator = False
    for char in normalized:
        if char.isalnum():
            if pending_separator and parts:
                parts.append("-")
            parts.append(char)
            pending_separator = False
        else:
            pending_separator = True
    slug = "".join(parts)
    if slug:
        return slug
    digest = hashlib.sha256(topic.encode("utf-8")).hexdigest()[:8]
    return f"topic-{digest}"


def _filesystem_name_max(path):
    try:
        value = os.pathconf(str(path), "PC_NAME_MAX")
    except (AttributeError, OSError, ValueError):
        return FALLBACK_NAME_MAX
    return value if isinstance(value, int) and value > 0 else FALLBACK_NAME_MAX


def _truncate_utf8(value, byte_limit):
    if byte_limit <= 0:
        return ""
    encoded = value.encode("utf-8")
    if len(encoded) <= byte_limit:
        return value
    return encoded[:byte_limit].decode("utf-8", errors="ignore")


def _run_component(slug, run_date, attempt, name_max):
    suffix = "" if attempt == 1 else f"-{attempt:02d}"
    fixed = f"{RUN_PREFIX}{run_date}{suffix}"
    slug_budget = name_max - len(fixed.encode("utf-8")) - 1
    if slug_budget < 1:
        raise ValueError(
            f"filesystem name limit {name_max} is too small for a research run"
        )
    trimmed_slug = _truncate_utf8(slug, slug_budget)
    if not trimmed_slug:
        raise ValueError(
            f"filesystem name limit {name_max} is too small for a research run slug"
        )
    return f"{RUN_PREFIX}{trimmed_slug}-{run_date}{suffix}"


def allocate_run_directory(project_root, topic, run_date=None, name_max=None):
    """Atomically reserve and return a unique project-local research run."""
    project_root = Path(project_root).resolve()
    if not project_root.is_dir():
        raise ValueError(
            f"project root is not an existing directory: {project_root}"
        )

    research_root = project_root / RESEARCH_DIR_NAME
    research_root.mkdir(parents=True, exist_ok=True)
    run_date = run_date or time.strftime("%Y-%m-%d")
    name_max = name_max or _filesystem_name_max(research_root)
    slug = topic_slug(topic)

    attempt = 1
    while True:
        component = _run_component(slug, run_date, attempt, name_max)
        candidate = research_root / component
        try:
            candidate.mkdir(exist_ok=False)
            return candidate
        except FileExistsError:
            attempt += 1


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
# ---------------------------------------------------------------------------
def channel_gemini(query, out_path, max_items):
    body = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            "Search the web (especially YouTube) for the topic below. "
                            "Find recent (2025-2026) videos / talks / tutorials. "
                            "For each finding: title, channel/author, url, key claim "
                            "(2-3 sentences). Flag contradictions with other sources. "
                            "Conclude with a 5-7 line summary of recurring themes.\n\n"
                            f"TOPIC: {query}"
                        )
                    }
                ],
            }
        ],
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
    body = {
        "model": "grok-4.20-reasoning",
        "input": [
            {
                "role": "system",
                "content": (
                    "You search X / Twitter for honest user voice on technical topics. "
                    "Quote actual posts when available. Note dates. Surface contradictions."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Search X for posts (2025-2026) about: {query}\n\n"
                    "Return: 1) 5-15 representative quotes (verbatim if possible) with "
                    "author handle and date, 2) recurring complaints, 3) workarounds "
                    "people share, 4) overall sentiment."
                ),
            },
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
    body = {
        "model": PERPLEXITY_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a citation-first research assistant. Answer with concrete, "
                    "recent (2025-2026) findings and always attribute claims to sources. "
                    "Surface disagreements between sources rather than smoothing them over."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Research this topic and report key findings with dates and sources, "
                    f"noting any contradictions: {query}"
                ),
            },
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
# Direct channels (structural signal)
# ---------------------------------------------------------------------------
def channel_hackernews(query, out_path, max_items):
    url = (
        "https://hn.algolia.com/api/v1/search?"
        + urllib.parse.urlencode({"query": query, "tags": "story", "hitsPerPage": max_items})
    )
    data = get_json(url, timeout=20)
    hits = data.get("hits", [])
    lines = [f"# Hacker News — top stories for: {query}\n"]
    if not hits:
        lines.append("_No stories found._\n")
    for h in hits:
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
    return len(hits)


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


def channel_github(query, out_path, max_items):
    """Repo + issue search. Prefer authed `gh` (higher rate limit); fall
    back to unauthenticated api.github.com search."""
    def gh_api(path):
        if shutil.which("gh"):
            r = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                return json.loads(r.stdout)
        return get_json("https://api.github.com/" + path, timeout=25)

    repos = gh_api(
        "search/repositories?" + urllib.parse.urlencode({"q": query, "sort": "stars", "per_page": max_items})
    )
    issues = gh_api(
        "search/issues?"
        + urllib.parse.urlencode({"q": f"{query} in:title", "sort": "updated", "per_page": max_items})
    )
    lines = [f"# GitHub — for: {query}\n", "## Top repositories (by stars)\n"]
    for r in repos.get("items", [])[:max_items]:
        lines.append(
            f"- **{r.get('full_name')}** — ★{r.get('stargazers_count',0):,}, "
            f"pushed {(r.get('pushed_at') or '')[:10]}"
        )
        if r.get("description"):
            lines.append(f"  - {r['description']}")
        lines.append(f"  - {r.get('html_url')}")
    lines.append("\n## Recent issues / PRs mentioning it\n")
    for it in issues.get("items", [])[:max_items]:
        kind = "PR" if it.get("pull_request") else "issue"
        lines.append(
            f"- [{kind}] **{it.get('title')}** — {it.get('comments',0)} comments, "
            f"updated {(it.get('updated_at') or '')[:10]}"
        )
        lines.append(f"  - {it.get('html_url')}")
    out_path.write_text("\n".join(lines) + "\n")
    return len(repos.get("items", [])) + len(issues.get("items", []))


def channel_reddit(query, out_path, max_items):
    """Best-effort: Reddit throttles unauthenticated .json and may return
    HTML — in which case we raise so the wrapper writes ERROR.md."""
    url = "https://www.reddit.com/search.json?" + urllib.parse.urlencode(
        {"q": query, "sort": "top", "t": "year", "limit": max_items}
    )
    data = get_json(url, timeout=20)  # raises/JSON-decode-errors if HTML served
    children = data.get("data", {}).get("children", [])
    lines = [f"# Reddit — top posts for: {query}\n"]
    if not children:
        lines.append("_No posts found._\n")
    for ch in children:
        d = ch.get("data", {})
        lines.append(
            f"- **{d.get('title','?')}** — ▲{d.get('ups',0)}, {d.get('num_comments',0)} comments, "
            f"r/{d.get('subreddit','?')}"
        )
        lines.append(f"  - https://www.reddit.com{d.get('permalink','')}")
    out_path.write_text("\n".join(lines) + "\n")
    return len(children)


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
    def __init__(self, name, kind, fn, source, requires=(), default=True):
        self.name = name
        self.kind = kind  # 'llm' | 'direct'
        self.fn = fn
        self.source = source
        self.requires = list(requires)
        self.default = default

    def missing_keys(self):
        return [k for k in self.requires if not KEYS.get(k)]

    def available(self):
        return not self.missing_keys()


CONNECTORS = {
    c.name: c
    for c in [
        Connector("gemini", "llm", channel_gemini, "YouTube + web (Gemini grounding)", ["gemini"]),
        Connector("grok", "llm", channel_grok, "X / Twitter live (Grok x_search)", ["grok"]),
        # openai is OFF by default: it bills the OpenAI API per token. Web/social
        # is covered by gemini+grok+perplexity (not OpenAI/Anthropic) + direct
        # channels. Opt in explicitly with --only openai when you want a GPT lens.
        Connector("openai", "llm", channel_openai, "Reddit/HN/GitHub/blogs (gpt-5.4 web_search) — OPT-IN, bills OpenAI API", ["openai"], default=False),
        Connector("perplexity", "llm", channel_perplexity, "web + news, citation-first (Sonar)", ["perplexity"]),
        Connector("hackernews", "direct", channel_hackernews, "HN Algolia — points/comments", []),
        Connector("hiring", "direct", channel_hiring, "HN Who-is-hiring — job-market hotness for a topic", []),
        Connector("polymarket", "direct", channel_polymarket, "real-money prediction odds", []),
        Connector("github", "direct", channel_github, "repo stars + velocity + issues", []),
        Connector("reddit", "direct", channel_reddit, "top posts by upvotes (best-effort)", []),
        Connector("bluesky", "direct", channel_bluesky, "top posts (best-effort)", []),
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
    "reddit": "reddit.md",
    "bluesky": "bluesky.md",
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run_connector(conn, query, out_dir, max_items, manifest, lock):
    t0 = time.time()
    out_path = out_dir / OUTPUT_NAMES[conn.name]
    try:
        n = conn.fn(query, out_path, max_items)
        dt = time.time() - t0
        with lock:
            manifest["channels"][conn.name] = {"status": "ok", "items_or_chars": n, "seconds": round(dt, 1)}
        print(f"[{conn.name}] OK {dt:.1f}s ({n})", file=sys.stderr)
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:800]
        out_path.with_suffix(".ERROR.md").write_text(f"HTTP {e.code}\n{detail}")
        with lock:
            manifest["channels"][conn.name] = {"status": "error", "error": f"HTTP {e.code}"}
        print(f"[{conn.name}] HTTP {e.code}: {detail[:160]}", file=sys.stderr)
    except Exception as e:  # noqa: BLE001 — degrade, never kill siblings
        out_path.with_suffix(".ERROR.md").write_text(f"ERROR: {e}")
        with lock:
            manifest["channels"][conn.name] = {"status": "error", "error": str(e)[:200]}
        print(f"[{conn.name}] ERROR: {e}", file=sys.stderr)


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
        rows.append(
            {
                "name": c.name,
                "kind": c.kind,
                "source": c.source,
                "default": c.default,
                "available": c.available(),
                "requires": c.requires,
                "missing_keys": c.missing_keys(),
            }
        )
    print(json.dumps({"connectors": rows}, indent=2))


def main():
    launch_cwd = Path.cwd().resolve()
    ap = argparse.ArgumentParser(description="Deep research: multi-channel parallel pull + synthesis")
    ap.add_argument("topic", nargs="?", help="Topic to research")
    ap.add_argument("--topic", dest="topic2")
    ap.add_argument("--output-dir")
    ap.add_argument(
        "--project-root",
        help="project that owns default research output (default: Git root or launch cwd)",
    )
    ap.add_argument("--only", help="comma list: run ONLY these connectors")
    ap.add_argument("--skip", help="comma list: skip these connectors")
    ap.add_argument("--max-items", type=int, default=10, help="items per direct channel (default 10)")
    ap.add_argument("--q", action="append", default=[], metavar="name:query",
                    help="per-channel query override, repeatable (e.g. --q gemini:\"...\")")
    modes = ap.add_mutually_exclusive_group()
    modes.add_argument("--list-connectors", action="store_true", help="print connector availability as JSON and exit")
    modes.add_argument("--render-html", metavar="MD", help="render a markdown file to a shareable HTML brief")
    modes.add_argument(
        "--allocate-run",
        action="store_true",
        help="reserve a project-local run directory, print it, and exit",
    )
    ap.add_argument("--html-out", metavar="HTML", help="output path for --render-html")
    # legacy aliases
    ap.add_argument("--gemini-q")
    ap.add_argument("--grok-q")
    ap.add_argument("--openai-q")
    ap.add_argument("--gpt-q", dest="openai_q_legacy", help=argparse.SUPPRESS)
    args = ap.parse_args()

    if args.html_out and not args.render_html:
        ap.error("--html-out requires --render-html")

    if args.list_connectors:
        list_connectors_json()
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

    if args.only and args.skip:
        ap.error("--only and --skip cannot be used together")

    if args.allocate_run:
        if args.output_dir:
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
            )
        ):
            ap.error("--allocate-run cannot be combined with connector options")
        try:
            project_root = resolve_project_root(launch_cwd, args.project_root)
            out_dir = allocate_run_directory(project_root, topic)
        except ValueError as exc:
            ap.error(str(exc))
        print(out_dir)
        return

    try:
        overrides = parse_query_overrides(args)
    except ValueError as exc:
        ap.error(str(exc))

    # Validate connector selection before creating a default run directory.
    live, skipped = select_connectors(args.only, args.skip)

    if args.output_dir:
        out_dir = resolve_output_directory(args.output_dir, launch_cwd)
    else:
        try:
            project_root = resolve_project_root(launch_cwd, args.project_root)
            out_dir = allocate_run_directory(project_root, topic)
        except ValueError as exc:
            ap.error(str(exc))

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "_topic.txt").write_text(topic + "\n")

    manifest = {
        "topic": topic,
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "connectors_run": [c.name for c in live],
        "connectors_skipped": {c.name: f"missing keys: {c.missing_keys()}" for c in skipped},
        "channels": {},
    }
    for c in skipped:
        print(f"[{c.name}] SKIP — missing keys: {c.missing_keys()}", file=sys.stderr)

    lock = threading.Lock()
    threads = [
        threading.Thread(
            target=run_connector,
            args=(c, overrides.get(c.name, topic), out_dir, args.max_items, manifest, lock),
        )
        for c in live
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    manifest["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"\nAll channels done. Output: {out_dir}", file=sys.stderr)
    for f in sorted(out_dir.iterdir()):
        if f.is_file():
            print(f"  {f.name}: {f.stat().st_size} bytes", file=sys.stderr)


if __name__ == "__main__":
    main()
