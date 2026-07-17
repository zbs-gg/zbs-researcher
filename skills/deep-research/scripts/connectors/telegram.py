"""Telegram connector (U6, R9; KTD4): channel posts + comment threads via a
read-only Telethon CLIENT session — the moat channel. A client session sees
what a human subscriber sees (views, reactions, discussion replies), which no
bot API exposes; that same power is why the connector is triple-gated:

  Gate 1 — acknowledgement. A client session can get the underlying account
  BANNED, and a ban/flag on a personal account also endangers personal DMs
  and chats. So the connector refuses to run until the environment carries
  DEEP_RESEARCH_TELEGRAM_ACK=separate-account (exact value): a SEPARATE /
  secondary research account only, never the personal one.

  Gate 2 — session location (KTD4). The Telethon *.session file is resolved
  ONLY under the SECRETS dir (DEEP_RESEARCH_SECRETS_DIR or
  ~/.openclaw/secrets). The project / research output tree is NEVER searched
  — a .session in cwd is a leak, not a credential. On POSIX the session file
  is best-effort chmod 0600; on Windows this is a silent no-op (no
  POSIX-only calls).

  Gate 3 — Telethon. An OPTIONAL lazy import inside _make_client: the
  deep-research core stays stdlib-only, and a missing package degrades to
  clean install guidance ("pip install telethon"), never a traceback crash.

Read-only core (reached only with ack + session + Telethon): resolve
channels — a `@handle` (or comma list of handles) is used directly; a plain
topic goes through Telethon global search plus GetChannelRecommendationsRequest
(subscriber-overlap discovery) seeded by the first hit — then pull recent
posts and top discussion replies per post, and rank with the runner's shared
rank_items (views = engagement, replies = corroboration). All
Telethon-touching logic lives behind small module hooks (_make_client,
_search_channels, _recommend_channels) so tests run without Telethon and
inject a fake client layer.

Helpers (SECRETS / read_key / rank_items) resolve through the runner's live
globals — see connectors/__init__.py.
"""
import os
import re

from . import runner

ACK_ENV = "DEEP_RESEARCH_TELEGRAM_ACK"
ACK_VALUE = "separate-account"
_MAX_CHANNELS = 4          # channels pulled per run (rate-friendly)
_SEARCH_LIMIT = 10         # global-search candidates before dedupe/cap
_COMMENT_POSTS = 5         # top posts that get comment excerpts
_COMMENTS_PER_POST = 5     # discussion replies per post
_EXCERPT_CHARS = 240

_HANDLE_RE = re.compile(r"^@[A-Za-z][A-Za-z0-9_]{2,31}$")

_HARD_WARNING = (
    "Telegram connector refused: the hard warning has not been acknowledged. "
    "This connector drives a REAL Telegram client session. Use a SEPARATE / "
    "secondary research account ONLY — never your personal account: "
    "client-session automation risks an account BAN, and a ban or flag on a "
    "personal account also endangers your personal DMs and chats. To opt in "
    f"explicitly, set {ACK_ENV}={ACK_VALUE} (exact value) and rerun with "
    "--only telegram."
)

_TELETHON_GUIDANCE = (
    "Telethon not installed — pip install telethon; connector skipped. "
    "(Telethon is an optional dependency of the telegram connector only; "
    "the deep-research core stays stdlib-only.)"
)


def _require_ack():
    if os.environ.get(ACK_ENV, "").strip() != ACK_VALUE:
        raise RuntimeError(_HARD_WARNING)


def _ensure_private(path):
    """Best-effort 0600 on POSIX; silent no-op elsewhere (Windows-safe)."""
    if os.name != "posix":
        return
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _resolve_session():
    """Resolve the Telethon session file under the SECRETS dir ONLY (KTD4:
    never the project or research output tree)."""
    secrets = runner("SECRETS")
    sessions = sorted(secrets.glob("*.session")) if secrets.is_dir() else []
    if not sessions:
        raise RuntimeError(
            f"no Telethon *.session file found in {secrets}. Create one ONCE "
            "by logging in with the SEPARATE research account via Telethon "
            "(interactive TelegramClient login), then move the resulting "
            ".session file into that secrets dir. Session files live ONLY in "
            "the secrets dir — never in the project or research output tree."
        )
    session = sessions[0]
    _ensure_private(session)
    return session


