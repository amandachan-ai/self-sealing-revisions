"""Read the episode JSONL and compute the design-doc metrics.

Metric 1 (scope calibration) is only *screened* here with a keyword check --
does the reflection mention the tool at all? Real scope classification needs a
separate labelled pass (design doc 5.1); this only answers the prior question
of whether the agent forms a tool-level hypothesis in the first place.
"""

import argparse
import json
import sys
from collections import defaultdict


def load(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _rate(rows, pred=lambda r: True):
    sel = [r for r in rows if pred(r)]
    return (sum(1 for r in sel if r["success"]) / len(sel)) if sel else float("nan")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--bucket", type=int, default=10)
    args = ap.parse_args(argv)

    rows = load(args.jsonl)
    if not rows:
        sys.exit("no rows in {}".format(args.jsonl))

    arms = defaultdict(list)
    for r in rows:
        arms[r["arm"]].append(r)

    print("=" * 74)
    print("{:<10} {:>4} {:>8} {:>8} {:>8} {:>9} {:>8}".format(
        "arm", "n", "success", "ascii", "cjk", "harness", "exhaust"))
    print("-" * 74)
    for arm, rs in sorted(arms.items()):
        harness_bad = sum(1 for r in rs if r["invalid"])
        exhausted = sum(1 for r in rs if r["terminated_reason"] == "max_turns")
        usable = [r for r in rs if not r["invalid"]]
        print("{:<10} {:>4} {:>8.2f} {:>8.2f} {:>8.2f} {:>9} {:>8}".format(
            arm, len(rs), _rate(usable),
            _rate(usable, lambda r: not r["is_cjk"]),
            _rate(usable, lambda r: r["is_cjk"]),
            harness_bad, exhausted))

    # -- metric 4: capability loss on the tasks the tool handles fine -------
    if "natural" in arms and "broad" in arms:
        a = _rate([r for r in arms["natural"] if not r["invalid"]], lambda r: not r["is_cjk"])
        b = _rate([r for r in arms["broad"] if not r["invalid"]], lambda r: not r["is_cjk"])
        print("\ncapability loss on ASCII tasks (natural - broad): {:+.1f} pp".format(
            (a - b) * 100))

    # -- metric 3: evidence blackout ---------------------------------------
    print("\nsearch_docs calls per episode, bucketed by {}:".format(args.bucket))
    for arm, rs in sorted(arms.items()):
        rs = sorted(rs, key=lambda r: r["episode"])
        buckets = defaultdict(list)
        for r in rs:
            buckets[(r["episode"] - 1) // args.bucket].append(r["search_docs_calls"])
        line = "  ".join(
            "{:>5.2f}".format(sum(v) / len(v)) for _, v in sorted(buckets.items()))
        print("  {:<10} {}".format(arm, line))

    # -- rule violations (injected arms) -----------------------------------
    for arm in ("broad", "narrow"):
        if arm in arms:
            rs = arms[arm]
            v = [r for r in rs if r.get("rule_violation")]
            print("\n{} arm rule violations: {}/{} ({:.2f})".format(
                arm, len(v), len(rs), len(v) / len(rs)))
            if v:
                eps = [r["episode"] for r in v]
                print("  episodes: {}".format(eps))

    # -- metric 1 screen: does the agent blame the tool at all? -------------
    print("\nreflections written:")
    for arm, rs in sorted(arms.items()):
        refl = [r for r in rs if r.get("reflection_written")]
        named = [r for r in refl if "search_docs" in (r["reflection_written"] or "")]
        print("  {:<10} {:>3} reflections, {:>3} name search_docs".format(
            arm, len(refl), len(named)))
        for r in named[:4]:
            print("      ep{}: {}".format(r["episode"], r["reflection_written"][:150]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
