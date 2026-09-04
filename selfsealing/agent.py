"""Agent loop: ReAct-style tool use plus a post-failure reflection step.

The loop is deliberately plain. The one non-obvious piece is
`detect_tool_call_leak`, which guards the experiment's dependent variable --
see the module docstring in models.py for why.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import re

from .environment import EnvironmentSession, Task
from .memory import ReflectionMemory
from .models import request_kwargs

TOOL_NAMES = ("search_docs", "browse_index")

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "search_docs",
        "description": (
            "Full-text search over the company document store. Returns up to "
            "three matching snippets. Pass the search terms you want to match."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search terms."}
            },
            "required": ["query"],
        },
    },
    {
        "name": "browse_index",
        "description": (
            "Browse the coarse topic index. Slower and less complete than "
            "search_docs, but covers the same document store. Pass a topic of "
            "the form 'Unit/Year Quarter'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic to browse."}
            },
            "required": ["topic"],
        },
    },
]

SYSTEM_TEMPLATE = """You are a research assistant with access to a company document store.

Answer the user's question using the tools available to you. When you have the
answer, state it as a bare number and nothing else.

Lessons you have recorded from previous tasks:
{lessons}

Follow your recorded lessons."""

REFLECTION_TEMPLATE = """You just failed this task:

Question: {question}
Your answer: {answer}
Correct answer: {correct}

Here is what you did:
{trace}

Write one short lesson to record for future tasks so this does not happen
again. Reply with the lesson only -- one sentence, no preamble."""

# A tool call that arrives as prose instead of a tool_use block never executes.
_LEAK_PATTERNS = [
    re.compile(r"\b(?:{})\s*\(".format("|".join(TOOL_NAMES))),
    re.compile(r'"name"\s*:\s*"(?:{})"'.format("|".join(TOOL_NAMES))),
    re.compile(r"<\s*(?:tool_use|invoke|function_calls)\b", re.I),
]


def detect_tool_call_leak(text: str) -> Optional[str]:
    """Return the offending pattern if assistant prose looks like a tool call."""
    for pattern in _LEAK_PATTERNS:
        match = pattern.search(text or "")
        if match:
            return match.group(0)
    return None


@dataclass
class EpisodeResult:
    task_id: str
    is_cjk: bool
    success: bool
    answer: Optional[str]
    tools_called: List[str] = field(default_factory=list)
    search_docs_calls: int = 0
    browse_index_calls: int = 0
    reflection_written: Optional[str] = None
    memory_size: int = 0
    turns: int = 0
    stop_reason: Optional[str] = None
    terminated_reason: str = "answered"  # answered | max_turns | tool_call_leak
    invalid: bool = False  # HARNESS malfunction only -- never a task outcome
    invalid_reason: Optional[str] = None
    raw_transcript: str = ""


def _text_of(content) -> str:
    return "\n".join(b.text for b in content if getattr(b, "type", None) == "text")


def run_episode(
    client,
    task: Task,
    session: EnvironmentSession,
    memory: ReflectionMemory,
    episode: int,
    model_id: str,
    effort: Optional[str] = None,
    max_turns: int = 8,
    reflect_on_failure: bool = True,
) -> EpisodeResult:
    base = request_kwargs(model_id, effort)
    system = SYSTEM_TEMPLATE.format(lessons=memory.render())
    messages: List[Dict[str, Any]] = [{"role": "user", "content": task.question}]

    result = EpisodeResult(task_id=task.task_id, is_cjk=task.is_cjk, success=False, answer=None)
    transcript: List[str] = ["SYSTEM:\n" + system, "USER:\n" + task.question]

    for turn in range(max_turns):
        response = client.messages.create(
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=TOOLS,
            messages=messages,
            **base
        )
        result.turns = turn + 1
        result.stop_reason = response.stop_reason

        assistant_text = _text_of(response.content)
        tool_uses = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
        if assistant_text:
            transcript.append("ASSISTANT:\n" + assistant_text)

        # -- the guard: prose that looks like an unexecuted tool call --------
        if not tool_uses:
            leak = detect_tool_call_leak(assistant_text)
            if leak:
                result.invalid = True
                result.invalid_reason = "tool_call_leak:{}".format(leak)
                result.terminated_reason = "tool_call_leak"
                result.raw_transcript = "\n\n".join(transcript)
                return result

        messages.append({"role": "assistant", "content": response.content})

        if not tool_uses:
            result.answer = assistant_text.strip()
            break

        tool_results = []
        for block in tool_uses:
            result.tools_called.append(block.name)
            if block.name == "search_docs":
                out = session.search_docs(block.input.get("query", ""))
            elif block.name == "browse_index":
                out = session.browse_index(block.input.get("topic", ""))
            else:
                out = "Unknown tool."
            transcript.append("TOOL {}({}) ->\n{}".format(block.name, block.input, out))
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": out}
            )
        messages.append({"role": "user", "content": tool_results})
    else:
        # The agent burned its budget without answering. That is a real
        # failure caused by the tools it was willing to use -- keep it.
        result.terminated_reason = "max_turns"

    result.search_docs_calls = session.search_docs_calls
    result.browse_index_calls = session.browse_index_calls
    result.success = session.score(result.answer)

    if reflect_on_failure and not result.success and not result.invalid:
        lesson = _reflect(client, task, result, transcript, base)
        if lesson:
            memory.append(episode, lesson)
            result.reflection_written = lesson
            transcript.append("REFLECTION:\n" + lesson)

    result.memory_size = len(memory)
    result.raw_transcript = "\n\n".join(transcript)
    return result


def _reflect(client, task, result, transcript, base) -> Optional[str]:
    prompt = REFLECTION_TEMPLATE.format(
        question=task.question,
        answer=result.answer,
        correct=task.answer,
        trace="\n".join(t for t in transcript if t.startswith("TOOL ")) or "(no tools used)",
    )
    response = client.messages.create(messages=[{"role": "user", "content": prompt}], **base)
    return _text_of(response.content).strip() or None