def _import_telethon():
    """Lazy optional import — Telethon must never be a hard dependency."""
    try:
        from telethon.sync import TelegramClient
    except ImportError:
        raise RuntimeError(_TELETHON_GUIDANCE) from None
    return TelegramClient


def _api_credentials():
    """api_id/api_hash from the secrets dir or env (my.telegram.org app)."""
    read_key = runner("read_key")
    api_id = read_key(["telegram-api-id.txt"], r"\d{4,}", "TELEGRAM_API_ID")
    api_hash = read_key(
        ["telegram-api-hash.txt"], r"[0-9a-fA-F]{16,}", "TELEGRAM_API_HASH"
    )
    if not api_id or not api_hash:
        raise RuntimeError(
            "Telegram API credentials missing — create an application at "
            "https://my.telegram.org (logged in as the separate research "
            "account) and store the values in telegram-api-id.txt / "
            "telegram-api-hash.txt in the secrets dir (or TELEGRAM_API_ID / "
            "TELEGRAM_API_HASH)."
        )
    return int(api_id), api_hash


def _make_client(session_path):
    """Build + connect a read-only Telethon client. Module-level hook so
    tests replace it with a fake client factory (no Telethon required)."""
    TelegramClient = _import_telethon()
    api_id, api_hash = _api_credentials()
    client = TelegramClient(str(session_path), api_id, api_hash)
    client.connect()
    if not client.is_user_authorized():
        client.disconnect()
        raise RuntimeError(
            "Telegram session file exists but is NOT authorized — log in "
            "once more with the separate research account to refresh it."
        )
    return client


def _close(client):
    try:
        client.disconnect()
    except Exception:  # noqa: BLE001 — closing must never mask the real error
        pass


def _parse_handles(query):
    """`@channel` or a comma/space list of handles -> bare usernames;
    anything else -> [] (discovery mode)."""
    tokens = [t for t in re.split(r"[,\s]+", (query or "").strip()) if t]
    if tokens and all(_HANDLE_RE.match(t) for t in tokens):
        return [t.lstrip("@") for t in tokens]
    return []


def _search_channels(client, query, limit=_SEARCH_LIMIT):
    """Telethon global search for public broadcast channels (lazy TL import;
    module-level hook — monkeypatched in tests)."""
    from telethon.tl import functions
    result = client(functions.contacts.SearchRequest(q=query, limit=limit))
    return [
        chat for chat in getattr(result, "chats", [])
        if getattr(chat, "username", None) and getattr(chat, "broadcast", False)
    ]


def _recommend_channels(client, seed):
    """Subscriber-overlap discovery: channels similar to the seed channel
    (GetChannelRecommendationsRequest). Module-level hook for tests."""
    from telethon.tl.functions.channels import GetChannelRecommendationsRequest
    result = client(GetChannelRecommendationsRequest(channel=seed))
    return [
        chat for chat in getattr(result, "chats", [])
        if getattr(chat, "username", None)
    ]


def _resolve_entities(client, query, limit=_MAX_CHANNELS):
    handles = _parse_handles(query)
    if handles:
        return [client.get_entity("@" + handle) for handle in handles[:limit]]
    found = _search_channels(client, query)
    recommended = []
    if found:
        try:
            recommended = _recommend_channels(client, found[0])
        except Exception:  # noqa: BLE001 — recommendations are best-effort
            recommended = []
    entities, seen = [], set()
    for chat in list(found) + list(recommended):
        username = getattr(chat, "username", None)
        if not username or username in seen:
            continue
        seen.add(username)
        entities.append(chat)
    return entities[:limit]


def _reaction_count(msg):
    reactions = getattr(msg, "reactions", None)
    total = 0
    for result in getattr(reactions, "results", None) or []:
        total += getattr(result, "count", 0) or 0
    return total


