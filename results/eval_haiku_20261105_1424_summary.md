### eval_haiku_20261105_1424

Config: claude-haiku-5-5, effort medium, top 5 paragraphs, system_prompt_v2.md, hybrid retrieval. Graded 40/40 (40 by hand).

| Metric | Result |
|---|---|
| Correct (partial = 0.5) | 92% (37/40) |
| Fully correct | 92% (37/40) |
| Correct refusals (out-of-corpus) | 100% (8/8) |
| False refusals (answerable but refused) | 3% (1/32) |
| Citation accurate (manual) | 100% (31/31) |
| Hallucination rate (manual) | 0% (0/40) |
| Retrieval: expected para sent to Claude | 97% (31/32); rank 1 in 24 |
| Latency median / p95 | 2.5s / 6.7s |
| Avg tokens in / out | 2880 / 569 |

| Category | Correct | Questions |
|---|---|---|
| single | 95% (18/19) | 19 |
| multi | 78% (7/9) | 9 |
| not_found | 100% (7/7) | 7 |
| adversarial | 100% (5/5) | 5 |
