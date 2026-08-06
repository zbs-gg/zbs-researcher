#!/usr/bin/env python3
"""Session-state detector for the deep-research plugin (SessionStart hook).

Prints one JSON object describing which research providers have keys
configured, whether a Telegram session file exists, the active profile,
whether the onboarding wizard already ran, and what the MACHINE can do:

    {"providers": {"gemini": false, "grok": false, "perplexity": false,
                   "openrouter": false, "scrapecreators": false,
                   "groq": false, "threads": false},
     "telegram_session": false, "cartographer": false, "profile": "client",
     "wizard_done": false, "tier": null, "persona": null,
     "hardware": {"os": "darwin", "arch": "arm64", "apple_silicon": true,
                  "ram_gb": 64, "cpu_count": 16, "chip": "Apple M4 Max"},
     "local_media": {"mlx_whisper": false, "yt_dlp": true,
                     "transcribe_route": "groq", "recommendation": "capable"}}

The hardware block exists so the wizard can offer the FREE local option
honestly: on a 64 GB Apple-silicon machine, whisper-large-v3-turbo runs at $0
with nothing leaving the box, and a wizard that cannot see the machine would
only ever pitch the paid cloud route. `recommendation` is "capable" (Apple
silicon, >=16 GB), "tight" (>=8 GB — suggest a smaller model), or "cloud".

Key resolution is delegated to the runtime itself: deep-research.py is loaded
fresh on every collect_state() call, so SECRETS/KEYS are re-evaluated from the
CURRENT environment (the hook, --diagnose, and tests may point
DEEP_RESEARCH_SECRETS_DIR anywhere after any earlier import). Only booleans
and names are ever emitted — never key values or prefixes.

Stdlib only; no network; no POSIX-only calls (Windows-safe). Every hardware
probe is individually guarded: a SessionStart hook that crashes would break
the user's whole session, so an unavailable probe reports null and moves on.
"""
import ctypes
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
RUNNER_PATH = SCRIPTS_DIR / "deep-research.py"

# Providers surfaced to the agent. Every name here is a key in the runner's
# KEYS dict, so bool(KEYS[name]) is the authoritative configured/absent signal.
PROVIDERS = ("gemini", "grok", "perplexity", "openrouter", "scrapecreators", "groq", "threads")
ONBOARDING_MARKER = "onboarding.json"
CARTOGRAPHER_ENV_VAR = "DEEP_RESEARCH_CARTOGRAPHER_URL"


def _cartographer_configured():
    """True only when a Cartographer relay URL is set AND https — the same
    gate investigate_feedback applies before any relay attempt. Availability
    info only: the boolean says a relay CAN happen, never that the local
    baseline does anything smarter on its own."""
    url = os.environ.get(CARTOGRAPHER_ENV_VAR, "").strip()
    if not url:
        return False
    try:
        return urllib.parse.urlsplit(url).scheme == "https"
    except ValueError:
        # A URL urlsplit rejects (e.g. a malformed IPv6 bracket) is not a valid
        # https relay — and a SessionStart hook must NEVER crash the session, so
        # this stays total (the _absent_state fallback calls it too).
        return False


# --- hardware probe -------------------------------------------------------
# Local whisper-large-v3-turbo peaks around 6 GB; 16 GB unified memory runs it
# comfortably, 8 GB only alongside little else.
CAPABLE_RAM_GB = 16
TIGHT_RAM_GB = 8


