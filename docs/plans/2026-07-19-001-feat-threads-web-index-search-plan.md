---
title: Threads Web-Index Search (no App Review) - Plan
type: feat
date: 2026-07-19
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
---

# Threads Web-Index Search (no App Review) - Plan

**Target repo:** zbs-research (skill `deep-research`, paths repo-relative). Depth: Standard.

---

## Goal Capsule

- **Objective.** Give the `threads` connector a **legal, no-App-Review** way to search *other people's* public Threads posts by keyword — the thing Nik actually wants for research. Discover post URLs + snippets through a web-search index (`site:threads.com "keyword"`), then optionally enrich the top results with full text + engagement counts via the existing pay-per-use vendor.
- **Why this and not the official API.** Meta's `keyword_search` only searches *your own* posts without Advanced Access, and Advanced Access needs App Review + business verification that Meta is likely to reject for a research-scraping use case. Reading Google's public index of Threads (indexed since Aug 2024) needs **no Meta permission and violates no ToS** — it is the pragmatic path.
- **Product authority.** Nikita. Decisions confirmed this session: SERP default = **Serper primary + Brave auto-fallback**; enrichment = **auto-enrich top-N when a vendor key is configured** (discovery-only otherwise).
- **Scope this run:** **first** run a gating coverage spike (U0) to confirm web-index actually returns topical Threads posts; **only if it passes**, add web-index discovery as the connector's new default search path, compose it with auto-enrichment, honest ranking/limits, tests, docs. Keeps the existing official-token (own-posts) and vendor-direct paths intact. If U0 fails, the fallback decision is to keep vendor-direct as the default and treat web-index as opt-in.
- **Honest floor.** Web-index Threads search is **not zero-key** — it needs one search key (Serper or Brave). It is "no App Review", not "no key". A default run makes no paid *vendor* calls unless a vendor key is present; the SERP call itself consumes the SERP provider's free tier / credits. **Honest edge over the existing vendor-direct path:** the vendor path already searches others' posts *with* engagement (~10 posts, 1 credit/query); web-index's only real advantages are the 2500 free Serper queries/mo and the pure-legality framing (reads Google's index) — its data is thinner (snippet-only, profile-skewed, laggy). U0 exists to check that edge is worth the added path.

---

## Product Contract

### Primary actor & core outcome

- **Primary:** Nik's client / Nik — a researcher who wants to find what people are posting on Threads about a topic, by keyword, without owning a Meta-approved app.
- **Core outcome:** run the `threads` connector with one cheap search key and get back real public Threads posts matching the topic (author, URL, snippet), ranked by relevance; when a vendor key is present, the top few come back enriched with full text and like/reply/repost counts — all without App Review or ToS-violating page scraping.

### Requirements

