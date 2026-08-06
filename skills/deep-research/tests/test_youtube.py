"""YouTube connector: spoken content, with our own transcription as fallback.

channel_youtube (connectors/youtube.py) discovers videos (ytsearch keyword
search, or explicit URLs in the query), reads the best caption track it can
get, JUDGES that track, and when the track is missing or too poor to quote it
transcribes the audio through media_backend. Every video carries an explicit
provenance label so a reader knows whether a quote came from a human caption,
a machine caption, or our own Whisper pass.

Every yt-dlp invocation goes through the single _run_yt_dlp seam, and the
transcriber through _transcriber — both patched here, so the suite never
touches the network, never spawns a process, and never spends a cent.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
RUNNER = SCRIPTS / "deep-research.py"
SOURCE = SCRIPTS / "connectors" / "youtube.py"

scripts_path = str(SCRIPTS)
path_added = scripts_path not in sys.path
if path_added:
    sys.path.insert(0, scripts_path)
try:
    SPEC = importlib.util.spec_from_file_location("deep_research_youtube", RUNNER)
    deep_research = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(deep_research)
    import connectors as connectors_pkg
    from connectors import youtube as youtube_mod
finally:
    if path_added:
        sys.path.remove(scripts_path)


TOPIC = "context engineering"
VIDEO_ID = "vD0E3EUb8-8"

# Punctuated, sentence-cased prose: what a usable caption track looks like.
# Repeated to a realistic density — a 472-second video carries roughly 500-1200
# words, and the quality gate rejects tracks far sparser than their runtime.
_GOOD_PARAGRAPH = (
    "I think by now most of us are familiar with the term prompt engineering. "
    "It's the process of crafting the input text used to prompt a large "
    "language model, including instructions and examples. Context engineering, "
    "on the other hand, is the broader discipline of assembling everything the "
    "model sees during inference. That includes prompts, retrieved documents, "
    "and tool outputs, which is why teams keep getting it wrong in production. "
)
GOOD_TEXT = (_GOOD_PARAGRAPH * 8).strip()
# Raw ASR at a realistic word rate: the words are all there, but there is no
# capitalisation and no sentence punctuation, so nothing can be quoted cleanly.
RAW_ASR_TEXT = " ".join(["so basically what happens here is the model just"] * 90)


def json3(lines):
    """Build a json3 caption payload whose events are LINES (the real shape:
    each event holds one caption line, with no trailing space)."""
    return {"events": [{"segs": [{"utf8": line}]} for line in lines]}


def search_record(video_id, title, views, description="", duration=472):
    return json.dumps({
        "id": video_id,
        "title": title,
        "channel": "IBM Technology",
        "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
        "view_count": views,
        "duration": duration,
        "description": description,
    })


class FakeYtDlp:
    """Stand-in for _run_yt_dlp. Routes on the argument list and records every
    call, so tests assert on WHAT was asked of yt-dlp, not just the result."""

    def __init__(self, search_lines=(), meta=None, subs=None, audio=b"audio",
                 search_code=0, meta_code=0, audio_code=0):
        self.search_lines = list(search_lines)
        self.meta = meta if meta is not None else {}
        self.subs = dict(subs or {})       # filename suffix -> json3 payload
        self.audio = audio
        self.search_code = search_code
        self.meta_code = meta_code
        self.audio_code = audio_code
        self.calls = []

    @staticmethod
    def video_id_of(args):
        """The id yt-dlp was actually asked about — taken from the trailing URL
        so caption files land under the right name for EACH video, not a single
        module-level constant."""
        match = re.search(r"[?/]v?=?([A-Za-z0-9_-]{11})$", args[-1])
        return match.group(1) if match else VIDEO_ID

    def __call__(self, args, timeout):
        args = list(args)
        self.calls.append(args)
        if any(a.startswith("ytsearch") for a in args):
            return self.search_code, "\n".join(self.search_lines), ""
        if "--write-subs" in args:
            outdir = Path(args[args.index("-o") + 1]).parent
            video_id = self.video_id_of(args)
            for suffix, payload in self.subs.items():
                (outdir / f"{video_id}.{suffix}.json3").write_text(
                    json.dumps(payload), encoding="utf-8"
                )
            return self.meta_code, json.dumps(self.meta), ""
        if "-f" in args:
            if self.audio is not None:
                outdir = Path(args[args.index("-o") + 1]).parent
                (outdir / "audio.m4a").write_bytes(self.audio)
            return self.audio_code, "", "" if self.audio_code == 0 else "boom"
        return 0, "", ""


class FakeTranscriber:
    def __init__(self, text="whisper heard this clearly and said so.", error=None):
        self.text = text
        self.error = error
        self.calls = []

    def transcribe(self, blob, mime="audio/mpeg"):
        self.calls.append((blob, mime))
        if self.error is not None:
            raise self.error
        return self.text


class YouTubeCase(unittest.TestCase):
    def setUp(self):
        connectors_pkg.attach_runner(deep_research.__dict__)
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        # EVERY budget knob the connector reads, or a developer's own shell
        # silently changes which branch these tests exercise.
        for name in (
            "DEEP_RESEARCH_YOUTUBE_READ_TOP",
            "DEEP_RESEARCH_YOUTUBE_TRANSCRIBE_TOP",
            "DEEP_RESEARCH_YOUTUBE_MAX_SECONDS",
            "DEEP_RESEARCH_YOUTUBE_DEADLINE",
            "DEEP_RESEARCH_YOUTUBE_SUB_LANGS",
        ):
            os.environ.pop(name, None)

    def run_channel(self, fake, transcriber=None, topic=TOPIC, max_items=10,
                    freshness_sink=None, evidence_sink=None,
                    route=("groq", "test route"), out_dir=None):
        """Drive the channel with every external seam pinned.

        The ROUTE is pinned too: leaving it to media_backend would make these
        tests read whichever keys the developer or CI happens to have exported,
        so the same suite would exercise a different code path per machine.
        """
        transcriber = transcriber or FakeTranscriber()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(out_dir or tmp) / "youtube.md"
            with mock.patch.object(youtube_mod, "_run_yt_dlp", fake), \
                    mock.patch.object(
                        youtube_mod, "_transcriber", lambda: transcriber
                    ), mock.patch.object(
                        youtube_mod, "transcribe_route", lambda: route
                    ):
                count = youtube_mod.channel_youtube(
                    topic, out, max_items,
                    freshness_sink=freshness_sink,
                    evidence_sink=evidence_sink,
                )
            return count, out.read_text(encoding="utf-8"), transcriber


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------
class DiscoveryTests(YouTubeCase):
    def test_search_parses_records_and_ranks_on_relevance(self):
        fake = FakeYtDlp(
            search_lines=[
                search_record("aaaaaaaaaaa", "unrelated dance clip", 5_000_000),
                search_record(VIDEO_ID, "context engineering explained", 231_441),
            ],
            meta={"subtitles": {}, "duration": 472},
            subs={"en-orig": json3(GOOD_TEXT.split(". "))},
        )
        count, report, _ = self.run_channel(fake)
        self.assertEqual(count, 2)
        # the on-topic video outranks the far more popular off-topic one
        self.assertLess(
            report.index("context engineering explained"),
            report.index("unrelated dance clip"),
        )

    def test_search_failure_with_no_output_raises(self):
        fake = FakeYtDlp(search_lines=[], search_code=1)
        with mock.patch.object(youtube_mod, "_run_yt_dlp", fake):
            with self.assertRaises(RuntimeError):
                youtube_mod._search(TOPIC, 5)

    def test_non_json_search_lines_are_skipped_not_fatal(self):
        fake = FakeYtDlp(
            search_lines=["WARNING: something", "{bad json", search_record(
                VIDEO_ID, "context engineering", 10
            )],
            meta={"subtitles": {}},
            subs={"en-orig": json3(GOOD_TEXT.split(". "))},
        )
        count, _, _ = self.run_channel(fake)
        self.assertEqual(count, 1)

    def test_explicit_urls_skip_search_entirely(self):
        cases = [
            f"https://www.youtube.com/watch?v={VIDEO_ID}",
            f"https://youtu.be/{VIDEO_ID}",
            f"https://www.youtube.com/shorts/{VIDEO_ID}",
            f"look at https://m.youtube.com/watch?v={VIDEO_ID}&t=90s please",
            VIDEO_ID,
        ]
        for query in cases:
            with self.subTest(query=query):
                self.assertEqual(youtube_mod._explicit_ids(query), [VIDEO_ID])

    def test_search_words_are_never_mistaken_for_a_video_id(self):
        # 11 chars, but part of a sentence -> still a search, not an id
        self.assertEqual(youtube_mod._explicit_ids("elevenchars are here"), [])
        self.assertEqual(youtube_mod._explicit_ids(TOPIC), [])

    def test_explicit_url_query_issues_no_search_call(self):
        fake = FakeYtDlp(
            meta={"subtitles": {"en": [{}]}, "duration": 472},
            subs={"en": json3(GOOD_TEXT.split(". "))},
        )
        self.run_channel(fake, topic=f"https://youtu.be/{VIDEO_ID}")
        self.assertFalse(
            any(a.startswith("ytsearch") for call in fake.calls for a in call)
        )


# ---------------------------------------------------------------------------
# Caption parsing + quality gate
# ---------------------------------------------------------------------------
class CaptionTextTests(YouTubeCase):
    def test_events_are_joined_with_a_space(self):
        """Regression: events are LINES. Concatenating them raw fuses the last
        word of one line with the first of the next ("familiarwith")."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.json3"
            path.write_text(
                json.dumps(json3([
                    "most of us are familiar",
                    "with the term prompt engineering.",
                ])),
                encoding="utf-8",
            )
            text = youtube_mod.json3_text(path)
        self.assertIn("familiar with", text)
        self.assertNotIn("familiarwith", text)

    def test_whitespace_is_collapsed_for_tracks_carrying_trailing_spaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.json3"
            path.write_text(
                json.dumps(json3(["auto tracks ", " already space padded"])),
                encoding="utf-8",
            )
            self.assertEqual(
                youtube_mod.json3_text(path), "auto tracks already space padded"
            )

    def test_unreadable_track_yields_empty_text_not_an_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.json3"
            path.write_text("{not json", encoding="utf-8")
            self.assertEqual(youtube_mod.json3_text(path), "")
            self.assertEqual(youtube_mod.json3_text(Path(tmp) / "absent"), "")