def _excerpt(text, limit=_EXCERPT_CHARS):
    flat = " ".join(str(text or "").split())
    return flat if len(flat) <= limit else flat[:limit].rstrip() + "…"


def _post_record(entity, msg):
    text = getattr(msg, "message", None) or getattr(msg, "text", None) or ""
    if not str(text).strip():
        return None
    date = getattr(msg, "date", None)
    return {
        "channel": getattr(entity, "title", None)
        or getattr(entity, "username", None) or "?",
        "username": getattr(entity, "username", None),
        "id": getattr(msg, "id", None),
        "text": " ".join(str(text).split()),
        "views": getattr(msg, "views", None) or 0,
        "reactions": _reaction_count(msg),
        "comment_count": getattr(getattr(msg, "replies", None), "replies", None)
        or 0,
        "date": date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else "?",
        "_entity": entity,
        "comments": [],
    }


def _pull_posts(client, entity, pool):
    posts = []
    for msg in client.iter_messages(entity, limit=pool):
        record = _post_record(entity, msg)
        if record:
            posts.append(record)
    return posts


def _pull_comments(client, post, limit=_COMMENTS_PER_POST):
    comments = []
    for msg in client.iter_messages(
        post["_entity"], limit=limit, reply_to=post["id"]
    ):
        text = getattr(msg, "message", None) or getattr(msg, "text", None) or ""
        if not str(text).strip():
            continue
        sender = getattr(msg, "sender", None)
        author = (
            getattr(sender, "username", None)
            or getattr(sender, "first_name", None) or "?"
        )
        comments.append({
            "author": author,
            "text": " ".join(str(text).split()),
            "reactions": _reaction_count(msg),
        })
    return comments


def channel_telegram(query, out_path, max_items):
    """Read-only pull of channel posts + top discussion replies, ranked by
    views/replies with the shared relevance floor. Triple-gated (ack env,
    session under SECRETS only, optional Telethon) — see module docstring."""
    _require_ack()
    session = _resolve_session()
    client = _make_client(session)
    try:
        entities = _resolve_entities(client, query)
        pool = min(30, max(10, max_items * 2))
        posts = []
        for entity in entities:
            posts.extend(_pull_posts(client, entity, pool))
        # Handle-mode has no meaningful topic text to rank against — an
        # empty topic makes rank_items order by engagement only, no floor.
        rank_topic = "" if _parse_handles(query) else query
        ranked = runner("rank_items")(
            posts, rank_topic, text_key="text", engagement_key="views",
            comments_key="comment_count", max_items=max_items,
        )
        shown = ranked.items
        for post in shown[:_COMMENT_POSTS]:
            if not post["comment_count"] or post["id"] is None:
                continue
            try:
                post["comments"] = _pull_comments(client, post)
            except Exception as exc:  # noqa: BLE001 — one thread never kills siblings
                post["comment_note"] = f"comments unavailable: {str(exc)[:120]}"
    finally:
        _close(client)

    lines = [
        f"# Telegram — channel posts + comments for: {query}\n",
        "_Source: read-only Telethon client session (separate research "
        "account; the session file lives only in the secrets dir)._\n",
    ]
    if ranked.note:
        lines.append(f"_Note: {ranked.note}._\n")
    if not shown:
        lines.append("_No channel posts matched._\n")
    for post in shown:
        handle = f" (@{post['username']})" if post["username"] else ""
        lines.append(
            f"- **{post['channel']}**{handle} — {post['date']}: "
            f"{_excerpt(post['text'])}"
        )
        lines.append(
            f"  - views {post['views']:,}, reactions {post['reactions']:,}, "
            f"comments {post['comment_count']:,}"
        )
        if post["username"] and post["id"] is not None:
            lines.append(f"  - https://t.me/{post['username']}/{post['id']}")
        if post.get("comment_note"):
            lines.append(f"  - _{post['comment_note']}_")
        for comment in post["comments"]:
            lines.append(
                f"  - @{comment['author']} (reactions {comment['reactions']}): "
                f"{_excerpt(comment['text'], 200)}"
            )
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(shown)
