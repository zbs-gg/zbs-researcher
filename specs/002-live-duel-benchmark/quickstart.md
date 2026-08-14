# Quickstart Validation: Live Duel Benchmark

The implementation gate is entirely local. Do not use a real provider key to
validate code.

## 1. Focused benchmark tests

```bash
cd skills/deep-research
python3 -m unittest discover -s tests -p 'test_duel_benchmark.py'
```

Expected: frozen-suite, preflight, snapshot, paid-consent, retry, blinding,
paid-call cost reconciliation, claim-ledger validation, partial-report refusal,
veto, scoring, recursive directory privacy, and mocked five-pair tests pass.

## 2. Full repository checks

```bash
cd skills/deep-research
python3 -m unittest discover -s tests -p 'test_*.py'
bash scripts/selftest.sh
```

Expected: complete suite passes and selftest reports 10/10 with no paid calls.

## 3. Initialize the internal bundle without spending

```bash
python3 skills/deep-research/scripts/duel_benchmark.py init \
  --confirm-price-checked
```

Expected: one ignored `research/duel-v1-<timestamp>/` bundle contains frozen
suite, revision, versions, 24-hour window, budgets, provider booleans, and
`paid_authorized: false`. The price flag records the already completed manual
check; it does not authorize spend. No provider request occurs.

## 4. Validate the paid gate without executing it

After a fixture or approved completed Researcher run has been snapshotted:

```bash
python3 skills/deep-research/scripts/duel_benchmark.py run-parallel \
  --bundle research/duel-v1-<timestamp> --question q01
```

Expected: the command prints the exact question, Ultra, published USD 0.30
price, remaining budget, and the fact that no call occurred because
`--confirm-paid` was absent.

## 5. Official run remains a separate owner action

The five live Researcher/Parallel pairs are not part of implementation. Before
any `--confirm-paid` use, re-open the official pricing and processor pages,
inspect the initialized preflight, and obtain a separate explicit instruction
to start the paid phase.
