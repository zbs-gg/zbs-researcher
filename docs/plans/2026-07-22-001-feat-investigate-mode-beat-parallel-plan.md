---
title: Investigate Mode — Beat Parallel on Native Social Depth - Plan
type: feat
date: 2026-07-22
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
deepened: 2026-07-23
---

# Investigate Mode — Beat Parallel on Native Social Depth - Plan

**Target repo:** zbs-researcher (skill `deep-research`, paths repo-relative). Scope: Deep — product.

---

## Goal Capsule

- **Objective.** Add a new `investigate` research mode to The Beast Researcher — agentic, question-driven deep research — and position it to **beat Parallel AI on QUALITY**, specifically on **native, full-breadth social/community depth**. Parallel exists but does not actually analyze social: a live head-to-head (2026-07-22, Parallel Pro run) showed it reaches X only through `site:twitter.com` web-index scraps, and its synthesized citations need re-verification. The Beast reads the whole social/community surface **from inside**, natively.
- **Product authority.** Nikita.
- **The take (explicit).** Compete on **quality only** — native primary-social depth + auditable receipts. "We're free / zero-key" is **not** the pitch (the tool stays free-capable, but that is explicitly rejected as the competitive take).
- **Empirical grounding (this session).** Live comparison run:
  - Parallel Pro composed adaptive sub-queries (`site:twitter.com agent memory evaluation cost` → `Letta API memory bug issue` → `Letta slow agent memory reddit`), read 28 / considered 1356 sources, produced a strong problems-first report — but social came from web-index `site:` operators, not native X; several citations looked shaky. Cost was material to Nik.
  - ZBS `single` mode with a long natural-language query returned **empty across every direct channel** — direct connectors are keyword engines. A **short, target-scoped** query (repo-scoped like `mem0ai/mem0`) surfaced the exact real issue (`#2800`) Parallel also found — cross-validated. Lesson: **the compose-step is do-or-die.**
- **Open blockers.** None product-level. Loop-location, bounds, coverage-receipt provenance, and eval-baseline choice are planning questions (Open Questions below).

---

## Product Contract

### Primary actor & core outcome

- **Primary actor.** A researcher (Nik / his client) asking a landscape question ("State of X in 2026 — where are the problems?") who wants **real human reactions and problems from inside the platforms**, with clickable primary evidence — not a synthesized web-index summary they must double-check.
- **Core outcome.** Run one research question and get back a **problems-first landscape report** built by an agentic loop that (a) composes short, target-scoped queries per source, (b) drills adaptively into the leads/problems that surface, (c) reaches the **full breadth of native social/community sources** the platforms actually hold, and (d) marks on the page what a web-index researcher (Parallel/Perplexity) structurally cannot reach.

### Requirements

**The research shape (investigate mode)**

- R1. **New `investigate` mode** — agentic, question-driven. Takes a research question; composes per-source queries; runs an autonomous multi-round loop (compose → fire → read → follow leads → repeat, bounded); synthesizes a problems-first landscape report. Runs **alongside** the existing `single` (broad-scan) and `entity-fanout` (matrix) modes — both kept, neither replaced.
- R2. **Compose-step is mandatory and per-source.** The mode decomposes the question into **short, target-scoped** queries tailored to each source (repo-scoped GitHub-issues, subreddit/entity Reddit, live-X operators, TG channels, YouTube). A blanket natural-language query is forbidden as the primary path — it returns nothing on keyword-based connectors (proven live). This is the core of the quality win.
- R3. **Adaptive drill-down.** The loop follows leads and problems as they surface — a pain point spotted on X triggers a targeted GitHub-issues query on that repo; a named system triggers a repo/subreddit dive — bounded by explicit round and budget caps.
- R4. **Deliverable = problems-first landscape report** ("State of X: the landscape + where the problems are"), foregrounding real quotes, author handles, and **clickable links to live primary threads**. Synthesis runs in the Claude session (subscription tokens), not a paid black-box.

**The quality moat (beat Parallel)**

