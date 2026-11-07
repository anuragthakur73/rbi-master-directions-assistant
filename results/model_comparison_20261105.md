### Model comparison

| Model | Correct | Correct refusals | False refusals | Hallucinations | Median / p95 latency | Avg tokens in / out (thinking) | Cost per 1,000 queries (USD) | (₹) |
|---|---|---|---|---|---|---|---|---|
| claude-sonnet-5-5 (medium) | 94% | 8/8 | 2/32 | 1/40 | 3.4s / 7.2s | 2,880 / 289 (42) | $8.65 | ₹820 |
| claude-haiku-5-5 (medium) | 94% | 8/8 | 1/32 | 0/40 | 2.5s / 6.7s | 2,880 / 569 (372) | $0.57 | ₹54 |
| claude-opus-5-5 (medium) | 94% | 8/8 | 1/32 | 0/40 | 5.6s / 10.6s | 2,874 / 465 (174) | $20.80 | ₹1,973 |

Prices: https://platform.claude.com/docs/en/about-claude/pricing (checked 2026-11-03), standard API, no caching or batch discount.
Cost per query = input tokens x input price + output tokens (including thinking) x output price.

### Correct by question type

| Question type | claude-sonnet-5-5 (medium) | claude-haiku-5-5 (medium) | claude-opus-5-5 (medium) |
|---|---|---|---|
| single | 18/19 | 18/19 | 18/19 |
| multi | 7.5/9 | 7.5/9 | 7.5/9 |
| not_found | 7/7 | 7/7 | 7/7 |
| adversarial | 5/5 | 5/5 | 5/5 |

Partial = 0.5. Routing only makes sense if a cheaper model matches the larger one on a whole question type (e.g. single-paragraph lookups) AND the type can be told apart before answering.

### Scale estimate

Estimate, not a measurement: 10,000 users x 3 queries a day x 22 working days = 660,000 queries a month, at the per-query cost measured above.

| Model | Est. API cost per month (USD) |
|---|---|
| claude-sonnet-5-5 (medium) | $5,709 |
| claude-haiku-5-5 (medium) | $378 |
| claude-opus-5-5 (medium) | $13,728 |

Excludes hosting, embeddings (run locally), retries and the Batch API / caching discounts.