- R1. **Web-index discovery** — search public Threads posts by keyword via `site:threads.com "<topic>"` against a SERP provider; parse results into normalized records (url, username, snippet, rank position). Reads a search engine's public index only.
- R2. **Provider tiering** — **Serper.dev** primary (`SERPER_API_KEY`; 2500 free queries/mo, then ~$0.30–1/1k; real Google index = best Threads coverage). **Brave** auto-fallback reusing the **existing** `brave` key hook (independent index, thinner coverage; free tier ended Feb 2026). Serper used when its key is present; else Brave when its key is present.
- R3. **No engagement in SERP snippets — be honest.** Web-index results carry no like/reply counts; the connector must not fabricate them and must say so in the output when results are discovery-only.
- R4. **Enrichment (auto top-N when vendor-keyed)** — when a ScrapeCreators key is configured, auto-enrich the top-N discovered posts via the vendor's post-detail endpoint to add full text + engagement counts. N is bounded and configurable; enrichment never runs without a vendor key (keeps default runs off the paid vendor). (Apify is not an enrichment vendor for Threads in v1 — the connector's vendor path is ScrapeCreators-only; adding Apify is deferred.)
- R5. **Composition & mode routing** — web-index is the new default search path for the connector. The existing **official-token** path (own posts) and **vendor-direct search** path remain available and are selected honestly when web-index cannot run (no SERP key) or when explicitly forced.
- R6. **Ranking** — discovery-only results rank by topic relevance (existing `rank_items` relevance floor on snippet text) blended with SERP position; enriched results rank by engagement (like_count) via `rank_items`. Output states which ranking was used.
- R7. **Availability** — the `threads` connector is available when **any** of {`serper`, `brave`, `threads` official, `scrapecreators`} is configured; skipped and recorded in the manifest when none are.
- R8. **Honest limits surfaced** — the output notes web-index caveats: index lag (hours–days), profile-skewed coverage (Threads sitemaps favor profiles/larger accounts), snippet-only without enrichment. **No crawler-UA scraping of threads.com pages** — that path is ToS-hostile and explicitly excluded.
- R9. **Windows-safe, stdlib-only, budget-safe** — urllib + threading only, no POSIX-only calls; no Anthropic/OpenAI calls; keys never printed/logged (extend the existing token-redaction discipline to the SERP + enrichment paths); graceful `ERROR.md` degrade with per-source isolation.
- R10. **Platform-dependency risk named** — the web-index default rests on Google continuing to index threads.com and Meta's robots.txt continuing to permit it; Meta already blocks AI crawlers and can de-index or restrict search engines at any time, silently killing this path. For a tool that may serve clients, this fragility is a named risk with vendor-direct search as the explicit continuity fallback.

### Scope boundaries

**In scope (v1)**
- SERP discovery (Serper + Brave) as the new default (R1, R2)
- Auto-enrich top-N via existing vendor path (R4)
- Mode routing + availability across four key sources (R5, R7)
- Ranking + honest rendering + limits (R3, R6, R8)
- KEYS/detect_state/docs/tests (R9)

**Non-goals / Deferred to Follow-Up Work**
- **Google Programmable Search (CSE)** as a third SERP provider — easy to add later behind the same interface (100/day free, needs key+cx); not needed once Serper+Brave land.
- **LLM-lens `site:threads.com` scoping** (route Gemini googleSearch / Perplexity Sonar at Threads) — Nik flagged it as "also consider"; deferred. Tradeoff has two axes, not one: it gives fuzzier summarized output (against it), BUT it is **zero-new-key for the common case** — many of this tool's users already have Gemini/Perplexity keys, so it would avoid the new-Serper-key friction the Honest Floor names (for it). Revisit as the zero-new-key default for keyless-SERP users if U0 shows SERP coverage is marginal, or if the new-key friction proves a real adoption drag.
- **Pagination beyond the first SERP page** — v1 takes the first page (~10–100 results per query); deeper paging is a follow-up if coverage is thin.
- **Crawler-UA fetch of threads.com post pages** — permanently out (ToS-hostile, breaks on Meta IP verification). Enrichment goes through the sanctioned vendor only.

---

## Planning Contract

Key Technical Decisions:

