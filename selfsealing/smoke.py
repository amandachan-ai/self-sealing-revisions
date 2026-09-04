"""P1 acceptance gate: run a handful of real episodes and print full transcripts.

This exists to be read by a human, not to produce data. Per the design doc,
do not scale up until you have eyeballed ~10 transcripts and confirmed:

  1. the reflection step fires and actually writes a rule
  2. an injected rule visibly changes behaviour
  3. every tool call is a real tool_use block (invalid rate must be ~0)
  4. the oracle's verdict matches your own reading

Usage:
    python -m selfsealing.smoke --model claude-sonnet-5 --effort high -n 5
    python -m selfsealing.smoke --inject-broad -n 5
"""

import argparse
import dataclasses
import json
import sys
import time

from .agent import run_episode
from .environment import Corpus, EnvironmentSession
from .memory import ReflectionMemory

RULE_BROAD = "search_docs is unreliable. Do not use it."
RULE_NARROW = "Do not use search_docs for queries written in Chinese."


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--effort", default=None,
                    help="omit for claude-haiku-4-5, which rejects it")
    ap.add_argument("-n", "--episodes", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--inject-broad", action="store_true")
    ap.add_argument("--inject-narrow", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="summary only")
    ap.add_argument("--arm", default=None, help="arm label recorded in the JSONL")
    ap.add_argument("--jsonl", default=None, help="write one row per episode here")
    args = ap.parse_args(argv)

    try:
        import anthropic
    except ImportError:
        sys.exit("anthropic SDK not installed. See SETUP.md")

    client = anthropic.Anthropic()
    corpus = Corpus(seed=args.seed, n_tasks=max(args.episodes, 50))
    memory = ReflectionMemory()
    if args.inject_broad:
        memory.inject(RULE_BROAD)
    if args.inject_narrow:
        memory.inject(RULE_NARROW)

    arm = args.arm or (
        "broad" if args.inject_broad else "narrow" if args.inject_narrow else "natural"
    )
    run_id = "{}-{}-s{}".format(arm, int(time.time()), args.seed)
    sink = open(args.jsonl, "a", encoding="utf-8") if args.jsonl else None

    rows = []
    for i, task in enumerate(corpus.tasks[: args.episodes], start=1):
        session = EnvironmentSession(corpus, task)
        res = run_episode(
            client, task, session, memory, episode=i,
            model_id=args.model, effort=args.effort,
        )
        rows.append(res)
        if sink is not None:
            row = dataclasses.asdict(res)
            row.update(
                run_id=run_id, arm=arm, episode=i,
                model=args.model, effort=args.effort, seed=args.seed,
                correct_answer=task.answer,
                rule_violation=(arm in ("broad", "narrow") and res.search_docs_calls > 0),
            )
            sink.write(json.dumps(row, ensure_ascii=False) + "\n")
            sink.flush()
        print("=" * 72)
        print("EPISODE {}  task={}  cjk={}  -> {}{}".format(
            i, res.task_id, res.is_cjk,
            "PASS" if res.success else "FAIL",
            "  [INVALID: {}]".format(res.invalid_reason) if res.invalid else "",
        ))
        print("  answer={!r} correct={!r} tools={} memory={}".format(
            res.answer, task.answer, res.tools_called, res.memory_size))
        if res.reflection_written:
            print("  reflection: {}".format(res.reflection_written))
        if not args.quiet:
            print("-" * 72)
            print(res.raw_transcript)

    valid = [r for r in rows if not r.invalid]
    exhausted = [r for r in rows if r.terminated_reason == "max_turns"]
    print("=" * 72)
    print("episodes           {}".format(len(rows)))
    print("invalid (harness)  {}   <- must be 0; see agent.detect_tool_call_leak"
          .format(len(rows) - len(valid)))
    print("turn-exhausted     {}   <- a task FAILURE, kept in the data"
          .format(len(exhausted)))
    if valid:
        print("success rate       {:.2f}".format(sum(r.success for r in valid) / len(valid)))
    print("search_docs calls  {}".format(sum(r.search_docs_calls for r in rows)))
    print("browse_index calls {}".format(sum(r.browse_index_calls for r in rows)))
    print("rules recorded     {}".format(len(memory)))
    for rule in memory.rules:
        print("  [{}] {}".format("injected" if rule.injected else rule.episode, rule.text))
    if arm in ("broad", "narrow"):
        v = sum(1 for r in rows if r.search_docs_calls > 0)
        print("rule violations    {}/{}  ({:.2f})".format(v, len(rows), v / len(rows)))
    if sink is not None:
        sink.close()
        print("jsonl              {}".format(args.jsonl))
    return 0


if __name__ == "__main__":
    sys.exit(main())
