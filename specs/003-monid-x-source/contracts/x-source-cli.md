# CLI Contract: Direct X via Monid

## Selection

```bash
python3 skills/deep-research/scripts/deep-research.py \
  "SHORT X-SPECIFIC QUERY" \
  --fire x \
  --output-dir RUN_DIR \
  --max-items 10
```

`x` is never selected by a default run. It is available only when
`MONID_API_KEY` or a supported Monid key file is configured.

## Paid-boundary stderr

After free discovery and inspection and before the paid run, stderr contains a
single human-readable line naming:

- `Monid`;
- the underlying provider and endpoint;
- the quoted price and pricing unit.

No such line means the paid request has not begun. Unknown/incompatible routes
must fail before this boundary.

## Success artifact

`RUN_DIR/x.md` contains:

1. Query and selected route.
2. Quoted price with no unsupported “actual” wording.
3. Up to `--max-items` posts with available text, handle, date, link, and
   engagement values.
4. An explicit no-results line when the provider returns none.

## Machine envelope

stdout remains exactly one JSON object with the existing fire contract:

```json
{
  "source": "x",
  "path": ".../x.md",
  "items": 10,
  "status": "ok",
  "provenance": {
    "source": "x",
    "query": "SHORT X-SPECIFIC QUERY",
    "items": 10,
    "freshness_hours": 3.0,
    "web_index_reachable": "no",
    "reason": "posted 3h ago — not yet web-indexed"
  }
}
```

## Manifest receipt

The appended call record names `provider: "monid"`. Its usage metadata names
the underlying provider, endpoint, and run ID. `cost_receipt.status` is:

- `actual` only when Monid exposes actual billing evidence;
- `quoted` when only the catalog/run price is known;
- `unavailable` when neither is available or the call fails before metadata.

## Failure behavior

- Missing key: command exits 2 before creating a run or calling Monid.
- No compatible route: `x.ERROR.md`, status `error`, no paid request.
- Poll timeout, Monid failure, or provider HTTP failure: `x.ERROR.md`, status
  `error`; other connectors remain unaffected.
- Failed `grok`: does not call `x`; its error explains that `--fire x` is a
  separate explicit choice when configured.
