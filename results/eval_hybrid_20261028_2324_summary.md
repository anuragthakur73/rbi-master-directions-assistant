### eval_hybrid_20261028_2324

Config: claude-sonnet-5-5, effort medium, top 5 paragraphs, system_prompt_v1.md, hybrid retrieval. Graded 40/40 (40 by hand).

| Metric | Result |
|---|---|
| Correct (partial = 0.5) | 91% (36.5/40) |
| Fully correct | 88% (35/40) |
| Correct refusals (out-of-corpus) | 100% (8/8) |
| False refusals (answerable but refused) | 3% (1/32) |
| Citation accurate (manual) | 100% (31/31) |
| Hallucination rate (manual) | 0% (0/40) |
| Retrieval: expected para sent to Claude | 97% (31/32); rank 1 in 24 |
| Latency median / p95 | 2.8s / 6.1s |
| Avg tokens in / out | 2635 / 297 |

| Category | Correct | Questions |
|---|---|---|
| single | 92% (17.5/19) | 19 |
| multi | 83% (7.5/9) | 9 |
| not_found | 100% (7/7) | 7 |
| adversarial | 90% (4.5/5) | 5 |
