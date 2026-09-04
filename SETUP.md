# Setup

Python 3.9+ (built against 3.9.6).

```bash
cd self-sealing-revisions
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Offline tests — no credentials, no network, no spend

```bash
python -m unittest discover -s tests -v
```

All 21 must pass before spending anything. They cover the environment's ground
truth (P0) and the agent loop's mechanics (P1).

## Authentication — browser login

No API key. `ant auth login` opens a browser, exchanges for a short-lived
token, and stores a profile the SDK reads automatically.

```bash
brew install anthropics/tap/ant
xattr -d com.apple.quarantine "$(brew --prefix)/bin/ant"

ant auth login          # browser opens; pick org + workspace
ant auth status         # shows which credential source is active
```

The code constructs a bare `anthropic.Anthropic()`, so it picks the profile up
with no env var set.

> **Trap:** an exported `ANTHROPIC_API_KEY` silently outranks every profile —
> even an empty string. If `ant auth status` shows a profile but requests hit
> the wrong account, `unset ANTHROPIC_API_KEY` (do not set it to `""`).

### Verify before building on it

```bash
python -m selfsealing.check_auth
```

This makes one minimal request and prints what actually happened, including
token usage. Do not skip it — a Claude Pro/Max **subscription** and the
**Claude Developer Platform** (programmatic Messages API, billed per token)
are separate entitlements. Claude Code running on a subscription does not by
itself mean a Python script can call `client.messages.create()` on that same
subscription.

If the probe fails with `authentication_error` / `permission_error`, the
credentials do not grant Messages API access and this experiment needs a
developer-platform workspace instead.

If the probe succeeds, confirm **which account the usage landed on** before
scaling to thousands of episodes — see "Before the full run" below.

## P1 smoke test — real model, small spend

```bash
python -m selfsealing.smoke --model claude-sonnet-5 --effort high -n 5
python -m selfsealing.smoke --model claude-sonnet-5 --effort high -n 5 --inject-broad
```

Haiku rejects the effort parameter — omit it:

```bash
python -m selfsealing.smoke --model claude-haiku-4-5 -n 5
```

Read the transcripts. Confirm all four before scaling:

1. the reflection step fires and writes a rule
2. an injected rule visibly changes behaviour
3. `invalid` is ~0 (a non-zero rate means tool calls are leaking into prose)
4. the oracle's verdict matches your own reading

## Before the full run

The full experiment is roughly 4,000 multi-turn episodes. Two things to settle
first, neither of which the code can settle for you:

- **Entitlement.** Confirm the credentials in use are meant for bulk
  programmatic access, and that the account's terms cover automated research
  workloads at this volume. Subscription plans are metered for interactive use
  and can rate-limit or restrict scripted traffic.
- **Cost.** Run `client.messages.count_tokens()` over a representative episode
  and multiply, rather than trusting an estimate.
