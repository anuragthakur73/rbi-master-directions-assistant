"""
Week 1 - Check that the API key in .env works (replaces test_key.py at the repo root).

Run from the repo root:  python scripts/check_api_key.py
Makes one tiny call to the cheapest model; costs a fraction of a US cent.
Uses the same client setup as the app, so ANTHROPIC_WORKSPACE_ID is honoured if your key needs it.
"""
import sys

import anthropic

from answer import make_client   # also loads .env from the repo root

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    msg = make_client().messages.create(
        model="claude-haiku-5-5",
        max_tokens=50,
        messages=[{"role": "user", "content": "Say hello in one line."}],
    )
    print("API key works. Reply:", msg.content[0].text)
except anthropic.AuthenticationError:
    sys.exit("The API key was rejected. Check ANTHROPIC_API_KEY (and ANTHROPIC_WORKSPACE_ID) in .env.")
