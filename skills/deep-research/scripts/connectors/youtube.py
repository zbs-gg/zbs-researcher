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
                 gives metadata (duration, upload timestamp, spoken language,
                 and the `subtitles` map that says which languages are
                 HUMAN-made), while `--no-simulate --write-subs
                 --write-auto-subs` lands the json3 tracks.
  3. judge     — caption_quality scores what landed. Missing, machine
                 translated, unpunctuated raw ASR, or suspiciously sparse
                 relative to the runtime all fail, and the REASON is printed.
  4. fallback  — a failed track sends the audio through media_backend's
                 transcriber, bounded by the per-run budgets below.
  5. report    — every video carries an explicit provenance label, so a reader
                 always knows whether a quote came from a human caption, a
                 machine caption, or our own Whisper pass. Full transcripts are
                 written beside the report so any quote stays auditable.

PROVENANCE IS DERIVED FROM METADATA, NEVER FROM A FILENAME. A language present
in the metadata's `subtitles` map is human-made. A track whose base language
differs from the video's spoken language is a machine TRANSLATION of a machine
transcript — the worst tier — and that comparison is the only reliable test:
YouTube serves a translated auto-caption for a Russian video under the bare code
`en`, so any dash-in-the-code heuristic both misses those and wrongly condemns
ordinary regional tracks like `pt-BR`.

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
import time
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
# Wall-clock ceiling for the WHOLE channel. Without it the per-call timeouts
# stack: 5 metadata reads plus 3 audio downloads could hold a run for ~45
# minutes against a documented 3-7 minute expectation.
DEFAULT_DEADLINE_SECONDS = 8 * 60
AUDIO_BYTES_CAP = 25 * 1024 * 1024
SEARCH_TIMEOUT = 120
VIDEO_TIMEOUT = 180
AUDIO_TIMEOUT = 600
# The retry exists to survive a transient format refusal, not to wait out a
# second full download.
AUDIO_RETRY_TIMEOUT = 240
TRANSCRIPT_DIR_NAME = "youtube-transcripts"

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
SOURCE_REJECTED = "captions found but unusable"
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


def _deadline_seconds():
    return _int_env("DEEP_RESEARCH_YOUTUBE_DEADLINE", DEFAULT_DEADLINE_SECONDS)


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

    `--ignore-config` is not optional hardening: yt-dlp reads a `yt-dlp.conf`
    from the CURRENT DIRECTORY, and research runs execute inside whatever
    project the user launched from. Without it, checking out a repository that
    carries such a file would let it inject arbitrary yt-dlp options — including
    ones that execute commands — into every run. The child also gets a private
    empty cwd so no config, cookie, or output file can be picked up by accident.

    Never raises on a non-zero exit: yt-dlp routinely partial-fails (one
    unavailable track, one age-gated video) while still producing usable
    output, so the CALLER decides what a failure means.
    """
    argv = _yt_dlp_argv() + ["--ignore-config"] + list(args)
    try:
        with tempfile.TemporaryDirectory() as sandbox:
            # Argument LIST only — no shell interpolation, so a topic
            # containing quotes or semicolons is data, never something the OS
            # can execute.
            completed = subprocess.run(  # noqa: S603
                argv,
                capture_output=True,
                timeout=timeout,
                check=False,
                cwd=sandbox,
            )
    except subprocess.TimeoutExpired:
        return 1, "", f"yt-dlp timed out after {timeout}s"
    except OSError as exc:
        return 1, "", f"could not run yt-dlp: {exc}"
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


def _base_lang(code):
    """Primary subtag of a language code: 'pt-BR' -> 'pt', 'en-orig' -> 'en'."""
    return (code or "").split("-", 1)[0].strip().lower() or None


def _spoken_language(meta):
    """The language actually spoken in the video.

    `language` when yt-dlp reports it; otherwise the `<lang>-orig` key that
    YouTube uses to mark the original-language auto-caption. Returns None when
    neither is available — and an unknown spoken language must never be used to
    condemn a track as a translation.
    """
    spoken = _base_lang(meta.get("language"))
    if spoken:
        return spoken
    for lang in (meta.get("automatic_captions") or {}):
        if lang.endswith("-orig"):
            return _base_lang(lang)
    return None


def _classify_track(lang, manual_langs, spoken):
    """('manual' | 'auto' | 'translated', sort rank) for one caption track.

    Provenance comes from the METADATA, never the filename: a language listed
    under `subtitles` is human-made. Translation is decided by comparing the
    track's base language against the SPOKEN language — the only test that
    catches YouTube serving a translated auto-caption under a bare `en`, and
    the only one that does not wrongly condemn `pt-BR` or `zh-Hans`.
    """
    if lang in manual_langs:
        return "manual", 0
    base = _base_lang(lang)
    if spoken and base and base != spoken:
        return "translated", 3
    if lang.endswith("-orig"):
        return "auto", 1
    return "auto", 2


def _pick_track(video_id, workdir, meta):
    """Choose the best caption file. Returns (path, lang, kind) or None."""
    manual_langs = set((meta.get("subtitles") or {}).keys())
    spoken = _spoken_language(meta)
    candidates = []
    for path in sorted(Path(workdir).glob(f"{video_id}.*.json3")):
        # "<id>.<lang>.json3" -> lang (which may itself contain dashes)
        lang = path.name[len(video_id) + 1: -len(".json3")]
        kind, rank = _classify_track(lang, manual_langs, spoken)
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
def _media_backend():
    """The media_backend module — sibling of the runner, imported lazily so the
    connector loads even where the scripts dir isn't on sys.path."""
    try:
        import media_backend
    except ImportError:
        scripts_dir = str(Path(__file__).resolve().parents[1])
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import media_backend
    return media_backend


