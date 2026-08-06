---
title: YouTube Channel + Transcription Routes + npm Org Release - Plan
type: feat
date: 2026-08-06
artifact_contract: ce-unified-plan/v1
artifact_readiness: shipped
product_contract_source: session (Nikita, 2026-08-06)
execution: code
---

# YouTube Channel + Transcription Routes + npm Org Release - Plan

**Target repo:** zbs-researcher (skill `deep-research`, paths repo-relative).
Scope: one release — 0.5.0.

---

## Goal Capsule

- **Objective.** Make YouTube a real source (not a Gemini paraphrase), give
  transcription three routes with the wizard able to see the machine, clear the
  release debts, and publish under the ZBS npm organization.
- **Product authority.** Nikita.
- **The take.** The transcript fallback is not a patch for bad captions. A web
  index reads a video's title and description and never the spoken content, so
  reading the words is already a coverage win — and when the captions are
  unusable and we transcribe the audio ourselves, that text provably exists in
  **no index at all**. This is the quality thesis (beat a web-index researcher
  on primary evidence), applied to video.
- **Empirical grounding (this session, live).**
  - `yt-dlp 2026.07.04` on the author's machine: `ytsearch` returns id, title,
    channel, views, duration; auto-captions download as `json3`. A plain stdlib
    request to `timedtext` does not work — the endpoint is PoToken-gated and
    returns an empty body.
  - `--dump-json` implies simulate mode and writes no files; `--no-simulate` is
    what actually lands the caption tracks.
  - Concatenating json3 events without a separator fuses words across caption
    lines ("familiarwith"). Events are lines; they must be joined with a space.
  - The metadata's `subtitles` map is the authoritative human-vs-machine
    signal; filenames alone cannot tell them apart.
  - YouTube intermittently refuses a format set it advertised moments earlier
    ("Requested format is not available") — observed once, then not
    reproducible. A single audio download attempt is therefore not enough.
  - OpenRouter shipped `/api/v1/audio/transcriptions` on 2026-07-22; a real
    call through it produced a correct transcript in this session.

---

## Product Contract

### Requirements

- **R1.** A `youtube` connector: discover by keyword or by explicit URL, read
  the best caption track, judge it, and transcribe the audio when the track
  cannot carry a quote.
- **R2.** Provenance is never guessed. Every video states whether its text came
  from human captions, machine captions, or our own transcription; a rejected
  track states the reason.
- **R3.** Transcription routes: local MLX, Groq, OpenRouter — resolved
  independently of the vision profile, because one OpenRouter key should be
  able to cover audio while vision stays on the profile.
- **R4.** An explicitly chosen route is honored even when its credential is
  missing. Silently billing a provider the user did not choose is worse than an
  error that names the fix.
- **R5.** The wizard can see the machine (OS, arch, RAM, chip, installed
  tooling) so it offers the free local route where it would actually run — and
  does not offer it where it would not.
- **R6.** Budgets are bounded and **disclosed**: whatever the read/transcribe
  caps dropped is stated in the report.
- **R7.** Release hygiene: one version number across plugin, marketplace,
  installer and changelog; ownership under the ZBS organization.

### Scope boundaries

**In scope:** R1–R7, plus the coverage-receipt downgrade for self-produced
evidence.

**Deferred:** adaptive per-video caption-language retry (today: a configurable
language list, then transcription); YouTube comments; per-entity YouTube
fan-out in `entity-fanout`; a Whisper route for non-Apple local hardware
(`faster-whisper`).

**Rejected:** a pure-stdlib `timedtext` path. It is PoToken-gated and would
silently return nothing — unacceptable for a tool whose pitch is auditable
primary evidence.

---

## Key Technical Decisions

- **KTD1 — yt-dlp is an optional dependency, not a hard one.** Binary on PATH
  first, then the `yt_dlp` package, then an honest `youtube.ERROR.md`. Same
  tier as Telethon and MLX. This bends "stdlib-only" knowingly; the
  alternative is a channel that does not work.
- **KTD2 — one yt-dlp call per video does double duty.** `--dump-json
  --no-simulate --write-subs --write-auto-subs` returns the metadata (which
  carries the human-vs-machine truth) and lands the tracks together.
- **KTD3 — routing lives beside the profile, never inside `ClientBackend`.**
  `get_backend()` keeps its exact contract; `get_transcriber()` is new. Putting
  a cascade inside `ClientBackend.transcribe` would have made the existing
  "missing Groq key raises" test pass or fail depending on whether the
  developer happened to have `OPENROUTER_API_KEY` exported.
- **KTD4 — budgets read the environment at call time.** Module-level constants
  would need `importlib.reload` to test, and a reload in test cleanup runs
  before the environment is restored, leaking settings into later tests.
- **KTD5 — `self_sourced` is a general provenance concept**, not a YouTube
  special case: it means the run produced the evidence. It outranks the static
  table, and an empty result can never claim it.
- **KTD6 — audio download retries once, more permissively.** A transient format
  refusal must not cost the evidence; only the retry pays for the broader
  match.

---

## Verification

- `python3 -m unittest discover -s tests -p 'test_*.py'` — 536 tests (from 455).
- `bash scripts/selftest.sh` — 10/10, 18 connectors, no paid APIs.
- Live: `--fire youtube` on a keyword query produced correct labels for human
  and machine captions with clean text; forcing an unavailable caption language
  drove the full fallback through a real OpenRouter transcription, and the
  coverage receipt read `no — produced by this run (own transcription)`.
- `npm publish --dry-run` — 3 files, 4.5 kB, no warnings.

---

## Definition of Done

Unit suite and selftest green; the live cascade proven end to end on both the
caption path and the transcription path; docs (SKILL, README, CONFIGURATION,
docs/README) describe 18 connectors and three transcription routes; versions
agree at 0.5.0; `installer/RELEASE.md` documents the org move. Publishing
itself is Nikita's action.
