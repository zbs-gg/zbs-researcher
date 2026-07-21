#!/usr/bin/env python3
"""Terminal UI for the deep-research runner: capability tiers, banner, live board.

``ansi_caps()`` decides one of three capability tiers for the stream the
runner writes to (stderr):

* ``unicode`` — SGR color + cursor-control animation + Braille spinner
  (non-Windows TTYs, and Windows Terminal detected via ``WT_SESSION``);
* ``ansi``    — SGR color + animation with the ASCII ``|/-\\`` spinner
  (legacy Windows console after guarded VT enablement succeeds);
* ``plain``   — no escape sequences at all (pipes, CI, NO_COLOR, TERM=dumb).

Precedence (pinned by tests): ``NO_COLOR``/``TERM=dumb`` > ``FORCE_COLOR``
> ``CI`` > ``isatty``. ``NO_COLOR`` counts only when present AND non-empty
(per no-color.org). ``FORCE_COLOR`` upgrades SGR color ONLY — animation
(cursor control) always additionally requires a real TTY on the stream.

Sanitization is a security boundary: every piece of interpolated text
(topic, channel error strings — third-party HTTP bytes reach ``str(e)``)
must pass through ``sanitize()``, which strips ALL escape sequences
(OSC/CSI/DCS/…) and control characters before the text can reach a frame.

Stdlib only; Windows-safe — the only platform-specific call is a guarded
``ctypes`` ``SetConsoleMode`` probe that can never crash the run.
"""
import os
import re
import sys
import time
from collections import namedtuple

__all__ = [
    "ASCII_FRAMES",
    "BRAILLE_FRAMES",
    "Caps",
    "LiveBoard",
    "PLAIN_TITLE",
    "SUBTITLE",
    "ansi_caps",
    "banner",
    "clip_visible",
    "sanitize",
    "spinner_frames",
    "term_size",
    "visible_len",
]

Caps = namedtuple("Caps", ("tier", "color", "animate"))

PLAIN_TITLE = "ZBS RESEARCHER — deep research"
SUBTITLE = "deep research · reactions from real humans"
ART_MIN_COLUMNS = 78

BRAILLE_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
ASCII_FRAMES = ("|", "/", "-", "\\")

_FPS = 10.0  # spinner phase is derived from the clock, so render() stays pure
_ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004

# Every escape sequence class, including unterminated tails (a truncated
# error string may cut a sequence in half — the remnant must not leak).
_ESC_RE = re.compile(
    "\x1b\\][^\x07\x1b]*(?:\x07|\x1b\\\\)?"  # OSC …BEL/ST (or unterminated)
    "|\x1b\\[[0-9;:<=>?]*[ -/]*[@-~]?"  # CSI (final byte optional if cut off)
    "|\x1b[PX^_][^\x1b]*(?:\x1b\\\\)?"  # DCS/SOS/PM/APC strings
    "|\x1b."  # any other two-byte escape
    "|\x1b"  # a lone trailing ESC
)

# C0 controls, DEL and C1 controls are dropped; whitespace controls become a
# plain space (newlines in third-party text must not fabricate frame rows).
_CTRL_MAP = {codepoint: None for codepoint in range(0x00, 0x20)}
_CTRL_MAP[0x7F] = None
_CTRL_MAP.update({codepoint: None for codepoint in range(0x80, 0xA0)})
for _ws in "\t\n\r":
    _CTRL_MAP[ord(_ws)] = " "
del _ws


def sanitize(text):
    """Strip ALL escape sequences and control characters from untrusted text.

    Security boundary: third-party bytes (HTTP error bodies via ``str(e)``,
    topics, key names) pass through here before they may enter a frame.
    """
    return _ESC_RE.sub("", str(text)).translate(_CTRL_MAP)


def visible_len(line):
    """Length of ``line`` as the terminal shows it (escape sequences = 0)."""
    return len(_ESC_RE.sub("", line))


def clip_visible(line, max_cols):
    """Truncate ``line`` to ``max_cols`` VISIBLE characters.

    Escape sequences are kept verbatim (zero width) so our own SGR
    open/reset pairs survive the cut and never bleed into the next row.
    """
    if max_cols <= 0:
        return ""
    if visible_len(line) <= max_cols:
        return line
    parts = []
    visible = 0
    pos = 0
    for match in _ESC_RE.finditer(line):
        chunk = line[pos : match.start()]
        room = max_cols - visible
        if room > 0:
            parts.append(chunk[:room])
            visible += min(len(chunk), room)
        parts.append(match.group(0))
        pos = match.end()
    chunk = line[pos:]
    room = max_cols - visible
    if room > 0:
        parts.append(chunk[:room])
    return "".join(parts)


