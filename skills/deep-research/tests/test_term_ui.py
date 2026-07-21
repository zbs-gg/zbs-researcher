import contextlib
import io
import os
import re
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
TERM_UI = SCRIPTS / "term_ui.py"

scripts_path = str(SCRIPTS)
path_added = scripts_path not in sys.path
if path_added:
    sys.path.insert(0, scripts_path)
try:
    import term_ui
finally:
    if path_added:
        sys.path.remove(scripts_path)


# Every env var the capability detector or size probe may read. Tests clear
# all of them so the host terminal's real state can never leak into (or
# accidentally satisfy) an assertion.
UI_ENV_VARS = ("NO_COLOR", "FORCE_COLOR", "CI", "TERM", "WT_SESSION", "COLUMNS", "LINES")

_SGR_RE = re.compile(r"\x1b\[[0-9;]*m")
_CSI_FINAL_RE = re.compile(r"\x1b\[[0-9;]*([A-Za-z])")


@contextlib.contextmanager
def ui_environment(**overrides):
    with mock.patch.dict(os.environ):
        for name in UI_ENV_VARS:
            os.environ.pop(name, None)
        os.environ.update(overrides)
        yield


class FakeStream(io.StringIO):
    """A stderr stand-in with a controllable isatty() and fileno()."""

    def __init__(self, tty=True, fd=77):
        super().__init__()
        self._tty = tty
        self._fd = fd

    def isatty(self):
        return self._tty

    def fileno(self):
        return self._fd


def fd_terminal_size(sizes_by_fd):
    """os.get_terminal_size replacement serving per-fd sizes and failing
    LOUDLY (AssertionError, deliberately outside the caught exceptions) on
    any other fd — the wrong-fd regression guard."""

    def _get(fd):
        if fd not in sizes_by_fd:
            raise AssertionError("terminal size probed on unexpected fd %r" % fd)
        return os.terminal_size(sizes_by_fd[fd])

    return _get


def strip_sgr(text):
    return _SGR_RE.sub("", text)


def ok_record(items=3, seconds=1.2):
    return {"status": "ok", "items_or_chars": items, "seconds": seconds}


def fake_windows_console(set_console_mode_result):
    """(ctypes, msvcrt) stand-ins for the guarded Windows VT-enable path."""

    class FakeUint:
        def __init__(self, value=0):
            self.value = value

    kernel32 = types.SimpleNamespace(
        GetConsoleMode=lambda handle, ref: 1,
        SetConsoleMode=lambda handle, mode: set_console_mode_result,
    )
    fake_ctypes = types.SimpleNamespace(
        windll=types.SimpleNamespace(kernel32=kernel32),
        c_uint32=FakeUint,
        byref=lambda obj: obj,
    )
    fake_msvcrt = types.SimpleNamespace(get_osfhandle=lambda fd: 1000 + fd)
    return fake_ctypes, fake_msvcrt


