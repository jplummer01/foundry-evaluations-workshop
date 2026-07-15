"""Validate deterministic tool-call contracts in precomputed response JSONL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from eval_artifacts import write_json

JSON_TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
    "null": type(None),
}


def issue(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "message": message, **details}


def validate_arguments(
    tool_name: str, arguments: Any, definition: dict[str, Any]
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    parameters = definition.get("parameters", {})
    properties = parameters.get("properties", {})
    required = parameters.get("required", [])

    for parameter in required:
        if parameter not in arguments:
            issues.append(
                issue(
                    "missing_required_parameter",
                    f"{tool_name} is missing required parameter {parameter!r}.",
                    tool=tool_name,
                    parameter=parameter,
                )
            )

    for parameter, value in arguments.items():
        schema = properties.get(parameter)
        if not isinstance(schema, dict) or "type" not in schema:
            continue
        expected_type = schema["type"]
        python_type = JSON_TYPES.get(expected_type)
        if python_type is None:
            continue
        type_matches = isinstance(value, python_type)
        if expected_type in {"integer", "number"} and isinstance(value, bool):
            type_matches = False
        if not type_matches:
            issues.append(
                issue(
                    "argument_type_mismatch",
                    f"{tool_name}.{parameter} must be {expected_type}.",
                    tool=tool_name,
                    parameter=parameter,
                    expected_type=expected_type,
                    actual_type=type(value).__name__,
                )
            )
    return issues


def parse_call_arguments(call: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    raw_arguments = call.get("arguments")
    if isinstance(raw_arguments, str):
        try:
            raw_arguments = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return None, issue(
                "invalid_arguments_json",
                f"Tool {call.get('name')!r} arguments are not valid JSON.",
                tool=call.get("name"),
            )
    if not isinstance(raw_arguments, dict):
        return None, issue(
            "arguments_not_object",
            f"Tool {call.get('name')!r} arguments must be a JSON object.",
            tool=call.get("name"),
        )
    return raw_arguments, None


def expectation_matches(call: dict[str, Any], expectation: dict[str, Any]) -> bool:
    if call.get("name") != expectation.get("name"):
        return False
    expected_arguments = expectation.get("arguments", {})
    actual_arguments = call.get("arguments", {})
    return all(actual_arguments.get(key) == value for key, value in expected_arguments.items())


def validate_row(row: dict[str, Any], row_number: int) -> dict[str, Any]:
    item = row.get("item") if isinstance(row.get("item"), dict) else {}
    sample = row.get("sample") if isinstance(row.get("sample"), dict) else {}
    definitions = item.get("tool_definitions")
    output_items = sample.get("output_items")
    row_issues: list[dict[str, Any]] = []

    if not isinstance(definitions, list):
        definitions = []
        row_issues.append(issue("missing_tool_definitions", "item.tool_definitions is required."))
    if not isinstance(output_items, list):
        output_items = []
        row_issues.append(issue("missing_output_items", "sample.output_items is required."))

    definitions_by_name = {
        definition.get("name"): definition
        for definition in definitions
        if isinstance(definition, dict) and isinstance(definition.get("name"), str)
    }
    calls: list[dict[str, Any]] = []
    for output_item in output_items:
        if not isinstance(output_item, dict) or output_item.get("type") != "function_call":
            continue
        name = output_item.get("name")
        definition = definitions_by_name.get(name)
        arguments, parse_issue = parse_call_arguments(output_item)
        if parse_issue:
            row_issues.append(parse_issue)
            arguments = {}
        call = {"name": name, "arguments": arguments}
        calls.append(call)
        if definition is None:
            row_issues.append(
                issue("unknown_tool", f"Tool {name!r} is not present in tool_definitions.", tool=name)
            )
        elif parse_issue is None:
            row_issues.extend(validate_arguments(name, arguments, definition))

    if item.get("expect_no_tool") is True and calls:
        row_issues.append(
            issue(
                "unexpected_tool_call",
                "This case explicitly expects no tool call.",
                actual_tools=[call["name"] for call in calls],
            )
        )

    expected_calls = item.get("expected_tool_calls")
    if expected_calls is not None:
        if not isinstance(expected_calls, list):
            row_issues.append(
                issue("invalid_expectation", "expected_tool_calls must be a JSON array.")
            )
        else:
            unmatched_calls = list(calls)
            for expectation in expected_calls:
                if not isinstance(expectation, dict) or not isinstance(
                    expectation.get("name"), str
                ):
                    row_issues.append(
                        issue(
                            "invalid_expectation",
                            "Each expected tool call must contain a string name.",
                        )
                    )
                    continue
                match = next(
                    (
                        call
                        for call in unmatched_calls
                        if expectation_matches(call, expectation)
                    ),
                    None,
                )
                if match is None:
                    row_issues.append(
                        issue(
                            "missing_expected_tool_call",
                            f"Expected tool call {expectation!r} was not observed.",
                            expectation=expectation,
                        )
                    )
                else:
                    unmatched_calls.remove(match)

    return {
        "row_number": row_number,
        "case_id": item.get("case_id"),
        "category": item.get("category"),
        "query": item.get("query"),
        "calls": calls,
        "outcome": "pass" if not row_issues else "fail",
        "issues": row_issues,
    }


def validate_file(path: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Row {line_number} must be a JSON object.")
            rows.append(validate_row(value, line_number))

    failed_rows = sum(row["outcome"] == "fail" for row in rows)
    return {
        "schema_version": 1,
        "source": str(path),
        "decision": "pass" if rows and failed_rows == 0 else "fail",
        "row_count": len(rows),
        "failed_rows": failed_rows,
        "issue_count": sum(len(row["issues"]) for row in rows),
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True, help="Precomputed response JSONL")
    parser.add_argument(
        "--output",
        type=Path,
        help="Output JSON (default: contract-results.json beside the dataset)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = validate_file(args.dataset)
    output = args.output or args.dataset.with_name("contract-results.json")
    write_json(output, result)
    print(
        f"Contract check: {result['decision']} "
        f"({result['failed_rows']}/{result['row_count']} rows failed; {output})"
    )
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())