def _transcriber():
    """media_backend.get_transcriber() — the route the user chose."""
    return _media_backend().get_transcriber()


def transcribe_route():
    """(route, reason) for the audio route that WOULD run, or (None, reason).

    Resolved BEFORE any audio is downloaded: with no route configured there is
    nothing to gain from fetching megabytes we cannot transcribe.
    """
    try:
        return _media_backend().resolve_transcribe_route()
    except Exception as exc:  # noqa: BLE001 — availability probe, never fatal
        return None, f"transcription backend unavailable ({str(exc)[:80]})"


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


def _completed_audio_files(workdir):
    """Fully-written audio files only.

    yt-dlp leaves `.part` / `.ytdl` / `.fN.` fragments behind when a download
    is interrupted. Globbing `audio.*` would hand one of those to the vendor as
    if it were the whole soundtrack, and a partial transcript presented as
    complete is exactly the failure this connector exists to avoid.
    """
    return sorted(
        path for path in Path(workdir).glob("audio.*")
        if path.suffix.lower() in _AUDIO_MIME
    )


def _clear_audio(workdir):
    for path in Path(workdir).glob("audio.*"):
        try:
            path.unlink()
        except OSError:
            pass


def _download_audio(video, workdir):
    """Fetch an audio-only stream. Returns (bytes, mime).

    Two selectors, tried in order. m4a first: no remux, and every
    transcription route accepts it. The permissive retry exists because
    YouTube intermittently serves a restricted format set for a video that
    listed m4a moments earlier — observed live, and a transient refusal must
    not cost us the evidence. Both selectors stay AUDIO-only so a fallback can
    never quietly pull a full video stream, and `--max-filesize` refuses an
    oversized file at the tool instead of after it has hit the disk.
    """
    cap_mb = max(1, AUDIO_BYTES_CAP // (1024 * 1024))
    attempts = (
        ("bestaudio[ext=m4a]/bestaudio", AUDIO_TIMEOUT),
        ("bestaudio*", AUDIO_RETRY_TIMEOUT),
    )
    last = ""
    for selector, timeout in attempts:
        # A stale fragment from a previous attempt must never be mistaken for
        # this attempt's output.
        _clear_audio(workdir)
        code, _stdout, stderr = _run_yt_dlp(
            [
                "-f", selector,
                "--max-filesize", f"{cap_mb}M",
                # A live stream has no meaningful duration, so the length cap
                # cannot bound it — refuse it here instead.
                "--match-filter", "!is_live",
                "--no-warnings",
                "-o", str(Path(workdir) / "audio.%(ext)s"),
                video["url"],
            ],
            timeout=timeout,
        )
        files = _completed_audio_files(workdir)
        if code != 0:
            last = f"exit {code}: {(stderr or '').strip()[:200]}"
            continue
        if not files:
            last = (
                f"no audio file (exit {code}): {(stderr or '').strip()[:200]}"
            )
            continue
        path = files[0]
        size = path.stat().st_size
        if size == 0:
            last = "audio download produced an empty file"
            continue
        if size > AUDIO_BYTES_CAP:
            # Refuse rather than slice. Sending the first 25 MB and printing
            # the result as the video's transcript would present half a talk
            # as the whole thing.
            raise RuntimeError(
                f"audio is {size // (1024 * 1024)} MB, over the "
                f"{cap_mb} MB cap — not transcribed rather than truncated"
            )
        return path.read_bytes(), _audio_mime(path.suffix)
    raise RuntimeError(f"audio download produced no file ({last})")


def _transcribe(video, workdir):
    blob, mime = _download_audio(video, workdir)
    return _transcriber().transcribe(blob, mime=mime)


# ---------------------------------------------------------------------------
# Per-video read
# ---------------------------------------------------------------------------
def _finish(video, source, note=None):
    video["source"] = source
    if note:
        video["note"] = note
    return video


def _read_video(video, may_transcribe):
    """Fill in transcript + source label for one video.

    Never raises for per-video problems: a broken video degrades to a note so
    its neighbours keep their evidence. YouTubeToolMissing is the deliberate
    exception — a missing tool is a CHANNEL-level failure, not a property of
    this video, and must reach run_connector so it writes youtube.ERROR.md.

    Sets video["transcribe_attempted"] whenever the paid/expensive path was
    entered, so the caller can budget ATTEMPTS rather than successes.
    """
    with tempfile.TemporaryDirectory() as workdir:
        try:
            meta = _fetch_metadata_and_subs(video, workdir)
        except YouTubeToolMissing:
            raise
        except Exception as exc:  # noqa: BLE001 — degrade, keep the neighbours
            return _finish(video, SOURCE_NONE,
                           f"could not read this video ({str(exc)[:120]})")

        for field in ("duration", "timestamp", "language", "view_count"):
            if meta.get(field) is not None:
                video["views" if field == "view_count" else field] = meta[field]
        if meta.get("title"):
            video["title"] = meta["title"]
        if meta.get("channel"):
            video["channel"] = meta["channel"]

        picked = _pick_track(video["id"], workdir, meta)
        text, kind, had_track = "", "auto", False
        if picked:
            path, lang, kind = picked
            text = json3_text(path)
            video["caption_lang"] = lang
            had_track = bool(text)
        ok, reason = caption_quality(text, video.get("duration"), kind)
        if ok:
            video["transcript"] = text
            return _finish(
                video, SOURCE_MANUAL if kind == "manual" else SOURCE_AUTO
            )

        # A video whose captions were READ AND REJECTED is not the same as one
        # that had none; collapsing them would hide why we spent money.
        rejected = SOURCE_REJECTED if had_track else SOURCE_NONE
        if not may_transcribe:
            return _finish(video, rejected,
                           f"{reason}; transcription budget spent on other videos")

        duration = video.get("duration") or 0
        cap = _max_seconds()
        if not duration:
            # Unknown duration is untrusted, not unlimited: live streams and
            # broken metadata both land here, and both can download forever.
            return _finish(video, rejected,
                           f"{reason}; duration unknown — skipped to bound cost")
        if duration > cap:
            return _finish(video, rejected, (
                f"{reason}; too long to transcribe "
                f"({duration // 60} min > {cap // 60} min cap)"
            ))

        video["transcribe_attempted"] = True
        try:
            transcribed = _transcribe(video, workdir)
        except Exception as exc:  # noqa: BLE001 — honest note, not a crash
            return _finish(video, rejected,
                           f"{reason}; transcription failed ({str(exc)[:120]})")
        if not transcribed:
            return _finish(video, rejected,
                           f"{reason}; transcription returned nothing")
        video["transcript"] = transcribed
        return _finish(video, SOURCE_WHISPER, f"captions rejected: {reason}")


def _was_transcribed(video):
    return video.get("source") == SOURCE_WHISPER


def _save_transcripts(out_path, videos):
    """Persist full transcripts beside the report.

    The markdown carries an excerpt; a reader auditing a quote past that point
    needs the whole text, and for a transcript WE produced this run directory
    is the only place it exists. Returns {video_id: relative path}.
    """
    saved = {}
    holders = [v for v in videos if v.get("transcript")]
    if not holders:
        return saved
    folder = Path(out_path).parent / TRANSCRIPT_DIR_NAME
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        return saved
    for video in holders:
        name = f"{video['id']}.txt"
        try:
            (folder / name).write_text(
                f"# {video['title']}\n# {video['url']}\n"
                f"# source: {video.get('source', '?')}\n\n"
                f"{video['transcript']}\n",
                encoding="utf-8",
            )
        except OSError:
            continue
        saved[video["id"]] = f"{TRANSCRIPT_DIR_NAME}/{name}"
    return saved


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

    Returns the number of videos that actually carry a transcript. Counting
    listed rows instead would let a run with zero readable videos claim it had
    the spoken content a web index lacks.
    """
    # Probe the tool ONCE, before either discovery path. The explicit-URL path
    # never calls _search, so without this a missing yt-dlp would degrade
    # per-video and report a healthy channel instead of youtube.ERROR.md.
    _yt_dlp_argv()

    explicit = _explicit_ids(query)
    if explicit:
        shown = [
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
        ][:max_items]
        ranked_note = None
    else:
        pool = min(25, max(10, max_items * 2))
        ranked = runner("rank_items")(
            _search(query, pool), query, text_key="text",
            engagement_key="views", max_items=max_items,
        )
        ranked_note = ranked.note
        shown = ranked.items

    route, route_reason = transcribe_route()
    read_limit = min(len(shown), _read_top())
    transcribe_budget = _transcribe_top() if route else 0
    deadline = time.monotonic() + _deadline_seconds()
    attempts = 0
    out_of_time = False

    for index, video in enumerate(shown):
        if index >= read_limit:
            _finish(video, SOURCE_NONE,
                    f"not read — only the top {read_limit} videos are opened per run")
            continue
        if time.monotonic() >= deadline:
            out_of_time = True
            _finish(video, SOURCE_NONE,
                    "not read — the channel hit its wall-clock budget")
            continue
        _read_video(video, may_transcribe=attempts < transcribe_budget)
        if video.get("transcribe_attempted"):
            # Budget ATTEMPTS, not successes: three failures in a row are three
            # downloads and three vendor calls already paid for.
            attempts += 1
        if _was_transcribed(video) and evidence_sink is not None:
            evidence_sink.append(f"self-transcribed:{video['id']}")
        runner("_note_ts")(freshness_sink, video.get("timestamp"))

    transcribed = sum(1 for v in shown if _was_transcribed(v))
    with_text = sum(1 for v in shown if v.get("transcript"))
    saved = _save_transcripts(out_path, shown)

    lines = [f"# YouTube — what was actually said about: {query}\n"]
    if ranked_note:
        lines.append(f"_Note: {ranked_note}._\n")
    # No silent caps: a reader must see what the run did NOT open.
    if len(shown) > read_limit:
        lines.append(
            f"_Read the top {read_limit} of {len(shown)} matches; the rest are "
            "listed with metadata only._\n"
        )
    if out_of_time:
        lines.append(
            "_The channel hit its wall-clock budget; the videos marked below "
            "were never opened._\n"
        )
    if transcribed:
        # Name the route: "we transcribed this" costs either money or nothing
        # at all depending on it, and an auditor needs to know which.
        cost = ("run locally at $0 — the audio never left this machine"
                if route == "local"
                else f"run via {route}, billed to your key")
        lines.append(
            f"_Transcribed {transcribed} video(s) ourselves because YouTube's "
            f"captions were unusable ({cost}). That text exists in no web "
            "index._\n"
        )
    elif not route:
        lines.append(
            f"_No transcription route configured ({route_reason}), so videos "
            "with unusable captions are listed as metadata only._\n"
        )
    if saved:
        lines.append(
            f"_Full transcripts saved beside this report in `{TRANSCRIPT_DIR_NAME}/`._\n"
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
            if saved.get(video["id"]):
                lines.append(f"  - full text: {saved[video['id']]}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return with_text
