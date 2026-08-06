"""YouTube connector: what people actually SAID, not what the description says.

A web index sees a video's title, description and tags. It does not see the
spoken content. This connector reads the words — and when YouTube's own
captions are missing or too poor to quote, it transcribes the audio itself,
producing primary evidence that exists in no index at all. That is the whole
point: the transcript fallback is not a patch for bad captions, it manufactures
sources a web-index researcher cannot reach.

Pipeline per run:

  1. discover  — `ytsearchN:` keyword search, or the explicit video URLs in the
                 query (so the investigate loop can drill one video found via
                 another lens). Ranked through the runner's shared rank_items
                 (relevance floor + bounded engagement on view counts).
  2. captions  — ONE yt-dlp call per video does double duty: `--dump-json`
                 gives metadata (duration, upload timestamp, language, and the
                 `subtitles` map that says which languages are HUMAN-made),
                 while `--no-simulate --write-subs --write-auto-subs` lands the
                 json3 tracks. Preference: manual > auto original-language >
                 machine-translated.
  3. judge     — _caption_quality scores what landed. Missing, machine
                 translated, unpunctuated raw ASR, or suspiciously sparse
                 relative to the runtime all fail, and the REASON is printed.
  4. fallback  — a failed track sends the audio through media_backend's
                 transcriber (local MLX / Groq / OpenRouter, per the user's
                 route), bounded by TRANSCRIBE_TOP and MAX_TRANSCRIBE_SECONDS.
  5. report    — every video carries an explicit provenance label, so a reader
                 always knows whether a quote came from a human caption, a
                 machine caption, or our own Whisper pass.

yt-dlp is an OPTIONAL dependency, the same tier as Telethon and MLX: the
binary on PATH is preferred, the `yt_dlp` Python module is the fallback, and
with neither the channel fails honestly (run_connector writes
youtube.ERROR.md) instead of pretending YouTube has nothing. It is needed
because YouTube's timedtext endpoint is PoToken-gated — a plain stdlib request
returns an empty body — while yt-dlp maintains the machinery to get through.

Windows-safe (R18): subprocess.run with an argument LIST, never a shell,
bounded by its own `timeout=` kwarg; no POSIX-only process control anywhere.

Budgets read the environment at CALL time (same discipline as media_backend's
key resolution), so a wizard-written setting takes effect without a reload.

Helpers (rank_items / excerpt / _note_ts) resolve through the runner's live
globals — see connectors/__init__.py.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import excerpt as _excerpt
from . import runner

WATCH_URL = "https://www.youtube.com/watch?v="
# Budget defaults. Reading captions costs one yt-dlp extraction per video and
# transcription costs money or GPU time, so both are bounded — and whatever the
# bound drops is stated in the report, never silently swallowed.
DEFAULT_READ_TOP = 5
DEFAULT_TRANSCRIBE_TOP = 3
DEFAULT_MAX_SECONDS = 45 * 60
DEFAULT_SUB_LANGS = "en-orig,en"
AUDIO_BYTES_CAP = 25 * 1024 * 1024
SEARCH_TIMEOUT = 120
VIDEO_TIMEOUT = 180
AUDIO_TIMEOUT = 600

_URL_RE = re.compile(
    r"https?://(?:www\.|m\.)?(?:youtube\.com/(?:watch\?\S*?v=|shorts/|live/)|youtu\.be/)"
    r"([A-Za-z0-9_-]{11})"
)
# A bare 11-char video id, but only when the query is nothing else — otherwise
# ordinary search words would be misread as ids.
_BARE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

INSTALL_HINT = (
    "yt-dlp is required for the youtube channel and was not found. Install "
    "the binary (brew install yt-dlp / winget install yt-dlp) or the package "
    "(pip install yt-dlp). It is optional on purpose — every other channel "
    "runs without it. YouTube's caption endpoint is PoToken-gated, so a plain "
    "HTTP request returns an empty body; yt-dlp maintains the way through."
)

# Provenance labels — the reader must always know where a quote came from.
SOURCE_MANUAL = "human-written captions"
SOURCE_AUTO = "YouTube auto-captions"
SOURCE_WHISPER = "our own transcription"
SOURCE_NONE = "no transcript — metadata only"


class YouTubeToolMissing(RuntimeError):
    """yt-dlp is not installed. Message is install guidance, not a traceback."""


def _int_env(name, default):
    """Read a positive int budget from the environment at call time. A blank
    or unparseable value falls back to the default rather than crashing a run
    over a typo in a shell profile."""
    try:
        value = int(os.environ.get(name, "").strip())
    except ValueError:
        return default
    return value if value >= 0 else default


def _read_top():
    return _int_env("DEEP_RESEARCH_YOUTUBE_READ_TOP", DEFAULT_READ_TOP)


def _transcribe_top():
    return _int_env("DEEP_RESEARCH_YOUTUBE_TRANSCRIBE_TOP", DEFAULT_TRANSCRIBE_TOP)


def _max_seconds():
    return _int_env("DEEP_RESEARCH_YOUTUBE_MAX_SECONDS", DEFAULT_MAX_SECONDS)


def _sub_langs():
    return os.environ.get(
        "DEEP_RESEARCH_YOUTUBE_SUB_LANGS", ""
    ).strip() or DEFAULT_SUB_LANGS


# ---------------------------------------------------------------------------
# yt-dlp invocation (ONE seam — tests patch _run_yt_dlp and never hit network)
# ---------------------------------------------------------------------------
def _yt_dlp_argv():
    """Binary on PATH first, then `python -m yt_dlp`. Raises YouTubeToolMissing
    with install guidance when neither is available."""
    binary = shutil.which("yt-dlp")
    if binary:
        return [binary]
    try:
        import yt_dlp  # noqa: F401 — probing availability only
    except ImportError:
        raise YouTubeToolMissing(INSTALL_HINT) from None
    return [sys.executable, "-m", "yt_dlp"]


def _run_yt_dlp(args, timeout):
    """Run yt-dlp with an argument LIST. Returns (returncode, stdout, stderr).

    Never raises on a non-zero exit: yt-dlp routinely partial-fails (one
    unavailable track, one age-gated video) while still producing usable
    output, so the CALLER decides what a failure means.
    """
    argv = _yt_dlp_argv() + list(args)
    try:
        # Argument LIST only — no shell interpolation, so a topic containing
        # quotes or semicolons is data, never something the OS can execute.
        completed = subprocess.run(  # noqa: S603
            argv,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return 1, "", f"yt-dlp timed out after {timeout}s"
    return (
        completed.returncode,
        completed.stdout.decode("utf-8", "replace"),
        completed.stderr.decode("utf-8", "replace"),
    )


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------
def _explicit_ids(query):
    """Video ids named directly in the query, in order, de-duplicated."""
    ids = list(dict.fromkeys(_URL_RE.findall(query or "")))
    if not ids:
        bare = (query or "").strip()
        if _BARE_ID_RE.match(bare):
            ids = [bare]
    return ids


def _search(query, limit):
    """Keyword search via `ytsearchN:`. Flat extraction — cheap, and it carries
    the ranking signal (views) plus the title text the ranker scores on."""
    code, stdout, stderr = _run_yt_dlp(
        [
            "--dump-json",
            "--flat-playlist",
            "--no-warnings",
            f"ytsearch{max(1, int(limit))}:{query}",
        ],
        timeout=SEARCH_TIMEOUT,
    )
    videos = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            raw = json.loads(line)
        except ValueError:
            continue
        video = _video_from_raw(raw)
        if video:
            videos.append(video)
    if not videos and code != 0:
        raise RuntimeError(
            f"yt-dlp search failed for {query!r}: {(stderr or '').strip()[:300]}"
        )
    return videos


def _video_from_raw(raw):
    """Normalize one yt-dlp record. `text` is what the ranker scores against —
    title plus description, because a title alone is a thin relevance signal."""
    if not isinstance(raw, dict):
        return None
    video_id = raw.get("id")
    if not video_id:
        return None
    title = raw.get("title") or ""
    description = raw.get("description") or ""
    return {
        "id": video_id,
        "title": title,
        "channel": raw.get("channel") or raw.get("uploader") or "unknown",
        "url": raw.get("webpage_url") or f"{WATCH_URL}{video_id}",
        "views": raw.get("view_count"),
        "duration": raw.get("duration"),
        "timestamp": raw.get("timestamp"),
        "language": raw.get("language"),
        "text": f"{title} {description}".strip(),
    }


# ---------------------------------------------------------------------------
# Captions
# ---------------------------------------------------------------------------
def _fetch_metadata_and_subs(video, workdir):
    """ONE call: metadata to stdout, json3 caption tracks onto disk.

    --dump-json alone implies simulate mode and writes nothing, so
    --no-simulate is what actually lands the files (verified against
    yt-dlp 2026.07).
    """
    code, stdout, stderr = _run_yt_dlp(
        [
            "--dump-json",
            "--no-simulate",
            "--skip-download",
            "--write-subs",
            "--write-auto-subs",
            "--sub-format", "json3",
            "--sub-langs", _sub_langs(),
            "--no-warnings",
            "-o", str(Path(workdir) / "%(id)s"),
            video["url"],
        ],
        timeout=VIDEO_TIMEOUT,
    )
    meta = {}
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                meta = json.loads(line)
                break
            except ValueError:
                continue
    if not meta and code != 0:
        raise RuntimeError((stderr or "yt-dlp failed").strip()[:300])
    return meta


def _pick_track(video_id, workdir, meta):
    """Choose the best caption file. Returns (path, lang, kind) or None.

    kind is "manual" | "auto" | "translated". Provenance is authoritative,
    not guessed: a language present in the metadata's `subtitles` map is
    human-made; anything else came from `automatic_captions`.
    """
    manual_langs = set((meta.get("subtitles") or {}).keys())
    candidates = []
    for path in sorted(Path(workdir).glob(f"{video_id}.*.json3")):
        # "<id>.<lang>.json3" -> lang (which may itself contain dots/dashes)
        lang = path.name[len(video_id) + 1: -len(".json3")]
        if lang in manual_langs:
            kind, rank = "manual", 0
        elif lang.endswith("-orig"):
            kind, rank = "auto", 1
        elif "-" in lang:
            # "ru-en" = machine translation of a machine transcription: the
            # worst tier, kept only as a last resort.
            kind, rank = "translated", 3
        else:
            kind, rank = "auto", 2
        candidates.append((rank, str(path), lang, kind))
    if not candidates:
        return None
    candidates.sort()
    _, path, lang, kind = candidates[0]
    return Path(path), lang, kind


def json3_text(path):
    """Flatten a json3 caption track into plain text.

    Events are LINES: their segments must be joined with a space, or the last
    word of one line fuses with the first of the next ("familiarwith"). Auto
    tracks already carry trailing spaces, so a final whitespace collapse keeps
    both shapes clean.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    events = data.get("events") if isinstance(data, dict) else None
    lines = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        segments = "".join(
            seg.get("utf8", "")
            for seg in (event.get("segs") or [])
            if isinstance(seg, dict)
        )
        if segments.strip():
            lines.append(segments)
    return " ".join(" ".join(lines).split())