class AnsiCapsTests(unittest.TestCase):
    def caps(self, tty, **env):
        with ui_environment(**env):
            return term_ui.ansi_caps(stream=FakeStream(tty=tty))

    def test_non_tty_is_plain(self):
        caps = self.caps(tty=False)
        self.assertEqual(caps, term_ui.Caps("plain", False, False))

    @unittest.skipIf(os.name == "nt", "posix default-tier expectation")
    def test_tty_defaults_to_animated_unicode_tier(self):
        caps = self.caps(tty=True)
        self.assertEqual(caps.tier, "unicode")
        self.assertTrue(caps.color)
        self.assertTrue(caps.animate)

    def test_tty_with_no_color_is_plain_and_banner_has_no_sgr(self):
        caps = self.caps(tty=True, NO_COLOR="1")
        self.assertEqual(caps, term_ui.Caps("plain", False, False))
        self.assertNotIn("\x1b", term_ui.banner(caps, width=120))

    @unittest.skipIf(os.name == "nt", "posix default-tier expectation")
    def test_empty_no_color_is_treated_as_absent(self):
        # no-color.org: NO_COLOR counts only when present AND non-empty.
        caps = self.caps(tty=True, NO_COLOR="")
        self.assertTrue(caps.color)
        self.assertTrue(caps.animate)

    def test_ci_forces_plain_even_on_a_tty(self):
        caps = self.caps(tty=True, CI="1")
        self.assertEqual(caps, term_ui.Caps("plain", False, False))

    def test_term_dumb_forces_plain_even_on_a_tty(self):
        caps = self.caps(tty=True, TERM="dumb")
        self.assertEqual(caps, term_ui.Caps("plain", False, False))

    def test_force_color_without_tty_gives_color_but_never_animation(self):
        caps = self.caps(tty=False, FORCE_COLOR="1")
        self.assertTrue(caps.color)
        self.assertFalse(caps.animate)

    def test_force_color_with_ci_gives_color_but_never_animation(self):
        caps = self.caps(tty=True, FORCE_COLOR="1", CI="1")
        self.assertTrue(caps.color)
        self.assertFalse(caps.animate)

    def test_no_color_beats_force_color(self):
        caps = self.caps(tty=True, NO_COLOR="1", FORCE_COLOR="1")
        self.assertEqual(caps, term_ui.Caps("plain", False, False))

    def test_term_dumb_beats_force_color(self):
        caps = self.caps(tty=True, TERM="dumb", FORCE_COLOR="1")
        self.assertEqual(caps, term_ui.Caps("plain", False, False))

    def test_isatty_that_raises_counts_as_not_a_tty(self):
        stream = FakeStream(tty=False)
        stream.isatty = mock.Mock(side_effect=ValueError("closed"))
        with ui_environment():
            caps = term_ui.ansi_caps(stream=stream)
        self.assertEqual(caps.tier, "plain")


class WindowsBranchTests(unittest.TestCase):
    def nt_caps(self, set_console_mode_result, **env):
        fake_ctypes, fake_msvcrt = fake_windows_console(set_console_mode_result)
        with ui_environment(**env):
            with mock.patch.dict(sys.modules, {"ctypes": fake_ctypes, "msvcrt": fake_msvcrt}):
                with mock.patch.object(os, "name", "nt"):
                    return term_ui.ansi_caps(stream=FakeStream(tty=True))

    def test_set_console_mode_failure_degrades_to_plain_without_crash(self):
        caps = self.nt_caps(set_console_mode_result=0)
        self.assertEqual(caps, term_ui.Caps("plain", False, False))

    def test_set_console_mode_success_gives_ansi_tier_ascii_spinner(self):
        caps = self.nt_caps(set_console_mode_result=1)
        self.assertEqual(caps.tier, "ansi")
        self.assertTrue(caps.color)
        self.assertTrue(caps.animate)
        self.assertEqual(term_ui.spinner_frames(caps), term_ui.ASCII_FRAMES)

    def test_wt_session_gives_unicode_tier_even_when_vt_enable_fails(self):
        # Windows Terminal defaults VT on; WT_SESSION is the confidence signal.
        caps = self.nt_caps(set_console_mode_result=0, WT_SESSION="guid-1234")
        self.assertEqual(caps.tier, "unicode")
        self.assertTrue(caps.animate)

    def test_nt_branch_never_crashes_without_windows_modules(self):
        # On this (non-Windows) host ctypes has no windll: the guarded probe
        # must swallow that and degrade to plain, never raise.
        with ui_environment():
            with mock.patch.object(os, "name", "nt"):
                caps = term_ui.ansi_caps(stream=FakeStream(tty=True))
        self.assertEqual(caps, term_ui.Caps("plain", False, False))


