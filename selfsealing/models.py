"""Model capability table and request construction.

Not every model accepts the same knobs, and sending an unsupported one is a
400 rather than a silent no-op:

  * `output_config.effort` is rejected by Haiku 4.5.
  * Adaptive thinking is the only thinking mode on Opus 5 / Sonnet 5, and it is
    ON when the `thinking` field is omitted. Haiku 4.5 predates it and needs
    the older `{"type": "enabled", "budget_tokens": N}` form.

Thinking stays ON everywhere on purpose. See the tool-call leak guard in
agent.py: with thinking disabled, Opus 5 can emit a tool call as plain text
that never executes, which this experiment would record as "the agent avoided
the tool" -- a false positive for the exact effect being measured.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    supports_effort: bool
    thinking_mode: str  # "adaptive" | "budget"
    default_budget_tokens: Optional[int] = None


SPECS: Dict[str, ModelSpec] = {
    "claude-opus-5": ModelSpec("claude-opus-5", True, "adaptive"),
    "claude-sonnet-5": ModelSpec("claude-sonnet-5", True, "adaptive"),
    "claude-haiku-4-5": ModelSpec("claude-haiku-4-5", False, "budget", 2048),
}

VALID_EFFORTS = ("low", "medium", "high", "xhigh", "max")


def spec_for(model_id: str) -> ModelSpec:
    if model_id not in SPECS:
        raise ValueError(
            "unknown model {!r}; known: {}".format(model_id, ", ".join(sorted(SPECS)))
        )
    return SPECS[model_id]


def request_kwargs(
    model_id: str, effort: Optional[str] = None, max_tokens: int = 8192
) -> Dict[str, Any]:
    """Build only the parameters this model actually accepts."""
    spec = spec_for(model_id)
    kwargs: Dict[str, Any] = {"model": spec.model_id, "max_tokens": max_tokens}

    if spec.thinking_mode == "adaptive":
        kwargs["thinking"] = {"type": "adaptive"}
    else:
        budget = spec.default_budget_tokens or 2048
        if budget >= max_tokens:
            raise ValueError("budget_tokens must be < max_tokens")
        kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget}

    if effort is not None:
        if effort not in VALID_EFFORTS:
            raise ValueError("effort must be one of {}".format(VALID_EFFORTS))
        if not spec.supports_effort:
            raise ValueError(
                "{} does not accept output_config.effort -- omit it for this model".format(
                    spec.model_id
                )
            )
        kwargs["output_config"] = {"effort": effort}

    return kwargs
