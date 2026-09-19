# Offline storage contract

- prepare --brief FILE --project-root PROJECT: existing inputs; return run_dir, raw_dir, processed_dir, dossier, project_index, readiness and zero network calls. Create one run and update only PROJECT/research indexes.
- finalize --run-dir RUN: validate processed/dossier.json for layout 2; dossier.json for legacy. Produce existing pair, inventory, and local index for RUN directly under research/. Never relocate sources.
- index --project-root PROJECT: rebuild listing offline without modifying runs or scanning outside PROJECT/research.
- Refuse non-owned index collisions, symlink escapes, wrong-layout evidence and invalid final data.
- If index refresh fails after committing a run/export, preserve and return its paths with index_error and project_index null. Repair the index without reallocating the run.
- New evidence paths must be in raw/ or processed/ without symlink components. Dossier, finals and metadata cannot serve as evidence artifacts.