class TermSizeTests(unittest.TestCase):
    def test_columns_and_lines_env_win_without_probing_any_fd(self):
        probe = mock.Mock(side_effect=AssertionError("must not probe an fd"))
        stream = FakeStream(fd=77)
        with ui_environment(COLUMNS="120", LINES="33"):
            with mock.patch.object(os, "get_terminal_size", probe):
                self.assertEqual(term_ui.term_size(stream), (120, 33))

    def test_size_follows_the_stderr_fd_not_stdout(self):
        # Wrong-fd regression: stdout is piped in half our runs — the size
        # must come from the fd of the stream the board writes to.
        stream = FakeStream(tty=True, fd=77)
        with ui_environment():
            with mock.patch.object(
                os, "get_terminal_size", fd_terminal_size({77: (120, 40)})
            ):
                self.assertEqual(term_ui.term_size(stream), (120, 40))

    def test_unprobeable_fd_falls_back_to_80x24(self):
        stream = FakeStream(fd=77)
        with ui_environment():
            with mock.patch.object(
                os, "get_terminal_size", mock.Mock(side_effect=OSError("not a tty"))
            ):
                self.assertEqual(term_ui.term_size(stream), (80, 24))

    def test_garbage_columns_env_falls_back_to_fd_probe(self):
        stream = FakeStream(fd=77)
        with ui_environment(COLUMNS="abc", LINES="-5"):
            with mock.patch.object(
                os, "get_terminal_size", fd_terminal_size({77: (66, 22)})
            ):
                self.assertEqual(term_ui.term_size(stream), (66, 22))


class SanitizeTests(unittest.TestCase):
    def test_strips_osc_csi_and_control_chars(self):
        self.assertEqual(
            term_ui.sanitize("a\x1b]0;evil\x07b\x1b[31mc\nd\te\x03f"),
            "abc d ef",
        )

    def test_strips_unterminated_sequences_and_lone_escape(self):
        self.assertEqual(term_ui.sanitize("x\x1b]0;evil"), "x")
        self.assertEqual(term_ui.sanitize("y\x1b[12"), "y")
        self.assertEqual(term_ui.sanitize("z\x1b"), "z")

    def test_render_strips_all_control_sequences_from_error_text(self):
        evil = "boom \x1b]0;evil\x07 \x1b[2A\x1b[9D mid \x9b31m end\x03"
        caps = term_ui.Caps("unicode", False, True)
        board = term_ui.LiveBoard(["chan"], caps, start_time=0.0, stream=FakeStream())
        with ui_environment(COLUMNS="200", LINES="24"):
            frame = board.render({"chan": {"status": "error", "error": evil}}, {}, now=1.0)
        joined = "\n".join(frame)
        self.assertNotIn("\x1b", joined)  # color off: NO escapes may survive
        self.assertNotIn("\x07", joined)
        self.assertNotIn("\x9b", joined)
        self.assertNotIn("evil", joined)  # whole OSC payload goes, not just ESC
        self.assertIn("boom", joined)
        self.assertIn("end", joined)