def _positive_int(raw):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def term_size(stream):
    """(columns, lines) for the fd this UI writes to; re-read every frame.

    ``COLUMNS``/``LINES`` win when set to positive integers; otherwise the
    size comes from ``os.get_terminal_size(stream.fileno())`` — the STREAM's
    fd, never stdout's (shutil.get_terminal_size probes stdout, which is
    piped in half our runs). Unprobeable fd falls back to (80, 24).
    """
    env = os.environ
    cols = _positive_int(env.get("COLUMNS"))
    lines = _positive_int(env.get("LINES"))
    if cols is None or lines is None:
        try:
            probed = os.get_terminal_size(stream.fileno())
            probed_cols, probed_lines = probed.columns, probed.lines
        except (AttributeError, ValueError, OSError):
            probed_cols, probed_lines = 80, 24
        if cols is None:
            cols = probed_cols
        if lines is None:
            lines = probed_lines
    if cols <= 0:
        cols = 80
    if lines <= 0:
        lines = 24
    return cols, lines


def _isatty(stream):
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError, OSError):
        return False


def _enable_windows_vt(stream):
    """Best-effort VT enablement on legacy Windows consoles.

    Guarded end to end: any failure (no ctypes.windll, no console, refused
    SetConsoleMode) returns False and the caller degrades to the plain tier.
    This must never crash the run — Microsoft-documented
    ENABLE_VIRTUAL_TERMINAL_PROCESSING via GetConsoleMode | SetConsoleMode.
    """
    if os.name != "nt":
        return True
    try:
        import ctypes
        import msvcrt

        handle = msvcrt.get_osfhandle(stream.fileno())
        kernel32 = ctypes.windll.kernel32
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        new_mode = ctypes.c_uint32(mode.value | _ENABLE_VIRTUAL_TERMINAL_PROCESSING)
        return bool(kernel32.SetConsoleMode(handle, new_mode))
    except Exception:  # noqa: BLE001 — capability probing must never crash
        return False


def ansi_caps(stream=None, environ=None):
    """Decide the capability tier for ``stream`` (default: sys.stderr).

    Returns ``Caps(tier, color, animate)`` with tier in
    {"unicode", "ansi", "plain"}. See the module docstring for precedence.
    """
    stream = sys.stderr if stream is None else stream
    env = os.environ if environ is None else environ

    if env.get("NO_COLOR", "") or env.get("TERM", "") == "dumb":
        return Caps("plain", False, False)

    force_color = bool(env.get("FORCE_COLOR", ""))
    ci = bool(env.get("CI", ""))
    tty = _isatty(stream)

    vt_ok = tty and (
        os.name != "nt" or bool(env.get("WT_SESSION", "")) or _enable_windows_vt(stream)
    )
    animate = vt_ok and not ci
    color = animate or force_color
    if not color:
        return Caps("plain", False, False)

    unicode_ok = os.name != "nt" or bool(env.get("WT_SESSION", ""))
    return Caps("unicode" if unicode_ok else "ansi", color, animate)


def spinner_frames(caps):
    """Braille frames only in the full-unicode tier; ASCII otherwise."""
    return BRAILLE_FRAMES if caps.tier == "unicode" else ASCII_FRAMES


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
_ART_FONT = {
    "Z": ("████", "  █ ", " █  ", "█   ", "████"),
    "B": ("███ ", "█  █", "███ ", "█  █", "███ "),
    "S": (" ███", "█   ", " ██ ", "   █", "███ "),
    "R": ("███ ", "█  █", "███ ", "█ █ ", "█  █"),
    "E": ("████", "█   ", "███ ", "█   ", "████"),
    "A": (" ██ ", "█  █", "████", "█  █", "█  █"),
    "C": (" ███", "█   ", "█   ", "█   ", " ███"),
    "H": ("█  █", "█  █", "████", "█  █", "█  █"),
    " ": ("  ", "  ", "  ", "  ", "  "),
}


def _compose_art(text):
    return tuple(
        " ".join(_ART_FONT[char][row] for char in text).rstrip() for row in range(5)
    )


_ART_LINES = _compose_art("ZBS RESEARCHER")
_ART_WIDTH = max(len(line) for line in _ART_LINES)


def banner(caps, width=None):
    """The ZBS RESEARCHER banner as a string (no trailing newline).

    Block-letter art only when the real width allows it (>= 78 columns) AND
    the tier supports ANSI; otherwise the one-line plain title. Callers
    print this to stderr — stdout artifacts stay clean.
    """
    if width is None:
        width, _ = term_size(sys.stderr)
    if caps.tier == "plain" or width < ART_MIN_COLUMNS:
        return PLAIN_TITLE
    subtitle = SUBTITLE.center(_ART_WIDTH).rstrip()
    if not caps.color:
        return "\n".join(_ART_LINES + (subtitle,))
    lines = ["\x1b[1;36m%s\x1b[0m" % line for line in _ART_LINES]
    lines.append("\x1b[2m%s\x1b[0m" % subtitle)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Live progress board
