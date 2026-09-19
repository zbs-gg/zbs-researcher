# Dossier v1

Brief: goal, decision, audience, success_criteria[], languages[] (ru/en),
output_language, as_of (ISO date), sources[], seeds[] (public HTTPS URLs), budget_usd.

Dossier: schema_version=1, brief, summary, status=complete|partial, evidence[],
claims[], actions[], coverage[], seeds[], open_questions[].

Evidence: id, source, kind (post/comment/thread/transcript/web/model_summary), url,
author, published_at (ISO date/timestamp or null), retrieved_at (ISO), language, text, artifact
(contained relative path), verification=direct|model_reported, limitations[].
Claim: id, text, evidence_ids[], confidence=supported|inference|unsupported,
fact_date (ISO date or null), caveat. Supported requires dated direct evidence.
Action: id, title, steps[], why, claim_ids[], measure, stop_when. No unsupported
claims drive actions; inference-driven actions must explicitly be experiments.
Coverage: source, language, status=covered|partial|unavailable, evidence_ids[], note.
Seed disposition: url, status=read|partial|unavailable, evidence_ids[], note.

Source extra fields (comment parent, approximate date precision, native source
ID) are preserved. Seed matching uses validated platform identities (including
YouTube short URLs); parent posts cannot satisfy a specific comment seed.
Final export targets cannot also be raw artifacts, including through symlinks.

State: brief -> source work -> dossier -> validated pair. Every requested source
and language and seed must have coverage/disposition. Missing or partial sources
force partial output. The host judges semantic truth; validation checks structure,
cross-references, evidence type/date and existing contained raw artifact paths.