- R5. **Native full-breadth inside-access.** The loop reaches the whole social/community surface **natively** — X (Grok live search), Telegram (client-session; communities with no web trace), Reddit (full archive via arctic-shift, not top-of-Google), Threads, IG/TikTok, Bluesky — plus GitHub/HN. This breadth of **primary** social/community evidence, read from inside rather than through `site:` web-index scraps, is the quality differentiator.
- R6. **Coverage-receipts on every report.** Each report explicitly marks what a web-index researcher cannot reach — e.g. "from a Telegram community with no web footprint", "X post 3h ago, not yet indexed", "Reddit archive over 12 months, not top results". The native-depth delta is legible on **every** run, not just in a benchmark.
- R7. **Auditability.** Every load-bearing claim traces to a real quote + handle + clickable link to the live primary thread. Primary evidence over synthesized prose whose citations must be re-verified (the observed Parallel weakness).
- R8. **Positioning is QUALITY, not price.** The pitch is native social/community depth + auditable receipts. The tool remains free-capable technically, but "free / cheaper" is **not** the competitive take and must not lead the positioning.

**The compound loop**

- R9. **Autonomous-to-report, then human feedback → compound.** The run is autonomous to the report; at the end, human feedback is captured and used to improve the **next** run's query composition, source selection, and report shape.
- R10. **Two-tier feedback.** Baseline (free, works now): persist the composed queries + the human feedback to a **local ledger** (the existing `signals.py` local-JSONL pattern) that the next run reads and adapts from. Opt-in: a **soft Cartographer integration** (the neighboring product) that accumulates the person/topic profile to improve composition over time — surfaced as an **honest soft-plug** ("connect Cartographer to compound this"), never overclaimed. Without Cartographer the baseline is an honest save, not ML learning.

**Proving the win**

- R11. **Eval harness (head-to-head).** A repeatable comparison — the same question through Beast vs a web-index baseline — scoring **primary-source depth, freshness, and social-coverage** on the user's own data ("свой эвал, не чужие бенчмарки"). Feeds the compound loop; the manual Beast-vs-Parallel run this session is the prototype.

### Scope boundaries

**In scope**
- `investigate` mode: agentic loop + mandatory compose-step + adaptive drill-down + problems-first report (R1–R4)
- Native full-breadth inside-access + coverage-receipts + auditability + quality-first positioning (R5–R8)
- Compound feedback loop: local-ledger baseline + Cartographer soft-plug (R9–R10)
- Head-to-head eval harness on own data (R11)

**Deferred for later**
- Full Cartographer integration internals — v1 ships only the soft-plug hook + honest local baseline.
- Real ML/profile learning without Cartographer — baseline is an honest save + read, not learning.
- A polished, automated recurring eval dashboard — v1's eval harness can be a scriptable head-to-head, not a productized UI.

**Outside this product's identity**
- "We're free / cheaper than Parallel" as the competitive pitch — explicitly rejected; quality only.
- Replacing `single` or `entity-fanout` modes — both kept alongside `investigate`.
- Becoming a hosted paid black-box research API — Beast is "your Claude session as the brain + native connectors + auditable primary evidence", not a Parallel clone.

### Open Questions (resolve in ce-plan)

- **Where the agentic loop lives** — SKILL.md session orchestration (the session is the "researcher brain", the Python runner is the per-source query tool) vs a Python-driven loop. Leaning session-orchestrated; ce-plan decides the split and what runner affordance the session needs (e.g. "fire one composed query on a named source, return results for the session to read").
- **Loop bounds** — round cap + budget cap; reuse `entity-fanout`'s honest cost/budget + degraded-flag machinery.
- **Coverage-receipt provenance** — per-result metadata (which connector, freshness timestamp, a "web-index-reachable?" heuristic) needed to render R6 truthfully without overclaiming.
- **Eval-harness baseline** — what stands in for "web-index researcher": a Serper/Brave `site:` pass, Perplexity, or Parallel via API? And the scoring rubric for depth/freshness/social-coverage.
- **Compose-step mechanism** — session-authored per-source queries (prompted by SKILL.md) vs a runner helper that proposes them; how it reuses `entity-fanout`'s enumeration + repo-scoping for the "target-scoped" part.
- **Telegram in the loop** — TG is the sharpest un-indexable moat but is opt-in + warning-gated (separate account). How prominently the loop leans on it vs the always-free connectors.

