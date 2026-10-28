### eval_prompt_v2_20261029_0020

Config: claude-sonnet-5-5, effort medium, top 5 paragraphs, system_prompt_v2.md, hybrid retrieval. Graded 40/40 (40 by hand).

| Metric | Result |
|---|---|
| Correct (partial = 0.5) | 94% (37.5/40) |
| Fully correct | 92% (37/40) |
| Correct refusals (out-of-corpus) | 100% (8/8) |
| False refusals (answerable but refused) | 6% (2/32) |
| Citation accurate (manual) | 100% (30/30) |
| Hallucination rate (manual) | 2% (1/40) |
| Retrieval: expected para sent to Claude | 97% (31/32); rank 1 in 24 |
| Latency median / p95 | 3.4s / 7.2s |
| Avg tokens in / out | 2880 / 289 |

| Category | Correct | Questions |
|---|---|---|
| single | 95% (18/19) | 19 |
| multi | 83% (7.5/9) | 9 |
| not_found | 100% (7/7) | 7 |
| adversarial | 100% (5/5) | 5 |
