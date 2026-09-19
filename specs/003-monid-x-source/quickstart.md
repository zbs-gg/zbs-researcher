# Quickstart: Validate Monid X Source

All automated scenarios use fixtures and make no external or paid call.

## 1. Focused contract tests

```bash
cd skills/deep-research
for test_file in \
  test_monid_x.py \
  test_fire.py \
  test_detect_state.py \
  test_provenance.py \
  test_entity_fanout.py \
  test_openrouter_routing.py; do
  python3 -m unittest discover -s tests -p "$test_file"
done
```

Expected: success, error, timeout, quoted/actual cost, no-fallback, key privacy,
and default-selection scenarios all pass.

## 2. Offline connector inspection

```bash
python3 skills/deep-research/scripts/deep-research.py --list-connectors
python3 skills/deep-research/scripts/deep-research.py --diagnose
```

Expected: `x` is default-off and reports only configured/absent Monid state;
`bluesky` is default-off but remains selectable.

## 3. Complete verification

```bash
cd skills/deep-research
python3 -m unittest discover -s tests
bash scripts/selftest.sh
```

Expected: the complete suite passes and selftest reports all ten checks passed
without a live provider or paid call.

## 4. Optional owner-authorized live smoke

Only after the operator explicitly approves the quoted Monid charge:

```bash
python3 skills/deep-research/scripts/deep-research.py \
  "one narrow current-practice query" \
  --fire x \
  --output-dir research/monid-x-smoke \
  --max-items 3
```

Verify stderr names Monid, route, and price before execution; inspect `x.md`
and `manifest.json`; do not publish or merge as part of this smoke.