> **Enrichment note (ce-plan, 2026-07-23).** Product Contract unchanged (R1–R11 preserved verbatim). The six Open Questions above are resolved into the Planning Contract below (confirmed with Nik this session): loop lives in the SKILL.md session; runner gains a single `--fire`/compose affordance; bounds + honesty reuse `entity-fanout`; coverage-receipts = per-result provenance; feedback = local ledger + Cartographer soft-plug; eval = free web-index `site:` baseline. They stay listed above as the trace of what planning decided.

---

## Planning Contract

**The loop is a SKILL.md playbook, not a Python loop (KTD0).** The Claude session is the "researcher brain": it composes per-source queries, reads results, spots leads, drills adaptively, and synthesizes. Python stays a set of stateless per-source query tools. This matches how the skill already works (the session authors `research-plan.md` + `synthesis.md`); investigate mode makes that iterative and composition-first.

Key Technical Decisions:

- KTD1. **Single-query "fire" affordance.** The session needs to fire ONE composed query on ONE named source and read the result. This mostly exists (`deep-research.py "Q" --only <src> --q <src>:"composed" --output-dir D`). Formalize it as an ergonomic `--fire <source>` mode (thin wrapper over the existing single-channel path + `--q`) that returns the result file path + a provenance record on stdout as JSON, so the session can chain calls in the loop without re-parsing manifests. Reuses the existing `channel_*` registry and `entity-fanout`'s repo/entity-scoping helpers for the "target-scoped" part of R2.
- KTD2. **Coverage-provenance per result (R6/R7).** Each fired result carries a provenance record: `{source, query, items, fetched_at, freshness (newest item age), web_index_reachable: yes|partial|no, reach_reason}`. `web_index_reachable` is a per-connector static classification (telegram=no, grok-live-X=partial/fresh, arctic-shift-reddit-archive=partial, github/hn/bluesky=yes) plus a freshness override (an item newer than ~48h on X/Telegram is flagged pre-index). This record is what makes the coverage-receipts (R6) truthful rather than a slogan. Lives in a new `provenance.py` helper + a `provenance` block in the manifest.
- KTD3. **Bounds + honesty reuse `entity-fanout` (R3).** Round cap (`--rounds`, default ~4) + a paid-call budget cap + the honest cost/time/`degraded` manifest already built for entity-fanout. The session is instructed (SKILL.md) to stop at the round cap or when a round surfaces no new leads.
- KTD4. **Feedback ledger = `signals.py` pattern (R9/R10 baseline).** A local append-only JSONL (`investigate-feedback.jsonl` in the secrets/config dir, mirroring `demand-signals.jsonl`) records `{ts, topic, composed_queries, sources_used, human_feedback, coverage}` at run end. A `--feedback` capture command appends the human note; the investigate playbook reads the last N ledger rows for the topic to inform composition next time. Honest: this is a save+read, not learning.
- KTD5. **Cartographer = optional detect-and-relay soft-plug (R10 opt-in).** Mirror the `signals.py` `DEEP_RESEARCH_NOTIFY_URL` relay: if a Cartographer endpoint/MCP is configured (`DEEP_RESEARCH_CARTOGRAPHER_URL` or a detected MCP), POST the feedback/profile signal there; else no-op. `detect_state.py`/`--diagnose` surface an honest soft-plug line ("connect Cartographer to compound your research profile") only as availability info, never overclaiming learning. No Cartographer internals live here.
- KTD6. **Coverage-receipts renderer (R6).** The problems-first report + `brief.html` render the provenance markers inline per finding/source ("from a Telegram community with no web footprint", "X post 3h ago — not yet indexed", "Reddit archive, 12 mo, not top results") and a per-run coverage summary ("N of M sources are web-index-unreachable"). Reuses the entity-fanout brief renderer; adds a provenance-aware section.
- KTD7. **Eval harness = free web-index `site:` baseline (R11).** `eval_harness.py`: run the same question through (a) Beast investigate and (b) a web-index baseline — a free `site:` pass via the existing Brave key support (`KEYS["brave"]`) or Serper, standing in for "a web-index researcher". Score three axes — primary-source depth (count of distinct primary threads with quotes+links), freshness (median item age), social-coverage (distinct native platforms reached) — and append a row to a local `eval-log.jsonl` in the run/config dir (public-repo-safe; no personal paths). Parallel-API is an opt-in richer baseline behind a key, never required. No paid calls without a key; the free `site:` baseline is the default.