def _total_ram_gb():
    """Physical RAM in whole GB, or None when it cannot be determined."""
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return int(round(pages * page_size / (1024 ** 3)))
    except (AttributeError, ValueError, OSError):
        pass
    try:  # Windows: no sysconf, ask the kernel through the Win32 API
        class _MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = _MemoryStatus()
        status.dwLength = ctypes.sizeof(_MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(round(status.ullTotalPhys / (1024 ** 3)))
    except Exception:  # noqa: BLE001 — probe only; unknown RAM is a valid answer
        pass
    return None


def _chip_name(system):
    """Human-readable CPU name. macOS only — that is where the local option is
    real, and it is what makes the wizard's offer concrete ("M4 Max, 64 GB")."""
    if system != "darwin":
        return None
    # Absolute path, not a PATH lookup: this runs in a SessionStart hook on
    # every session, so a "sysctl" earlier in someone's PATH would execute on
    # every start. The chip name is a nicety; refusing to hunt for it is free.
    sysctl = "/usr/sbin/sysctl"
    if not os.path.exists(sysctl):
        return None
    try:
        completed = subprocess.run(
            [sysctl, "-n", "machdep.cpu.brand_string"],
            capture_output=True, timeout=2, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    name = completed.stdout.decode("utf-8", "replace").strip()
    return name or None


def _module_available(name):
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, AttributeError):
        return False


def hardware_profile():
    """What this machine can do. Never raises."""
    system = (platform.system() or "").lower()
    arch = (platform.machine() or "").lower()
    apple_silicon = system == "darwin" and arch in ("arm64", "aarch64")
    return {
        "os": system or None,
        "arch": arch or None,
        "apple_silicon": apple_silicon,
        "ram_gb": _total_ram_gb(),
        "cpu_count": os.cpu_count(),
        "chip": _chip_name(system),
    }


def _local_recommendation(hardware):
    """capable | tight | cloud — is local, $0, private transcription realistic?

    MLX is Apple-silicon only, so everything else is honestly "cloud" rather
    than a suggestion the user cannot act on.
    """
    if not hardware.get("apple_silicon"):
        return "cloud"
    ram = hardware.get("ram_gb")
    if ram is None:
        return "cloud"
    if ram >= CAPABLE_RAM_GB:
        return "capable"
    if ram >= TIGHT_RAM_GB:
        return "tight"
    return "cloud"


def _transcribe_route():
    """Which audio route WOULD run right now, per media_backend. None when
    media_backend cannot be loaded — availability info only, never a claim."""
    try:
        spec = importlib.util.spec_from_file_location(
            "deep_research_media_probe", SCRIPTS_DIR / "media_backend.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        route, _reason = module.resolve_transcribe_route()
        return route
    except Exception:  # noqa: BLE001 — the hook must never crash the session
        return None


def local_media_state(hardware=None):
    """Optional local tooling + the resolved audio route."""
    hardware = hardware if hardware is not None else hardware_profile()
    return {
        "mlx_whisper": _module_available("mlx_whisper"),
        "yt_dlp": bool(shutil.which("yt-dlp")) or _module_available("yt_dlp"),
        "transcribe_route": _transcribe_route(),
        "recommendation": _local_recommendation(hardware),
    }


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
    hardware = hardware_profile()
    return {
        "providers": providers,
        "telegram_session": telegram_session,
        "cartographer": _cartographer_configured(),
        "profile": profile,
        "wizard_done": wizard_done,
        "tier": tier,
        "persona": persona,
        "hardware": hardware,
        "local_media": local_media_state(hardware),
    }


_ROUTE_WORDS = {
    "local": "local MLX Whisper ($0, nothing leaves this machine)",
    "groq": "Groq Whisper (cloud)",
    "openrouter": "OpenRouter (cloud)",
}
_RECOMMENDATION_WORDS = {
    "capable": "this machine can run local transcription comfortably",
    "tight": "local transcription fits, but only with a smaller model",
    "cloud": "local transcription is not realistic here — use a cloud route",
}


def _hardware_lines(state):
    """--diagnose lines for the machine and the audio route. Purely
    informational: it says what WOULD run, never that anything has run."""
    hardware = state.get("hardware") or {}
    media = state.get("local_media") or {}
    chip = hardware.get("chip") or hardware.get("arch") or "unknown"
    ram = hardware.get("ram_gb")
    ram_text = f"{ram} GB" if ram is not None else "unknown RAM"
    lines = [f"  machine     : {chip}, {ram_text}"]
    route = media.get("transcribe_route")
    if route:
        lines.append(
            f"  transcribe  : {_ROUTE_WORDS.get(route, route)}"
        )
    else:
        lines.append(
            "  transcribe  : not configured — pip install mlx-whisper (local, "
            "$0), or set GROQ_API_KEY / OPENROUTER_API_KEY"
        )
    tools = []
    tools.append("yt-dlp " + ("present" if media.get("yt_dlp") else "missing"))
    tools.append(
        "mlx-whisper " + ("present" if media.get("mlx_whisper") else "missing")
    )
    lines.append(f"  media tools : {', '.join(tools)}")
    hint = _RECOMMENDATION_WORDS.get(media.get("recommendation"))
    if hint:
        lines.append(f"                {hint}")
    return lines


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
    lines.extend(_hardware_lines(state))
    wizard = "done" if state["wizard_done"] else "not run"
    tier = state["tier"] if state["tier"] is not None else "-"
    lines.append(f"  onboarding  : wizard {wizard}, tier {tier}")
    persona = state["persona"]
    if persona is None:
        lines.append("  persona     : not set")
    else:
        # Free-text tone (and unmapped gender) may carry pasted content —
        # strip control/escape bytes so --diagnose can never inject terminal
        # sequences (title rewrites, colors) into the viewer's TTY.
        def _clean(text):
            return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?|\x1b.|[\x00-\x08\x0b-\x1f\x7f]", "", str(text))

        gender_word = {"m": "male", "f": "female", "neutral": "neutral"}.get(
            persona["gender"], _clean(persona["gender"])
        )
        lines.append(f"  persona     : {gender_word} voice, tone {_clean(persona['tone'])}")
    # Honest soft-plug: availability of the OPTIONAL Cartographer relay only.
    # Compounding happens in Cartographer; this baseline just saves feedback
    # notes locally, so neither branch may claim anything smarter than that.
    if state["cartographer"]:
        lines.append("  cartographer: relay on — research-profile compounding across runs")
    else:
        lines.append(
            "  cartographer: not connected — connect Cartographer (neighboring product)"
            " to compound your research profile across runs"
        )
    return "\n".join(lines)


def _absent_state():
    """The documented all-absent shape — the safe fallback when state can't
    be computed (e.g. an undecodable key file). A SessionStart hook must never
    crash the session; emitting 'nothing configured' degrades to the wizard
    asking, which is correct."""
    # Hardware is independent of key state, so it survives the fallback: a
    # broken key file must not also blind the wizard to the machine.
    try:
        hardware = hardware_profile()
        local_media = local_media_state(hardware)
    except Exception:  # noqa: BLE001 — the fallback itself must never raise
        hardware = {"os": None, "arch": None, "apple_silicon": False,
                    "ram_gb": None, "cpu_count": None, "chip": None}
        local_media = {"mlx_whisper": False, "yt_dlp": False,
                       "transcribe_route": None, "recommendation": "cloud"}
    return {
        "providers": {name: False for name in PROVIDERS},
        "telegram_session": False,
        "cartographer": _cartographer_configured(),
        "profile": os.environ.get("DEEP_RESEARCH_PROFILE", "").strip() or "client",
        "wizard_done": False,
        "tier": None,
        "persona": None,
        "hardware": hardware,
        "local_media": local_media,
    }


def main():
    try:
        state = collect_state()
    except Exception:  # noqa: BLE001 — the hook must degrade, never crash the session
        state = _absent_state()
    print(json.dumps(state))


if __name__ == "__main__":
    main()