class QualityGateTests(YouTubeCase):
    def test_good_prose_passes(self):
        ok, _ = youtube_mod.caption_quality(GOOD_TEXT, 472, "manual")
        self.assertTrue(ok)

    def test_missing_track_fails(self):
        ok, reason = youtube_mod.caption_quality("", 472, "auto")
        self.assertFalse(ok)
        self.assertIn("no caption track", reason)

    def test_machine_translation_is_rejected_outright(self):
        ok, reason = youtube_mod.caption_quality(GOOD_TEXT, 472, "translated")
        self.assertFalse(ok)
        self.assertIn("machine translation", reason)

    def test_raw_asr_without_punctuation_fails(self):
        ok, reason = youtube_mod.caption_quality(RAW_ASR_TEXT, 120, "auto")
        self.assertFalse(ok)
        self.assertIn("punctuation", reason)

    def test_sparse_track_relative_to_runtime_fails(self):
        # good prose, but only ~90 words against a 60-minute video
        ok, reason = youtube_mod.caption_quality(GOOD_TEXT * 1, 3600, "auto")
        self.assertFalse(ok)
        self.assertIn("gaps", reason)

    def test_very_short_track_fails(self):
        ok, reason = youtube_mod.caption_quality("Too short.", None, "auto")
        self.assertFalse(ok)
        self.assertIn("words", reason)


