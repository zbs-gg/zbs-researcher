#!/usr/bin/env python3
"""Session-state detector for the deep-research plugin (SessionStart hook).

Prints one JSON object describing which research providers have keys
configured, whether a Telegram session file exists, the active profile, and
whether the onboarding wizard already ran:

    {"providers": {"gemini": false, "grok": false, "perplexity": false,
                   "openrouter": false, "scrapecreators": false,
                   "groq": false},
     "telegram_session": false, "profile": "client",
     "wizard_done": false, "tier": null}

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

# Providers surfaced to the agent. Names missing from the runner's KEYS dict
# are resolved with the runner's own read_key() using these extra specs.
PROVIDERS = ("gemini", "grok", "perplexity", "openrouter", "scrapecreators", "groq")
EXTRA_KEY_SPECS = {
    "openrouter": (["openrouter-key.txt"], r"sk-or-[A-Za-z0-9_\-]+", "OPENROUTER_API_KEY"),
    "groq": (["groq-key.txt"], r"gsk_[A-Za-z0-9_\-]+", "GROQ_API_KEY"),
}
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
    """Return (wizard_done, tier); absent or malformed marker -> (False, None)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False, None
    if not isinstance(data, dict):
        return False, None
    tier = data.get("tier")
    if isinstance(tier, bool) or not isinstance(tier, (str, int)):
        tier = None
    return data.get("wizard_done") is True, tier


def collect_state(runner=None):
    """Compute the session-state dict from the CURRENT environment."""
    runner = runner if runner is not None else _load_runner()
    providers = {}
    for name in PROVIDERS:
        key = runner.KEYS.get(name)
        if key is None:
            filenames, pattern, env_var = EXTRA_KEY_SPECS[name]
            key = runner.read_key(filenames, pattern, env_var)
        providers[name] = bool(key)
    secrets = runner.SECRETS
    telegram_session = bool(secrets.is_dir() and any(secrets.glob("*.session")))
    wizard_done, tier = _read_onboarding_marker(secrets / ONBOARDING_MARKER)
    profile = os.environ.get("DEEP_RESEARCH_PROFILE", "").strip() or "client"
    return {
        "providers": providers,
        "telegram_session": telegram_session,
        "profile": profile,
        "wizard_done": wizard_done,
        "tier": tier,
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
    return "\n".join(lines)


def main():
    print(json.dumps(collect_state()))


if __name__ == "__main__":
    main()
