# Comparison case

case.json: schema_version, case_id, question, captured_on, historical, current_version_tested, owner_judgment_complete, winner, methods and limitations.

Each method: label, answer_file (relative to docs/comparison), source_sha256 (original full saved answer), excerpt_sha256 (curated file), extraction description. Digests establish identity, not source accuracy. No private absolute paths or account IDs.

No state transitions: immutable historical observation; any future matched live comparison is a separate case, not an overwrite.
