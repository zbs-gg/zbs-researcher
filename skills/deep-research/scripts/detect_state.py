#!/usr/bin/env python3
"""Session-state detector for the deep-research plugin (SessionStart hook).

Prints one JSON object describing which research providers have keys
configured, whether a Telegram session file exists, the active profile, and
whether the onboarding wizard already ran:

    {"providers": {"gemini": false, "grok": false, "perplexity": false,
                   "openrouter": false, "scrapecreators": false,
                   "groq": false, "threads": false},
     "telegram_session": false, "profile": "client",
     "wizard_done": false, "tier": null, "persona": null}

Key resolution is delegated to the runtime itself: deep-research.py is loaded
fresh on every collect_state() call, so SECRETS/KEYS are re-evaluated from the
CURRENT environment (the hook, --diagnose, and tests may point
DEEP_RESEARCH_SECRETS_DIR anywhere after any earlier import). Only booleans
and names are ever emitted — never key values or prefixes.

Stdlib only; no network; no POSIX-only calls (Windows-safe).
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
RUNNER_PATH = SCRIPTS_DIR / "deep-research.py"

# Providers surfaced to the agent. Every name here is a key in the runner's
# KEYS dict, so bool(KEYS[name]) is the authoritative configured/absent signal.
PROVIDERS = ("gemini", "grok", "perplexity", "openrouter", "scrapecreators", "groq", "threads")
ONBOARDING_MARKER = "onboarding.json"


def _load_runner():
    """Load a fresh copy of the hyphen-named deep-research.py module.

    A fresh load is what makes state collection honest at call time: the
    runner computes SECRETS and KEYS at import, so a cached module would pin
    the environment as it looked on first import.
    """
    spec = importlib.util.spec_from_file_location("deep_research_state_probe", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    scripts_path = str(SCRIPTS_DIR)
    added = scripts_path not in sys.path
    if added:
        sys.path.insert(0, scripts_path)  # the runner imports sibling output_paths
    try:
        spec.loader.exec_module(module)
    finally:
        if added:
            sys.path.remove(scripts_path)
    return module


def _read_onboarding_marker(path):
    """Return (wizard_done, tier, persona).

    Absent or malformed marker -> (False, None, None). Persona is surfaced
    verbatim as {"gender": <str>, "tone": <str>} only when both fields are
    strings (tone may be free text); any other shape — legacy markers without
    persona included — degrades to None with the same tolerance as
    wizard_done/tier. Never raises on marker content.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False, None, None
    if not isinstance(data, dict):
        return False, None, None
    tier = data.get("tier")
    if isinstance(tier, bool) or not isinstance(tier, (str, int)):
        tier = None
    persona = data.get("persona")
    if isinstance(persona, dict) and all(
        isinstance(persona.get(field), str) for field in ("gender", "tone")
    ):
        persona = {"gender": persona["gender"], "tone": persona["tone"]}
    else:
        persona = None
    return data.get("wizard_done") is True, tier, persona


def collect_state(runner=None):
    """Compute the session-state dict from the CURRENT environment."""
    runner = runner if runner is not None else _load_runner()
    providers = {name: bool(runner.KEYS.get(name)) for name in PROVIDERS}
    secrets = runner.SECRETS
    telegram_session = bool(secrets.is_dir() and any(secrets.glob("*.session")))
    wizard_done, tier, persona = _read_onboarding_marker(secrets / ONBOARDING_MARKER)
    profile = os.environ.get("DEEP_RESEARCH_PROFILE", "").strip() or "client"
    return {
        "providers": providers,
        "telegram_session": telegram_session,
        "profile": profile,
        "wizard_done": wizard_done,
        "tier": tier,
        "persona": persona,
    }


def doctor_report():
    """Human-readable report for --diagnose (offline; no key material)."""
    runner = _load_runner()
    state = collect_state(runner)
    width = max(len(name) for name in PROVIDERS)
    lines = [
        "deep-research doctor",
        f"  secrets dir : {runner.SECRETS}",
        f"  profile     : {state['profile']}",
        "  providers:",
    ]
    for name in PROVIDERS:
        status = "configured" if state["providers"][name] else "missing"
        lines.append(f"    {name.ljust(width)} : {status}")
    telegram = "session file present" if state["telegram_session"] else "no session file"
    lines.append(f"  telegram    : {telegram}")
    wizard = "done" if state["wizard_done"] else "not run"
    tier = state["tier"] if state["tier"] is not None else "-"
    lines.append(f"  onboarding  : wizard {wizard}, tier {tier}")
    persona = state["persona"]
    if persona is None:
        lines.append("  persona     : not set")
    else:
        gender_word = {"m": "male", "f": "female", "neutral": "neutral"}.get(
            persona["gender"], persona["gender"]
        )
        lines.append(f"  persona     : {gender_word} voice, tone {persona['tone']}")
    return "\n".join(lines)


def _absent_state():
    """The documented all-absent shape — the safe fallback when state can't
    be computed (e.g. an undecodable key file). A SessionStart hook must never
    crash the session; emitting 'nothing configured' degrades to the wizard
    asking, which is correct."""
    return {
        "providers": {name: False for name in PROVIDERS},
        "telegram_session": False,
        "profile": os.environ.get("DEEP_RESEARCH_PROFILE", "").strip() or "client",
        "wizard_done": False,
        "tier": None,
        "persona": None,
    }


def main():
    try:
        state = collect_state()
    except Exception:  # noqa: BLE001 — the hook must degrade, never crash the session
        state = _absent_state()
    print(json.dumps(state))


if __name__ == "__main__":
    main()