# ---------------------------------------------------------------------------
# Quality gate
# ---------------------------------------------------------------------------
MIN_WORDS = 40
MIN_WORDS_PER_MINUTE = 40
PUNCT_PER_100_WORDS = 2.0


def caption_quality(text, duration=None, kind="auto"):
    """Is this caption track good enough to quote? Returns (ok, reason).

    The reason is user-facing: when we spend money on Whisper, the report must
    say what was wrong with the free text we already had.
    """
    words = text.split()
    if not words:
        return False, "no caption track"
    if kind == "translated":
        return False, "only a machine translation of a machine transcript"
    if len(words) < MIN_WORDS:
        return False, f"caption track is only {len(words)} words"
    if duration:
        minutes = max(duration, 1) / 60.0
        wpm = len(words) / minutes
        if wpm < MIN_WORDS_PER_MINUTE:
            return False, (
                f"{wpm:.0f} words/min over {minutes:.0f} min — the track has gaps"
            )
    punctuation = sum(1 for char in text if char in ".!?,")
    density = punctuation * 100.0 / len(words)
    if density < PUNCT_PER_100_WORDS:
        return False, "raw ASR — no sentence punctuation to quote cleanly"
    return True, "usable"


# ---------------------------------------------------------------------------
# Transcription fallback
# ---------------------------------------------------------------------------
def _transcriber():
    """media_backend.get_transcriber() — the route the user chose (local MLX,
    Groq, or OpenRouter). Imported lazily so the connector loads even where the
    scripts dir isn't on sys.path."""
    try:
        import media_backend
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import media_backend
    return media_backend.get_transcriber()