---

## High-Level Technical Design

```mermaid
flowchart TB
  Q["research question<br/>(State of X — where are the problems?)"] --> FB["read feedback ledger (KTD4)<br/>prior composed queries + notes for this topic"]
  FB --> COMPOSE["SESSION composes per-source queries (R2, KTD1)<br/>repo-scoped GH-issues · live-X operators · TG channels · subreddits"]
  COMPOSE --> FIRE["--fire <source> (KTD1)<br/>one composed query per source, native connector"]
  FIRE --> PROV["provenance per result (KTD2)<br/>source · freshness · web-index-reachable?"]
  PROV --> READ["SESSION reads results, spots leads/problems"]
  READ -->|new lead & rounds left| COMPOSE
  READ -->|round cap / no new leads (KTD3)| SYN["SESSION synthesizes problems-first report (R4)<br/>quotes + handles + live links"]
  SYN --> RCPT["coverage-receipts renderer (KTD6)<br/>mark what web-index can't reach + brief.html"]
  RCPT --> OUT["report + brief + honest cost/degraded"]
  OUT --> HFB["human feedback at end (R9)"]
  HFB --> LEDGER["append feedback ledger (KTD4)"]
  LEDGER -.opt-in.-> CARTO["Cartographer relay (KTD5, soft-plug)"]
  OUT -.periodic.-> EVAL["eval harness (KTD7)<br/>Beast vs web-index site: baseline · depth/freshness/social"]
```

---

## Implementation Units

| U-ID | Title | Key files | Depends on |
|---|---|---|---|
| U1 | Coverage-provenance helper + manifest block | `scripts/provenance.py`, `scripts/deep-research.py` | — |
| U2 | `--fire <source>` single-composed-query affordance | `scripts/deep-research.py` | U1 |
| U3 | Investigate-mode SKILL.md playbook (the loop) | `skills/deep-research/SKILL.md` | U1, U2 |
| U4 | Feedback ledger + `--feedback` capture | `scripts/investigate_feedback.py`, `scripts/deep-research.py` | — |
| U5 | Cartographer detect-and-relay soft-plug | `scripts/investigate_feedback.py`, `scripts/detect_state.py` | U4 |
| U6 | Coverage-receipts renderer (report + brief) | `scripts/entity_fanout.py` or `scripts/deep-research.py` | U1 |
| U7 | Eval harness (Beast vs web-index baseline) | `scripts/eval_harness.py` | U1, U2 |
| U8 | Quality-first positioning + docs + selftest | `SKILL.md`, `README.md`, `CONFIGURATION.md`, `scripts/selftest.sh` | U1–U7 |

### U1. Coverage-provenance helper + manifest block

