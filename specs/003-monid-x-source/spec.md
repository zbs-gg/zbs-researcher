# Feature Specification: Monid X Source

**Feature Branch**: `codex/monid-x-source`

**Created**: 2026-08-16

**Status**: Implemented

**Input**: User description: "Stop spending default research effort on Bluesky, keep X research useful when the direct xAI API budget is exhausted, check whether SuperGrok Heavy can fund programmatic use, and use the existing Monid API account as the explicit alternative."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pull real X posts without xAI API credit (Priority: P1)

As a researcher with a configured Monid account, I want to request one direct X
search explicitly, so an exhausted xAI team budget does not remove current user
voice from the investigation.

**Why this priority**: Current research loses its strongest social source when
the direct Grok call reaches its spending limit; a web-index answer is not an
equivalent replacement for recent X posts.

**Independent Test**: With deterministic Monid discovery, inspection, run, and
polling fixtures, fire one X query and verify a readable post list, fresh-post
provenance, route metadata, and a cost receipt without any live or paid call.

**Acceptance Scenarios**:

1. **Given** a configured Monid credential, **When** the user explicitly fires
   the X source, **Then** the system validates a compatible current catalog
   route before executing it and returns real post text, author, date, link,
   and available engagement fields.
2. **Given** a paid route with a published price, **When** execution is about
   to begin, **Then** the system names Monid, the underlying data provider, and
   the quoted price before the paid request.
3. **Given** a completed Monid run, **When** its audit manifest is written,
   **Then** it records the route, run identifier, price basis, returned item
   count, and actual charge when the provider exposes one; a quoted price is
   never mislabeled as an actual charge.
4. **Given** no Monid credential or no compatible discovered route, **When** X
   is requested, **Then** the system refuses before a paid call and explains
   what is missing.

---

### User Story 2 - Keep paid alternatives explicit (Priority: P2)

As a cost-conscious operator, I want direct xAI, subscription OAuth, Monid, and
OpenRouter to remain visibly distinct routes, so a failed provider never spends
money through another provider behind my back.

**Why this priority**: The current direct xAI key can fail after selection, and
silent fallback would violate the product's spending and provenance promises.

**Independent Test**: Simulate an xAI spending-limit response while Monid and
OpenRouter are configured and verify that neither alternative is called; the
error artifact points to explicit choices instead.

**Acceptance Scenarios**:

1. **Given** a direct xAI key that returns a spending-limit error, **When** the
   Grok source runs, **Then** no Monid or OpenRouter request occurs
   automatically and the operator receives an actionable alternative.
2. **Given** a SuperGrok subscription, **When** configuration guidance is read,
   **Then** it distinguishes supported subscription OAuth integrations from a
   standard xAI API key and does not claim that the existing key inherits the
   subscription allowance.
3. **Given** several configured paid providers, **When** a fire receipt is
   inspected, **Then** it names the provider that actually received the request.

---

### User Story 3 - Remove low-value Bluesky work from defaults (Priority: P3)

As a researcher running the default workflow, I want Bluesky excluded unless I
choose it, so time and coverage attention go to sources that materially affect
the decision.

**Why this priority**: Repeated default Bluesky calls currently add failures or
low-signal output without replacing the audience and practitioner evidence on X.

**Independent Test**: Select default connectors and build a default entity
fan-out plan, then verify that neither contains Bluesky; explicitly selecting
Bluesky must continue to work with its existing best-effort behavior.

**Acceptance Scenarios**:

1. **Given** no connector selection, **When** the default run is planned,
   **Then** Bluesky is absent.
2. **Given** a default entity fan-out run, **When** free cells are built,
   **Then** no Bluesky cells are created.
3. **Given** an explicit Bluesky selection, **When** the connector is available,
   **Then** its existing public search still runs and failures remain isolated.

### Edge Cases

- Monid discovery returns a higher-ranked endpoint with an incompatible input
  contract, or stops returning every route the system has validated.
- Monid accepts a run asynchronously but never reaches a terminal state within
  the bounded polling window.
