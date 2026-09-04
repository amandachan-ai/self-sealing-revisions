"""Probe whether the current credentials can make a real Messages API call.

Run this before anything else. It makes one minimal request and reports what
actually happened, so the auth question is answered by the API rather than by
guessing.

    python -m selfsealing.check_auth
"""

import os
import sys


def main():
    print("credential sources visible to the SDK")
    print("-" * 60)
    for var in (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_PROFILE",
        "ANTHROPIC_BASE_URL",
    ):
        val = os.environ.get(var)
        if val:
            shown = val if var in ("ANTHROPIC_PROFILE", "ANTHROPIC_BASE_URL") else "set"
            print("  {:<22} {}".format(var, shown))
        else:
            print("  {:<22} -".format(var))

    cfg = os.path.expanduser(
        os.environ.get("ANTHROPIC_CONFIG_DIR", "~/.config/anthropic")
    )
    creds = os.path.join(cfg, "credentials")
    if os.path.isdir(creds):
        profiles = sorted(f[:-5] for f in os.listdir(creds) if f.endswith(".json"))
        print("  {:<22} {}".format("oauth profiles", ", ".join(profiles) or "(none)"))
    else:
        print("  {:<22} - (no {} )".format("oauth profiles", creds))

    print()
    try:
        import anthropic
    except ImportError:
        sys.exit("anthropic SDK not installed -- see SETUP.md")

    print("making one minimal request ...")
    try:
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=16,
            messages=[{"role": "user", "content": "Reply with the single word: ok"}],
        )
    except Exception as exc:  # noqa: BLE001 -- we want to show the user anything
        print("FAILED: {}: {}".format(type(exc).__name__, exc))
        print()
        print("If this says authentication_error / permission_error, the")
        print("credentials do not grant Messages API access. See SETUP.md.")
        return 1

    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    print("OK -- model={} stop_reason={}".format(resp.model, resp.stop_reason))
    print("     reply={!r}".format(text.strip()))
    print("     usage in={} out={}".format(resp.usage.input_tokens, resp.usage.output_tokens))
    print()
    print("Messages API access confirmed. Note the usage numbers above: this")
    print("call was billed somewhere. Confirm which account before scaling.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