class TrackPreferenceTests(YouTubeCase):
    def pick(self, langs, manual=(), spoken=None, auto=()):
        with tempfile.TemporaryDirectory() as tmp:
            for lang in langs:
                (Path(tmp) / f"{VIDEO_ID}.{lang}.json3").write_text("{}", "utf-8")
            meta = {"subtitles": {lang: [{}] for lang in manual}}
            if spoken:
                meta["language"] = spoken
            if auto:
                meta["automatic_captions"] = {lang: [{}] for lang in auto}
            picked = youtube_mod._pick_track(VIDEO_ID, tmp, meta)
        return None if picked is None else (picked[1], picked[2])

    def test_human_captions_beat_every_machine_track(self):
        self.assertEqual(
            self.pick(["en", "en-orig", "ru-en"], manual=["en"], spoken="en"),
            ("en", "manual"),
        )

    def test_original_language_auto_beats_plain(self):
        self.assertEqual(
            self.pick(["en-orig", "en"], spoken="en"), ("en-orig", "auto")
        )

    def test_no_track_returns_none(self):
        self.assertIsNone(self.pick([]))

    def test_provenance_comes_from_metadata_not_the_filename(self):
        """The same "en" file is human-made or machine-made depending ONLY on
        whether the metadata lists it under `subtitles`."""
        self.assertEqual(self.pick(["en"], manual=["en"], spoken="en")[1], "manual")
        self.assertEqual(self.pick(["en"], spoken="en")[1], "auto")


class TranslationDetectionTests(YouTubeCase):
    """A machine translation of a machine transcript is the worst tier, and
    YouTube does NOT mark it in the language code — so the only reliable test
    is the track's language against the language actually spoken."""

    def classify(self, lang, manual=(), spoken=None):
        return youtube_mod._classify_track(lang, set(manual), spoken)[0]

    def test_bare_code_translation_of_a_russian_video_is_caught(self):
        # The regression: YouTube serves the translated auto-caption for a
        # Russian video under a plain "en". A dash-based rule calls this an
        # ordinary auto-caption and the report then quotes a translation as if
        # it were what the speaker said.
        self.assertEqual(self.classify("en", spoken="ru"), "translated")

    def test_regional_and_script_subtags_are_not_translations(self):
        for lang, spoken in (("pt-BR", "pt"), ("zh-Hans", "zh"),
                             ("en-GB", "en"), ("es-419", "es")):
            with self.subTest(lang=lang):
                self.assertEqual(self.classify(lang, spoken=spoken), "auto")

    def test_original_language_track_is_never_a_translation(self):
        self.assertEqual(self.classify("ru-orig", spoken="ru"), "auto")

    def test_unknown_spoken_language_never_condemns_a_track(self):
        # Over-claiming "translated" would push a perfectly good track into
        # paid transcription; with no spoken language known, stay neutral.
        self.assertEqual(self.classify("ru-en", spoken=None), "auto")

    def test_manual_track_outranks_a_language_mismatch(self):
        self.assertEqual(
            self.classify("en", manual=["en"], spoken="ru"), "manual"
        )

    def test_spoken_language_falls_back_to_the_orig_caption_key(self):
        self.assertEqual(
            youtube_mod._spoken_language(
                {"automatic_captions": {"ru-orig": [{}], "en": [{}]}}
            ),
            "ru",
        )


