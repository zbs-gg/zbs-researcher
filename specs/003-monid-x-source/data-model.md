# Data Model: Monid X Source

## MonidRoute

Represents one compatible endpoint found and inspected immediately before a
paid X search.

- `provider`: Monid catalog provider slug.
- `endpoint`: Monid endpoint path.
- `description`: catalog description, if present.
- `price_type`: `PER_CALL` or `PER_RESULT`.
- `price_amount_usd`: normalized decimal-dollar amount.
- `price_currency`: expected to be `USD`; unknown currencies fail closed.
- `adapter`: locally validated input/output contract identifier.

Validation rules:

- Provider and endpoint must match a shipped adapter.
- The inspected record must match the discovered provider and endpoint.
- Price must be numeric, non-negative, and denominated in USD.
- No route means no paid request.

## MonidRunReceipt

Represents the auditable outcome of one explicit paid request.

- `run_id`: Monid run identifier.
- `status`: lifecycle status.
- `provider_http_status`: underlying provider response status.
- `route`: the selected `MonidRoute`.
- `result_count`: provider/Monid item count when present.
- `quoted_cost_usd`: route price available before the call.
- `actual_cost_usd`: normalized actual billing amount only when returned.
- `billing_unit`: original cost unit retained for audit.

State transitions:

```text
discovered -> inspected -> announced -> running -> completed
                                      \-> failed
                           running -> timed_out
```

Only `announced -> running` crosses the paid-call boundary.

## NormalizedXPost

Represents one public post rendered into the research artifact.

- `tweet_id`: source identifier, optional.
- `screen_name`: author handle, optional.
- `author_name`: display name, optional.
- `created_at`: original provider date, optional.
- `text`: post text, optional.
- `url`: deterministic X status URL when an identifier exists.
- `favorites`, `retweets`, `replies`, `quotes`, `bookmarks`, `views`: optional
  source engagement values.

Validation rules:

- Source values are preserved, not inferred.
- Missing fields render as unknown or are omitted.
- Freshness is recorded only when the date or status identifier parses safely.

## Call Manifest Extension

Existing call records retain their current fields. For the `x` source:

- `provider` is `monid`.
- `usage[0]` contains route and run metadata.
- `cost_receipt.status` is `actual`, `quoted`, or `unavailable`.
- `cost_receipt.amount` is never a quoted amount labeled as actual.