def _download_audio(video, workdir):
    """Fetch an audio-only stream. Returns (bytes, mime).

    Two selectors, tried in order. m4a first: no remux, and every
    transcription route accepts it. The permissive retry exists because
    YouTube intermittently serves a restricted format set for a video that
    lists m4a moments earlier — observed live, and a transient refusal must
    not cost us the evidence. Only the retry pays for the broader match.
    """
    attempts = ["bestaudio[ext=m4a]/bestaudio", "bestaudio*/best"]
    last = ""
    for selector in attempts:
        code, _stdout, stderr = _run_yt_dlp(
            [
                "-f", selector,
                "--no-warnings",
                "-o", str(Path(workdir) / "audio.%(ext)s"),
                video["url"],
            ],
            timeout=AUDIO_TIMEOUT,
        )
        files = sorted(Path(workdir).glob("audio.*"))
        if files:
            path = files[0]
            blob = path.read_bytes()[:AUDIO_BYTES_CAP]
            if blob:
                return blob, _audio_mime(path.suffix)
            last = "audio download produced an empty file"
            path.unlink(missing_ok=True)
            continue
        last = f"exit {code}: {(stderr or '').strip()[:200]}"
    raise RuntimeError(f"audio download produced no file ({last})")


_AUDIO_MIME = {
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".webm": "audio/webm",
    ".opus": "audio/opus",
    ".ogg": "audio/ogg",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
}


