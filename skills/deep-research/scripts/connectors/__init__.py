"""Market-radar connector package (R22/KTD7).

Connector modules here (launch_radar, revenue_radar) reuse the runner's
helpers — get_json / post_json / gh_api / read_key / rank_items /
relevance_score / RELEVANCE_FLOOR — instead of duplicating them.

deep-research.py has a hyphen in its filename and is loaded both as a script
and via importlib in tests, so a plain `import` back into it is impossible.
Instead the runner injects its live module globals via attach_runner() right
after its own imports. Lookups happen per call (late binding), so tests that
patch attributes on their loaded deep-research module copy are honored inside
the connectors — provided that copy attached last (test setUp re-attaches).
"""

import time

_RUNNER_GLOBALS = None


def now():
    """Current epoch seconds — module-level so tests can freeze time by
    patching the per-connector `_now` binding."""
    return time.time()


def excerpt(text, limit=240):
    """Whitespace-collapsed excerpt, truncated with an ellipsis."""
    flat = " ".join(str(text or "").split())
    return flat if len(flat) <= limit else flat[:limit].rstrip() + "…"


def first(*values):
    """First value that is neither None nor empty-string, else None."""
    for value in values:
        if value not in (None, ""):
            return value
    return None


def subdict(raw, key):
    """raw[key] when it is a dict, else an empty dict."""
    value = raw.get(key)
    return value if isinstance(value, dict) else {}


def attach_runner(runner_globals):
    """Register the live globals dict of the deep-research runner module."""
    global _RUNNER_GLOBALS
    _RUNNER_GLOBALS = runner_globals


def runner(name):
    """Resolve a helper from the attached runner at call time."""
    if _RUNNER_GLOBALS is None:
        raise RuntimeError(
            "connectors package is not wired: deep-research.py must call "
            "connectors.attach_runner(globals()) before channels run"
        )
    return _RUNNER_GLOBALS[name]
