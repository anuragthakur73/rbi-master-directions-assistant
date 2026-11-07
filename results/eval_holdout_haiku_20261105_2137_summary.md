### eval_holdout_haiku_20261105_2137

Config: claude-haiku-5-5, effort medium, top 5 paragraphs, system_prompt_v2.md, hybrid retrieval. Graded 15/15 (15 by hand).

| Metric | Result |
|---|---|
| Correct (partial = 0.5) | 100% (15/15) |
| Fully correct | 100% (15/15) |
| Correct refusals (out-of-corpus) | 100% (2/2) |
| False refusals (answerable but refused) | 15% (2/13) |
| Citation accurate (manual) | 100% (11/11) |
| Hallucination rate (manual) | 7% (1/15) |
| Retrieval: expected para sent to Claude | 92% (12/13); rank 1 in 9 |
| Latency median / p95 | 3.2s / 4.2s |
| Avg tokens in / out | 2470 / 496 |

| Category | Correct | Questions |
|---|---|---|
| single | 100% (7/7) | 7 |
| multi | 100% (4/4) | 4 |
| not_found | 100% (2/2) | 2 |
| adversarial | 100% (2/2) | 2 |