def _audio_mime(suffix):
    """Container -> mime. The permissive retry can land a non-m4a file, and a
    mislabelled upload is rejected by every transcription vendor."""
    return _AUDIO_MIME.get(suffix.lower(), "audio/mp4")


def _transcribe(video, workdir):
    blob, mime = _download_audio(video, workdir)
    return _transcriber().transcribe(blob, mime=mime)


# ---------------------------------------------------------------------------
# Per-video read
# ---------------------------------------------------------------------------
def _read_video(video, may_transcribe):
    """Fill in transcript + source label for one video. Never raises: a broken
    video degrades to a note so its neighbours keep their evidence."""
    with tempfile.TemporaryDirectory() as workdir:
        try:
            meta = _fetch_metadata_and_subs(video, workdir)
        except Exception as exc:  # noqa: BLE001 — degrade, never kill the channel
            video["source"] = SOURCE_NONE
            video["note"] = f"could not read this video ({str(exc)[:120]})"
            return video

        for field in ("duration", "timestamp", "language", "view_count"):
            if meta.get(field) is not None:
                video["views" if field == "view_count" else field] = meta[field]
        if meta.get("title"):
            video["title"] = meta["title"]
        if meta.get("channel"):
            video["channel"] = meta["channel"]

        picked = _pick_track(video["id"], workdir, meta)
        text, kind = "", "auto"
        if picked:
            path, lang, kind = picked
            text = json3_text(path)
            video["caption_lang"] = lang
        ok, reason = caption_quality(text, video.get("duration"), kind)
        if ok:
            video["transcript"] = text
            video["source"] = (
                SOURCE_MANUAL if kind == "manual" else SOURCE_AUTO
            )
            return video

        if not may_transcribe:
            video["source"] = SOURCE_NONE
            video["note"] = f"{reason}; transcription budget spent on other videos"
            return video
        duration = video.get("duration") or 0
        cap = _max_seconds()
        if duration and duration > cap:
            video["source"] = SOURCE_NONE
            video["note"] = (
                f"{reason}; too long to transcribe "
                f"({duration // 60} min > {cap // 60} min cap)"
            )
            return video
        try:
            transcribed = _transcribe(video, workdir)
        except Exception as exc:  # noqa: BLE001 — honest note, not a crash
            video["source"] = SOURCE_NONE
            video["note"] = f"{reason}; transcription failed ({str(exc)[:120]})"
            return video
        if not transcribed:
            video["source"] = SOURCE_NONE
            video["note"] = f"{reason}; transcription returned nothing"
            return video
        video["transcript"] = transcribed
        video["source"] = SOURCE_WHISPER
        video["note"] = f"captions rejected: {reason}"
        return video