# ---------------------------------------------------------------------------
def _fmt_seconds(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "%.1fs" % value
    return "?s"


class LiveBoard:
    """Live multi-line connector board over a manifest-style snapshot.

    ``render(state, skipped, now)`` is PURE frame composition (no I/O):
    ``state`` is the manifest ``channels`` mapping (entries appear at
    completion: ``{"status": "ok", "items_or_chars": n, "seconds": s}`` or
    ``{"status": "error", "error": msg}``), ``skipped`` maps name -> reason.
    A channel in neither mapping is running (elapsed = now - start_time; all
    connector threads start together). Rows keep the registry order given at
    construction — statuses update in place, rows never re-sort.

    ``write()``/``clear_and_write()`` do the I/O; ``stop()`` erases the live
    frame and prints no text — the caller prints the final per-channel
    summary exactly once. Cursor control is emitted only when
    ``caps.animate`` is True (never without a real TTY).
    """

    def __init__(self, channel_names, caps, start_time, stream=sys.stderr):
        self.channel_names = [str(name) for name in channel_names]
        self.caps = caps
        self.start_time = start_time
        self.stream = stream
        self._name_width = max(
            (len(sanitize(name)) for name in self.channel_names), default=0
        )
        self._live_lines = 0

    # -- pure frame composition --------------------------------------------
    def render(self, state, skipped, now):
        """Compose one frame as a list of clipped lines (pure; no I/O).

        Width and height are re-read from the stream's fd every frame; each
        line is clipped to columns-1 by VISIBLE length and the frame never
        exceeds lines-1 rows (finished/skipped collapse into one aggregate
        row on overflow).
        """
        cols, term_lines = term_size(self.stream)
        width = max(1, cols - 1)
        budget = max(1, term_lines - 1)
        frames = spinner_frames(self.caps)
        spin = frames[int(now * _FPS) % len(frames)]

        rows = []
        for name in self.channel_names:
            if name in skipped:
                rows.append((True, self._skip_row(name, skipped.get(name))))
            elif name in state:
                rows.append((True, self._done_row(name, state.get(name))))
            else:
                rows.append((False, self._running_row(name, spin, now)))

        if len(rows) <= budget:
            lines = [line for _, line in rows]
        else:
            running = [line for finished, line in rows if not finished]
            done_count = len(rows) - len(running)
            hidden = 0
            if len(running) + 1 > budget:
                hidden = len(running) - (budget - 1)
                running = running[: budget - 1]
            lines = running + [self._aggregate_row(done_count, hidden)]
        return [clip_visible(line, width) for line in lines]

    def _paint(self, code, text):
        if not self.caps.color:
            return text
        return "\x1b[%sm%s\x1b[0m" % (code, text)

    def _marks(self):
        if self.caps.tier == "unicode":
            return ("✔", "✖", "•")
        return ("+", "x", "-")

    def _label(self, name):
        return sanitize(name).ljust(self._name_width)

    def _running_row(self, name, spin, now):
        elapsed = max(0.0, now - self.start_time)
        return "%s %s  running %.1fs" % (
            self._paint("36", spin),
            self._label(name),
            elapsed,
        )

    def _done_row(self, name, record):
        record = record if isinstance(record, dict) else {}
        ok_mark, error_mark, _ = self._marks()
        if record.get("status") == "ok":
            detail = "OK %s (%s)" % (
                _fmt_seconds(record.get("seconds")),
                sanitize(record.get("items_or_chars")),
            )
            return "%s %s  %s" % (
                self._paint("32", ok_mark),
                self._label(name),
                self._paint("32", detail),
            )
        detail = ("ERROR %s" % sanitize(record.get("error", ""))).rstrip()
        return "%s %s  %s" % (
            self._paint("31", error_mark),
            self._label(name),
            self._paint("31", detail),
        )

    def _skip_row(self, name, reason):
        skip_mark = self._marks()[2]
        detail = ("SKIP %s" % sanitize("" if reason is None else reason)).rstrip()
        return "%s %s  %s" % (
            self._paint("2", skip_mark),
            self._label(name),
            self._paint("2", detail),
        )

    def _aggregate_row(self, done_count, hidden):
        parts = []
        if done_count:
            parts.append("+%d done/skipped" % done_count)
        if hidden:
            parts.append("+%d running" % hidden)
        return self._paint("2", "  " + ", ".join(parts))

    # -- I/O ----------------------------------------------------------------
    def write(self, state, skipped, now=None):
        """Render and append one frame to the stream."""
        now = time.time() if now is None else now
        lines = self.render(state, skipped, now)
        if not lines:
            return
        self.stream.write("\n".join(lines) + "\n")
        self.stream.flush()
        self._live_lines = len(lines)

    def clear_and_write(self, state, skipped, now=None):
        """Erase the previous frame in place, then write the next one."""
        self._erase()
        self.write(state, skipped, now)

    def stop(self):
        """Erase the live frame and go quiet.

        Prints no text — the caller prints the final per-channel summary.
        """
        self._erase()

    def _erase(self):
        if self._live_lines and self.caps.animate:
            self.stream.write("\x1b[%dF\x1b[0J" % self._live_lines)
            self.stream.flush()
        self._live_lines = 0