# ---------------------------------------------------------------------------
# The fallback — the point of the whole connector
# ---------------------------------------------------------------------------
class TranscriptionFallbackTests(YouTubeCase):
    def usable_search(self):
        return [search_record(VIDEO_ID, "context engineering explained", 231_441)]

    def test_good_captions_are_used_and_nothing_is_transcribed(self):
        fake = FakeYtDlp(
            search_lines=self.usable_search(),
            meta={"subtitles": {"en": [{}]}, "duration": 472},
            subs={"en": json3(GOOD_TEXT.split(". "))},
        )
        _, report, transcriber = self.run_channel(fake)
        self.assertIn(youtube_mod.SOURCE_MANUAL, report)
        self.assertEqual(transcriber.calls, [])

    def test_raw_asr_captions_trigger_our_own_transcription(self):
        fake = FakeYtDlp(
            search_lines=self.usable_search(),
            meta={"subtitles": {}, "duration": 472},
            subs={"en-orig": json3([RAW_ASR_TEXT])},
        )
        _, report, transcriber = self.run_channel(fake)
        self.assertEqual(len(transcriber.calls), 1)
        self.assertIn(youtube_mod.SOURCE_WHISPER, report)
        # the report must say WHY we spent money on Whisper
        self.assertIn("punctuation", report)
        self.assertIn("whisper heard this", report)

    def test_absent_captions_trigger_transcription(self):
        fake = FakeYtDlp(
            search_lines=self.usable_search(),
            meta={"subtitles": {}, "duration": 472},
            subs={},
        )
        _, report, transcriber = self.run_channel(fake)
        self.assertEqual(len(transcriber.calls), 1)
        self.assertIn(youtube_mod.SOURCE_WHISPER, report)

    def test_transcription_failure_degrades_to_a_note(self):
        fake = FakeYtDlp(
            search_lines=self.usable_search(),
            meta={"subtitles": {}, "duration": 472},
            subs={},
        )
        transcriber = FakeTranscriber(error=RuntimeError("no route configured"))
        count, report, _ = self.run_channel(fake, transcriber=transcriber)
        # No transcript was obtained, so the channel reports zero EVIDENCE even
        # though the video is still listed with its metadata.
        self.assertEqual(count, 0)
        self.assertIn("context engineering explained", report)
        self.assertIn("transcription failed", report)
        self.assertIn("no route configured", report)
        self.assertIn(youtube_mod.SOURCE_NONE, report)

    def test_audio_download_failure_degrades_to_a_note(self):
        fake = FakeYtDlp(
            search_lines=self.usable_search(),
            meta={"subtitles": {}, "duration": 472},
            subs={}, audio=None, audio_code=1,
        )
        count, report, _ = self.run_channel(fake)
        self.assertEqual(count, 0)
        self.assertIn("transcription failed", report)
        # The video is still listed with its metadata — a download failure
        # loses the transcript, not the row.
        self.assertIn("context engineering explained", report)


    def test_unreadable_video_does_not_kill_its_neighbours(self):
        fake = FakeYtDlp(
            search_lines=[
                search_record(VIDEO_ID, "context engineering explained", 500),
            ],
            meta={}, meta_code=1, subs={},
        )
        count, report, _ = self.run_channel(fake)
        self.assertEqual(count, 0)
        self.assertIn("could not read this video", report)

    def test_over_long_videos_are_skipped_with_a_stated_reason(self):
        os.environ["DEEP_RESEARCH_YOUTUBE_MAX_SECONDS"] = "60"
        fake = FakeYtDlp(
            search_lines=self.usable_search(),
            meta={"subtitles": {}, "duration": 3600},
            subs={},
        )
        _, report, transcriber = self.run_channel(fake)
        self.assertEqual(transcriber.calls, [])
        self.assertIn("too long to transcribe", report)

    def test_transcription_budget_is_bounded_and_disclosed(self):
        os.environ["DEEP_RESEARCH_YOUTUBE_TRANSCRIBE_TOP"] = "1"
        fake = FakeYtDlp(
            search_lines=[
                search_record("aaaaaaaaaaa", "context engineering one", 900),
                search_record(VIDEO_ID, "context engineering two", 800),
            ],
            meta={"subtitles": {}, "duration": 472},
            subs={},
        )
        _, report, transcriber = self.run_channel(fake)
        self.assertEqual(len(transcriber.calls), 1)
        self.assertIn("transcription budget spent", report)

    def test_unread_videos_are_disclosed_never_silently_dropped(self):
        os.environ["DEEP_RESEARCH_YOUTUBE_READ_TOP"] = "1"
        fake = FakeYtDlp(
            search_lines=[
                search_record("aaaaaaaaaaa", "context engineering one", 900),
                search_record(VIDEO_ID, "context engineering two", 800),
            ],
            meta={"subtitles": {"en": [{}]}, "duration": 472},
            subs={"en": json3(GOOD_TEXT.split(". "))},
        )
        count, report, _ = self.run_channel(fake)
        # One video was opened and yielded a transcript; the second is listed
        # but unread, so it is not evidence.
        self.assertEqual(count, 1)
        self.assertIn("Read the top 1 of 2 matches", report)
        self.assertIn("not read", report)


