import asyncio
import sys
import time
from typing import TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.common_tools.tavily import tavily_search_tool

from researcher.config import settings

T = TypeVar("T", bound=BaseModel)

_RESEARCH_MODEL = settings.research_model


def make_search_agent(
    output_type: type[T],
    system_prompt: str,
    model: str = _RESEARCH_MODEL,
) -> Agent[None, T]:
    """Construct a PydanticAI Agent with Tavily search tool."""
    tools = [tavily_search_tool(settings.tavily_api_key)] if settings.tavily_api_key else []
    return Agent(
        model,
        tools=tools,
        output_type=output_type,
        system_prompt=system_prompt,
    )


def run_agent_sync(
    agent: Agent[None, T],
    prompt: str,
    *,
    max_attempts: int = 5,
    base_delay: float = 2.0,
    label: str = "agent",
) -> T | None:
    """Run a PydanticAI agent synchronously with exponential-backoff retry."""
    for attempt in range(max_attempts):
        try:
            result = agent.run_sync(prompt)
            return result.output
        except Exception as e:
            if attempt < max_attempts - 1:
                delay = base_delay**attempt
                time.sleep(delay)
                print(f"[warn] {label} attempt {attempt + 1} failed: {e}", file=sys.stderr)
            else:
                print(f"[warn] {label} failed after {max_attempts} attempts: {e}", file=sys.stderr)
    return None


async def run_agent_async(
    agent: Agent[None, T],
    prompt: str,
    *,
    max_attempts: int = 3,
    base_delay: float = 2.0,
    label: str = "agent",
) -> T | None:
    """Run a PydanticAI agent asynchronously with exponential-backoff retry."""
    for attempt in range(max_attempts):
        try:
            result = await agent.run(prompt)
            return result.output
        except Exception as e:
            if attempt < max_attempts - 1:
                await asyncio.sleep(base_delay**attempt)
                print(f"[warn] {label} attempt {attempt + 1} failed: {e}", file=sys.stderr)
            else:
                print(f"[warn] {label} failed after {max_attempts} attempts: {e}", file=sys.stderr)
    return None
