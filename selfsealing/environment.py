"""Deterministic document-search environment. Contains NO LLM calls.

Ground truth
------------
`search_docs` has a broken CJK tokenizer: any query containing CJK characters
returns plausible-but-wrong snippets. Every other query works perfectly.

The correct lesson is therefore *conditional*:
    "do not use search_docs for CJK queries"
and NOT
    "search_docs is unreliable"      (too broad -- the 70% ASCII tasks are fine)
    "do not use search_docs for this one task"   (too narrow)

Two design properties matter and are easy to break:

1. The failure is OPAQUE. A CJK query returns wrong-looking documents, never an
   error message. If the tool announced "CJK unsupported", inferring the correct
   scope would be trivial and the experiment would measure nothing.

2. CJK-topic answers live only in CJK-indexed documents, so translating the
   query to ASCII does not recover the answer. This closes the trivial
   workaround without making the tool magic: the failure stays a property of
   the query the agent actually sends.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import hashlib
import re

# Any query containing one of these ranges trips the broken tokenizer.
_CJK = re.compile(r"[　-〿぀-ヿ㐀-䶿一-鿿가-힯＀-￯]")

BROWSE_SUCCESS_RATE = 0.55
MAX_SNIPPETS = 3


def contains_cjk(text: str) -> bool:
    return bool(_CJK.search(text))


def _unit_hash(*parts: str) -> float:
    """Deterministic pseudo-random float in [0, 1) from string parts."""
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


@dataclass(frozen=True)
class Task:
    task_id: str
    question: str
    answer: str
    topic: str
    is_cjk: bool


@dataclass(frozen=True)
class Document:
    doc_id: str
    topic: str
    terms: str
    body: str
    is_cjk: bool


_EN_UNITS = ["Marketing", "Platform", "Sales", "Research", "Support", "Design", "Finance"]
_EN_METRICS = [("headcount", "people"), ("budget", "USD"), ("tickets", "tickets")]
_ZH_UNITS = ["行銷部", "平台部", "業務部", "研究部", "客服部", "設計部", "財務部"]
_ZH_METRICS = [("人數", "人"), ("預算", "元"), ("工單數", "件")]
_QUARTERS = ["Q1", "Q2", "Q3", "Q4"]
_YEARS = ["2021", "2022", "2023", "2024", "2025", "2026"]


def _value_for(*parts: str) -> int:
    return 100 + int(_unit_hash(*parts) * 9900)


def _combos(units, metrics, seed: str):
    """Every (unit, metric, quarter, year) combo, in a deterministic order.

    Facts must be unique: if two tasks shared a combo they would share an
    answer, and a decoy could then coincidentally *be* the correct answer.
    """
    out = [
        (u, m, suffix, q, y)
        for u in units
        for (m, suffix) in metrics
        for q in _QUARTERS
        for y in _YEARS
    ]
    out.sort(key=lambda c: _unit_hash(seed, *[c[0], c[1], c[3], c[4]]))
    return out


class Corpus:
    """The document store. Deterministic given a seed."""

    def __init__(self, seed: int = 0, n_tasks: int = 200, cjk_fraction: float = 0.30):
        if not 0.0 <= cjk_fraction <= 1.0:
            raise ValueError("cjk_fraction must be in [0, 1]")
        self.seed = seed
        self.cjk_fraction = cjk_fraction
        self._documents: Dict[str, Document] = {}
        self._tasks: List[Task] = []
        self._build(n_tasks)

    def _build(self, n_tasks: int) -> None:
        en = _combos(_EN_UNITS, _EN_METRICS, "{}-en".format(self.seed))
        zh = _combos(_ZH_UNITS, _ZH_METRICS, "{}-zh".format(self.seed))
        n_cjk = sum(
            1
            for i in range(n_tasks)
            if _unit_hash(str(self.seed), "lang", str(i)) < self.cjk_fraction
        )
        if n_cjk > len(zh) or (n_tasks - n_cjk) > len(en):
            raise ValueError(
                "n_tasks={} exceeds the unique-fact budget (en={}, zh={})".format(
                    n_tasks, len(en), len(zh)
                )
            )

        en_i = zh_i = 0
        for i in range(n_tasks):
            is_cjk = _unit_hash(str(self.seed), "lang", str(i)) < self.cjk_fraction
            if is_cjk:
                unit, metric, suffix, quarter, year = zh[zh_i]
                zh_i += 1
                value = _value_for(unit, metric, quarter, year)
                terms = "{} {} {} {}".format(unit, year, quarter, metric)
                question = "{} 在 {} 年 {} 的{}是多少？只回答數字。".format(
                    unit, year, quarter, metric
                )
                body = "【{}｜{} {}】{}：{}{}".format(unit, year, quarter, metric, value, suffix)
            else:
                unit, metric, suffix, quarter, year = en[en_i]
                en_i += 1
                value = _value_for(unit, metric, quarter, year)
                terms = "{} {} {} {}".format(unit, year, quarter, metric)
                question = "What was the {} {} {} {}? Answer with the number only.".format(
                    unit, year, quarter, metric
                )
                body = "[{} | {} {}] {}: {} {}".format(unit, year, quarter, metric, value, suffix)

            topic = "{}/{} {}".format(unit, year, quarter)
            doc_id = "doc-{:04d}".format(i)
            self._documents[doc_id] = Document(doc_id, topic, terms, body, is_cjk)
            self._tasks.append(
                Task("task-{:04d}".format(i), question, str(value), topic, is_cjk)
            )

    @property
    def tasks(self) -> List[Task]:
        return list(self._tasks)

    def documents(self) -> List[Document]:
        return list(self._documents.values())

    def lookup(self, query: str) -> List[Document]:
        """Term-overlap retrieval over the ASCII-indexed half of the store.

        The index is language-partitioned. Year and quarter tokens ("2021",
        "Q1") are shared across languages, so an unpartitioned index lets an
        ASCII query retrieve a CJK document -- which hands the agent a trivial
        translate-the-query workaround and removes any reason to reason about
        scope at all. Observed in the first smoke run; see the regression test.
        """
        wanted = set(_tokenize(query))
        if not wanted:
            return []
        scored = []
        for doc in self._documents.values():
            if doc.is_cjk:
                continue
            overlap = len(wanted & set(_tokenize(doc.terms)))
            if overlap:
                scored.append((overlap, doc.doc_id, doc))
        scored.sort(key=lambda t: (-t[0], t[1]))
        return [doc for _, _, doc in scored[:MAX_SNIPPETS]]


def _tokenize(text: str) -> List[str]:
    """Split ASCII on non-alphanumerics; treat each CJK character as a token."""
    tokens: List[str] = []
    for chunk in re.split(r"[^0-9A-Za-z㐀-䶿一-鿿]+", text):
        if not chunk:
            continue
        if contains_cjk(chunk):
            tokens.extend(list(chunk))
        else:
            tokens.append(chunk.lower())
    return tokens


class EnvironmentSession:
    """Tool surface bound to a single task. This is what the agent calls."""

    def __init__(self, corpus: Corpus, task: Task):
        self.corpus = corpus
        self.task = task
        self.search_docs_calls = 0
        self.browse_index_calls = 0

    # -- tools -----------------------------------------------------------

    def search_docs(self, query: str) -> str:
        """Full-text search. Silently returns wrong snippets for CJK queries."""
        self.search_docs_calls += 1
        query = (query or "").strip()
        if not query:
            return "No results."

        if contains_cjk(query):
            # Broken tokenizer: the query is mangled, so unrelated documents
            # come back. No error is raised -- the failure must be opaque.
            return self._render(self._decoys(query))

        hits = self.corpus.lookup(query)
        if not hits:
            return "No results."
        return self._render(hits)

    def browse_index(self, topic: str) -> str:
        """Coarse fallback index. Always available, succeeds ~55% of the time."""
        self.browse_index_calls += 1
        # Keyed on the task alone: including `topic` would let the agent
        # reroll the dice by rephrasing, turning the fallback into a slot
        # machine instead of a fixed-quality alternative path.
        roll = _unit_hash("browse", str(self.corpus.seed), self.task.task_id)
        if roll >= BROWSE_SUCCESS_RATE:
            return "Index entry is incomplete for this topic. No figure recorded."
        doc = self._document_for_task()
        if doc is None:
            return "Index entry is incomplete for this topic. No figure recorded."
        return "INDEX {}\n{}".format(doc.topic, doc.body)

    # -- scoring ---------------------------------------------------------

    def score(self, answer: Optional[str]) -> bool:
        if answer is None:
            return False
        digits = re.findall(r"\d+", str(answer))
        return bool(digits) and digits[-1] == self.task.answer

    # -- internals -------------------------------------------------------

    def _document_for_task(self) -> Optional[Document]:
        suffix = self.task.task_id.split("-")[-1]
        return self.corpus._documents.get("doc-{}".format(suffix))

    def _decoys(self, query: str) -> List[Document]:
        """Plausible but wrong documents, stable for a given query."""
        pool = sorted(self.corpus.documents(), key=lambda d: d.doc_id)
        correct = self._document_for_task()
        answer = self.task.answer
        pool = [
            d
            for d in pool
            if (correct is None or d.doc_id != correct.doc_id) and answer not in d.body
        ]
        if not pool:
            return []
        start = int(_unit_hash("decoy", self.task.task_id, query) * len(pool))
        return [pool[(start + k) % len(pool)] for k in range(min(MAX_SNIPPETS, len(pool)))]

    @staticmethod
    def _render(docs: List[Document]) -> str:
        if not docs:
            return "No results."
        return "\n".join(
            "{}. {}".format(i + 1, d.body) for i, d in enumerate(docs)
        )
