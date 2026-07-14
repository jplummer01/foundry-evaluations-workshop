"""Local function-handler catalog for the workshop prompt agents."""
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import create_agent
import create_agent_gcp
import create_agent_gdp
import create_agent_glp
import create_agent_gmp
import create_agent_gxp


@dataclass(frozen=True)
class AgentRuntime:
    handlers: dict[str, Callable[..., str]]
    tool_definitions: list[dict[str, Any]]
    version: str | None


AGENT_RUNTIMES = {
    create_agent.AGENT_NAME: AgentRuntime(
        handlers={
            "get_weather": create_agent.get_weather,
            "get_forecast": create_agent.get_forecast,
        },
        tool_definitions=create_agent.TOOL_DEFINITIONS,
        version=os.environ.get("DEMO_AGENT_VERSION"),
    ),
    create_agent_gxp.AGENT_NAME: AgentRuntime(
        handlers={"lookup_sop": create_agent_gxp.lookup_sop},
        tool_definitions=create_agent_gxp.TOOL_DEFINITIONS,
        version=os.environ.get("GXP_AGENT_VERSION"),
    ),
    create_agent_gmp.AGENT_NAME: AgentRuntime(
        handlers={"lookup_sop": create_agent_gmp.lookup_sop},
        tool_definitions=create_agent_gmp.TOOL_DEFINITIONS,
        version=os.environ.get("GMP_AGENT_VERSION"),
    ),
    create_agent_glp.AGENT_NAME: AgentRuntime(
        handlers={"lookup_method": create_agent_glp.lookup_method},
        tool_definitions=create_agent_glp.TOOL_DEFINITIONS,
        version=os.environ.get("GLP_AGENT_VERSION"),
    ),
    create_agent_gcp.AGENT_NAME: AgentRuntime(
        handlers={"lookup_protocol": create_agent_gcp.lookup_protocol},
        tool_definitions=create_agent_gcp.TOOL_DEFINITIONS,
        version=os.environ.get("GCP_AGENT_VERSION"),
    ),
    create_agent_gdp.AGENT_NAME: AgentRuntime(
        handlers={"lookup_dist_sop": create_agent_gdp.lookup_dist_sop},
        tool_definitions=create_agent_gdp.TOOL_DEFINITIONS,
        version=os.environ.get("GDP_AGENT_VERSION"),
    ),
}


def get_agent_runtime(agent_name: str) -> AgentRuntime:
    try:
        return AGENT_RUNTIMES[agent_name]
    except KeyError as exc:
        supported = ", ".join(sorted(AGENT_RUNTIMES))
        raise ValueError(f"No local tools registered for '{agent_name}'. Supported: {supported}") from exc