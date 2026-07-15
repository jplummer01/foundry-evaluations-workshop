"""Apply deterministic policy gates to normalized Foundry evaluation artifacts.

Foundry's native comparison remains the source for confidence intervals and
statistical significance. This command enforces explicit workshop policy only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from eval_artifacts import comparison_mismatches, write_json

PASS = 0
POLICY_FAILURE = 1
REVIEW_REQUIRED = 2


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}.")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Expected an object at {path}:{line_number}.")
            values.append(value)
    return values


def load_artifacts(directory: Path) -> dict[str, Any]:
    return {
        "directory": str(directory),
        "run": load_json(directory / "run.json"),
        "summary": load_json(directory / "summary.json"),
        "items": load_jsonl(directory / "output-items.jsonl"),
    }


def metric_bucket(
    artifacts: dict[str, Any], evaluator: str, category: str | None = None
) -> dict[str, Any] | None:
    summary = artifacts["summary"]
    if category is None:
        metrics = summary.get("per_testing_criteria_results", {})
    else:
        metrics = summary.get("per_category_results", {}).get(category, {})
    bucket = metrics.get(evaluator)
    return bucket if isinstance(bucket, dict) else None


def add_evidence_result(
    checks: list[dict[str, Any]],
    *,
    artifacts: dict[str, Any],
    evaluator: str,
    minimum_pass_rate: float,
    required: bool,
    category: str | None = None,
) -> None:
    bucket = metric_bucket(artifacts, evaluator, category)
    scope = f"category:{category}" if category else "overall"
    if bucket is None or not bucket.get("total") or bucket.get("pass_rate") is None:
        checks.append(
            {
                "type": "evidence",
                "evaluator": evaluator,
                "scope": scope,
                "outcome": "review_required" if required else "skipped",
                "message": "Required evaluator evidence is missing."
                if required
                else "Optional evaluator evidence is not present.",
            }
        )
        return

    pass_rate = float(bucket["pass_rate"])
    checks.append(
        {
            "type": "minimum_pass_rate",
            "evaluator": evaluator,
            "scope": scope,
            "actual": pass_rate,
            "minimum": minimum_pass_rate,
            "outcome": "pass" if pass_rate >= minimum_pass_rate else "fail",
        }
    )


def evaluate_policy(
    candidate: dict[str, Any],
    policy: dict[str, Any],
    incumbent: dict[str, Any] | None = None,
    contracts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    candidate_run = candidate["run"]

    if candidate_run.get("status") != "completed" or not candidate_run.get("gateable"):
        checks.append(
            {
                "type": "run_status",
                "outcome": "review_required",
                "actual": candidate_run.get("status"),
                "message": "Only completed, gateable runs contain sufficient evidence.",
            }
        )

    if contracts is not None:
        checks.append(
            {
                "type": "tool_contracts",
                "outcome": "pass" if contracts.get("decision") == "pass" else "fail",
                "failed_rows": contracts.get("failed_rows"),
                "message": f"{contracts.get('failed_rows', 0)} tool-contract row(s) failed.",
            }
        )

    if incumbent is not None:
        incumbent_run = incumbent["run"]
        if incumbent_run.get("status") != "completed" or not incumbent_run.get("gateable"):
            checks.append(
                {
                    "type": "incumbent_run_status",
                    "outcome": "review_required",
                    "actual": incumbent_run.get("status"),
                    "message": "The incumbent run is not a completed, gateable baseline.",
                }
            )
        mismatches = comparison_mismatches(candidate_run, incumbent_run)
        if mismatches:
            checks.append(
                {
                    "type": "provenance_compatibility",
                    "outcome": "review_required",
                    "mismatches": mismatches,
                    "message": (
                        "Direct comparison requires the same evaluation group, dataset hash, "
                        "criteria hash, and judge deployment. Use an overlap set and establish "
                        "a reviewed baseline."
                    ),
                }
            )

    for gate in policy.get("hard_gates", []):
        add_evidence_result(
            checks,
            artifacts=candidate,
            evaluator=gate["evaluator"],
            minimum_pass_rate=float(gate.get("minimum_pass_rate", 1.0)),
            required=gate.get("required", True),
        )

    for gate in policy.get("quality_gates", []):
        evaluator = gate["evaluator"]
        add_evidence_result(
            checks,
            artifacts=candidate,
            evaluator=evaluator,
            minimum_pass_rate=float(gate["minimum_pass_rate"]),
            required=gate.get("required", True),
        )
        if incumbent is not None and "maximum_regression_percentage_points" in gate:
            candidate_bucket = metric_bucket(candidate, evaluator)
            incumbent_bucket = metric_bucket(incumbent, evaluator)
            if (
                candidate_bucket is None
                or incumbent_bucket is None
                or candidate_bucket.get("pass_rate") is None
                or incumbent_bucket.get("pass_rate") is None
            ):
                checks.append(
                    {
                        "type": "regression",
                        "evaluator": evaluator,
                        "scope": "overall",
                        "outcome": "review_required",
                        "message": "Candidate or incumbent evidence is missing.",
                    }
                )
            else:
                candidate_rate = float(candidate_bucket["pass_rate"])
                incumbent_rate = float(incumbent_bucket["pass_rate"])
                regression = (incumbent_rate - candidate_rate) * 100
                maximum = float(gate["maximum_regression_percentage_points"])
                checks.append(
                    {
                        "type": "regression",
                        "evaluator": evaluator,
                        "scope": "overall",
                        "candidate_pass_rate": candidate_rate,
                        "incumbent_pass_rate": incumbent_rate,
                        "regression_percentage_points": regression,
                        "maximum_regression_percentage_points": maximum,
                        "outcome": "pass" if regression <= maximum else "fail",
                    }
                )

    for gate in policy.get("category_hard_gates", []):
        for category in gate["categories"]:
            for evaluator in gate["evaluators"]:
                add_evidence_result(
                    checks,
                    artifacts=candidate,
                    evaluator=evaluator,
                    minimum_pass_rate=float(gate.get("minimum_pass_rate", 1.0)),
                    required=gate.get("required", True),
                    category=category,
                )

    outcomes = {check["outcome"] for check in checks}
    if "review_required" in outcomes:
        decision = "review_required"
        exit_code = REVIEW_REQUIRED
    elif "fail" in outcomes:
        decision = "fail"
        exit_code = POLICY_FAILURE
    else:
        decision = "pass"
        exit_code = PASS

    return {
        "schema_version": 1,
        "decision": decision,
        "exit_code": exit_code,
        "policy": policy.get("name"),
        "candidate_run_id": candidate_run.get("run_id"),
        "incumbent_run_id": incumbent["run"].get("run_id") if incumbent else None,
        "checks": checks,
        "statistics_note": (
            "Use Foundry native comparison for confidence intervals and statistical significance; "
            "this gate does not calculate p-values."
        ),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Evaluation gate",
        "",
        f"**Decision:** `{result['decision']}`",
        "",
        "| Check | Scope | Outcome | Detail |",
        "|---|---|---|---|",
    ]
    for check in result["checks"]:
        name = check.get("evaluator") or check["type"]
        scope = check.get("scope", "run")
        detail = check.get("message")
        if detail is None and check["type"] == "minimum_pass_rate":
            detail = f"{check['actual']:.1%} (minimum {check['minimum']:.1%})"
        elif detail is None and check["type"] == "regression":
            detail = (
                f"{check['regression_percentage_points']:.1f} pp "
                f"(maximum {check['maximum_regression_percentage_points']:.1f} pp)"
            )
        lines.append(f"| {name} | {scope} | `{check['outcome']}` | {detail or ''} |")
    lines.extend(["", result["statistics_note"], ""])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply a policy to evaluation artifacts.")
    parser.add_argument("--candidate", type=Path, required=True, help="Candidate artifact directory")
    parser.add_argument("--incumbent", type=Path, help="Incumbent artifact directory")
    parser.add_argument("--policy", type=Path, required=True, help="Gate policy JSON file")
    parser.add_argument("--contracts", type=Path, help="Candidate contract-results.json")
    parser.add_argument("--output-dir", type=Path, help="Output directory (default: candidate)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candidate = load_artifacts(args.candidate)
    incumbent = load_artifacts(args.incumbent) if args.incumbent else None
    policy = load_json(args.policy)
    contracts = load_json(args.contracts) if args.contracts else None
    result = evaluate_policy(candidate, policy, incumbent, contracts)
    output_dir = args.output_dir or args.candidate
    write_json(output_dir / "gate-result.json", result)
    markdown = render_markdown(result)
    (output_dir / "gate-summary.md").write_text(markdown, encoding="utf-8")
    print(markdown)
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())