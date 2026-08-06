# docs — example run & design notes

Supporting material for the ZBS Research plugin (the code lives at the repo
root under `skills/`).

## Contents

- **`examples/ai-memory-run/`** — a real deep-research run on "State of AI Memory, July 2026": every channel report + `manifest.json` + `synthesis.md` + `brief.html`. Shows what the plugin actually produces.

## Key design decisions

- **No Anthropic/OpenAI API spend by default** — Gemini/Grok/Perplexity + free direct connectors; synthesis in-session.
- **Plan-first** — every research run writes a plan before firing connectors.
- **Three transcription routes** — local MLX ($0, Apple silicon, nothing leaves the machine), Groq, or OpenRouter. Chosen independently of the vision profile (*self* local vs *client/portable* cloud-cheap), because one OpenRouter key should be able to cover audio while vision stays elsewhere. Media transcription/vision is a pluggable backend, not hardcoded local compute.
- **Reddit reality (2026)** — `.json` dead, OAuth self-service closed; Arctic Shift is the free default.
