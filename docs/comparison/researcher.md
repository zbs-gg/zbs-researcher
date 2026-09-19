> Historical answer, 2026-08-14. Not a current product recommendation or a 0.7.0 benchmark.
> See [comparison and limitations](README.md). Full saved synthesis retained.

# Choose the owner of state first; “memory features” are the wrong comparison

## Recommendation

Choose **Mem0** when an existing agent runtime already owns orchestration and you want a replaceable memory service that extracts, stores, and searches user or agent facts. Choose **Letta** when you want the agent itself to be a durable stateful process and are willing to adopt Letta’s runtime, memory blocks, archival tools, and persistence model. Build a **custom layer** when provenance, tenant boundaries, deletion, deterministic policy, repository-aware state, or rollback are product requirements rather than implementation details.

Do not choose from benchmark leaderboards alone. The strongest current primary evidence in this run is a Mem0 reproducibility dispute: a maintainer says the hosted platform uses improved “Contextual ADD” and search, while users report that the open-source system cannot reproduce the published LoCoMo scores. That means “Mem0 performance” is not one stable object; deployment and product tier are part of the result. **T1/T2, updated March 23, 2026.** [mem0ai/mem0 #2800](https://github.com/mem0ai/mem0/issues/2800)

## The products own different boundaries

Mem0 presents add, search, and update as memory-layer operations over an existing application. Its current documentation shows scoped search with filters such as `user_id`, a managed platform, an open-source SDK/self-host path, and optional graph backends. This makes it a natural sidecar for a coding agent whose planner, tools, permissions, and run loop already exist. **T1 product documentation/repository, current retrieval August 2026.** [Mem0 overview](https://docs.mem0.ai/platform/overview), [mem0ai/mem0](https://github.com/mem0ai/mem0)

Letta’s boundary is larger. Its official docs describe memory blocks as structured, editable state kept in the context window; archival memory is out-of-context semantic storage accessed through tools; messages, reasoning, and tools are persisted as agent state. Shared blocks can update across multiple agents. This is not merely a vector-store adapter—it is an opinionated stateful-agent runtime. **T1 official documentation, current retrieval August 2026.** [Memory blocks](https://docs.letta.com/v1-sdk/memory/memory-blocks), [Archival memory](https://docs.letta.com/v1-sdk/memory/archival-memory), [Stateful agents](https://docs.letta.com/v1-sdk/concepts/stateful-agents/), [Shared memory](https://docs.letta.com/v1-sdk/memory/shared-memory)

A custom layer owns only what the team deliberately implements. That can be an advantage for coding agents: commits, decisions, tests, file paths, user preferences, and task state have different truth and invalidation rules. It is also a liability because the team must implement extraction, conflict handling, retention, deletion, evaluation, migrations, and operational tooling itself.

## Failures practitioners are actually seeing

### Mem0: isolation bugs can become privacy bugs

Two July 2026 issues show a concrete scope failure. One reports that `addMemory` excludes custom metadata such as `app_id` from partitioning, creating cross-context contamination in multi-app setups. A related TypeScript issue has maintainer triage confirming that `buildSessionScope()` hardcodes `agent_id`, `run_id`, and `user_id` instead of all filters. Another open issue reports entity links crossing `user_id` and `agent_id` boundaries. These are not abstract retrieval-quality complaints: in a multi-tenant system they can change whose memory an agent sees. **T1 primary issues and maintainer triage, June–July 2026.** [#5121](https://github.com/mem0ai/mem0/issues/5121), [#5812](https://github.com/mem0ai/mem0/issues/5812), [#5439](https://github.com/mem0ai/mem0/issues/5439)

The production control is therefore not “remember to pass a user id.” The application must test every write and read path with organisation, application, user, agent, and run scopes; probe graph/entity edges separately from vector search; and fail closed when required scope is absent.

### Mem0: successful transport can still mean no memory was saved

OpenMemory users reported a Claude client connecting and exchanging messages while memories did not appear in the UI or list API; one called it “a critical bug.” The thread also exposes MCP/SSE/stdio gateway sensitivity. **T2 reproducible practitioner reports, updated March 26, 2026.** [mem0ai/mem0 #2712](https://github.com/mem0ai/mem0/issues/2712)

This argues for end-to-end receipts: after every write, record the durable memory id, scope, extraction decision, and a read-after-write probe. A green MCP connection is not evidence that memory persisted.

### Mem0: hosted and open-source results diverge

In the LoCoMo issue, the maintainer explicitly says hosted-platform improvements in addition and search explain lower open-source scores. Users ask for verifiable reproduction details. **T1/T2, March 2026.** [#2800](https://github.com/mem0ai/mem0/issues/2800)

This is both a benchmark and procurement failure mode. A team can validate one deployment and ship another. Treat hosted Mem0, open-source Mem0, chosen models, vector store, graph option, and extraction configuration as separate systems in evaluation.

### Letta: runtime and provider coupling are part of memory reliability

A 2025 issue reports Azure models failing in Letta’s then-current release; another user independently reproduced the failure and linked it to deployment-specific configuration. **T2 practitioner report with maintainer acknowledgement, updated September 7, 2025.** [letta-ai/letta #2582](https://github.com/letta-ai/letta/issues/2582)

For Letta, a provider/API regression can impair the agent’s ability to edit memory, not just produce a response. Production qualification must include the exact model/provider combination, tool-calling behavior, context pressure, and recovery after failed memory operations.

### Letta: migration is more than importing messages

A July 2026 migration request argues that importing only raw conversations loses importance scores, entity relationships, and temporal ordering. The issue remains open. **T2 practitioner/design evidence, July 9, 2026.** [letta-ai/letta #3237](https://github.com/letta-ai/letta/issues/3237)

The run did **not** find a well-corroborated current Letta issue proving routine silent memory loss. Claims that Letta necessarily loses nuance through compression came from secondary commentary, not a current primary incident, so they are not used as a deciding fact here.

## When each choice is justified

### Choose Mem0 when

- the application already has a stable agent loop and wants memory behind an API or SDK;
- user preferences and extracted facts are the main durable unit;
- the team can run strict scope/isolation tests and read-after-write receipts;
- hosted versus open-source behavior is evaluated separately;
- swapping the memory subsystem later matters more than giving the memory layer control of the agent.

Reject or delay Mem0 when cross-tenant isolation cannot be independently proven, benchmark results cannot be reproduced on the intended tier, or hosted/self-hosted boundaries conflict with privacy and cost requirements.

### Choose Letta when

- the product is genuinely a long-lived stateful agent, not a stateless workflow with recall;
- always-visible structured memory blocks plus tool-retrieved archival memory match the mental model;
- persistent messages, reasoning, tools, and agent state should live under one runtime;
- the team accepts Letta’s lifecycle, migration model, and model/tool-call coupling.

Reject or delay Letta when an existing runtime must remain authoritative, when agent state must be portable in a simpler open schema, or when model/provider variance cannot be qualified end to end.

### Build custom when

- memory must cite its origin, owner, confidence, validity window, and superseding fact;
- deletion, export, access control, or local-only processing is contractual;
- coding-agent memory must bind to repository SHA, branch, file, test result, or decision state;
- deterministic write rules and rollback matter more than automatic extraction;
- a narrow set of memory types can be evaluated much more rigorously than a general platform.

Do not build custom merely to avoid a dependency. The minimum real system needs a typed schema, write gate, identity/scope model, conflict and staleness policy, retrieval/reranking, citations, delete/export, observability, migrations, and task-level evaluation. If the team will not own those, a product is safer.

## What people repeat that is no longer safe to say

- **“A benchmark score tells you which memory system is best.”** The Mem0 reproduction dispute shows that product tier and configuration can change the score. Benchmark fit must be verified on the deployment you will ship.
- **“User-level filtering solves isolation.”** Current Mem0 issues show custom app scope and graph/entity edges can escape a narrow hardcoded scope model.
- **“Letta and Mem0 are interchangeable memory libraries.”** Letta owns a stateful agent runtime; Mem0 is primarily a pluggable memory layer. Comparing checkbox counts hides the main architecture decision.
- **“Long context removes the need for memory.”** None of the systems can rely on unbounded context without latency, cost, relevance, and state-validity problems; but persistent storage alone does not solve write quality or stale facts.

## What remains unresolved

- Reliable **write policy**: deciding what deserves memory without storing guesses, prompt injection, or transient state.
- **Contradiction and temporal truth**: replacing or scoping old facts without erasing useful history.
- **Task-level evaluation**: translating recall benchmarks into fewer coding mistakes, better decisions, or successful long-running work.
- **Memory poisoning and trust**: preserving provenance and trust at write time so later retrieval does not launder bad input.
- **Migration fidelity**: moving derived state, not just messages or vectors, across vendors and runtimes.
- **Forgetting and deletion**: enforcing user deletion across vector, graph, cache, derived summaries, backups, and shared blocks.
- **Repository drift for coding agents**: preventing a once-correct memory from surviving a code or branch change that invalidates it.

These problems are not resolved by picking Mem0, Letta, or PostgreSQL. The choice determines who owns them and how visible the failures will be.
