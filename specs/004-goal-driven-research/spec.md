# Feature Specification: Goal-driven bilingual research and playbooks

**Feature Branch**: existing `codex/monid-x-source` working copy (preserve owner's uncommitted source work)
**Created**: 2026-09-05
**Status**: Implemented and locally qualified; unreleased
**Input**: Owner requests goal clarification, necessary service setup, deep research across social comments, Reddit posts, X threads, YouTube, Russian and English web; exactly two final deliverables: human HTML playbook and agent-readable JSON or Markdown. Live-test allowance: USD 1 total.

## User Scenarios & Testing

### User Story 1 - From a human problem to a ready investigation (Priority: P1)

A person states their problem and optionally shares videos or posts. Researcher
clarifies the intended decision and success criteria, captures scope and languages,
then requests only missing services needed for that investigation. Once those
choices and spending are authorized, the session proceeds without repeated permission.

**Independent Test**: A vague Russian request triggers a goal question; an already
complete brief preserves its answers and seed links without repeating onboarding.

**Acceptance Scenarios**:
1. Given a complete goal, when intake is saved, then decision, audience, timeframe,
   success criteria, language scope, source needs and seed links remain inspectable.
2. Given an absent provider, when readiness is checked, then the unmet source and
   credential name are shown without exposing secrets or spending money.

### User Story 2 - Read what people actually said (Priority: P1)

Researcher discovers relevant material in Russian and English, reads supplied
videos and targeted conversations, follows useful leads, and retains source text,
authorship, dates, links, evidence type and limitations. It checks counterexamples,
conflicting advice, recency and promotional bias before making recommendations.

**Independent Test**: A bounded investigation produces distinct post/comment/video
evidence and explicitly reports inaccessible threads and missing language coverage.

**Acceptance Scenarios**:
1. Given unreliable Reddit archive search, when Reddit is requested, then selected
   Perplexity search can discover Reddit sources independently of archive availability.
2. Given a public Reddit thread or YouTube video, when read, then retained evidence
   includes available body/transcript and bounded comments with provenance.
3. Given X threads, when selected, then targeted Grok follow-up includes replies
   and thread context, and does not present unverified model paraphrases as raw text.
4. Given a failed or partial source, the other sources continue and the final
   artifacts carry the gap. A missing mandatory source cannot be marked complete.

### User Story 3 - Two actionable deliverables (Priority: P1)

The person receives a navigable, printable HTML playbook describing what to do,
why, in what order, how to measure success and what remains uncertain. Agents get
the same information, source references and bounds in a structured reusable file.

**Independent Test**: One validated dossier produces both documents, and every
action and supported claim resolves to dated evidence in both. Invalid references,
fabricated coverage and unsafe links fail validation before output replacement.

**Acceptance Scenarios**:
1. Given a valid dossier, export produces `playbook.html` and `agent-context.json`
   in the same run, with matching goals, claims, action IDs and evidence IDs.
2. Given incomplete research, export visibly labels both outputs partial and lists
   gaps rather than silently omitting unavailable channels or seeds.
3. Given a phone/tablet/desktop, the playbook remains readable and its navigation,
   evidence links, action controls and print action function.

### Edge Cases

Missing keys or depleted balances; mixed-language and duplicate seed URLs; private
or malformed URLs; deleted posts; empty comments; bot and promotional replies;
captions unavailable or poor; transcript language mismatch; interrupted runs;
unknown cost; prompt injection inside source text; unsafe HTML in quotations.

## Requirements

### Functional Requirements

- **FR-001**: Persist decision-oriented intake and seed URLs, with Russian/English
  source search by default and output language following the person.
- **FR-002**: Perform offline source readiness and request only task-needed setup;
  never treat stored credentials as proof of a working live connection.
- **FR-003**: Support Perplexity-led Reddit discovery as an explicitly selected paid
  source; preserve archive search as optional, and support targeted thread reading.
- **FR-004**: Read available Reddit post bodies/comments, targeted X conversations,
  YouTube transcript/comments and existing social sources without conflating types.
- **FR-005**: Follow leads and contradictions across both languages; record coverage
  and each supplied seed's disposition. Stop on sufficient evidence, budget, or an
  explicit documented gap, not just a single query per source.
- **FR-006**: Retain evidence, dates, author, source links, local raw artifact and
  verified/inferred/unsupported distinctions; source text cannot issue instructions.
- **FR-007**: Generate exactly two final user deliverables from a shared dossier:
  human HTML playbook and agent JSON, retaining internal evidence alongside them.
- **FR-008**: Validate cross-references and completeness; reject unsafe output,
  unsupported actions and false full-coverage declarations.
- **FR-009**: Bound live tests to owner's USD 1 allowance; record actual cost where
  available, conservative reservations otherwise; no automatic paid retry/fallback.
- **FR-010**: Preserve existing raw CLI compatibility and isolated failures; update
  public/operator docs, meaningful offline tests, full suite, selftest and final review.

### Key Entities

Research brief; selected source; seed disposition; evidence item; claim; action;
coverage result; cost receipt; shared research dossier; two final deliverables.

## Success Criteria

- **SC-001**: Complete briefs proceed without repeating answered questions; missing
  goal/service information produces one relevant next question at a time.
- **SC-002**: Every seed and requested source/language is accounted for in the two
  final documents, whether read successfully or explicitly unavailable.
- **SC-003**: Every supported claim/action has resolvable evidence, and both final
  documents agree on all claim/action IDs and completeness status.
- **SC-004**: An authorized live mixed-source test yields the final pair within
  USD 1; no superiority claim follows from fixtures or a single smoke test.
- **SC-005**: Desktop/tablet/mobile inspection and all mandatory project checks pass.

## Assumptions

The installed product remains an agent skill with Python retrieval tools; the host
agent reasons and synthesizes. No standalone background AI service, universal crawler,
account automation, publishing, or new paid subscriptions are implied. Public and
authorized sources only. Parallel remains a separately selected comparison baseline.
Monid feature 003 is implemented and retained as the preceding increment. Work on
this dirty checkout is intentional to preserve it; release integration with current
main, versioning and installation are separate from this qualified candidate.