class AudioDownloadTests(YouTubeCase):
    """YouTube intermittently refuses a format set it advertised moments
    earlier (observed live). A transient refusal must not cost the evidence."""

    def download(self, responder):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(youtube_mod, "_run_yt_dlp", responder):
                return youtube_mod._download_audio(
                    {"url": "https://youtu.be/" + VIDEO_ID}, tmp
                )

    def test_m4a_is_preferred_on_the_first_attempt(self):
        calls = []

        def responder(args, timeout):
            calls.append(args[args.index("-f") + 1])
            outdir = Path(args[args.index("-o") + 1]).parent
            (outdir / "audio.m4a").write_bytes(b"m4a-bytes")
            return 0, "", ""

        blob, mime = self.download(responder)
        self.assertEqual(blob, b"m4a-bytes")
        self.assertEqual(mime, "audio/mp4")
        self.assertEqual(calls, ["bestaudio[ext=m4a]/bestaudio"])

    def test_a_refused_format_set_is_retried_more_permissively(self):
        calls = []

        def responder(args, timeout):
            selector = args[args.index("-f") + 1]
            calls.append(selector)
            if len(calls) == 1:
                return 1, "", "ERROR: Requested format is not available."
            outdir = Path(args[args.index("-o") + 1]).parent
            (outdir / "audio.webm").write_bytes(b"webm-bytes")
            return 0, "", ""

        blob, mime = self.download(responder)
        self.assertEqual(blob, b"webm-bytes")
        self.assertEqual(mime, "audio/webm")
        self.assertEqual(len(calls), 2)
        self.assertNotEqual(calls[0], calls[1])

    def test_both_attempts_failing_reports_the_last_error(self):
        def responder(args, timeout):
            return 1, "", "ERROR: Requested format is not available."

        with self.assertRaises(RuntimeError) as ctx:
            self.download(responder)
        self.assertIn("Requested format is not available", str(ctx.exception))

    def test_an_empty_file_is_not_mistaken_for_success(self):
        attempts = []

        def responder(args, timeout):
            attempts.append(1)
            outdir = Path(args[args.index("-o") + 1]).parent
            (outdir / "audio.m4a").write_bytes(b"" if len(attempts) == 1 else b"ok")
            return 0, "", ""

        blob, _ = self.download(responder)
        self.assertEqual(blob, b"ok")
        self.assertEqual(len(attempts), 2)

    def test_container_maps_to_a_mime_every_vendor_accepts(self):
        for suffix, expected in (
            (".m4a", "audio/mp4"), (".mp4", "audio/mp4"),
            (".webm", "audio/webm"), (".opus", "audio/opus"),
            (".mp3", "audio/mpeg"), (".unknown", "audio/mp4"),
        ):
            with self.subTest(suffix=suffix):
                self.assertEqual(youtube_mod._audio_mime(suffix), expected)


# ---------------------------------------------------------------------------
# Sinks: freshness + the self-sourced evidence claim
# ---------------------------------------------------------------------------
class SinkTests(YouTubeCase):
    def test_upload_timestamp_feeds_the_freshness_sink(self):
        fake = FakeYtDlp(
            search_lines=[search_record(VIDEO_ID, "context engineering", 10)],
            meta={"subtitles": {"en": [{}]}, "duration": 472,
                  "timestamp": 1755514894},
            subs={"en": json3(GOOD_TEXT.split(". "))},
        )
        sink = []
        self.run_channel(fake, freshness_sink=sink)
        self.assertEqual(sink, [1755514894])

    def test_evidence_sink_marks_only_videos_we_transcribed(self):
        fake = FakeYtDlp(
            search_lines=[search_record(VIDEO_ID, "context engineering", 10)],
            meta={"subtitles": {}, "duration": 472},
            subs={},
        )
        sink = []
        self.run_channel(fake, evidence_sink=sink)
        self.assertEqual(len(sink), 1)
        self.assertIn(VIDEO_ID, sink[0])

    def test_evidence_sink_stays_empty_when_captions_were_usable(self):
        fake = FakeYtDlp(
            search_lines=[search_record(VIDEO_ID, "context engineering", 10)],
            meta={"subtitles": {"en": [{}]}, "duration": 472},
            subs={"en": json3(GOOD_TEXT.split(". "))},
        )
        sink = []
        self.run_channel(fake, evidence_sink=sink)
        self.assertEqual(sink, [])


