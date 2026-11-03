### Model comparison

| Model | Correct | Correct refusals | False refusals | Hallucinations | Median / p95 latency | Avg tokens in / out (thinking) | Cost per 1,000 queries (USD) |
|---|---|---|---|---|---|---|---|
| claude-sonnet-5-5 (medium) | 94% | 8/8 | 2/32 | 1/40 | 3.4s / 7.2s | 2,880 / 289 (42) | $8.65 |

Prices: https://platform.claude.com/docs/en/about-claude/pricing (checked 2026-10-29), standard API, no caching or batch discount.
Cost per query = input tokens x input price + output tokens (including thinking) x output price.
