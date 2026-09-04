"""P1 harness tests. No API key, no network, no spend.

Proves the loop mechanics before any real model is involved: tool dispatch,
memory injection, scoring, reflection, and the tool-call leak guard.
"""
import unittest

from selfsealing.agent import EpisodeResult, TOOLS, run_episode, detect_tool_call_leak
from selfsealing.environment import Corpus, EnvironmentSession
from selfsealing.memory import ReflectionMemory


class _Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Response:
    def __init__(self, content, stop_reason):
        self.content = content
        self.stop_reason = stop_reason


class ScriptedClient:
    """Replays a fixed list of responses. Records every request it received."""

    def __init__(self, script):
        self._script = list(script)
        self.requests = []
        self.messages = self

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if not self._script:
            raise AssertionError("script exhausted")
        return self._script.pop(0)


def _tool_use(name, tool_input, block_id="tu-1"):
    return _Response(
        [_Block(type="tool_use", name=name, input=tool_input, id=block_id)], "tool_use"
    )


def _text(s, stop_reason="end_turn"):
    return _Response([_Block(type="text", text=s)], stop_reason)


class TestAgentLoop(unittest.TestCase):
    def setUp(self):
        self.corpus = Corpus(seed=0, n_tasks=100)
        self.task = next(t for t in self.corpus.tasks if not t.is_cjk)
        self.session = EnvironmentSession(self.corpus, self.task)
        self.memory = ReflectionMemory()

    def _run(self, script, **kw):
        client = ScriptedClient(script)
        res = run_episode(
            client, self.task, self.session, self.memory,
            episode=1, model_id="claude-sonnet-5", effort="high", **kw
        )
        return client, res

    def test_successful_episode(self):
        unit, period = self.task.topic.split("/")
        client, res = self._run([
            _tool_use("search_docs", {"query": "{} {}".format(unit, period)}),
            _text(self.task.answer),
        ])
        self.assertTrue(res.success)
        self.assertEqual(res.tools_called, ["search_docs"])
        self.assertEqual(res.search_docs_calls, 1)
        self.assertFalse(res.invalid)
        self.assertIsNone(res.reflection_written)

    def test_failure_triggers_reflection_and_appends_memory(self):
        client, res = self._run([
            _tool_use("search_docs", {"query": "nothing relevant here"}),
            _text("0"),
            _text("Do not use search_docs for this kind of question."),
        ])
        self.assertFalse(res.success)
        self.assertEqual(res.reflection_written,
                         "Do not use search_docs for this kind of question.")
        self.assertEqual(len(self.memory), 1)
        self.assertEqual(res.memory_size, 1)

    def test_injected_rule_reaches_the_system_prompt(self):
        self.memory.inject("search_docs is unreliable, do not use it.")
        client, _ = self._run([_text("123")], reflect_on_failure=False)
        system = client.requests[0]["system"][0]["text"]
        self.assertIn("search_docs is unreliable", system)

    def test_tool_call_leak_is_flagged_and_episode_discarded(self):
        """The guard that protects the dependent variable."""
        client, res = self._run([_text('I will call search_docs("Marketing Q3").')])
        self.assertTrue(res.invalid)
        self.assertTrue(res.invalid_reason.startswith("tool_call_leak:"))
        self.assertFalse(res.success)
        self.assertIsNone(res.reflection_written)

    def test_normal_prose_is_not_flagged(self):
        client, res = self._run([_text("The answer is 4210.")],
                                reflect_on_failure=False)
        self.assertFalse(res.invalid)

    def test_max_turns_exhausted_is_a_failure_not_a_discard(self):
        """Turn exhaustion is real data: it is how an over-broad ban hurts."""
        script = [_tool_use("browse_index", {"topic": self.task.topic},
                            "tu-{}".format(i)) for i in range(6)]
        script.append(_text("lesson recorded"))  # reflection still fires
        client, res = self._run(script, max_turns=6)
        self.assertFalse(res.invalid, "turn exhaustion must not be discarded")
        self.assertEqual(res.terminated_reason, "max_turns")
        self.assertFalse(res.success)
        self.assertIsNotNone(res.reflection_written)

    def test_browse_index_path_is_usable(self):
        client, res = self._run([
            _tool_use("browse_index", {"topic": self.task.topic}),
            _text(self.task.answer),
        ])
        self.assertEqual(res.browse_index_calls, 1)
        self.assertTrue(res.success)

    def test_request_carries_tools_and_cache_breakpoint(self):
        client, _ = self._run([_text("1")], reflect_on_failure=False)
        req = client.requests[0]
        self.assertEqual([t["name"] for t in req["tools"]],
                         ["search_docs", "browse_index"])
        self.assertEqual(req["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(req["thinking"], {"type": "adaptive"})
        self.assertEqual(req["output_config"], {"effort": "high"})


class TestLeakDetector(unittest.TestCase):
    def test_positives(self):
        for s in ['call search_docs("x")', '{"name": "browse_index"}', "<tool_use>"]:
            self.assertIsNotNone(detect_tool_call_leak(s), s)

    def test_negatives(self):
        for s in ["The answer is 42.", "I searched the docs.", "", None]:
            self.assertIsNone(detect_tool_call_leak(s), s)


if __name__ == "__main__":
    unittest.main(verbosity=2)
