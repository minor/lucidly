"""Agent registry: definitions and strategies for benchmark agents."""

from pydantic import BaseModel


class Agent(BaseModel):
    id: str
    name: str
    strategy: str  # claude_direct, openai_cot, claude_sdk
    description: str
    model: str  # model to use when submitting prompts


# ---------------------------------------------------------------------------
# Agent definitions
# ---------------------------------------------------------------------------

AGENTS: list[Agent] = [
    Agent(
        id="claude-direct",
        name="Claude Direct",
        strategy="claude_direct",
        description="Single-model direct code generation. Uses DEFAULT_MODEL from your .env (OpenAI, OpenRouter, etc.).",
        model="",  # empty = use backend DEFAULT_MODEL so it works with any configured API
    ),
    Agent(
        id="openai-cot",
        name="OpenAI Chain-of-Thought",
        strategy="openai_cot",
        description="OpenAI model with chain-of-thought system prompt.",
        model="gpt-4o",
    ),
    Agent(
        id="claude-sdk",
        name="Claude Agent SDK",
        strategy="claude_sdk",
        description="Claude with Agent SDK: tools, reasoning, and multi-step code generation.",
        model="",  # empty = use backend DEFAULT_MODEL
    ),
    Agent(
        id="openai-assistant",
        name="OpenAI Assistant",
        strategy="openai_assistant",
        description="OpenAI Assistants API with a submit_prompt function tool.",
        model="gpt-4o",
    ),
]


def get_all_agents() -> list[Agent]:
    return list(AGENTS)


def get_agent_by_id(agent_id: str) -> Agent | None:
    for a in AGENTS:
        if a.id == agent_id:
            return a
    return None
