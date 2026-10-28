### eval_holdout_20261029_0032

Config: claude-sonnet-5-5, effort medium, top 5 paragraphs, system_prompt_v2.md, hybrid retrieval. Graded 15/15 (15 by hand).

| Metric | Result |
|---|---|
| Correct (partial = 0.5) | 83% (12.5/15) |
| Fully correct | 80% (12/15) |
| Correct refusals (out-of-corpus) | 100% (2/2) |
| False refusals (answerable but refused) | 15% (2/13) |
| Citation accurate (manual) | 100% (11/11) |
| Hallucination rate (manual) | 0% (0/15) |
| Retrieval: expected para sent to Claude | 92% (12/13); rank 1 in 9 |
| Latency median / p95 | 2.8s / 4.1s |
| Avg tokens in / out | 2470 / 264 |

| Category | Correct | Questions |
|---|---|---|
| single | 71% (5/7) | 7 |
| multi | 88% (3.5/4) | 4 |
| not_found | 100% (2/2) | 2 |
| adversarial | 100% (2/2) | 2 |