# ---------------------------------------------------------------------------
# Optional dependency + portability
# ---------------------------------------------------------------------------
class ToolingTests(YouTubeCase):
    def test_missing_yt_dlp_raises_install_guidance_not_a_traceback(self):
        with mock.patch.object(youtube_mod.shutil, "which", return_value=None), \
                mock.patch.dict(sys.modules, {"yt_dlp": None}):
            with self.assertRaises(youtube_mod.YouTubeToolMissing) as ctx:
                youtube_mod._yt_dlp_argv()
        message = str(ctx.exception)
        self.assertNotIsInstance(ctx.exception, ImportError)
        self.assertIn("pip install yt-dlp", message)
        self.assertIn("optional", message)

    def test_binary_on_path_is_preferred_over_the_python_module(self):
        with mock.patch.object(
            youtube_mod.shutil, "which", return_value="/usr/local/bin/yt-dlp"
        ):
            self.assertEqual(
                youtube_mod._yt_dlp_argv(), ["/usr/local/bin/yt-dlp"]
            )

    def test_python_module_is_the_fallback_when_no_binary_exists(self):
        with mock.patch.object(youtube_mod.shutil, "which", return_value=None), \
                mock.patch.dict(sys.modules, {"yt_dlp": mock.Mock()}):
            self.assertEqual(
                youtube_mod._yt_dlp_argv(), [sys.executable, "-m", "yt_dlp"]
            )

    def test_subprocess_is_invoked_with_an_argument_list_never_a_shell(self):
        captured = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            return subprocess.CompletedProcess(argv, 0, b"{}", b"")

        with mock.patch.object(
            youtube_mod, "_yt_dlp_argv", return_value=["yt-dlp"]
        ), mock.patch.object(subprocess, "run", fake_run):
            youtube_mod._run_yt_dlp(["--version"], timeout=5)
        self.assertIsInstance(captured["argv"], list)
        self.assertNotIn("shell", captured["kwargs"])
        self.assertEqual(captured["kwargs"]["timeout"], 5)

    def test_timeout_is_reported_not_raised(self):
        def fake_run(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, kwargs.get("timeout", 1))

        with mock.patch.object(
            youtube_mod, "_yt_dlp_argv", return_value=["yt-dlp"]
        ), mock.patch.object(subprocess, "run", fake_run):
            code, out, err = youtube_mod._run_yt_dlp(["--version"], timeout=7)
        self.assertNotEqual(code, 0)
        self.assertEqual(out, "")
        self.assertIn("timed out", err)

    def test_source_avoids_posix_only_calls(self):
        """R18: the selftest greps for these tokens too, so even a comment or
        docstring mentioning one would fail the Windows-portability gate."""
        source = SOURCE.read_text(encoding="utf-8")
        for token in ("SIGALRM", "killpg", "fcntl", "os.fork", "setsid",
                      "shell=True", "pwd.", "grp."):
            self.assertNotIn(
                token, source, f"{SOURCE.name} must not contain {token!r}"
            )


class ConfigIsolationTests(YouTubeCase):
    """yt-dlp reads a yt-dlp.conf from the CURRENT DIRECTORY, and research runs
    execute inside the user's project. A checked-in config could otherwise
    inject arbitrary options — including ones that execute commands."""

    def run_once(self):
        captured = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            return subprocess.CompletedProcess(argv, 0, b"{}", b"")

        with mock.patch.object(
            youtube_mod, "_yt_dlp_argv", return_value=["yt-dlp"]
        ), mock.patch.object(subprocess, "run", fake_run):
            youtube_mod._run_yt_dlp(["--version"], timeout=5)
        return captured

    def test_every_invocation_disables_config_discovery(self):
        captured = self.run_once()
        self.assertIn("--ignore-config", captured["argv"])
        # Immediately after the binary, before anything a caller supplied.
        self.assertEqual(captured["argv"][1], "--ignore-config")

    def test_child_runs_in_a_private_directory(self):
        captured = self.run_once()
        cwd = captured["kwargs"].get("cwd")
        self.assertTrue(cwd)
        # Not the repo / not the launch dir: a throwaway directory.
        self.assertNotEqual(Path(cwd), Path.cwd())

    def test_unrunnable_binary_is_reported_not_raised(self):
        with mock.patch.object(
            youtube_mod, "_yt_dlp_argv", return_value=["yt-dlp"]
        ), mock.patch.object(subprocess, "run", side_effect=OSError("denied")):
            code, out, err = youtube_mod._run_yt_dlp(["--version"], timeout=5)
        self.assertNotEqual(code, 0)
        self.assertIn("could not run yt-dlp", err)


class MissingToolTests(YouTubeCase):
    """A missing tool is a CHANNEL failure on BOTH discovery paths — the
    documented degrade is youtube.ERROR.md, not a healthy report full of
    per-video excuses."""

    def channel_with_no_tool(self, topic):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "youtube.md"
            with mock.patch.object(
                youtube_mod, "_yt_dlp_argv",
                side_effect=youtube_mod.YouTubeToolMissing(youtube_mod.INSTALL_HINT),
            ):
                with self.assertRaises(youtube_mod.YouTubeToolMissing) as ctx:
                    youtube_mod.channel_youtube(topic, out, 10)
        return str(ctx.exception)

    def test_keyword_query_propagates_the_install_hint(self):
        self.assertIn("pip install yt-dlp", self.channel_with_no_tool(TOPIC))

    def test_explicit_url_query_propagates_too(self):
        # The regression: this path never calls _search, so before the
        # channel-level probe it degraded per-video and reported status ok.
        message = self.channel_with_no_tool(f"https://youtu.be/{VIDEO_ID}")
        self.assertIn("pip install yt-dlp", message)


