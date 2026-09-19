# Research: Monid X Source

## Decision 1: Treat subscription OAuth and the xAI API key as separate routes

**Decision**: Do not try to reuse SuperGrok browser/session state or present it
as credit for the existing `GROK_API_KEY`. Document that xAI officially supports
SuperGrok subscription OAuth in named agent clients such as OpenCode, while the
Researcher direct Grok connector still uses a standard API bearer key and its
team billing state.

**Rationale**: xAI's 2026 OpenCode instructions explicitly use “xAI Grok OAuth
(SuperGrok Subscription)”. The xAI API management documentation separately
describes team API keys and prepaid balances. No official generic bearer-token
contract was found that lets this runner exchange a consumer subscription for a
normal Responses API key.

**Alternatives considered**:

- Shell out to OpenCode under subscription OAuth: rejected because it turns a
  data-source connector into an undocumented agent-client dependency and does
  not prove native `x_search` access through a stable machine contract.
- Reuse browser cookies or reverse-engineer OAuth: rejected as brittle,
  security-sensitive, and unsupported.
- Claim SuperGrok cannot fund any programmatic use: rejected because current
  official OpenCode, Kilo, and similar integrations disprove that broader claim.

**Primary sources**:

- <https://x.ai/news/grok-opencode>
- <https://docs.x.ai/grok/faq>
- <https://docs.x.ai/developers/rest-api-reference/management>

## Decision 2: Add Monid as a separate direct X connector

**Decision**: Add a separately selected `x` source. It discovers and inspects a
current Monid endpoint for free, announces the provider and price, and only then
runs the paid request. It never replaces `grok` automatically.

**Rationale**: Monid's official API is explicitly designed around discover →
inspect → run and returns provider, endpoint, pricing, run, provider-response,
and result metadata. A live 2026-08-16 preflight selected TikHub's verified X
search route at USD 0.0015 per call. One explicitly approved live run completed
successfully and confirmed the nested `output.timeline[]` fields needed by the
normalizer.

**Alternatives considered**:

- Automatic xAI → Monid fallback: rejected because it would silently change
  provider, evidence semantics, and payee after a paid failure.
- Keep using OpenRouter Grok web grounding: retained as a separate lens, but it
  is web-index retrieval rather than equivalent native/direct X coverage.
- Call X's official API directly: deferred because the existing configured and
  live-confirmed route is Monid, and this feature is a small recovery patch.

**Primary sources**:

- <https://docs.monid.ai/api/discover.html>
- <https://docs.monid.ai/api/inspect.html>
- <https://docs.monid.ai/api/run.html>
- <https://docs.monid.ai/guide/pricing.html>

## Decision 3: Discover dynamically, execute only validated routes

**Decision**: Discover on every explicit fire, but choose only from compatible
route adapters shipped with the connector. Initially support TikHub search and
the documented Apify tweet scraper. Inspect the discovered route before any run
and fail without charge if no validated route remains.

**Rationale**: Monid's catalog ranking and response shapes can change. Blindly
executing the first result would risk paying for a LinkedIn, analytics, or
otherwise incompatible endpoint. A static endpoint alone would ignore Monid's
own routing contract and fail when catalog availability changes.

**Alternatives considered**:

- Always use one hard-coded endpoint: simpler but unable to survive catalog
  replacement and contrary to the service's discovery guidance.
- Execute any discovered Twitter-like result: rejected because discover's
  description is not a sufficient input/output contract.
- Generate adapters from arbitrary schemas at runtime: rejected as too broad
  and difficult to test honestly.

## Decision 4: Record quoted cost separately from actual billing

**Decision**: Store a catalog/run price as `quoted` unless Monid returns an
`actualCost` billing field. Preserve both route price and billing block metadata
when available.

**Rationale**: The live run returned a valid price but no billing block. Calling
that amount “actual” would overstate the evidence. Monid's API documentation
shows both price and billing fields and makes their distinction explicit.

**Alternatives considered**:

- Treat the per-call price as actual: rejected as unsupported when billing is
  absent.
- Mark every such call cost-unavailable: honest but needlessly discards the
  useful quoted price.

## Decision 5: Disable Bluesky by default, preserve explicit access

**Decision**: Set the connector's default flag to false and remove it from the
default free entity-fan-out set. Keep the implementation, pacing, provenance,
and explicit selection behavior intact.

**Rationale**: The observed default run produced an HTTP 403 and no decision-
changing evidence, while the product owner explicitly prefers X for this job.
Removing the connector entirely would destroy a potentially useful niche source
and exceed the requested patch.

**Alternatives considered**:

- Delete Bluesky: rejected as unnecessary and irreversible product narrowing.
- Keep it in entity fan-out only: rejected because that multiplies the lowest-
  value work across every entity.
