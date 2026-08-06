"""Pluggable media backend (U9, R16, R17; KTD5): transcription + vision.

Standalone module (sibling of deep-research.py, NOT a connector) that media
consumers (tiktok/instagram, youtube) call through ONE surface:

    backend = get_backend()          # or get_backend("self")  — VISION profile
    desc = backend.describe_image(image_bytes, mime="image/jpeg")

    transcriber = get_transcriber()  # AUDIO route (may differ from the profile)
    text = transcriber.transcribe(audio_bytes, mime="audio/mpeg")

Vision profiles (explicit arg > DEEP_RESEARCH_PROFILE env > "client"; an
unknown profile warns on stderr and falls back to client):

  client — cloud-cheap raw HTTP, stdlib urllib only:
             audio  -> Groq Whisper (whisper-large-v3-turbo), multipart
                       upload, Bearer key from groq-key.txt / GROQ_API_KEY;
             vision -> Gemini Flash generateContent with inline_data base64,
                       key from gemini-key.txt / GEMINI_API_KEY sent in the
                       x-goog-api-key header (never in the URL).
           A missing key raises MediaBackendError with setup guidance so
           the calling connector can degrade honestly (note line, not fake
           output).
  self   — local $0 via lazy imports: mlx_whisper for audio, mlx_vlm for
           vision. Neither is a dependency of this plugin; when the import
           fails the error is clean install guidance (pip install
           mlx-whisper / mlx-vlm), never a raw ImportError traceback.

TRANSCRIPTION ROUTING is deliberately separate from the vision profile, so
one OpenRouter key can cover audio while vision still runs on the profile.
resolve_transcribe_route() picks, in order:

  1. DEEP_RESEARCH_TRANSCRIBE_BACKEND (local | groq | openrouter) — explicit
     force; an unknown value warns on stderr and is ignored.
  2. the wizard's stored answer: "transcribe" in <secrets-dir>/onboarding.json.
  3. derived from the vision profile: self -> local; client -> groq when its
     key is configured, else openrouter when its key is configured.
  4. nothing configured -> the route is None and .transcribe() raises one
     MediaBackendError naming ALL three options with setup hints.

An EXPLICIT choice (1 or 2) is honored even when its credential is missing:
the resulting error names exactly what to fix, which beats silently billing
a provider the user did not choose.

R17 hard constraint: this module never talks to OpenAI or Anthropic. Groq
lives under api.groq.com (its /openai/ path segment is Groq's own
OpenAI-compatible route, not OpenAI), vision is Google Gemini, and the
OpenRouter transcription route posts to openrouter.ai — a broker, not a
first-party OpenAI endpoint. `openai/whisper-large-v3` there is an OpenRouter
MODEL ID, not a hostname. Tests assert the constraint on the source text and
on captured request URLs.

Key resolution happens at CALL time from the current environment (mirrors
detect_state.py: same filenames, patterns, env vars as the runner's KEYS),
so a wizard-written key is picked up without any reload.

Stdlib only; Windows-safe (tempfile.TemporaryDirectory, no POSIX-only
calls); never logs or echoes key material.
"""
import base64
import json
import mimetypes
import os
import re
import sys
import tempfile
import threading
import urllib.request
import uuid
from pathlib import Path

GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
DEFAULT_GROQ_WHISPER_MODEL = "whisper-large-v3-turbo"
# OpenRouter's transcription endpoint (shipped 2026-07-22). Same key that
# already covers the Tier-2 LLM lenses, so one credential now buys audio too.
OPENROUTER_TRANSCRIBE_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
DEFAULT_OPENROUTER_TRANSCRIBE_MODEL = "openai/whisper-large-v3"
# mlx_whisper's own default is whisper-TINY. Leaving the model unset would
# quietly give the local route a far weaker model than the docs promise (and
# than the wizard's RAM thresholds assume), so pin it here.
DEFAULT_SELF_WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"
# Ceiling for the in-process local transcription call (see _run_bounded).
LOCAL_TRANSCRIBE_TIMEOUT = int(
    os.environ.get("DEEP_RESEARCH_LOCAL_TRANSCRIBE_TIMEOUT", "") or 900
)
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_VISION_MODEL = os.environ.get(
    "DEEP_RESEARCH_VISION_MODEL", "gemini-2.0-flash"
)
SELF_VISION_MODEL = os.environ.get(
    "DEEP_RESEARCH_SELF_VISION_MODEL", "mlx-community/Qwen2.5-VL-3B-Instruct-4bit"
)
PROFILES = ("client", "self")
# Audio routes, independent of the vision profile (see the module docstring).
TRANSCRIBE_ROUTES = ("local", "groq", "openrouter")
TRANSCRIBE_ROUTE_ENV_VAR = "DEEP_RESEARCH_TRANSCRIBE_BACKEND"
ONBOARDING_MARKER = "onboarding.json"