def _needs_transcription(video):
    return video.get("source") == SOURCE_WHISPER


# ---------------------------------------------------------------------------
# Channel
# ---------------------------------------------------------------------------
def channel_youtube(query, out_path, max_items, freshness_sink=None,
                    evidence_sink=None):
    """Spoken content from YouTube, with our own transcription when the
    platform's captions are unusable.

    `evidence_sink` (additive, like freshness_sink) receives a marker for each
    video WE transcribed — that is what lets coverage-receipts say truthfully
    that no web index holds this text.
    """
    explicit = _explicit_ids(query)
    if explicit:
        videos = [
            {
                "id": video_id,
                "title": video_id,
                "channel": "unknown",
                "url": f"{WATCH_URL}{video_id}",
                "views": None,
                "duration": None,
                "timestamp": None,
                "language": None,
                "text": query,
            }
            for video_id in explicit
        ]
        ranked_note = None
        shown = videos[:max_items]
    else:
        pool = min(25, max(10, max_items * 2))
        found = _search(query, pool)
        ranked = runner("rank_items")(
            found, query, text_key="text", engagement_key="views",
            max_items=max_items,
        )
        ranked_note = ranked.note
        shown = ranked.items

    read_limit = min(len(shown), _read_top())
    transcribe_budget = _transcribe_top()
    transcribed = 0
    for index, video in enumerate(shown):
        if index >= read_limit:
            video["source"] = SOURCE_NONE
            video["note"] = (
                f"not read — only the top {read_limit} videos are opened per run"
            )
            continue
        _read_video(video, may_transcribe=transcribed < transcribe_budget)
        if _needs_transcription(video):
            transcribed += 1
            if evidence_sink is not None:
                evidence_sink.append(f"self-transcribed:{video['id']}")
        runner("_note_ts")(freshness_sink, video.get("timestamp"))

    lines = [f"# YouTube — what was actually said about: {query}\n"]
    if ranked_note:
        lines.append(f"_Note: {ranked_note}._\n")
    # No silent caps: a reader must see what the run did NOT open.
    if len(shown) > read_limit:
        lines.append(
            f"_Read the top {read_limit} of {len(shown)} matches; the rest are "
            "listed with metadata only._\n"
        )
    if transcribed:
        lines.append(
            f"_Transcribed {transcribed} video(s) ourselves because YouTube's "
            "captions were unusable — that text exists in no web index._\n"
        )
    if not shown:
        lines.append("_No videos matched this topic._\n")

    for video in shown:
        lines.append(f"- **{video['title']}** — {video['channel']}")
        facts = []
        if video.get("views") is not None:
            facts.append(f"views {video['views']:,}")
        if video.get("duration"):
            facts.append(f"{video['duration'] // 60} min")
        facts.append(f"source: {video.get('source', SOURCE_NONE)}")
        lines.append(f"  - {', '.join(facts)}")
        lines.append(f"  - {video['url']}")
        if video.get("note"):
            lines.append(f"  - _{video['note']}_")
        if video.get("transcript"):
            lines.append(f"  - transcript: {_excerpt(video['transcript'], 600)}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(shown)
