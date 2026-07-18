"""Pluggable media backend (U9, R16, R17; KTD5): transcription + vision.

Standalone module (sibling of deep-research.py, NOT a connector) that media
consumers (tiktok/instagram connector, U7) call through ONE surface:

    backend = get_backend()          # or get_backend("self")
    text = backend.transcribe(audio_bytes, mime="audio/mpeg")
    desc = backend.describe_image(image_bytes, mime="image/jpeg")

Profiles (explicit arg > DEEP_RESEARCH_PROFILE env > "client"; an unknown
profile warns on stderr and falls back to client):

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

R17 hard constraint: this module never talks to OpenAI or Anthropic — the
Groq endpoint lives under api.groq.com (its /openai/ path segment is Groq's
own OpenAI-compatible route, not OpenAI), vision is Google Gemini. Tests
assert the constraint on both the source text and captured request URLs.

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
import urllib.request
import uuid
from pathlib import Path

GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_WHISPER_MODEL = os.environ.get(
    "DEEP_RESEARCH_WHISPER_MODEL", "whisper-large-v3-turbo"
)
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_VISION_MODEL = os.environ.get(
    "DEEP_RESEARCH_VISION_MODEL", "gemini-2.0-flash"
)
SELF_VISION_MODEL = os.environ.get(
    "DEEP_RESEARCH_SELF_VISION_MODEL", "mlx-community/Qwen2.5-VL-3B-Instruct-4bit"
)
PROFILES = ("client", "self")

_VISION_PROMPT = (
    "Describe this image factually for a research report: visible text, "
    "products, UI elements, people count, setting. 2-4 sentences, no "
    "speculation beyond what is visible."
)

# Same resolution contracts as the runner's KEYS / detect_state.py.
_GROQ_KEY_SPEC = (("groq-key.txt",), r"gsk_[A-Za-z0-9_\-]+", "GROQ_API_KEY")
_GEMINI_KEY_SPEC = (("gemini-key.txt",), r"AIza[A-Za-z0-9_\-]+", "GEMINI_API_KEY")

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
            "DEEP_RESEARCH_SECRETS_DIR", str(Path.home() / ".openclaw" / "secrets")
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
            {"model": GROQ_WHISPER_MODEL, "response_format": "json"},
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
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / _audio_filename(mime)
            path.write_bytes(audio_bytes)
            result = mlx_whisper.transcribe(str(path))
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


def get_backend(profile=None):
    """Resolve the media backend: arg > DEEP_RESEARCH_PROFILE > client.
    Unknown profiles warn on stderr and fall back to client."""
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
