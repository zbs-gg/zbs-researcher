# Quickstart Validation: Parallel Baseline and Claim Freshness

All automated checks are local and must not call paid providers.

## 1. Focused evaluation tests

```bash
cd skills/deep-research
python3 -m unittest discover -s tests -p 'test_eval_harness.py'
```

Expected: the default path makes no Parallel call, missing/failed baselines are
unavailable rather than zero, singular/plural excerpts score equally, and
corporate social-domain pages do not count as native conversation.

## 2. Full repository checks

```bash
cd skills/deep-research
python3 -m unittest discover -s tests -p 'test_*.py'
bash scripts/selftest.sh
```

Expected: the full suite passes and self-test reports all ten steps, including
the no-paid-call contract and the required investigate playbook ordering.

## 3. Default evaluation remains free

Use a stored run directory and an empty temporary secrets directory:

```bash
DEEP_RESEARCH_SECRETS_DIR=/absolute/empty/secrets \
python3 skills/deep-research/scripts/eval_harness.py \
  "question" --beast-dir /absolute/stored/run
```

Expected: the researcher side is scored; the web-index baseline may state that
no key is configured; Parallel is explicitly reported as not used.

## 4. Paid operator acceptance (manual and optional)

Only after the operator confirms the current listed price and intentionally
chooses the paid opponent:

```bash
python3 skills/deep-research/scripts/eval_harness.py \
  "question" --beast-dir /absolute/stored/run \
  --baseline parallel --processor ultra \
  --artifact-dir /private/runtime/parallel-attempt
```

Expected before network activity: the CLI names Parallel, the processor, and
the per-run list price. The resulting ledger names the opponent and preserves
an unavailable state if the task cannot finish. The private directory contains
raw JSON, a readable answer, normalized score receipts, and run/timing/cost
metadata with only relative internal paths. This step is not part of CI and
must never be run with a real key merely to validate code.

## 5. Claim-grading report check

Run the investigate playbook on fixtures or an approved real question and
inspect `synthesis.md`:

- every load-bearing claim carries a fact date, tier, quote, author, and link;
- no T4 trace supports a conclusion;
- claims older than 12 months without fresh T1/T2 confirmation appear only in
  the stale/historical section;
- unresolved questions are stated instead of filled by inference.
