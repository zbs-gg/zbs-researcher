"""Demand-signal capture for the deep-research plugin (R13, R14, R15).

Records explicit "want paid" / "just host it" presses to a local JSONL ledger
so willingness to pay can be measured. Three hard rules:

  1. Never auto-mint: recording a signal provisions nothing and bills nothing.
  2. Never lie: the user-facing confirmation claims a notification ONLY after
     an actual HTTP 2xx from the operator's own relay. No relay configured, or
     any send failure -> honest "recorded locally" copy.
  3. Never lose the press: the local JSONL append happens first and a failure
     to write raises loudly instead of vanishing.

Notification is strictly opt-in per install: if DEEP_RESEARCH_NOTIFY_URL is
set (an HTTPS webhook/relay the operator configures themselves — this repo
ships no token, no endpoint, no default), the signal JSON is POSTed there with
a short timeout. Without it, no network I/O of any kind happens.

Stdlib only; no POSIX-only calls (Windows-safe); never logs secrets.
"""
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple, Optional

SIGNAL_KINDS = ("want-paid", "host-for-me")
SIGNALS_FILENAME = "demand-signals.jsonl"
NOTIFY_ENV_VAR = "DEEP_RESEARCH_NOTIFY_URL"
NOTIFY_TIMEOUT_SECONDS = 5


class SignalResult(NamedTuple):
    logged: bool
    notified: bool
    error: Optional[str]


def _validate_kind(kind):
    if kind not in SIGNAL_KINDS:
        raise ValueError(
            f"unknown demand-signal kind: {kind!r} (expected one of: "
            + ", ".join(SIGNAL_KINDS)
            + ")"
        )


def default_signals_dir():
    """Signals base dir, resolved from the CURRENT environment at call time.

    Defaults to the secrets/config dir so signals survive across projects and
    work with zero configuration.
    """
    return Path(
        os.environ.get(
            "DEEP_RESEARCH_SECRETS_DIR", str(Path.home() / "elle" / ".secrets")
        )
    ).expanduser()


def _append_jsonl_line(path, entry):
    """Append one JSON line; O_APPEND single-write mirrors output_paths' care."""
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
    with urllib.request.urlopen(request, timeout=NOTIFY_TIMEOUT_SECONDS) as response:
        status = getattr(response, "status", None)
        return status if status is not None else response.getcode()


def _notify(entry, sender):
    """Send the signal to the operator relay if (and only if) one is set.

    Returns (notified, error). Never raises: a broken relay must not undo a
    successful local record.
    """
    notify_url = os.environ.get(NOTIFY_ENV_VAR, "").strip()
    if not notify_url:
        return False, None
    if urllib.parse.urlsplit(notify_url).scheme != "https":
        return False, "notify skipped: " + NOTIFY_ENV_VAR + " must be an https:// URL"
    payload = json.dumps(entry, ensure_ascii=False).encode("utf-8")
    sender = sender if sender is not None else _https_post
    try:
        status = sender(notify_url, payload)
    except Exception as exc:  # noqa: BLE001 — any relay failure means "not notified"
        # Deliberately not echoing the URL: relay URLs may embed a token.
        return False, f"notify failed: {type(exc).__name__}: {exc}"
    if isinstance(status, int) and 200 <= status < 300:
        return True, None
    return False, f"notify failed: relay answered HTTP {status}"


def record_signal(kind, tier_context=None, profile=None, base_dir=None, sender=None):
    """Record one demand signal locally, then optionally notify the operator.

    Appends {"ts", "kind", "tier_context", "profile"} as one JSON line to
    <base_dir>/demand-signals.jsonl (base_dir defaults to the secrets/config
    dir; parents are created). Raises ValueError for an unknown kind and
    OSError when the ledger cannot be written — a pressed signal must never
    vanish silently. Returns SignalResult(logged, notified, error).
    """
    _validate_kind(kind)
    base_dir = Path(base_dir) if base_dir is not None else default_signals_dir()
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": kind,
        "tier_context": tier_context,
        "profile": profile,
    }
    ledger = base_dir / SIGNALS_FILENAME
    try:
        base_dir.mkdir(parents=True, exist_ok=True)
        _append_jsonl_line(ledger, entry)
    except OSError as exc:
        raise OSError(f"could not record demand signal to {ledger}: {exc}") from exc

    notified, error = _notify(entry, sender)
    return SignalResult(logged=True, notified=notified, error=error)


def signal_message(kind, notified):
    """Honest user-facing confirmation. Claims notification ONLY when true."""
    _validate_kind(kind)
    subject = {
        "want-paid": "Your interest in a paid tier",
        "host-for-me": "Your hosted-setup request",
    }[kind]
    if notified:
        head = f"{subject} was recorded and Nik was notified."
    else:
        head = (
            f"{subject} was recorded locally in {SIGNALS_FILENAME} — "
            "no notification was sent; Nik will see it when this install syncs."
        )
    if kind == "host-for-me":
        return (
            head
            + " Nothing has been provisioned or billed — Nik will follow up"
            " before anything changes."
        )
    return head + " Nothing changes until Nik follows up — this only measures demand."
