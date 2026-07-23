"""Investigate-mode feedback ledger for the deep-research plugin (R9, R10).

Persists what a finished investigate run was made of — the composed per-source
queries, the sources actually fired, an optional human feedback note, and the
coverage summary — as one JSON line per run, so the NEXT run on the same topic
can read it back (STEP I0 of the investigate playbook). Three hard rules,
mirroring signals.py:

  1. Never overclaim: feedback is *saved locally to inform the next run* —
     the baseline stores notes and replays them, nothing more. No copy in
     this module may say the tool "learned" anything.
  2. Never lie about the relay: the user-facing confirmation claims a
     Cartographer relay ONLY after an actual HTTP 2xx. No relay configured,
     or any send failure -> honest "recorded locally" copy.
  3. Never lose the note: the local JSONL append happens first and a failure
     to write raises loudly instead of vanishing.

The relay is strictly opt-in per install: if DEEP_RESEARCH_CARTOGRAPHER_URL is
set (an HTTPS endpoint of the operator's own Cartographer install — this repo
ships no token, no endpoint, no default), the feedback JSON is POSTed there
with a short timeout so a research profile can compound across runs. Without
it, no network I/O of any kind happens.

Stdlib only; no POSIX-only calls (Windows-safe); never logs secrets.
"""
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple, Optional

FEEDBACK_FILENAME = "investigate-feedback.jsonl"
CARTOGRAPHER_ENV_VAR = "DEEP_RESEARCH_CARTOGRAPHER_URL"
RELAY_TIMEOUT_SECONDS = 5


class FeedbackResult(NamedTuple):
    logged: bool
    notified: bool
    error: Optional[str]


def default_feedback_dir():
    """Feedback base dir, resolved from the CURRENT environment at call time.

    Defaults to the secrets/config dir so the ledger survives across projects
    and works with zero configuration (same resolution as signals.py).
    """
    return Path(
        os.environ.get(
            "DEEP_RESEARCH_SECRETS_DIR",
            str((Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")) / "zbs-researcher" / "secrets")),
        )
    ).expanduser()


def _append_jsonl_line(path, entry):
    """Append one JSON line; O_APPEND single-write mirrors signals.py's care."""
    line = (json.dumps(entry, ensure_ascii=False) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(descriptor, line)
    finally:
        os.close(descriptor)


def _https_post(url, payload):
    """Default sender: POST JSON bytes, return the HTTP status code."""
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=RELAY_TIMEOUT_SECONDS) as response:
        status = getattr(response, "status", None)
        return status if status is not None else response.getcode()


def _relay(entry, sender):
    """Send the feedback row to Cartographer if (and only if) a relay is set.

    Returns (notified, error). Never raises: a broken relay must not undo a
    successful local ledger write.
    """
    relay_url = os.environ.get(CARTOGRAPHER_ENV_VAR, "").strip()
    if not relay_url:
        return False, None
    if urllib.parse.urlsplit(relay_url).scheme != "https":
        return False, "relay skipped: " + CARTOGRAPHER_ENV_VAR + " must be an https:// URL"
    payload = json.dumps(entry, ensure_ascii=False).encode("utf-8")
    sender = sender if sender is not None else _https_post
    try:
        status = sender(relay_url, payload)
    except Exception as exc:  # noqa: BLE001 — any relay failure means "not relayed"
        # Deliberately not echoing the URL: relay URLs may embed a token.
        return False, f"relay failed: {type(exc).__name__}: {exc}"
    if isinstance(status, int) and 200 <= status < 300:
        return True, None
    return False, f"relay failed: Cartographer answered HTTP {status}"


def record_feedback(topic, composed_queries=None, sources_used=None,
                    human_feedback=None, coverage=None, base_dir=None, sender=None):
    """Record one run's feedback locally, then optionally relay to Cartographer.

    Appends {"ts", "topic", "composed_queries", "sources_used",
    "human_feedback", "coverage"} as one JSON line to
    <base_dir>/investigate-feedback.jsonl (base_dir defaults to the
    secrets/config dir; parents are created). Raises ValueError for a blank
    topic and OSError when the ledger cannot be written — a captured feedback
    note must never vanish silently. Returns FeedbackResult(logged, notified,
    error).
    """
    if not isinstance(topic, str) or not topic.strip():
        raise ValueError("feedback topic must be a non-empty string")
    base_dir = Path(base_dir) if base_dir is not None else default_feedback_dir()
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "topic": topic,
        "composed_queries": composed_queries,
        "sources_used": sources_used,
        "human_feedback": human_feedback,
        "coverage": coverage,
    }
    ledger = base_dir / FEEDBACK_FILENAME
    try:
        base_dir.mkdir(parents=True, exist_ok=True)
        _append_jsonl_line(ledger, entry)
    except OSError as exc:
        raise OSError(f"could not record investigate feedback to {ledger}: {exc}") from exc

    notified, error = _relay(entry, sender)
    return FeedbackResult(logged=True, notified=notified, error=error)


def read_recent(topic, n=5, base_dir=None):
    """Return the last `n` ledger rows for `topic`, newest-first.

    Missing or empty ledger -> []. Malformed lines are skipped, not fatal —
    one half-written row must never block STEP I0 from reading the rest.
    """
    if n <= 0:
        return []
    base_dir = Path(base_dir) if base_dir is not None else default_feedback_dir()
    ledger = base_dir / FEEDBACK_FILENAME
    try:
        raw_lines = ledger.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    rows = []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue  # a garbled line; the rest of the ledger still counts
        if isinstance(entry, dict) and entry.get("topic") == topic:
            rows.append(entry)
    rows = rows[-n:]
    rows.reverse()
    return rows


def feedback_message(notified):
    """Honest user-facing confirmation. Claims a Cartographer relay ONLY when
    an actual 2xx came back; the local baseline saves notes, it does not
    train on anything.
    """
    head = (
        "Your feedback was saved locally to " + FEEDBACK_FILENAME
        + " to inform the next run on this topic"
    )
    if notified:
        return head + " and relayed to Cartographer."
    return head + " — it was not relayed anywhere."
