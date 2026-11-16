# Week 5: UX fallbacks, polish and deploy

**Goal (from the build guide):** a public URL anyone can use, tested by 3+ people, with their feedback captured.
**Exit criteria:** public URL works · 3+ people have tested it · feedback in `docs/user_testing_notes.md`.

## 1. What was built (7 Nov 2026)

| Guide item | Before Week 5 | Now | Where |
|---|---|---|---|
| Nothing relevant retrieved | "Not found" info box | Same, plus scope hint (other directions, live rates, individual cases) | `app.py` `render_result` |
| Low-confidence / partial answer | Not handled | Warning when an answer has **no citation**, or cites a paragraph that **was not retrieved** (possible hallucinated citation). Clarifying questions labelled as such | `guards.review_answer` |
| API error or timeout | Error text, question lost | Plain message, question kept on screen with **Try again**; 60 s timeout, 2 automatic retries; "busy" message for 5xx/529 | `app.py` `ask` |
| User pastes personal data | Footer note only | Question **not sent to Claude** if it looks like PAN, Aadhaar, mobile, email, card or account number; logged redacted | `guards.find_personal_data`, `redact` |
| Out of scope (legal opinion, live rates) | Prompt v2 rule 3 + "not found" | Unchanged (prompt is the Week 3/4 evaluated version); UI explains scope on refusal | prompt v2 |
| Clickable citations | Raw excerpt dump | **Cited paragraphs** panel: one expander per cited paragraph with its RBI text, pages, direction date | `app.py`, `answer.py` returns `excerpts` |
| Sources-loaded list with dates | Short names + date | Full title, RBI reference, "updated as on" date | sidebar |
| Standing disclaimer | Footer caption | Banner at the top of every page | `DISCLAIMER` |
| Thumbs up/down to log | None | 👍/👎 on every answer, optional "what was wrong?" box → `logs/feedback.csv` (join on `run_id`) | `qa_log.log_feedback` |
| API key in secrets | `.env` | `.env` locally; Streamlit Secrets in the cloud (no code change: root-level secrets become environment variables) | |
| Rate limit / usage cap | None | 20 questions per session, 200 per day across all users, 500-character question limit; optional passcode; owner-only log download | `guards.UsageCounter`, settings below |
| Deployable data | Index git-ignored | `data/processed/chunks.jsonl` committed; the app builds the Chroma index on first start if missing | `.gitignore`, `embed_store.ensure_store` |

Design choice to note in the retrospective: the partial-answer flag is a **deterministic check after the model** (citations vs retrieved paragraphs), not a new prompt rule, so the Week 3/4 scores for prompt v2 + Haiku still describe what is deployed.

## 2. Test locally (about 30 min)

```
conda activate rbi-rag
streamlit run scripts/app.py
```
Check each row and note pass/fail in your build journal:

| # | Do this | Expect |
|---|---|---|
| 1 | Click "maximum LTV for a gold loan of ₹4 lakh" | Cited answer, **Cited paragraphs** expander shows CF Para 44 text, 👍/👎 below |
| 2 | Click 👎, type a comment, click **Send comment** | "✅ Comment saved"; two rows in `logs/feedback.csv` (rating, then rating + comment) |
| 3 | "What is the current repo rate?" | Blue "couldn't find" box with scope hint |
| 4 | "Borrower PAN ABCDE1234F, can we give a gold loan?" | Red "Not sent" box; `logs/qa_log.csv` row has outcome `blocked` and `[REDACTED]` |
| 5 | "Home loan of ₹25,00,000 on a ₹30 lakh flat: is it within LTV?" | Answered normally (amounts with commas are not flagged) |
| 6 | Turn Wi-Fi off, ask anything | "Couldn't reach the Claude API" + **Try again**; Wi-Fi on, click it → answer |
| 7 | Paste 600 characters | "Please keep questions under 500 characters" |
| 8 | Add `SESSION_QUESTION_LIMIT=2` to `.env`, restart, ask 3 questions | Third is refused. Remove the line afterwards |
| 9 | Phone: run `streamlit run scripts/app.py --server.address 0.0.0.0`, open the "Network URL" on your phone (same Wi-Fi) | Readable, buttons tappable |

