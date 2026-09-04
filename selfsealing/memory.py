"""Append-only reflection memory.

Injected verbatim into the system prompt every episode. Arms B/C/D pre-seed a
rule here; the agent may still append its own, because the question is whether
it can *overturn* an injected rule, not merely whether the rule takes effect.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Rule:
    episode: Optional[int]
    text: str
    injected: bool = False


@dataclass
class ReflectionMemory:
    rules: List[Rule] = field(default_factory=list)

    def inject(self, text: str) -> None:
        self.rules.append(Rule(episode=None, text=text.strip(), injected=True))

    def append(self, episode: int, text: str) -> None:
        text = (text or "").strip()
        if text:
            self.rules.append(Rule(episode=episode, text=text))

    def render(self) -> str:
        if not self.rules:
            return "(no lessons recorded yet)"
        return "\n".join("- {}".format(r.text) for r in self.rules)

    def __len__(self) -> int:
        return len(self.rules)