- The run completes while its underlying provider returns an error status.
- Monid returns one result envelope containing a nested timeline rather than a
  top-level list of posts.
- A post omits its handle, date, engagement count, or text.
- The provider returns a listed per-call price but no actual billing block.
- xAI returns an authorization error unrelated to spending limits.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose direct X retrieval as a separately named,
  opt-in source that requires a Monid credential.
- **FR-002**: The X source MUST discover and inspect the current Monid catalog
  before a paid run and MUST execute only a compatible validated route.
- **FR-003**: The X source MUST name Monid, the selected underlying provider,
  endpoint, and quoted price before the paid request.
- **FR-004**: Selecting or failing the Grok source MUST NOT automatically call
  Monid, OpenRouter, or another paid provider.
- **FR-005**: A direct xAI spending-limit failure MUST preserve the error and
  point to the separately selectable X route when it is configured.
- **FR-006**: Successful X output MUST preserve available post text, author
  handle, creation date, canonical link, and engagement fields without
  inventing missing values.
- **FR-007**: The manifest MUST preserve the Monid run identifier, underlying
  provider and endpoint, returned item count, price, and billing evidence.
- **FR-008**: A listed price MUST be labeled as quoted or estimated unless the
  provider returns an actual billing value.
- **FR-009**: Missing credentials, catalog incompatibility, polling timeout,
  infrastructure failure, and underlying-provider failure MUST produce an
  explicit error artifact while unrelated sources continue.
- **FR-010**: Bluesky MUST be disabled in default single runs and default
  entity fan-out plans while remaining available by explicit selection.
- **FR-011**: Configuration guidance MUST state that SuperGrok subscription
  OAuth and standard xAI API-key billing are distinct integrations, and MUST
  not claim subscription-backed API-key access without current evidence.
- **FR-012**: Provider state detection MUST report only whether Monid is
  configured and MUST never emit credential material.
- **FR-013**: Public documentation MUST disclose the Monid network destination,
  transmitted query, credential source, pay-per-use class, default-off state,
  and the current route-discovery behavior.
- **FR-014**: Automated tests MUST cover successful retrieval, nested response
  normalization, missing fields, incompatible discovery, provider errors,
  timeout, cost classification, xAI failure guidance, and default connector
  selection with zero live or paid calls.

### Key Entities

- **X Source**: The explicit direct-social connector selected independently of
  the Grok reasoning lens.
- **Monid Route**: A currently discovered and inspected underlying provider,
  endpoint, input contract, and quoted price eligible for one X search.
- **Monid Run Receipt**: The run identifier, lifecycle status, provider status,
  price, available billing evidence, and result count retained for audit.
- **Normalized X Post**: Available text, author, date, canonical URL, and
  engagement values rendered without filling missing data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: One explicit X fire produces a readable artifact and auditable
  receipt from compatible fixtures in 100% of success cases.
- **SC-002**: All failure fixtures make zero calls to an unselected paid
  provider, including when multiple alternative credentials are configured.
- **SC-003**: Every successful fixture post with source fields retains its text,
  handle, date, link, and engagement values exactly; missing fields remain
  visibly unknown rather than fabricated.
- **SC-004**: Every Monid fire receipt distinguishes actual billing evidence
  from a quoted catalog price.
- **SC-005**: Default connector selection and default entity fan-out create
  zero Bluesky calls, while explicit Bluesky tests remain passing.
- **SC-006**: State and output scans find zero credential values.
- **SC-007**: The complete unit suite and ten-step self-test pass without a
  provider, external-search, or paid call.

## Assumptions

- The direct X source is valuable for current public user voice; it is not a
  replacement for Grok's synthesis or reasoning.
- Monid catalog discovery and inspection are free, while the selected data run
  is pay-per-use and therefore remains explicit.
- The first implementation supports only catalog routes whose response and
  input contracts have been validated; it fails closed on unknown routes.
- Subscription OAuth support in named third-party clients proves a possible
  future integration path, not a reusable standard API credential for this
  runner.
- The live-duel benchmark remains unchanged and does not select Monid.