- **Goal:** Every fired result carries a truthful provenance record so coverage-receipts (R6) and auditability (R7) rest on data, not a slogan.
- **Requirements:** R6, R7
- **Dependencies:** none
- **Files:** `skills/deep-research/scripts/provenance.py` (new), `skills/deep-research/scripts/deep-research.py` (manifest wiring), `skills/deep-research/tests/test_provenance.py` (new)
- **Approach:** `provenance.py` exposes `web_index_reachable(source, newest_item_age_hours)` returning `yes|partial|no` + a `reason`, from a per-connector static table (telegram=no; grok/live-X=partial, `no` when an item is <~48h old = pre-index; reddit arctic-shift archive=partial; github/github-issues/hackernews/bluesky=yes) and a `provenance_record(source, query, items, newest_ts)` builder. `run_connector`/the fire path attach the record to the manifest under a `provenance` block.
- **Execution note:** Pure classification + record-building; test the table and the freshness override directly.
- **Patterns:** the manifest-writing pattern in `deep-research.py`; `signals.py` for a small stdlib helper module.
- **Test scenarios:** Happy: `web_index_reachable("telegram", 200)` → `no`; `("github", 10)` → `yes`; `("grok", 200)` → `partial`; `("grok", 3)` → `no` (pre-index freshness override). Record shape: `provenance_record` returns all keys (source, query, items, fetched_at, freshness, web_index_reachable, reason). Unknown source → defaults to `yes` (conservative, never over-claims un-reachability). Empty result (0 items) → record still built, freshness null.
- **Verification:** For each connector the reachability tag matches the table + freshness rule; the manifest gains a populated `provenance` block on a real run.

### U2. `--fire <source>` single-composed-query affordance

