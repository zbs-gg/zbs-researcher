# docs — research, design & session record

Supporting material for the ZBS Research plugin (the code lives at the repo
root under `skills/`). This folder is the paper trail: how the design was
reached, an example run, and the working chat.

## Contents

- **`ideation/`** — the multi-platform research-plugin ideation.
  - [`2026-07-15-multiplatform-research-plugin-ideation.html`](ideation/2026-07-15-multiplatform-research-plugin-ideation.html) — 7 ranked ideas (48 raw → verified), open in a browser.
  - `2026-07-17-multi-platform-research-plugin-ideation.html` — a parallel Codex-authored pass.
  - **`_workings/`** — the raw ideation trail: `grounding.md` (consolidated research digests + constraints + axes), `raw-candidates.md` (16 merged candidates), `survivors.md` (arbitration notes).
- **`plans/`** — plan-first design docs (deep-research rewrite, plugin packaging, project-local output).
- **`examples/ai-memory-run/`** — a real deep-research run on "State of AI Memory, July 2026": every channel report + `manifest.json` + `synthesis.md` + `brief.html`. Shows what the plugin actually produces.
- **`chat/`** — `session-2026-07-transcript.md`, the working Nikita ↔ Эли dialogue that produced all of the above (tool calls collapsed to one line each).

## Key design decisions captured here

- **No Anthropic/OpenAI API spend by default** — Gemini/Grok/Perplexity + free direct connectors; synthesis in-session.
- **Plan-first** — every research run writes a plan before firing connectors.
- **Two deployment profiles** — *self* (local, $0, Mac-bound) vs *client/portable* (cloud-cheap, installs anywhere). Media transcription/vision is a pluggable backend, not hardcoded local compute.
- **Reddit reality (2026)** — `.json` dead, OAuth self-service closed; Arctic Shift is the free default.