class AudioBoundsTests(YouTubeCase):
    """Oversized, live, and partial downloads must never become a transcript
    that reads as the whole soundtrack."""

    def download(self, responder):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(youtube_mod, "_run_yt_dlp", responder):
                return youtube_mod._download_audio(
                    {"url": "https://youtu.be/" + VIDEO_ID}, tmp
                )

    def test_oversized_audio_is_refused_not_truncated(self):
        def responder(args, timeout):
            outdir = Path(args[args.index("-o") + 1]).parent
            (outdir / "audio.m4a").write_bytes(
                b"x" * (youtube_mod.AUDIO_BYTES_CAP + 1)
            )
            return 0, "", ""

        with self.assertRaises(RuntimeError) as ctx:
            self.download(responder)
        message = str(ctx.exception)
        self.assertIn("cap", message)
        self.assertIn("rather than truncated", message)

    def test_size_and_live_bounds_are_pushed_down_to_the_tool(self):
        seen = []

        def responder(args, timeout):
            seen.append(args)
            outdir = Path(args[args.index("-o") + 1]).parent
            (outdir / "audio.m4a").write_bytes(b"ok")
            return 0, "", ""

        self.download(responder)
        self.assertIn("--max-filesize", seen[0])
        self.assertIn("--match-filter", seen[0])
        self.assertIn("!is_live", seen[0])

    def test_partial_fragments_are_never_accepted_as_audio(self):
        def responder(args, timeout):
            outdir = Path(args[args.index("-o") + 1]).parent
            # exactly what an interrupted yt-dlp leaves behind
            (outdir / "audio.m4a.part").write_bytes(b"half a file")
            return 0, "", ""

        with self.assertRaises(RuntimeError) as ctx:
            self.download(responder)
        self.assertIn("no audio file", str(ctx.exception))

    def test_a_failed_exit_is_not_salvaged_from_leftovers(self):
        def responder(args, timeout):
            outdir = Path(args[args.index("-o") + 1]).parent
            (outdir / "audio.m4a").write_bytes(b"truncated")
            return 1, "", "ERROR: interrupted"

        with self.assertRaises(RuntimeError) as ctx:
            self.download(responder)
        self.assertIn("exit 1", str(ctx.exception))

    def test_retry_starts_from_a_clean_directory(self):
        attempts = []

        def responder(args, timeout):
            attempts.append(args)
            outdir = Path(args[args.index("-o") + 1]).parent
            if len(attempts) == 1:
                (outdir / "audio.m4a").write_bytes(b"stale leftover")
                return 1, "", "ERROR: Requested format is not available."
            self.assertEqual(list(outdir.glob("audio.*")), [])
            (outdir / "audio.webm").write_bytes(b"fresh")
            return 0, "", ""

        blob, mime = self.download(responder)
        self.assertEqual(blob, b"fresh")
        self.assertEqual(mime, "audio/webm")

    def test_retry_stays_audio_only_and_is_not_given_a_second_full_timeout(self):
        seen = []

        def responder(args, timeout):
            seen.append((args[args.index("-f") + 1], timeout))
            if len(seen) == 1:
                return 1, "", "ERROR: Requested format is not available."
            outdir = Path(args[args.index("-o") + 1]).parent
            (outdir / "audio.m4a").write_bytes(b"ok")
            return 0, "", ""

        self.download(responder)
        # never "best" on its own — that can be a full muxed video
        self.assertNotIn("/best", seen[1][0])
        self.assertLess(seen[1][1], seen[0][1])