class LiveBoardRenderTests(unittest.TestCase):
    def board(self, names, caps=None, start_time=0.0, stream=None):
        caps = caps if caps is not None else term_ui.Caps("unicode", False, True)
        stream = stream if stream is not None else FakeStream()
        return term_ui.LiveBoard(names, caps, start_time=start_time, stream=stream)

    def test_running_ok_error_and_skip_rows(self):
        board = self.board(["alpha", "beta", "gamma", "delta"], start_time=10.0)
        state = {
            "beta": ok_record(items=24, seconds=3.4),
            "gamma": {"status": "error", "error": "HTTP 500"},
        }
        skipped = {"delta": "missing keys: ['telegram']"}
        with ui_environment(COLUMNS="120", LINES="24"):
            frame = board.render(state, skipped, now=12.5)
        self.assertEqual(len(frame), 4)
        self.assertIn("running", frame[0])
        self.assertIn("2.5s", frame[0])  # elapsed = now - start_time
        self.assertIn("OK 3.4s (24)", frame[1])
        self.assertIn("ERROR HTTP 500", frame[2])
        self.assertIn("SKIP missing keys: ['telegram']", frame[3])

    def test_row_order_follows_registry_order_across_frames(self):
        names = ["gamma", "alpha", "mu"]
        board = self.board(names)
        with ui_environment(COLUMNS="120", LINES="24"):
            first = board.render({}, {}, now=1.0)
            second = board.render(
                {"mu": ok_record(), "gamma": {"status": "error", "error": "boom"}},
                {},
                now=2.0,
            )

        def order(frame):
            return [next(n for n in names if n in line) for line in frame]

        self.assertEqual(order(first), names)
        self.assertEqual(order(second), names)

    def test_height_overflow_collapses_finished_into_aggregate(self):
        names = ["ch%02d" % i for i in range(17)]
        board = self.board(names)
        state = {"ch%02d" % i: ok_record() for i in range(9)}
        skipped = {"ch16": "missing keys: ['x']"}
        with ui_environment(COLUMNS="80", LINES="10"):
            frame = board.render(state, skipped, now=1.0)
        self.assertLessEqual(len(frame), 9)  # lines - 1
        joined = "\n".join(frame)
        self.assertIn("+10 done/skipped", joined)
        for name in ("ch09", "ch10", "ch11", "ch12", "ch13", "ch14", "ch15"):
            self.assertIn(name, joined)  # in-flight rows stay individual
        for name in ("ch00", "ch08", "ch16"):
            self.assertNotIn(name, joined)  # finished/skipped are aggregated

    def test_height_overflow_with_everything_running_still_fits(self):
        names = ["ch%02d" % i for i in range(17)]
        board = self.board(names)
        with ui_environment(COLUMNS="80", LINES="10"):
            frame = board.render({}, {}, now=1.0)
        self.assertLessEqual(len(frame), 9)

    def test_width_clamps_to_columns_minus_one_by_visible_length(self):
        caps = term_ui.Caps("unicode", True, True)  # color ON: SGR in the row
        board = self.board(["chan"], caps=caps)
        long_error = "x" * 200
        with ui_environment(COLUMNS="60", LINES="24"):
            frame = board.render(
                {"chan": {"status": "error", "error": long_error}}, {}, now=1.0
            )
        line = frame[0]
        self.assertIn("\x1b[", line)  # SGR survives the clip
        self.assertLessEqual(len(strip_sgr(line)), 59)
        self.assertGreater(len(line), len(strip_sgr(line)))

    def test_resize_between_frames_uses_the_new_size(self):
        stream = FakeStream(fd=77)
        board = self.board(["chan"], stream=stream)
        state = {"chan": {"status": "error", "error": "y" * 150}}
        sizes = iter([(100, 40), (30, 40)])
        with ui_environment():
            with mock.patch.object(
                os, "get_terminal_size", lambda fd: os.terminal_size(next(sizes))
            ):
                wide = board.render(state, {}, now=1.0)
                narrow = board.render(state, {}, now=1.1)
        self.assertGreater(len(strip_sgr(wide[0])), 29)
        self.assertLessEqual(len(strip_sgr(wide[0])), 99)
        self.assertLessEqual(len(strip_sgr(narrow[0])), 29)


class LiveBoardIoTests(unittest.TestCase):
    def test_clear_and_write_erases_exactly_the_previous_frame(self):
        stream = FakeStream(tty=True)
        caps = term_ui.Caps("unicode", True, True)
        board = term_ui.LiveBoard(["a", "b", "c"], caps, start_time=0.0, stream=stream)
        with ui_environment(COLUMNS="80", LINES="24"):
            board.write({}, {}, now=1.0)
            first = stream.getvalue()
            board.clear_and_write({"a": ok_record()}, {}, now=2.0)
        self.assertEqual(first.count("\n"), 3)
        second = stream.getvalue()[len(first):]
        self.assertTrue(second.startswith("\x1b[3F\x1b[0J"), repr(second[:12]))

    def test_stop_emits_no_visible_text(self):
        stream = FakeStream(tty=True)
        caps = term_ui.Caps("unicode", True, True)
        board = term_ui.LiveBoard(["a"], caps, start_time=0.0, stream=stream)
        with ui_environment(COLUMNS="80", LINES="24"):
            board.write({}, {}, now=1.0)
            before = stream.getvalue()
            board.stop()
        tail = stream.getvalue()[len(before):]
        self.assertEqual(term_ui.sanitize(tail).strip(), "")

    def test_no_animate_caps_never_emit_cursor_control(self):
        # FORCE_COLOR without a TTY: SGR is allowed, cursor control never is.
        stream = FakeStream(tty=False)
        caps = term_ui.Caps("unicode", True, False)
        board = term_ui.LiveBoard(["a", "b"], caps, start_time=0.0, stream=stream)
        with ui_environment(COLUMNS="80", LINES="24"):
            board.write({}, {}, now=1.0)
            board.clear_and_write({"a": ok_record()}, {}, now=2.0)
            board.stop()
        out = stream.getvalue()
        self.assertIn("\x1b[", out)  # color is there…
        for match in _CSI_FINAL_RE.finditer(out):
            self.assertEqual(match.group(1), "m", "cursor control leaked: %r" % out)