- KTD1. **Web-index discovery lives inside `threads.py`, not a new connector.** It is a third *search source* for the same `threads` output, not a new source class — reuse the connector's registration, `rank_items`, redaction, and rendering. Factor the SERP calls into small provider functions (`_serper_search`, `_brave_search`) behind one `_webindex_search(topic, limit)` returning normalized records, so a third provider (CSE) drops in later without touching callers.
- KTD1a. **URL host-allowlist is a security boundary, not just a relevance filter.** SERP results are untrusted third-party input, and a matched URL is later forwarded to the paid vendor `/v1/threads/post` endpoint (KTD5). Parse each result URL with `urllib.parse.urlparse` and accept a post record **only** when `hostname` is exactly in {`threads.com`, `www.threads.com`, `threads.net`, `www.threads.net`} AND the path matches `/@user/post/<id>`. Reject lookalike hosts (`threads.com.attacker.example`) and non-post paths. This prevents a poisoned SERP result from steering a vendor call (on our key) or a fetch at an attacker-chosen URL.
- KTD2. **Query shape = quoted-phrase first, unquoted fallback.** `site:threads.com "<topic>"` (quoted) is precise but a multi-word topic in quotes is an *exact-phrase* match that near-zeros for typical 3–5 word research topics. So: issue the quoted query; when it yields fewer than the enrichment N (≈5) Threads-post URLs after filtering, retry unquoted (`site:threads.com <topic>`) before giving up. Serper: `POST https://google.serper.dev/search` with `{"q": ..., "num": N}` and header `X-API-KEY`. Brave: `GET https://api.search.brave.com/res/v1/web/search?q=...` with header `X-Subscription-Token` (reuse the existing `brave` key). Both return organic results with `link` + `title`/`snippet`. Verify exact response field names + phrase-query behavior live (U0) before building.
- KTD3. **Availability = any-of-N keys.** Extend the `Connector.fallback_key` mechanism from a single string to also accept a tuple/list of fallback key names (backward compatible: a bare string still works). `threads` becomes `requires=["threads"], fallback_key=("serper", "brave", "scrapecreators")` — available when the official token OR any discovery/vendor key is present. `missing_keys()`/`select_connectors` honesty preserved (report the primary `threads` miss only when *nothing* is available).
- KTD4. **Mode routing is honest and deterministic — and subsumes the existing `DEEP_RESEARCH_THREADS_VENDOR` env.** The connector today routes on `DEEP_RESEARCH_THREADS_VENDOR` with pinned tests (unknown-value error, forced-vendor-without-key error, override-over-official). This plan **replaces** that env with `DEEP_RESEARCH_THREADS_MODE` (`webindex` | `official` | `vendor`) and keeps `DEEP_RESEARCH_THREADS_VENDOR` as a back-compat alias mapping to `mode=vendor` for one release; the existing override/error tests migrate to the new env (same semantics: a set-but-keyless mode errors before any network call, matching today's forced-vendor contract). Order: (1) `DEEP_RESEARCH_THREADS_MODE` override wins if set (and errors if its key is missing); else (2) web-index if a SERP key (serper/brave) is present — the new default; else (3) vendor-direct search if a vendor key is present; else (4) official own-posts if only the official token is present (with the existing Standard-Access note). Each fallback records which path ran in the output.
- KTD5. **Enrichment composes on top of discovery, bounded — and is a NEW vendor call.** The current vendor path is search-only (`/v1/threads/search`); there is no reusable per-post fetch, so enrichment adds a **new** `/v1/threads/post` fetch + a new normalizer for the post-detail response shape (only the `x-api-key` header pattern is reused). After web-index discovery, if a vendor key is present, enrich the top-N (`DEEP_RESEARCH_THREADS_ENRICH_N`, default 5, hard cap ~10; when discovered post URLs < N, enrich only what exists — effective N clamps down, note it) discovered post URLs, adding full text + engagement. **Redaction:** each per-post exception is routed through the existing `_redact(str(exc), vendor_key)` before it becomes a note — the vendor key must never reach `threads.md`. Per-post failure degrades that post to snippet-only with a redacted note; siblings continue. No vendor key → discovery-only, no paid call.
- KTD6. **Two ranking modes, labelled.** Discovery-only: `rank_items` relevance floor on snippet text vs topic, blended with SERP position (position as a weak prior). Enriched: `rank_items` with `engagement_key=like_count`. The rendered header states which ranking + whether engagement is real or absent (R3).
- KTD7. **Redaction + budget discipline reused.** SERP keys ride in headers (never URL), never printed; SERP + enrichment errors go through the existing redaction helper and `ERROR.md` degrade. stdlib urllib only; no OpenAI/Anthropic; Windows-safe.
- KTD8. **Web-index-as-default is contingent on a coverage spike (U0), not assumed.** The default choice is deliberately gated: the existing vendor-direct path already returns others' posts *with* engagement (richer data), so web-index only earns "default" if it actually surfaces enough topical post URLs to be useful. U0 runs live Serper/Brave `site:threads.com` queries for 2–3 representative research topics and counts distinct on-topic *post* URLs (not profile pages) surviving the host-allowlist filter. **Pass gate:** a typical topic yields ≥ N (enrichment default, 5) post URLs → proceed to U1–U5 with web-index as default. **Fail gate:** keep vendor-direct as the default, demote web-index to opt-in (`mode=webindex`), and reconsider the deferred quoted/unquoted, pagination, and LLM-lens alternatives before spending the full build.

---

## High-Level Technical Design

`channel_threads` gains a discovery→enrichment pipeline. Web-index is the default; the other paths are honest fallbacks. Enrichment only fires with a vendor key.

```mermaid
flowchart TB
  A["channel_threads(topic)"] --> B{mode routing (KTD4)}
  B -->|SERP key present| C["web-index discovery<br/>site:threads.com (KTD1/2)"]
  B -->|no SERP, vendor key| V["vendor-direct search (existing)"]
  B -->|no SERP/vendor, official token| O["official keyword_search<br/>(own posts, honest note)"]
  C --> P["parse → normalized records<br/>url, username, snippet, position"]
  P --> E{vendor key present?}
  E -->|yes| N["auto-enrich top-N via vendor<br/>full text + engagement (KTD5)"]
  E -->|no| D["discovery-only<br/>no engagement, honest note (R3)"]
  N --> R["rank by engagement (KTD6)"]
  D --> R2["rank by relevance + SERP position (KTD6)"]
  V --> R
  O --> R2
  R --> OUT["render threads.md + honest limits (R8)"]
  R2 --> OUT
```

---

## Implementation Units

### U0. Coverage spike — verify web-index actually returns topical Threads posts (GATE)

- **Goal:** Before building anything, confirm the load-bearing premise — that `site:threads.com "<topic>"` returns enough real, on-topic *post* URLs (not profile pages) to justify web-index as the default. This is a throwaway spike, not shipped code.
- **Requirements:** gates R1, R2 (and KTD8)
- **Dependencies:** none — runs first
- **Files:** none shipped (a scratch script + a recorded findings note; capture results in the PR/plan follow-up, not the repo)
- **Approach:** Run live Serper (and Brave if keyed) `site:threads.com "<topic>"` for 2–3 representative research topics Nik actually cares about. For each, count distinct organic results whose URL passes the KTD1a host-allowlist + `/@user/post/<id>` path filter (i.e. real posts, not `/@user` profile pages). Also run the unquoted variant (KTD2) and compare hit counts. Record: post-URL yield per topic (quoted vs unquoted), profile-vs-post ratio, whether threads.com or threads.net dominates, and the exact organic-result field names each provider returns.
- **Execution note:** This is a live-probe spike — the one place minimal real SERP spend is expected. It exists specifically to falsify the premise cheaply before U1–U5.
- **Test scenarios:** Test expectation: none — throwaway spike. The deliverable is the recorded yield numbers + a PASS/FAIL call against the KTD8 gate (≥ N=5 topical post URLs for a typical topic).
- **Verification:** A written PASS/FAIL against KTD8. PASS → proceed to U1 with web-index default. FAIL → stop, keep vendor-direct default, and revisit the deferred alternatives before building.

### U1. Web-index discovery backend (Serper primary + Brave fallback)

- **Goal:** Search public Threads posts by keyword via `site:threads.com "<topic>"` and return normalized post records, no Meta permission.
- **Requirements:** R1, R2, R3, R9
- **Dependencies:** U0 (gate must PASS)
- **Files:** `skills/deep-research/scripts/connectors/threads.py` (add `_serper_search`, `_brave_search`, `_webindex_search`, host-allowlist URL parsing), `skills/deep-research/tests/test_threads_webindex.py` (new)
- **Approach:** `_webindex_search(topic, limit)` picks Serper when its key is present, else Brave; builds `site:threads.com "<topic>"` (quoted), with the KTD2 unquoted retry when the quoted yield is below N; POSTs/GETs via the runner's `get_json`/`post_json` with the key in a header (never the URL); parses organic results and accepts a record only when the URL passes the KTD1a host-allowlist + `/@user/post/<id>` path check; extracts username from the URL path, keeps snippet + 1-based position. Returns records `{url, username, snippet, position, source: "serper"|"brave"}`. Honest empty when no post URLs matched.
- **Execution note:** Field names + phrase-query behavior come from U0's live findings — build to those. Mocked tests only in the suite — no live paid calls.
- **Patterns:** existing `get_json`/`post_json` and header-auth in `threads.py` official path; `_redact` token discipline; existing permalink URL handling.
- **Test scenarios:** Happy: Serper key set → builds quoted `site:threads.com "<topic>"` with `X-API-KEY` header, parses mocked organic results into records (username-from-URL + snippet + position). Fallback: no Serper key, Brave key set → Brave request with `X-Subscription-Token`, parsed. Quoted-underdelivers: quoted mock returns < N post URLs → an unquoted retry fires and recovers results (assert two calls + the unquoted `q`). Host-allowlist (security): a lookalike-host URL (`threads.com.attacker.example/@user/post/1`) is REJECTED; a genuine `www.threads.com/@user/post/1` accepted; a profile URL (`threads.com/@user`, no `/post/`) dropped. Edge: zero organic results → honest empty, no crash. Edge: results present but none pass the allowlist → empty with note. Error: SERP HTTP 429/5xx → raises (ERROR.md degrade), key never in the raised message. Windows: no POSIX-only calls.
- **Verification:** For mocked Serper and Brave payloads, `_webindex_search` returns correctly-parsed, host-validated Threads post records; the quoted→unquoted fallback fires on low yield; keys and lookalike hosts never pass.

### U2. Multi-key availability + KEYS + detect_state

- **Goal:** Make the `threads` connector available whenever any of official/serper/brave/vendor keys exist, and surface `serper` in detected state.
- **Requirements:** R2, R7, R9
- **Dependencies:** none (U1 uses the serper key; this unit registers it)
- **Files:** `skills/deep-research/scripts/deep-research.py` (`KEYS["serper"]`, extend `Connector.fallback_key` to accept a tuple, update `threads` registration), `skills/deep-research/scripts/detect_state.py` (add `serper` **and** `brave` to `PROVIDERS`), `skills/deep-research/tests/test_detect_state.py` (update pinned providers dict), `skills/deep-research/tests/test_threads.py` (update `test_connector_registered_with_fallback_key`), `skills/deep-research/tests/test_openrouter_routing.py` (verify its skip-set pin still holds — openrouter is not in the threads tuple, so it does)
- **Approach:** Add `KEYS["serper"] = read_key(["serper-key.txt"], r"[A-Za-z0-9]{20,}", "SERPER_API_KEY")`. Generalize `Connector.fallback_key` so `missing_keys()` returns `[]` when the direct key OR **any** fallback key is present (accept `str` or `tuple`; a `str` keeps current behavior exactly — verified: the openrouter lenses use a plain string and must stay unchanged). Re-register `threads` with `fallback_key=("serper", "brave", "scrapecreators")`. **Migrate the existing pin:** `test_threads.py::test_connector_registered_with_fallback_key` asserts `fallback_key == "scrapecreators"` — update it to the tuple. Add both `"serper"` and `"brave"` to `detect_state.PROVIDERS` (brave gates threads availability but was never surfaced in detected state — a pre-existing blind spot this closes) and update the pinned providers-dict test.
- **Patterns:** the existing single `fallback_key` (added for OpenRouter in the runner); `read_key` shape; `detect_state.PROVIDERS` contract + its exact-shape test; the `test_threads.py` registration pin.
- **Test scenarios:** Happy: only `SERPER_API_KEY` set → `threads` available, `missing_keys()==[]`, appears in default `--list-connectors`. Only `brave` set → available. Only official `threads` token → available (unchanged). None of the four → unavailable, `missing_keys()` reports the `threads` primary, recorded skipped in manifest. Backward-compat: a connector with a plain-string `fallback_key` (openrouter lenses) resolves exactly as before. Registration pin: `threads.fallback_key == ("serper","brave","scrapecreators")`. detect_state: `serper` and `brave` present in the providers dict; a set `SERPER_API_KEY` → `serper: true`, a set `BRAVE_API_KEY` → `brave: true`, no key value in output.
- **Verification:** `--list-connectors` shows `threads` available with any single one of the four keys; the openrouter lenses' availability is unchanged; `test_threads.py` registration pin green; detect_state emits `serper` + `brave`.

### U3. Mode routing + discovery→enrichment composition

- **Goal:** Make web-index the default search path and compose it with bounded auto-enrichment, with honest fallbacks to vendor-direct and official-own-posts.
- **Requirements:** R4, R5, R8, R9
- **Dependencies:** U1, U2
- **Files:** `skills/deep-research/scripts/connectors/threads.py` (`channel_threads` routing + `_enrich_top_n` + new `_vendor_post_detail`), `skills/deep-research/scripts/connectors/threads.py` env alias handling, `skills/deep-research/tests/test_threads.py` (migrate the existing `DEEP_RESEARCH_THREADS_VENDOR` override/error tests to `DEEP_RESEARCH_THREADS_MODE` + back-compat alias), `skills/deep-research/tests/test_threads_webindex.py`
- **Approach:** In `channel_threads`, implement the KTD4 routing order on `DEEP_RESEARCH_THREADS_MODE`, with `DEEP_RESEARCH_THREADS_VENDOR` kept as a back-compat alias → `mode=vendor` (migrate the existing pinned override/error tests). On the web-index path, after discovery, if a vendor key is present, call `_enrich_top_n(records, n)` where `n = min(DEEP_RESEARCH_THREADS_ENRICH_N default 5, hard cap 10, len(records))`: for each of those URLs, a **new** `_vendor_post_detail(url)` calls `/v1/threads/post` (new fetch + normalizer — the current vendor path is search-only) to add full text + engagement; per-post failure → `_redact(str(exc), vendor_key)` into a snippet-only note, continue. Record which path + whether enrichment ran in the output.
- **Execution note:** Enrichment is a NEW vendor call (`/v1/threads/post`), not a reuse of the search path — only the `x-api-key` header pattern is shared. A set-but-keyless `DEEP_RESEARCH_THREADS_MODE` errors before any network call, matching today's forced-vendor contract.
- **Patterns:** existing vendor `x-api-key` header in `threads.py`; the existing `_select_path`/`DEEP_RESEARCH_THREADS_VENDOR` handling to migrate; per-source degrade + note from launch_radar/revenue_radar; `_redact`.
- **Test scenarios:** Happy: SERP key + vendor key → web-index discovers, top-N enriched with engagement, output notes "enriched via vendor". SERP key, no vendor key → discovery-only, no vendor call attempted (assert), honest "no engagement" note. Mode override: `DEEP_RESEARCH_THREADS_MODE=official` with official token → official path runs even when a SERP key is present. Alias: `DEEP_RESEARCH_THREADS_VENDOR=scrapecreators` still routes to vendor (back-compat). Keyless-mode error: `DEEP_RESEARCH_THREADS_MODE=vendor` with no vendor key → clear error before any network call. Fallback: no SERP key, vendor key only → vendor-direct search runs. Enrichment bound: 30 discovered, N=5 → exactly 5 `/v1/threads/post` calls. Clamp: 3 discovered, N=5 → exactly 3 calls. Enrichment failure + redaction (security): one post's vendor call 500s with the key echoed in the body → that post snippet-only, the vendor key does NOT appear in the note or ERROR.md, other 4 enriched, no crash. Cost guard: enrichment never called without a vendor key.
- **Verification:** With SERP+vendor keys a run yields redacted-safe enriched top-N + discovery tail; with SERP only, zero vendor calls; mode override + `THREADS_VENDOR` alias + keyless-mode error all honored.

### U4. Ranking + honest rendering

- **Goal:** Rank and render both result shapes correctly and label which ranking + whether engagement is real.
- **Requirements:** R3, R6, R8
- **Dependencies:** U3
- **Files:** `skills/deep-research/scripts/connectors/threads.py` (rendering + ranking selection), `skills/deep-research/tests/test_threads_webindex.py`
- **Approach:** Discovery-only → `rank_items` relevance floor on snippet vs topic, blended with SERP position as a weak prior; render @username · snippet · URL, header note "ranked by relevance; web-index results carry no engagement counts (SERP snippets)". Enriched → `rank_items` with `engagement_key=like_count`; render with like/reply/repost counts, header note "top N enriched via vendor". Always append the R8 limits block (index lag; profile-skewed coverage; snippet-only without enrichment; no page scraping).
- **Patterns:** existing `rank_items(...)` usage in `threads.py`; the honest-note rendering already in the official/vendor paths; `excerpt` helper.
- **Test scenarios:** Discovery-only: on-topic snippet ranks above off-topic; output contains the "no engagement counts" note and NOT any fabricated counts. Enriched: posts ordered by like_count desc; counts rendered. Mixed: enriched top-N appear above the discovery-only tail with a visible boundary. Limits: the R8 caveats block is always present. Relevance floor: an off-topic high-position SERP hit is demoted below an on-topic lower-position one.
- **Verification:** Rendered `threads.md` shows correct ranking + honest notes for both shapes; no fabricated engagement in discovery-only mode.

### U5. Docs + selftest + honest limits

- **Goal:** Document the new default path and keep the transparency/selftest surface accurate.
- **Requirements:** R2, R8, R9
- **Dependencies:** U1–U4
- **Files:** `skills/deep-research/SKILL.md` (Threads tier copy + onboarding bullet + the `DEEP_RESEARCH_THREADS_MODE` / `DEEP_RESEARCH_THREADS_ENRICH_N` env knobs), `CONFIGURATION.md` (threads row in BOTH the gated-connectors table AND the "Security & transparency — what it does, what it sends where" table; key-files list adds `serper-key.txt`), `README.md` (threads row copy), `skills/deep-research/scripts/selftest.sh` (secret-scan resolves the Serper-key shape; connector count unchanged at 17)
- **Approach:** Update the Threads sections to describe the honest routes with the new **web-index default** ("one search key, no App Review, searches everyone's public posts; no engagement counts unless a vendor key enriches the top-N") — and name the config knobs (`DEEP_RESEARCH_THREADS_MODE`, `DEEP_RESEARCH_THREADS_ENRICH_N`) so the override is discoverable. In CONFIGURATION.md's **Security & transparency** table, add `google.serper.dev` / `api.search.brave.com` to the threads row with "topic/query text sent to a third-party search index" as what leaves the machine (matching the tiktok-ig/meta-ads disclosure convention) — the SERP query carries the topic, not the key (header). Add `serper-key.txt` / `SERPER_API_KEY` to the key-files list. **Resolve the secret-scan (security):** the U2 read regex `[A-Za-z0-9]{20,}` is too broad for a repo-wide leak scan; from U0's findings, if Serper keys have a distinctive fixed prefix add a keyed pattern, otherwise add a call-site-scoped rule (e.g. a string of that shape adjacent to `serper`/`SERPER_API_KEY`) so U5 never ships with zero scan coverage for this key. Confirm connector count stays 17 (no new connector) and the zero-key dry-run still skips `threads`.
- **Execution note:** Docs/config + selftest unit — verify by the existing selftest steps (marker-order, secret-scan, connector count, zero-key dry-run), not new unit tests. The secret-scan rule choice depends on U0's recorded Serper key format.
- **Patterns:** the threads rows added to CONFIGURATION.md/README/SKILL.md in the R23 work; the tiktok-ig/meta-ads security-transparency disclosure rows; selftest secret-scan + connector-count checks.
- **Test scenarios:** Test expectation: mostly smoke via `selftest.sh` — connector count stays 17; zero-key dry-run still skips `threads`; secret-scan clean AND covers a planted Serper-key-shaped fake; SKILL.md marker order intact and no `${CLAUDE_PLUGIN_ROOT}`.
- **Verification:** `bash skills/deep-research/scripts/selftest.sh` green; docs describe the web-index default, name `SERPER_API_KEY` + the env knobs; CONFIGURATION security-transparency table lists `google.serper.dev`/`api.search.brave.com` with "query text"; secret-scan catches a planted Serper key.

---

## Verification Contract

- **U0 gate (blocks the build):** the coverage spike returns a written PASS/FAIL against KTD8 (≥ N=5 topical *post* URLs for a typical research topic, quoted or unquoted). FAIL means U1–U5 do not proceed as specified — vendor-direct stays default.
- **Unit tests** for U1–U4 pass (`skills/deep-research/tests/` — the selftest `unittest discover` root; never discover from repo root). All mocked: Serper + Brave SERP payloads (incl. quoted-underdelivers→unquoted retry, lookalike-host rejection), vendor enrichment responses (incl. per-post error with key-redaction), mode routing + `THREADS_VENDOR` alias + keyless-mode error, ranking. No live/paid calls in the suite.
- **selftest.sh** stays green (10 steps): connector count 17 (no new connector), zero-key dry-run skips `threads`, banned-POSIX grep clean, secret-scan clean AND catches a planted Serper-key fake, `claude plugin validate` passes, SKILL.md marker order intact.
- **Live smokes (documented, minimal spend):** covered by U0 for discovery (Serper + Brave field names + real post-URL yield); plus one vendor `/v1/threads/post` enrichment on a discovered URL to confirm the new endpoint's response shape.
- **Security:** a test proves the vendor key never reaches `threads.md`/ERROR.md on a per-post enrichment error, and that a lookalike-host SERP URL is rejected before any vendor call.
- **Budget invariant:** a discovery-only run (SERP key, no vendor key) makes zero vendor calls (asserted); no Anthropic/OpenAI calls anywhere.
- **Cross-platform:** Windows-safe (stdlib + threading, no POSIX-only calls) — covered by the selftest POSIX grep over `connectors/`.

## Definition of Done

- **U0 gate passed** (or the plan pivoted to vendor-direct default on FAIL) — the web-index-as-default decision is backed by a recorded coverage measurement, not an assumption.
- Running `threads` with only a Serper (or Brave) key returns real public Threads posts by keyword (author + URL + snippet), ranked by relevance, with an honest "no engagement counts" note — no App Review, no Meta token, no page scraping.
- Only host-allowlisted (`threads.com`/`threads.net`) post URLs are accepted from SERP results; a lookalike host never reaches a vendor call; the vendor key never appears in output/logs/errors.
- `DEEP_RESEARCH_THREADS_MODE` (+ `DEEP_RESEARCH_THREADS_VENDOR` back-compat alias) and `DEEP_RESEARCH_THREADS_ENRICH_N` are documented and honored; the existing vendor-env override/error tests are migrated, not broken.
- With a vendor key also present, the top-N (default 5, capped ~10) come back enriched with full text + like/reply/repost counts, ranked by engagement; per-post enrichment failure degrades to snippet-only without crashing.
- The connector is available with any one of {serper, brave, official threads token, scrapecreators}; skipped and recorded when none; the openrouter lenses' single-fallback availability is unchanged.
- Mode override (`DEEP_RESEARCH_THREADS_MODE`) and the honest fallbacks (vendor-direct, official own-posts) work and label which path ran.
- SERP/vendor keys never appear in output, logs, or error text; discovery-only runs make no paid vendor call.
- `SERPER_API_KEY` documented in SKILL.md / CONFIGURATION.md / README; selftest green (17 connectors, zero-key dry-run skips threads); output surfaces the R8 web-index limits.
- The R8 exclusion holds: no crawler-UA fetch of threads.com pages anywhere in the diff.
- Abandoned-attempt code from dead-end approaches is removed before declaring done.