class BudgetTests(YouTubeCase):
    def search_lines(self, count):
        return [
            search_record(f"vid{i:07d}xxx"[:11], f"context engineering {i}", 900 - i)
            for i in range(count)
        ]

    def test_failed_transcriptions_still_consume_the_budget(self):
        """Three failures in a row are three downloads and three vendor calls
        already paid for — counting only successes would keep retrying."""
        os.environ["DEEP_RESEARCH_YOUTUBE_TRANSCRIBE_TOP"] = "2"
        fake = FakeYtDlp(
            search_lines=self.search_lines(4),
            meta={"subtitles": {}, "duration": 472},
            subs={},
        )
        transcriber = FakeTranscriber(error=RuntimeError("vendor down"))
        _, report, _ = self.run_channel(fake, transcriber=transcriber)
        attempts = sum(
            1 for call in fake.calls if "-f" in call
        )
        self.assertEqual(attempts, 2)
        self.assertIn("transcription budget spent", report)

    def test_no_route_means_no_download_is_ever_attempted(self):
        """With nothing configured there is nothing to gain from fetching
        megabytes we cannot transcribe."""
        fake = FakeYtDlp(
            search_lines=self.search_lines(2),
            meta={"subtitles": {}, "duration": 472},
            subs={},
        )
        _, report, transcriber = self.run_channel(
            fake, route=(None, "no local install and no cloud key")
        )
        self.assertEqual(transcriber.calls, [])
        self.assertFalse([c for c in fake.calls if "-f" in c])
        self.assertIn("No transcription route configured", report)

    def test_wall_clock_budget_stops_the_run_and_says_so(self):
        os.environ["DEEP_RESEARCH_YOUTUBE_DEADLINE"] = "0"
        fake = FakeYtDlp(
            search_lines=self.search_lines(3),
            meta={"subtitles": {"en": [{}]}, "duration": 472, "language": "en"},
            subs={"en": json3(GOOD_TEXT.split(". "))},
        )
        count, report, _ = self.run_channel(fake)
        self.assertEqual(count, 0)
        self.assertIn("wall-clock budget", report)

    def test_unknown_duration_is_skipped_rather_than_downloaded(self):
        """A live stream reports no duration anywhere, so the length cap cannot
        bound it — the download would run until something else stops it."""
        fake = FakeYtDlp(
            search_lines=[search_record(
                VIDEO_ID, "context engineering live", 900, duration=None
            )],
            meta={"subtitles": {}},  # no duration in the metadata either
            subs={},
        )
        _, report, transcriber = self.run_channel(fake)
        self.assertEqual(transcriber.calls, [])
        self.assertIn("duration unknown", report)


class ReportHonestyTests(YouTubeCase):
    def usable(self):
        return [search_record(VIDEO_ID, "context engineering explained", 900)]

    def test_rejected_captions_are_not_reported_as_absent(self):
        fake = FakeYtDlp(
            search_lines=self.usable(),
            meta={"subtitles": {}, "duration": 472, "language": "en"},
            subs={"en-orig": json3([RAW_ASR_TEXT])},
        )
        transcriber = FakeTranscriber(error=RuntimeError("vendor down"))
        _, report, _ = self.run_channel(fake, transcriber=transcriber)
        self.assertIn(youtube_mod.SOURCE_REJECTED, report)
        self.assertNotIn(youtube_mod.SOURCE_NONE, report)

    def test_local_route_is_disclosed_as_free_and_private(self):
        fake = FakeYtDlp(
            search_lines=self.usable(),
            meta={"subtitles": {}, "duration": 472},
            subs={},
        )
        _, report, _ = self.run_channel(fake, route=("local", "profile self"))
        self.assertIn("never left this machine", report)

    def test_cloud_route_is_disclosed_as_billed(self):
        fake = FakeYtDlp(
            search_lines=self.usable(),
            meta={"subtitles": {}, "duration": 472},
            subs={},
        )
        _, report, _ = self.run_channel(fake, route=("groq", "key configured"))
        self.assertIn("billed to your key", report)

    def test_full_transcripts_are_saved_beside_the_report(self):
        fake = FakeYtDlp(
            search_lines=self.usable(),
            meta={"subtitles": {}, "duration": 472},
            subs={},
        )
        with tempfile.TemporaryDirectory() as tmp:
            _, report, _ = self.run_channel(fake, out_dir=tmp)
            saved = Path(tmp) / youtube_mod.TRANSCRIPT_DIR_NAME / f"{VIDEO_ID}.txt"
            self.assertTrue(saved.exists())
            text = saved.read_text(encoding="utf-8")
        # the evidence we paid to produce is kept in full, not just excerpted
        self.assertIn("whisper heard this", text)
        self.assertIn(VIDEO_ID, report)
        self.assertIn(youtube_mod.TRANSCRIPT_DIR_NAME, report)

    def test_each_video_gets_its_own_captions(self):
        """Regression guard on the harness itself: caption files must land
        under the id yt-dlp was asked about, not one shared constant."""
        fake = FakeYtDlp(
            search_lines=[
                search_record("aaaaaaaaaaa", "context engineering one", 900),
                search_record("bbbbbbbbbbb", "context engineering two", 800),
            ],
            meta={"subtitles": {"en": [{}]}, "duration": 472, "language": "en"},
            subs={"en": json3(GOOD_TEXT.split(". "))},
        )
        count, report, _ = self.run_channel(fake)
        self.assertEqual(count, 2)
        self.assertEqual(report.count(youtube_mod.SOURCE_MANUAL), 2)


class RegistryTests(YouTubeCase):
    def test_youtube_is_a_free_default_connector(self):
        connector = deep_research.CONNECTORS["youtube"]
        self.assertEqual(connector.kind, "direct")
        self.assertTrue(connector.default)
        self.assertEqual(connector.requires, [])
        self.assertTrue(connector.available())

    def test_output_file_is_registered(self):
        self.assertEqual(deep_research.OUTPUT_NAMES["youtube"], "youtube.md")


if __name__ == "__main__":
    unittest.main()