class SpinnerTests(unittest.TestCase):
    def test_braille_frames_only_in_unicode_tier(self):
        unicode_frames = term_ui.spinner_frames(term_ui.Caps("unicode", True, True))
        self.assertEqual(unicode_frames, term_ui.BRAILLE_FRAMES)
        self.assertIn("⠋", unicode_frames)

    def test_ascii_frames_in_ansi_and_plain_tiers(self):
        for tier in ("ansi", "plain"):
            frames = term_ui.spinner_frames(term_ui.Caps(tier, False, False))
            self.assertEqual(frames, ("|", "/", "-", "\\"))

    def test_spinner_phase_advances_with_time(self):
        caps = term_ui.Caps("unicode", False, True)
        board = term_ui.LiveBoard(["a"], caps, start_time=0.0, stream=FakeStream())
        with ui_environment(COLUMNS="80", LINES="24"):
            f1 = board.render({}, {}, now=0.0)
            f2 = board.render({}, {}, now=0.1)
        self.assertNotEqual(f1[0][0], f2[0][0])


class BannerTests(unittest.TestCase):
    def test_narrow_terminal_gets_one_line_plain_title(self):
        caps = term_ui.Caps("unicode", True, True)
        out = term_ui.banner(caps, width=70)
        self.assertEqual(out, term_ui.PLAIN_TITLE)
        self.assertNotIn("\n", out)
        self.assertNotIn("\x1b", out)

    def test_plain_tier_gets_one_line_title_even_when_wide(self):
        caps = term_ui.Caps("plain", False, False)
        self.assertEqual(term_ui.banner(caps, width=200), term_ui.PLAIN_TITLE)

    def test_wide_capable_terminal_gets_block_art_within_78_cols(self):
        caps = term_ui.Caps("unicode", True, True)
        out = term_ui.banner(caps, width=120)
        lines = out.split("\n")
        self.assertGreater(len(lines), 3)
        for line in lines:
            self.assertLessEqual(len(strip_sgr(line)), 78)
        self.assertIn("█", out)
        self.assertIn("reactions from real humans", out)
        self.assertIn("deep research", out)

    def test_banner_colored_only_when_caps_color(self):
        colored = term_ui.banner(term_ui.Caps("unicode", True, True), width=120)
        colorless = term_ui.banner(term_ui.Caps("unicode", False, True), width=120)
        self.assertIn("\x1b[", colored)
        self.assertNotIn("\x1b", colorless)
        self.assertEqual(strip_sgr(colored), colorless)

    def test_plain_title_names_the_persona(self):
        self.assertEqual(term_ui.PLAIN_TITLE, "ZBS RESEARCHER — deep research")


class SourceHygieneTests(unittest.TestCase):
    def test_term_ui_source_avoids_posix_only_calls(self):
        source = TERM_UI.read_text(encoding="utf-8")
        for token in (
            "SIGALRM",
            "killpg",
            "fcntl",
            "os.fork",
            "setsid",
            "termios",
            "import pty",
            "openpty",
            "pwd.",
            "grp.",
        ):
            self.assertNotIn(token, source)

    def test_term_ui_is_stdlib_only(self):
        source = TERM_UI.read_text(encoding="utf-8")
        for token in ("colorama", "rich", "curses"):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