- **Goal:** Give the session a clean primitive to fire ONE composed query on ONE named source and read the result + provenance, so it can drive the loop without manifest re-parsing.
- **Requirements:** R1, R2, R5
- **Dependencies:** U1
- **Files:** `skills/deep-research/scripts/deep-research.py` (argparse + `--fire` branch), `skills/deep-research/tests/test_fire.py` (new)
- **Approach:** Add `--fire <source>` (alias over the existing single-channel path): resolve the source via the `CONNECTORS` registry, run it with the composed query (`--q`/positional), write the result file, and print a JSON line `{source, path, items, provenance}` to stdout for the session to read. Reuse `entity-fanout`'s repo/entity-scoping helper so a composed query like `mem0ai/mem0` scopes github-issues correctly. Back-compat: existing `--only`/`--q` behavior unchanged.
- **Execution note:** Characterize the reuse — `--fire grok "..."` calls the SAME `channel_grok` the single mode uses; assert the JSON stdout shape (the loop's contract).
- **Patterns:** existing `--only` + `--q` handling; the entity-fanout `_cell_query`/registry dispatch; `list_connectors_json` for the JSON-to-stdout pattern.
- **Test scenarios:** Happy: `--fire github "mem0ai/mem0"` (mocked) → result file written, one JSON line with `{source:"github", path, items, provenance}`. Unknown source → error exit, no run. Composed query with the target-scoping (owner/repo) reaches github-issues repo-mode. JSON stdout is valid and single-line (loop-parseable). Back-compat: a plain `--only github` run is byte-unchanged (characterization).
- **Verification:** One composed query on a named source returns a parseable JSON envelope + a real result file; default modes unchanged.

### U3. Investigate-mode SKILL.md playbook (the loop)

- **Goal:** The session-driven agentic loop — compose per-source → fire → read → drill adaptively (bounded) → synthesize a problems-first report — written as the SKILL.md playbook the session follows.
- **Requirements:** R1, R2, R3, R4
- **Dependencies:** U1, U2
- **Files:** `skills/deep-research/SKILL.md` (new "investigate mode" STEP flow + marker), `skills/deep-research/tests/` (marker/order test via selftest, see U8)
- **Approach:** Add an `investigate` STEP flow: (STEP I0) read the feedback ledger for the topic; (STEP I1) compose short, target-scoped per-source queries (repo-scoped GH-issues, live-X operators, subreddits, TG channels), write them into `research-plan.md` BEFORE firing (plan-first); (STEP I2) fire each via `--fire`, read the JSON envelopes; (STEP I3) spot leads/problems, compose targeted follow-ups, fire again — repeat until the round cap or no new leads (KTD3); (STEP I4) synthesize the problems-first landscape report with real quotes/handles/live links; (STEP I5) render coverage-receipts (U6) + capture human feedback (U4). The compose-step is explicitly "short target-scoped queries, NEVER a blanket sentence" — with the live proof (blanket query → empty) cited as the rationale.
- **Execution note:** This is session-orchestration prose; verify via selftest markers (ordered STEP flow) + the doc contract, not unit tests.
- **Patterns:** the existing STEP 0 / wizard STEP flows in SKILL.md; the ordered-marker contract the selftest enforces.
- **Test scenarios:** Test expectation: none — session-prose orchestration; covered by the U8 selftest marker/order check (investigate STEP flow present + ordered: compose → fire → synthesize → coverage-receipts) and the "compose-step forbids blanket query" marker.
- **Verification:** SKILL.md contains an ordered `investigate` playbook a session can follow end-to-end; the compose-step rule is explicit; selftest markers pass.

### U4. Feedback ledger + `--feedback` capture

- **Goal:** Persist composed queries + human feedback locally so the next run can adapt (R9/R10 baseline).
- **Requirements:** R9, R10
- **Dependencies:** none
- **Files:** `skills/deep-research/scripts/investigate_feedback.py` (new), `skills/deep-research/scripts/deep-research.py` (`--feedback` command), `skills/deep-research/tests/test_investigate_feedback.py` (new)
- **Approach:** Mirror `signals.py`: `record_feedback(topic, composed_queries, sources_used, human_feedback, coverage, base_dir=None)` appends one JSON line to `investigate-feedback.jsonl` in the secrets/config dir (O_APPEND single-write; raises loudly on write failure). `read_recent(topic, n)` returns the last N rows for a topic (for the playbook's STEP I0). A `--feedback "<note>"` CLI command appends a human note against the most recent run. Honest: docstring + messaging say "saved locally to inform the next run", never "learned".
- **Execution note:** Reuse `signals.py`'s O_APPEND + honesty discipline exactly.
- **Patterns:** `signals.py` (`_append_jsonl_line`, `default_signals_dir`, honest messaging).
- **Test scenarios:** Happy: `record_feedback(...)` appends a valid JSON line; `read_recent(topic, 3)` returns the last 3 matching rows, newest-first. Topic filter: rows for other topics excluded. Write failure (unwritable dir) → raises OSError loudly (no silent loss). `--feedback "note"` appends against the latest run. Empty ledger → `read_recent` returns []. Windows-safe (stdlib only, no POSIX-only calls).
- **Verification:** Feedback round-trips through the ledger; the playbook can read prior rows; failures are loud.

### U5. Cartographer detect-and-relay soft-plug

- **Goal:** Optionally relay the feedback/profile signal to Cartographer, surfaced as an honest soft-plug — never overclaimed (R10 opt-in).
- **Requirements:** R10
- **Dependencies:** U4
- **Files:** `skills/deep-research/scripts/investigate_feedback.py` (relay), `skills/deep-research/scripts/detect_state.py` (soft-plug availability line), `skills/deep-research/tests/test_investigate_feedback.py`
- **Approach:** Mirror `signals.py`'s `_notify`: if `DEEP_RESEARCH_CARTOGRAPHER_URL` (HTTPS) is set, POST the feedback JSON with a short timeout; any failure is non-fatal (the local ledger already succeeded). `detect_state.py`/`--diagnose` add one honest line: Cartographer configured → "profile-compounding on"; not → "connect Cartographer (neighboring product) to compound your research profile across runs" — availability info only, never claiming the baseline learns. No secret material logged.
- **Execution note:** Relay must never undo a successful local ledger write (same invariant as `signals.py`).
- **Patterns:** `signals.py` `_notify` / `_https_post` (HTTPS-only, timeout, failure-tolerant, no secret echo).
- **Test scenarios:** Relay success (mocked 2xx) → recorded notified=true. Relay failure (timeout/non-2xx) → local ledger unaffected, notified=false, no raise. No URL set → no network I/O. Non-HTTPS URL → skipped with a reason. `--diagnose` shows the honest soft-plug line in both configured/unconfigured states; never claims learning without Cartographer.
- **Verification:** Cartographer relay is opt-in, failure-tolerant, honest; diagnose messaging never overclaims.

### U6. Coverage-receipts renderer (report + brief)

- **Goal:** Make the native-depth delta legible on every report — mark inline what a web-index researcher can't reach (R6).
- **Requirements:** R6
- **Dependencies:** U1
- **Files:** `skills/deep-research/scripts/entity_fanout.py` (or `deep-research.py`) renderer extension, `skills/deep-research/tests/test_coverage_receipts.py` (new)
- **Approach:** From the manifest `provenance` block, render per-source/per-finding markers ("from a Telegram community with no web footprint", "X post 3h ago — not yet indexed", "Reddit archive, 12 mo, not top results") and a per-run coverage summary ("N of M sources web-index-unreachable; freshest signal 3h old"). Extend the existing self-contained `brief.html` renderer with a provenance-aware section; the markdown report gets a Coverage section. Never claim un-reachability for a `yes`-tagged source.
- **Execution note:** Truthfulness gate — a marker only renders from a real provenance record, never inferred.
- **Patterns:** the entity-fanout `render_entity_brief` + `markdown_to_html`; the manifest `provenance` block from U1.
- **Test scenarios:** Happy: a manifest with telegram(no)+github(yes)+grok(no,fresh) → report shows the TG + fresh-X markers, NOT a marker on github; coverage summary counts 2 of 3 unreachable. Self-contained brief (no external `src=`/`@import`). No provenance → no coverage section (not a fake one). A `yes`-only run → "0 sources web-index-unreachable" (honest, not hidden).
- **Verification:** Coverage-receipts render only from real provenance; the delta is visible; brief stays self-contained.

### U7. Eval harness (Beast vs web-index baseline)

- **Goal:** Prove the quality win measurably — same question through Beast vs a web-index `site:` baseline, scored on depth/freshness/social-coverage (R11).
- **Requirements:** R11
- **Dependencies:** U1, U2
- **Files:** `skills/deep-research/scripts/eval_harness.py` (new), `skills/deep-research/tests/test_eval_harness.py` (new)
- **Approach:** `eval_harness.py <question>`: run the Beast side (a bounded investigate/fire pass) and a **web-index baseline** — a free `site:` pass via `KEYS["brave"]`/Serper, standing in for "a web-index researcher". Score three axes from the two result sets: primary-source depth (distinct primary threads with quote+link), freshness (median newest-item age), social-coverage (distinct native platforms reached). Append a row to a local `eval-log.jsonl` in the run/config dir (no personal paths — public-repo-safe). Parallel-API is an opt-in richer baseline behind a key; never required. No paid calls without a key.
- **Execution note:** The scoring functions are pure over two result sets — test them with fixtures; no live calls in tests.
- **Patterns:** `rank_items`/relevance helpers for parsing evidence; `signals.py` ledger append for the eval log.
- **Test scenarios:** Scoring: fixtures where Beast has 3 native platforms + fresh items and the baseline has 1 (web) + stale → Beast scores higher on all three axes. Depth counts distinct primary threads (dedup by url). Freshness = median age. No brave/serper key → baseline degrades to an honest "baseline unavailable" row, not a crash, and Beast still scores. Eval-log row appended with both sides + scores. No paid calls in tests.
- **Verification:** The harness scores both sides on the three axes and logs a row; runs free (no keys) with an honest degraded baseline.

### U8. Quality-first positioning + docs + selftest

- **Goal:** Position on QUALITY (native depth), NOT free (R8); document the mode; keep the suite green.
- **Requirements:** R5, R8, and the U3 playbook markers
- **Dependencies:** U1–U7
- **Files:** `skills/deep-research/SKILL.md`, `README.md`, `CONFIGURATION.md`, `skills/deep-research/scripts/selftest.sh`
- **Approach:** SKILL.md/README lead the positioning with **native full-breadth social/community depth + auditable primary evidence** — explicitly NOT "free/cheaper" (a one-line "why not just 'free'" note keeps the take honest). Document the `investigate` mode, `--fire`, `--feedback`, the Cartographer soft-plug, and the eval harness. selftest: a keyless smoke for `--fire` (one source, provenance in output), the investigate STEP-flow markers (ordered + compose-step-forbids-blanket), and the eval harness scoring on fixtures — all zero paid calls; keep the existing markers/connector-count intact.
- **Execution note:** Config/smoke unit — verify via selftest + the doc-marker checks, not new unit logic.
- **Test scenarios:** Test expectation: mostly smoke via selftest — `--fire` keyless run emits provenance; investigate STEP markers present + ordered; positioning markers present (native-depth lead; "not free" note); banned-POSIX grep clean over the new scripts; existing markers + connector count unchanged; secret-scan clean.
- **Verification:** `bash scripts/selftest.sh` green incl. the new investigate/fire/eval smokes and positioning markers; docs lead on quality.

---

## Verification Contract

- **Unit tests** for U1, U2, U4, U5, U6, U7 pass (`skills/deep-research/tests/`, the selftest discovery root; never discover from repo root). All mocked: provenance table + freshness override, `--fire` JSON envelope + back-compat, feedback ledger round-trip + loud failure, Cartographer relay opt-in/failure-tolerance, coverage-receipts truthfulness, eval scoring on fixtures. No live/paid calls in tests.
- **Back-compat keystone:** `--fire` and the new flags do not change the default `single` / `entity-fanout` paths (characterization); the existing full suite stays green.
- **selftest.sh** green: keyless `--fire` smoke emits a provenance record; investigate STEP-flow markers present + ordered (compose → fire → synthesize → coverage-receipts) + the compose-step-forbids-blanket marker; positioning markers (native-depth lead, "not free" note); eval-harness scoring smoke on fixtures with zero paid calls; banned-POSIX grep clean over new scripts; existing ordered markers + connector count intact; secret-scan clean.
- **Budget invariant (R17 house rule):** no paid API call without a configured key and never in tests; the eval baseline runs free via the `site:` pass, paid baselines opt-in only.
- **Honesty invariants:** coverage-receipts render only from real provenance (never inferred un-reachability); the feedback ledger is described as save+read, not learning; the Cartographer plug never claims learning without Cartographer; cost/time reporting stays real (reuse entity-fanout's honest manifest).
- **Cross-platform:** Windows-safe / stdlib-only across all new scripts (`provenance.py`, `investigate_feedback.py`, `eval_harness.py`) — selftest POSIX grep covers it.

## Definition of Done

- Running the `investigate` playbook on a question produces a **problems-first landscape report** built by the session's compose → fire → read → drill (bounded) → synthesize loop, with real quotes/handles/live links — the compose-step uses short target-scoped queries, never a blanket sentence.
- The report + `brief.html` carry **coverage-receipts** rendered from real provenance: what a web-index researcher can't reach (Telegram no-web-trace, fresh pre-index X, deep Reddit archive) is marked inline + summarized, and a `yes`-only run honestly says "0 unreachable".
- `--fire <source> "<composed query>"` returns a parseable JSON envelope + result file for the session loop; default `single`/`entity-fanout` modes are byte-unchanged.
- Human feedback at run end persists to the local ledger and is read by the next run; the Cartographer relay is opt-in, failure-tolerant, and honestly surfaced (no learning claim without it).
- The eval harness scores Beast vs a free web-index `site:` baseline on primary-source depth / freshness / social-coverage and logs a row; it runs with zero paid keys.
- Positioning (SKILL.md/README) leads on **native social/community depth + auditable primary evidence**, explicitly not on "free/cheaper".
- Full existing suite + selftest green; all new scripts Windows-safe/stdlib-only; no paid calls in tests; abandoned dead-end code removed before done.