If any row fails, send me the screen or the error and I'll fix it before you deploy.

## 3. Commit

In VS Code, commit these together ("Week 5: fallbacks, trust features, usage caps, deploy prep"):
`scripts/app.py`, `scripts/guards.py`, `scripts/answer.py`, `scripts/embed_store.py`, `scripts/qa_log.py`, `.gitignore`, `data/processed/chunks.jsonl`, `docs/week5_plan.md`, `docs/user_testing_notes.md`.
Also still uncommitted from Week 4: `docs/eval_log.md` and `results/eval_opus_20261105_2043.csv`.
Before pushing, check the commit does **not** include `.env` (it is git-ignored; confirm in the Source Control list).

## 4. Protect the bill (before the link is public)

1. Claude Console → create a **separate API key** just for the deployed app (so you can revoke it without breaking your laptop setup).
2. Claude Console → set a low **monthly spend limit** for the workspace (e.g. $5). At Week 4's measured ~$0.57 per 1,000 Haiku queries, the in-app 200/day cap is about $3.50/month even if fully used every day (my arithmetic from your Week 4 number; verify against the Console after a week).

## 5. Deploy on Streamlit Community Cloud

1. Go to share.streamlit.io and sign in with GitHub (account `anuragthakur73`). You do this step yourself.
2. **Create app** → deploy from GitHub → repo `anuragthakur73/rbi-master-directions-assistant`, branch `main`, main file path `scripts/app.py`. Pick a custom subdomain, e.g. `credit-assist-rbi`.
3. **Advanced settings** → Python version **3.11** (matches `requirements.txt` and your Week 1–4 results).
   Secrets (TOML, keep keys at the root level, not under a `[section]`):
   ```
   ANTHROPIC_API_KEY = "sk-ant-..."
   DAILY_QUESTION_LIMIT = "200"
   SESSION_QUESTION_LIMIT = "20"
   ADMIN_KEY = "choose-a-long-random-string"
   # APP_PASSCODE = "..."   # uncomment to limit the demo to invited testers
   # ANTHROPIC_WORKSPACE_ID = "wrkspc_..."   # only if your key needs it
   ```
4. Deploy. The first start installs packages, downloads the embedding model (~130 MB) and builds the index from `chunks.jsonl`, so expect a few minutes. Watch **Manage app → logs**.
5. Smoke test on the live URL: rows 1, 3, 4 and 9 from section 2. Then open **Owner** in the sidebar, enter the admin key, and download `qa_log.csv` to confirm logging works.

**Platform facts, checked 7 Nov 2026 (Streamlit docs):** root-level secrets are also exposed as environment variables; apps with no traffic for 12 hours go to sleep and wake when someone visits; resource limits are documented as approximate and changeable without notice. Third-party write-ups put memory at about 1 GB; I couldn't confirm a current official figure, so watch the logs for "over its resource limits".

**Known limits to state honestly in the README and retrospective:**
- Cloud logs and the daily counter reset when the app restarts or sleeps. Download logs after each test session (Owner panel). Persistent storage (e.g. Google Sheets) is a V2 item.
- The personal-data check is pattern-based: it will miss some data (names, addresses) and can flag a 10+ digit amount written without commas.
- Questions are sent to the Anthropic API; only public RBI text is in the corpus.

## 6. User testing (3–5 people)

Combine with the staff conversations from `docs/user_evidence_plan.md` (same people, same ground rules: personal capacity, no customer data, no employer channels).

1. Send the link with one line: what it is, that it's a personal portfolio project, not to enter customer data.
2. For at least one person, watch them use it (screen-share is fine) **without helping**. Note where they hesitate.
3. Ask each: what did you expect to happen? Would you trust the answer? What would you check before acting on it?
4. Download `qa_log.csv` and `feedback.csv` the same day.
5. Fill `docs/user_testing_notes.md`. Record only what you actually saw and heard.

## 7. Journal (3 lines, Sunday routine)

Decided · broke · learned. Suggested first line: "Chose a post-answer citation check over a prompt change so the evaluated prompt + model stay what's deployed."