_VISION_PROMPT = (
    "Describe this image factually for a research report: visible text, "
    "products, UI elements, people count, setting. 2-4 sentences, no "
    "speculation beyond what is visible."
)

# Same resolution contracts as the runner's KEYS / detect_state.py.
_GROQ_KEY_SPEC = (("groq-key.txt",), r"gsk_[A-Za-z0-9_\-]+", "GROQ_API_KEY")
_GEMINI_KEY_SPEC = (("gemini-key.txt",), r"AIza[A-Za-z0-9_\-]+", "GEMINI_API_KEY")
_OPENROUTER_KEY_SPEC = (
    ("openrouter-key.txt",), r"sk-or-[A-Za-z0-9_\-]+", "OPENROUTER_API_KEY",
)

_AUDIO_EXT = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/ogg": ".ogg",
    "audio/opus": ".opus",
    "audio/flac": ".flac",
    "audio/webm": ".webm",
}


class MediaBackendError(RuntimeError):
    """Media backend cannot run — the message says exactly what to set up."""


def _secrets_dir():
    return Path(
        os.environ.get(
            "DEEP_RESEARCH_SECRETS_DIR",
            str((Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")) / "zbs-researcher" / "secrets")),
        )
    ).expanduser()


def _read_key(spec):
    """Resolve a key at call time: first matching secrets file, then env.
    Mirrors the runner's read_key contract exactly."""
    filenames, pattern, env_var = spec
    for filename in filenames:
        path = _secrets_dir() / filename
        if path.exists():
            raw = path.read_text().strip()
            m = re.search(pattern, raw)
            if m:
                return m.group(0)
            if raw:
                return raw
    return os.environ.get(env_var, "").strip()


def _require_key(spec, provider, hint):
    key = _read_key(spec)
    if not key:
        filenames, _, env_var = spec
        raise MediaBackendError(
            f"{provider} API key missing: put it in "
            f"{_secrets_dir() / filenames[0]} or set {env_var}. {hint} "
            "The media channel degrades honestly without it."
        )
    return key


def _http_post_raw(url, data, headers, timeout=120):
    """POST raw bytes, parse the JSON response. Module-level so tests patch
    ONE seam and capture url/body/headers."""
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def _multipart(fields, file_name, file_bytes, file_mime):
    """Encode multipart/form-data (stdlib only). Returns (body, content_type)."""
    boundary = "deep-research-" + uuid.uuid4().hex
    chunks = []
    for name, value in fields.items():
        chunks.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode("utf-8")
        )
    chunks.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'
        f"Content-Type: {file_mime}\r\n\r\n".encode("utf-8")
    )
    chunks.append(file_bytes)
    chunks.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _audio_filename(mime):
    ext = _AUDIO_EXT.get((mime or "").lower()) or mimetypes.guess_extension(
        mime or ""
    ) or ".bin"
    return f"audio{ext}"


def _audio_format(mime):
    """Bare container name ("mp3", "m4a", ...) for OpenRouter's `format`
    field — the same extension table, without the leading dot."""
    return _audio_filename(mime).rsplit(".", 1)[-1]


def _model(env_var, default):
    """Model id read at CALL time — same discipline as key resolution, so a
    setting exported after this module was imported still takes effect."""
    return os.environ.get(env_var, "").strip() or default


