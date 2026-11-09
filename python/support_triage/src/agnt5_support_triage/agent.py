"""The support agent and the one tool it can call.

With `MOCK_MODE=1`, or no `OPENAI_API_KEY`, the agent runs on a
scripted stand-in model: it calls `get_policy` once, then writes a reply from
the tool result. The tool call, the tool result and both model turns still go
through the real agent loop, so Studio shows the same trace a real model makes.
"""
# No `from __future__ import annotations` here: @tool checks that the first
# parameter is annotated with the Context class itself, and a deferred
# annotation arrives as the string "Context" (agnt5 0.14.5).
import json
import os

from agnt5 import Agent, Context, tool
from agnt5.lm import GenerateResponse, LanguageModel

from .data import POLICIES

SUPPORT_PROMPT = """You are a support agent. Call get_policy with the ticket's
category, then write a short, friendly reply (2-3 sentences) to the customer
that uses the policy text. Sign it "AGNT5 Support"."""


@tool
async def get_policy(ctx: Context, topic: str) -> dict:
    """Look up the support policy for a ticket category.

    Args:
        topic: Ticket category: refund, bug or question
    """
    return {"topic": topic, "policy": POLICIES.get(topic, POLICIES["question"])}


def _field(prompt: str, name: str) -> str:
    for line in prompt.splitlines():
        if line.startswith(f"{name}:"):
            return line.split(":", 1)[1].strip()
    return ""


class ScriptedSupportModel(LanguageModel):
    """Deterministic stand-in for an LLM: one get_policy call, then a reply."""

    async def generate(self, request):
        prompt = request.messages[0].content
        if len(request.messages) == 1:
            return GenerateResponse(
                text="",
                tool_calls=[{
                    "id": "call_policy",
                    "name": "get_policy",
                    "arguments": json.dumps({"topic": _field(prompt, "Category")}),
                }],
            )
        policy = json.loads(request.messages[-1].content)["policy"]
        return GenerateResponse(
            text=(
                f"Hi {_field(prompt, 'Customer')}, thanks for reaching out about your "
                f"{_field(prompt, 'Category')} request. {policy} — AGNT5 Support"
            ),
        )

    async def stream(self, request):
        if False:
            yield None


def mock_mode() -> bool:
    """MOCK_MODE=1 forces the scripted model; unset, it's used only without an OpenAI key.

    Not AGNT5_MOCK_MODE: `agnt5 dev` doesn't pass AGNT5_* variables from .env to the worker.
    """
    flag = os.getenv("MOCK_MODE")
    return flag == "1" if flag is not None else not os.getenv("OPENAI_API_KEY")


def _model() -> str | LanguageModel:
    if mock_mode():
        return ScriptedSupportModel()
    return "openai/gpt-6-luna"


def build_support_agent() -> Agent:
    """Build the agent per call so a changed MOCK_MODE takes effect."""
    return Agent(
        name="support_agent",
        model=_model(),
        temperature=None,  # gpt-6 rejects any temperature; None stops the SDK sending its 0.7 default
        instructions=SUPPORT_PROMPT,
        tools=[get_policy],
        max_iterations=4,
    )
