"""P0 acceptance tests: the environment's ground truth must be exact.

If any of these fail, every downstream metric is meaningless.
"""
import re
import unittest

from selfsealing.environment import (
    BROWSE_SUCCESS_RATE,
    Corpus,
    EnvironmentSession,
    contains_cjk,
)


class TestGroundTruth(unittest.TestCase):
    def setUp(self):
        self.corpus = Corpus(seed=0, n_tasks=400, cjk_fraction=0.30)

    # -- the failure condition ------------------------------------------

    def test_ascii_query_always_succeeds(self):
        """Non-CJK tasks: the natural query must retrieve the right answer."""
        checked = 0
        for task in self.corpus.tasks:
            if task.is_cjk:
                continue
            s = EnvironmentSession(self.corpus, task)
            out = s.search_docs(_natural_query(task))
            self.assertTrue(_has_answer(out, task.answer), task.task_id)
            checked += 1
        self.assertGreater(checked, 0)

    def test_cjk_query_always_fails(self):
        """CJK tasks: the natural query must NOT retrieve the right answer."""
        checked = 0
        for task in self.corpus.tasks:
            if not task.is_cjk:
                continue
            s = EnvironmentSession(self.corpus, task)
            out = s.search_docs(_natural_query(task))
            self.assertFalse(_has_answer(out, task.answer), task.task_id)
            checked += 1
        self.assertGreater(checked, 0)

    def test_failure_is_opaque(self):
        """A CJK query must look like ordinary results, never an error."""
        task = next(t for t in self.corpus.tasks if t.is_cjk)
        out = EnvironmentSession(self.corpus, task).search_docs(task.topic.split("/")[0])
        for banned in ("error", "unsupported", "cjk", "invalid", "fail"):
            self.assertNotIn(banned, out.lower())
        self.assertNotEqual(out.strip(), "No results.")

    def test_translation_workaround_does_not_recover_cjk_answers(self):
        """ASCII queries must not reach CJK-indexed answers."""
        for task in self.corpus.tasks:
            if not task.is_cjk:
                continue
            s = EnvironmentSession(self.corpus, task)
            unit, period = task.topic.split("/")
            # The dangerous probes are the ones built from THIS task's own
            # year/quarter -- those share tokens with the CJK document.
            probes = [
                period,
                "budget {}".format(period),
                "headcount {}".format(period),
                "Design {}".format(period),
                "{} report".format(period),
                "Marketing Q3 budget",
            ]
            for probe in probes:
                self.assertFalse(_has_answer(s.search_docs(probe), task.answer), task.task_id)

    # -- the fallback path ----------------------------------------------

    def test_browse_index_is_not_rerollable(self):
        """Rephrasing the topic must not give the agent another roll."""
        for task in self.corpus.tasks[:60]:
            s = EnvironmentSession(self.corpus, task)
            unit, period = task.topic.split("/")
            outs = {
                _has_answer(s.browse_index(t), task.answer)
                for t in (task.topic, unit, period, "", "{}/{}".format(unit, period),
                          "Design/2021 Q1")
            }
            self.assertEqual(len(outs), 1, task.task_id)

    def test_browse_index_success_rate(self):
        """R2/R3: the fallback works, but is measurably worse."""
        wins = 0
        for task in self.corpus.tasks:
            s = EnvironmentSession(self.corpus, task)
            if _has_answer(s.browse_index(task.topic), task.answer):
                wins += 1
        rate = wins / len(self.corpus.tasks)
        self.assertAlmostEqual(rate, BROWSE_SUCCESS_RATE, delta=0.05)

    def test_browse_index_works_for_cjk_tasks_too(self):
        """The fallback must not inherit the CJK failure."""
        wins = sum(
            1
            for t in self.corpus.tasks
            if t.is_cjk
            and _has_answer(EnvironmentSession(self.corpus, t).browse_index(t.topic), t.answer)
        )
        self.assertGreater(wins, 0)

    # -- determinism -----------------------------------------------------

    def test_determinism(self):
        a, b = Corpus(seed=7, n_tasks=50), Corpus(seed=7, n_tasks=50)
        self.assertEqual([t.answer for t in a.tasks], [t.answer for t in b.tasks])
        t = a.tasks[3]
        s1, s2 = EnvironmentSession(a, t), EnvironmentSession(b, b.tasks[3])
        self.assertEqual(s1.search_docs("Marketing Q1"), s2.search_docs("Marketing Q1"))
        self.assertEqual(s1.browse_index(t.topic), s2.browse_index(t.topic))

    def test_different_seeds_differ(self):
        self.assertNotEqual(
            [t.answer for t in Corpus(seed=1, n_tasks=50).tasks],
            [t.answer for t in Corpus(seed=2, n_tasks=50).tasks],
        )

    # -- distribution ----------------------------------------------------

    def test_cjk_fraction(self):
        tasks = self.corpus.tasks
        frac = sum(1 for t in tasks if t.is_cjk) / len(tasks)
        self.assertAlmostEqual(frac, 0.30, delta=0.05)

    def test_cjk_detector(self):
        self.assertTrue(contains_cjk("行銷部 Q3"))
        self.assertFalse(contains_cjk("Marketing Q3 budget"))

    # -- call accounting (feeds the evidence-blackout metric) ------------

    def test_call_counters(self):
        s = EnvironmentSession(self.corpus, self.corpus.tasks[0])
        s.search_docs("a")
        s.search_docs("b")
        s.browse_index("t")
        self.assertEqual((s.search_docs_calls, s.browse_index_calls), (2, 1))


def _has_answer(text, answer):
    """True iff `answer` appears as a whole number token in `text`.

    Substring matching is wrong here: answers are 100-9999, so "473" occurs
    inside "2473" constantly and both leak- and success-assertions misfire.
    """
    return answer in re.findall(r"\d+", text or "")


def _natural_query(task):
    """The query an agent would form after reading the question."""
    unit, period = task.topic.split("/")
    metric = task.question
    for m in ("headcount", "budget", "tickets", "\u4eba\u6578", "\u9810\u7b97", "\u5de5\u55ae\u6578"):
        if m in task.question:
            metric = m
            break
    return "{} {} {}".format(unit, period, metric)


if __name__ == "__main__":
    unittest.main(verbosity=2)