def _run_bounded(call, timeout, label):
    """Run a blocking local call with a deadline.

    Cloud routes get their timeout from urllib; the local route is an
    in-process library call that can wedge on a model download or a pathological
    input and would otherwise hang a whole research run with no ceiling. A
    daemon thread is the Windows-safe watchdog (R18 rules out signal-based
    timeouts). The worker cannot be killed, but it stops holding the run: it is
    a daemon, so it never blocks interpreter exit.
    """
    box = {}

    def target():
        try:
            box["value"] = call()
        except BaseException as exc:  # noqa: BLE001 — re-raised on the caller's thread
            box["error"] = exc

    worker = threading.Thread(target=target, daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        raise MediaBackendError(
            f"{label} exceeded {timeout}s and was abandoned — try a smaller "
            "model via DEEP_RESEARCH_SELF_WHISPER_MODEL, raise "
            "DEEP_RESEARCH_LOCAL_TRANSCRIBE_TIMEOUT, or use a cloud route."
        )
    if "error" in box:
        raise box["error"]
    return box.get("value") or {}


class ClientBackend:
    """Cloud-cheap profile: Groq Whisper for audio, Gemini Flash for vision.
    Raw urllib HTTP; keys resolved at call time; NO OpenAI/Anthropic (R17)."""

    profile = "client"

    def transcribe(self, audio_bytes, mime="audio/mpeg"):
        key = _require_key(
            _GROQ_KEY_SPEC, "Groq",
            "Free key: https://console.groq.com/keys (Whisper transcription "
            "has a generous free tier).",
        )
        body, content_type = _multipart(
            {
                "model": _model(
                    "DEEP_RESEARCH_WHISPER_MODEL", DEFAULT_GROQ_WHISPER_MODEL
                ),
                "response_format": "json",
            },
            _audio_filename(mime), audio_bytes, mime or "application/octet-stream",
        )
        data = _http_post_raw(
            GROQ_TRANSCRIBE_URL,
            body,
            {"Authorization": f"Bearer {key}", "Content-Type": content_type},
            timeout=300,
        )
        return (data.get("text") or "").strip()

    def describe_image(self, image_bytes, mime="image/jpeg"):
        key = _require_key(
            _GEMINI_KEY_SPEC, "Gemini",
            "Free key: https://aistudio.google.com/apikey.",
        )
        url = f"{GEMINI_BASE_URL}/models/{GEMINI_VISION_MODEL}:generateContent"
        payload = {
            "contents": [{
                "role": "user",
                "parts": [
                    {"text": _VISION_PROMPT},
                    {"inline_data": {
                        "mime_type": mime or "image/jpeg",
                        "data": base64.b64encode(image_bytes).decode("ascii"),
                    }},
                ],
            }],
            "generationConfig": {"maxOutputTokens": 1000, "temperature": 0.2},
        }
        data = _http_post_raw(
            url,
            json.dumps(payload).encode("utf-8"),
            # Key in a header, never in the URL (URLs end up in logs).
            {"Content-Type": "application/json", "x-goog-api-key": key},
            timeout=120,
        )
        candidates = data.get("candidates") or []
        if not candidates:
            raise MediaBackendError(
                f"Gemini vision returned no candidates: {json.dumps(data)[:300]}"
            )
        parts = (candidates[0].get("content") or {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts).strip()


class SelfBackend:
    """Local $0 profile: MLX on Apple silicon via lazy imports. Neither
    mlx_whisper nor mlx_vlm is a plugin dependency — a missing package
    raises clean install guidance, never an ImportError traceback."""

    profile = "self"

    def transcribe(self, audio_bytes, mime="audio/mpeg"):
        try:
            import mlx_whisper
        except ImportError:
            raise MediaBackendError(
                "Local transcription needs the mlx-whisper package "
                "(Apple silicon): pip install mlx-whisper — or use the "
                "default client profile (Groq) instead."
            ) from None
        model = _model(
            "DEEP_RESEARCH_SELF_WHISPER_MODEL", DEFAULT_SELF_WHISPER_MODEL
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / _audio_filename(mime)
            path.write_bytes(audio_bytes)
            # The model is passed EXPLICITLY: mlx_whisper's own default is
            # whisper-tiny, so omitting it would quietly deliver a far weaker
            # transcript than the docs promise and than the wizard's RAM
            # thresholds are sized for.
            result = _run_bounded(
                lambda: mlx_whisper.transcribe(str(path), path_or_hf_repo=model),
                LOCAL_TRANSCRIBE_TIMEOUT,
                f"local transcription with {model}",
            )
        return (result.get("text") or "").strip()

    def describe_image(self, image_bytes, mime="image/jpeg"):
        try:
            import mlx_vlm
        except ImportError:
            raise MediaBackendError(
                "Local vision needs the mlx-vlm package (Apple silicon): "
                "pip install mlx-vlm — or use the default client profile "
                "(Gemini Flash) instead."
            ) from None
        suffix = mimetypes.guess_extension(mime or "") or ".jpg"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"image{suffix}"
            path.write_bytes(image_bytes)
            try:
                model, processor = mlx_vlm.load(SELF_VISION_MODEL)
                result = mlx_vlm.generate(
                    model, processor, _VISION_PROMPT, image=str(path)
                )
            except Exception as exc:  # noqa: BLE001 — surface honest guidance
                raise MediaBackendError(
                    "Local vision path failed (mlx-vlm APIs vary by "
                    f"version): {type(exc).__name__}: {exc}"
                ) from exc
        text = getattr(result, "text", None)
        if text is None:
            text = result if isinstance(result, str) else str(result)
        return text.strip()


class OpenRouterBackend:
    """Transcription through OpenRouter's audio endpoint — the SAME key that
    already routes the Tier-2 LLM lenses. Audio only: vision stays on the
    profile (Gemini for client, mlx-vlm for self), so this backend is only
    ever handed out by get_transcriber()."""

    profile = "openrouter"

    def transcribe(self, audio_bytes, mime="audio/mpeg"):
        key = _require_key(
            _OPENROUTER_KEY_SPEC, "OpenRouter",
            "Key: https://openrouter.ai/keys — the same one that routes the "
            "gemini/grok/perplexity lenses.",
        )
        payload = {
            "model": _model(
                "DEEP_RESEARCH_TRANSCRIBE_MODEL",
                DEFAULT_OPENROUTER_TRANSCRIBE_MODEL,
            ),
            "input_audio": {
                "data": base64.b64encode(audio_bytes).decode("ascii"),
                "format": _audio_format(mime),
            },
        }
        data = _http_post_raw(
            OPENROUTER_TRANSCRIBE_URL,
            json.dumps(payload).encode("utf-8"),
            {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            timeout=300,
        )
        text = data.get("text") if isinstance(data, dict) else None
        if not isinstance(text, str):
            raise MediaBackendError(
                "OpenRouter transcription returned no text field: "
                f"{json.dumps(data)[:300]}"
            )
        return text.strip()

    def describe_image(self, image_bytes, mime="image/jpeg"):
        raise MediaBackendError(
            "OpenRouter is wired for transcription only here — vision runs on "
            "the profile: DEEP_RESEARCH_PROFILE=client uses Gemini Flash, "
            "=self uses local mlx-vlm."
        )


class UnconfiguredTranscriber:
    """No transcription route is configured. Constructing this never raises —
    the error arrives at .transcribe() time (same call-time contract as key
    resolution), so a connector's try/except degrades to an honest note."""

    profile = None

    def transcribe(self, audio_bytes, mime="audio/mpeg"):
        raise MediaBackendError(
            "No transcription route configured. Pick one: (1) local $0 on "
            "Apple silicon — pip install mlx-whisper, then "
            "DEEP_RESEARCH_PROFILE=self; (2) Groq — put the key in "
            f"{_secrets_dir() / 'groq-key.txt'} or set GROQ_API_KEY "
            "(free tier, https://console.groq.com/keys); (3) OpenRouter — "
            f"{_secrets_dir() / 'openrouter-key.txt'} or OPENROUTER_API_KEY. "
            f"Force one explicitly with {TRANSCRIBE_ROUTE_ENV_VAR}="
            + "|".join(TRANSCRIBE_ROUTES)
            + "."
        )

    def describe_image(self, image_bytes, mime="image/jpeg"):
        raise MediaBackendError(
            "This object routes audio only; call get_backend() for vision."
        )


# Synonyms people actually type. "self" is the important one: the vision
# profile already spells local as DEEP_RESEARCH_PROFILE=self, so anyone
# setting the audio route by analogy writes "self" — and a route name that
# silently means "not local" would ship their audio to a vendor.
_ROUTE_ALIASES = {
    "self": "local",
    "mlx": "local",
    "offline": "local",
    "client": "groq",
    "whisper": "local",
}


def normalize_route(value):
    """Canonical route name for a user-supplied string, or None if unknown."""
    candidate = (value or "").strip().lower()
    if candidate in TRANSCRIBE_ROUTES:
        return candidate
    return _ROUTE_ALIASES.get(candidate)


def _stored_transcribe_route():
    """The wizard's answer from <secrets-dir>/onboarding.json, or None.
    Tolerant by design: a missing, unreadable, or malformed marker simply
    means "the user hasn't chosen", never a crash."""
    try:
        data = json.loads(
            (_secrets_dir() / ONBOARDING_MARKER).read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return normalize_route(data.get("transcribe"))


def resolve_transcribe_route(profile=None):
    """Return (route, reason) — which audio route WILL run, and why.

    route is one of TRANSCRIBE_ROUTES, or None when nothing is configured.
    The reason string is for --diagnose: it must let a human see WHY this
    route won without reading the code.
    """
    forced = os.environ.get(TRANSCRIBE_ROUTE_ENV_VAR, "").strip()
    if forced:
        route = normalize_route(forced)
        if route:
            return route, f"forced by {TRANSCRIBE_ROUTE_ENV_VAR}"
        # FAIL CLOSED. Falling through to derivation here would answer a
        # typo'd request for local, private transcription by uploading the
        # audio to whichever cloud key happens to be configured — the exact
        # outcome the person was trying to avoid.
        return None, (
            f"{TRANSCRIBE_ROUTE_ENV_VAR}={forced!r} is not a known route "
            "(" + ", ".join(TRANSCRIBE_ROUTES) + ")"
        )
    stored = _stored_transcribe_route()
    if stored:
        return stored, "chosen during onboarding"

    chosen = (profile or os.environ.get("DEEP_RESEARCH_PROFILE", "")).strip()
    if chosen == "self":
        return "local", "profile 'self' — local MLX, $0, nothing leaves the machine"
    if _read_key(_GROQ_KEY_SPEC):
        return "groq", "Groq key configured"
    if _read_key(_OPENROUTER_KEY_SPEC):
        return "openrouter", "OpenRouter key configured (no Groq key)"
    return None, "no local install and no cloud key"


def get_transcriber(profile=None):
    """Resolve the AUDIO backend. Never raises: an unconfigured route returns
    UnconfiguredTranscriber, whose .transcribe() carries the full guidance."""
    route, _reason = resolve_transcribe_route(profile)
    if route == "local":
        return SelfBackend()
    if route == "groq":
        return ClientBackend()
    if route == "openrouter":
        return OpenRouterBackend()
    return UnconfiguredTranscriber()


def get_backend(profile=None):
    """Resolve the VISION media backend: arg > DEEP_RESEARCH_PROFILE > client.
    Unknown profiles warn on stderr and fall back to client.

    Unchanged contract: this is the profile-shaped backend. Audio callers
    should prefer get_transcriber(), which may route elsewhere."""
    chosen = (profile or os.environ.get("DEEP_RESEARCH_PROFILE", "")).strip()
    if not chosen:
        chosen = "client"
    if chosen not in PROFILES:
        print(
            f"[media-backend] unknown profile {chosen!r} — falling back to "
            "'client' (known: " + ", ".join(PROFILES) + ")",
            file=sys.stderr,
        )
        chosen = "client"
    return SelfBackend() if chosen == "self" else ClientBackend()
