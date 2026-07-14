"""Invoke a prompt agent and execute its local function tools.

Foundry prompt agents store tool schemas, not the Python implementations. This
client supplies the missing function-call loop: invoke the agent, execute each
requested local function, submit its output, and continue to the final answer.
"""
import argparse
import json
import os
from pathlib import Path
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from openai import BadRequestError

from agent_tools import AGENT_RUNTIMES, AgentRuntime, get_agent_runtime

load_dotenv()

MAX_TOOL_ROUNDS = 8


def is_content_filter_error(exc: BadRequestError) -> bool:
    """Return whether Foundry rejected a prompt under its content policy."""
    error = exc.body
    return isinstance(error, dict) and error.get("code") == "content_filter"


def parse_json_value(value: str) -> Any:
    """Parse JSON tool data when possible, preserving non-JSON strings."""
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def to_evaluator_messages(output_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Responses API items to Foundry's role-bearing agent schema."""
    messages: list[dict[str, Any]] = []
    for item in output_items:
        item_type = item.get("type")
        if item_type == "function_call":
            messages.append(
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_call",
                            "tool_call_id": item["call_id"],
                            "name": item["name"],
                            "arguments": parse_json_value(item["arguments"]),
                        }
                    ],
                }
            )
        elif item_type == "function_call_output":
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": item["call_id"],
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_result": parse_json_value(item["output"]),
                        }
                    ],
                }
            )
        elif item_type == "message":
            content = [
                {"type": "text", "text": part["text"]}
                for part in item.get("content", [])
                if part.get("type") in {"input_text", "output_text"} and "text" in part
            ]
            if content:
                messages.append({"role": item.get("role", "assistant"), "content": content})
    return messages


def run_agent(
    client: Any,
    *,
    agent_name: str,
    query: str,
    runtime: AgentRuntime,
    agent_version: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Run one query, resolving all requested local function calls."""
    conversation = client.conversations.create()
    agent_reference = {"name": agent_name, "type": "agent_reference"}
    if agent_version:
        agent_reference["version"] = agent_version

    response_items: list[dict[str, Any]] = []
    next_input: Any = query

    try:
        for _ in range(MAX_TOOL_ROUNDS):
            response = client.responses.create(
                input=next_input,
                conversation=conversation.id,
                extra_body={"agent_reference": agent_reference},
            )
            response_items.extend(item.model_dump(mode="json") for item in response.output)

            function_calls = [item for item in response.output if item.type == "function_call"]
            if not function_calls:
                if not response.output_text:
                    raise RuntimeError("Agent returned neither a function call nor final text.")
                return response.output_text, response_items

            tool_outputs = []
            for call in function_calls:
                function = runtime.handlers.get(call.name)
                if function is None:
                    raise RuntimeError(f"Agent requested unknown local tool: {call.name}")

                try:
                    arguments = json.loads(call.arguments)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(
                        f"Tool {call.name} returned invalid JSON arguments: {call.arguments}"
                    ) from exc
                if not isinstance(arguments, dict):
                    raise RuntimeError(f"Tool {call.name} arguments must be a JSON object.")

                output = function(**arguments)
                print(f"Tool call: {call.name}({json.dumps(arguments, sort_keys=True)})")
                print(f"Tool output: {output}")
                tool_output = {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": output,
                }
                tool_outputs.append(tool_output)
                response_items.append(tool_output)

            next_input = tool_outputs

        raise RuntimeError(f"Agent exceeded {MAX_TOOL_ROUNDS} function-call rounds.")
    finally:
        client.conversations.delete(conversation_id=conversation.id)


def run_dataset(
    client: Any,
    *,
    agent_name: str,
    agent_version: str | None,
    runtime: AgentRuntime,
    dataset_path: Path,
    output_path: Path,
) -> None:
    """Run every JSONL query and atomically write Foundry eval input."""
    temporary_path = output_path.with_name(f"{output_path.name}.tmp")
    row_count = 0
    skipped_rows: list[int] = []

    try:
        with dataset_path.open(encoding="utf-8") as source, temporary_path.open(
            "w", encoding="utf-8"
        ) as destination:
            for line_number, line in enumerate(source, start=1):
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON on {dataset_path}:{line_number}") from exc
                if not isinstance(item, dict) or not isinstance(item.get("query"), str):
                    raise ValueError(f"Row {line_number} must be an object with a string 'query'.")
                if "review_status" in item and item["review_status"] != "approved":
                    raise ValueError(
                        f"Row {line_number} has review_status={item['review_status']!r}; "
                        "only approved GxP rows may be evaluated."
                    )

                print(f"\n[{line_number}] {item['query']}")
                try:
                    answer, output_items = run_agent(
                        client,
                        agent_name=agent_name,
                        agent_version=agent_version,
                        query=item["query"],
                        runtime=runtime,
                    )
                except BadRequestError as exc:
                    if not is_content_filter_error(exc):
                        raise
                    skipped_rows.append(line_number)
                    print("Skipped: prompt was blocked by the Azure OpenAI content filter.")
                    continue
                destination.write(
                    json.dumps(
                        {
                            "item": {
                                **item,
                                "tool_definitions": runtime.tool_definitions,
                            },
                            "sample": {
                                "output_items": output_items,
                                "output_messages": to_evaluator_messages(output_items),
                                "output_text": answer,
                            },
                        }
                    )
                    + "\n"
                )
                row_count += 1
        if row_count == 0:
            raise RuntimeError("No responses were generated; every query was content-filtered.")
        temporary_path.replace(output_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise

    print(f"\nWrote {row_count} completed response rows to {output_path}")
    if skipped_rows:
        rows = ", ".join(str(row) for row in skipped_rows)
        print(f"Skipped {len(skipped_rows)} content-filtered row(s): {rows}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--query", help="One question to send to the agent")
    mode.add_argument("--dataset", type=Path, help="Input JSONL containing a query field")
    parser.add_argument("--output", type=Path, help="Output JSONL for --dataset mode")
    parser.add_argument(
        "--agent-name",
        default=os.environ.get("DEMO_AGENT_NAME", "demo-weather-agent"),
        choices=sorted(AGENT_RUNTIMES),
        help="Prompt-agent name with registered local tools",
    )
    parser.add_argument(
        "--agent-version",
        help="Prompt-agent version (default: matching track's version variable or latest)",
    )
    args = parser.parse_args()

    if args.dataset and not args.output:
        parser.error("--output is required with --dataset")
    if args.query and args.output:
        parser.error("--output is only valid with --dataset")

    runtime = get_agent_runtime(args.agent_name)
    agent_version = args.agent_version or runtime.version

    project = AIProjectClient(
        endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        credential=DefaultAzureCredential(),
    )
    client = project.get_openai_client()
    if args.query:
        answer, _ = run_agent(
            client,
            agent_name=args.agent_name,
            agent_version=agent_version,
            query=args.query,
            runtime=runtime,
        )
        print(f"\nAgent: {answer}")
    else:
        run_dataset(
            client,
            agent_name=args.agent_name,
            agent_version=agent_version,
            runtime=runtime,
            dataset_path=args.dataset,
            output_path=args.output,
        )


if __name__ == "__main__":
    main()