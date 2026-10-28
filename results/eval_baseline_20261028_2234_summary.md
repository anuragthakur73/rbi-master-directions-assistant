### eval_baseline_20261028_2234

Config: claude-sonnet-5-5, effort medium, top 5 paragraphs, system_prompt_v1.md. Graded 40/40 (40 by hand).

| Metric | Result |
|---|---|
| Correct (partial = 0.5) | 82% (33/40) |
| Fully correct | 78% (31/40) |
| Correct refusals (out-of-corpus) | 100% (8/8) |
| False refusals (answerable but refused) | 9% (3/32) |
| Citation accurate (manual) | 100% (29/29) |
| Hallucination rate (manual) | 0% (0/40) |
| Retrieval: expected para sent to Claude | 88% (28/32); rank 1 in 22 |
| Latency median / p95 | 2.8s / 6.1s |
| Avg tokens in / out | 2565 / 277 |

| Category | Correct | Questions |
|---|---|---|
| single | 82% (15.5/19) | 19 |
| multi | 83% (7.5/9) | 9 |
| not_found | 100% (7/7) | 7 |
| adversarial | 60% (3/5) | 5 |
