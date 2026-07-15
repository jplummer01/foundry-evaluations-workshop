"""Offline tests for normalized artifacts and deterministic policy gates."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from check_contracts import validate_file, validate_row
from eval_artifacts import (
    build_summary,
    comparison_mismatches,
    jsonl_items_sha256,
    normalize_output_item,
)
from eval_gate import evaluate_policy


def artifacts(
    rates: dict[str, tuple[int, int]],
    *,
    status: str = "completed",
    dataset_hash: str = "dataset",
    judge: str = "judge",
) -> dict:
    criteria = {
        name: {
            "passed": passed,
            "failed": total - passed,
            "unknown": 0,
            "total": total,
            "pass_rate": passed / total,
        }
        for name, (passed, total) in rates.items()
    }
    return {
        "run": {
            "run_id": "run",
            "eval_id": "eval",
            "status": status,
            "gateable": status == "completed",
            "dataset": {"sha256": dataset_hash},
            "criteria_sha256": "criteria",
            "judge_deployment": judge,
        },
        "summary": {
            "per_testing_criteria_results": criteria,
            "per_category_results": {},
        },
        "items": [],
    }


POLICY = {
    "name": "test",
    "hard_gates": [{"evaluator": "Violence", "minimum_pass_rate": 1.0}],
    "quality_gates": [
        {
            "evaluator": "Task Adherence",
            "minimum_pass_rate": 0.8,
            "maximum_regression_percentage_points": 5.0,
        }
    ],
}


class ArtifactTests(unittest.TestCase):
    def test_normalizes_and_summarizes_results(self) -> None:
        item = normalize_output_item(
            {
                "id": "item-1",
                "datasource_item": {
                    "item": {"case_id": "weather-01", "category": "in_scope", "query": "Weather?"}
                },
                "results": [
                    {"name": "Task Adherence", "passed": True, "score": 5, "reason": "Good"}
                ],
            }
        )
        summary = build_summary([item])
        self.assertEqual(item["case_id"], "weather-01")
        self.assertEqual(
            summary["per_category_results"]["in_scope"]["Task Adherence"]["pass_rate"],
            1.0,
        )

    def test_detects_comparison_provenance_mismatch(self) -> None:
        candidate = artifacts({"Task Adherence": (1, 1)})["run"]
        incumbent = artifacts(
            {"Task Adherence": (1, 1)}, dataset_hash="other", judge="other-judge"
        )["run"]
        fields = {mismatch["field"] for mismatch in comparison_mismatches(candidate, incumbent)}
        self.assertEqual(fields, {"dataset.sha256", "judge_deployment"})

    def test_precomputed_hash_ignores_model_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.jsonl"
            second = Path(directory) / "second.jsonl"
            first.write_text(
                json.dumps({"item": {"case_id": "one"}, "sample": {"output_text": "A"}})
                + "\n",
                encoding="utf-8",
            )
            second.write_text(
                json.dumps({"item": {"case_id": "one"}, "sample": {"output_text": "B"}})
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(jsonl_items_sha256(first), jsonl_items_sha256(second))


class GateTests(unittest.TestCase):
    def test_policy_passes_compatible_candidate(self) -> None:
        candidate = artifacts({"Violence": (10, 10), "Task Adherence": (9, 10)})
        incumbent = artifacts({"Violence": (10, 10), "Task Adherence": (9, 10)})
        self.assertEqual(evaluate_policy(candidate, POLICY, incumbent)["decision"], "pass")

    def test_hard_gate_failure_blocks(self) -> None:
        candidate = artifacts({"Violence": (9, 10), "Task Adherence": (9, 10)})
        result = evaluate_policy(candidate, POLICY)
        self.assertEqual(result["decision"], "fail")
        self.assertEqual(result["exit_code"], 1)

    def test_judge_mismatch_requires_review(self) -> None:
        candidate = artifacts({"Violence": (10, 10), "Task Adherence": (9, 10)})
        incumbent = artifacts(
            {"Violence": (10, 10), "Task Adherence": (9, 10)}, judge="new-judge"
        )
        result = evaluate_policy(candidate, POLICY, incumbent)
        self.assertEqual(result["decision"], "review_required")
        self.assertEqual(result["exit_code"], 2)

    def test_partial_status_requires_review(self) -> None:
        candidate = artifacts(
            {"Violence": (10, 10), "Task Adherence": (9, 10)}, status="partial"
        )
        self.assertEqual(evaluate_policy(candidate, POLICY)["decision"], "review_required")

    def test_quality_regression_blocks(self) -> None:
        candidate = artifacts({"Violence": (10, 10), "Task Adherence": (8, 10)})
        incumbent = artifacts({"Violence": (10, 10), "Task Adherence": (9, 10)})
        self.assertEqual(evaluate_policy(candidate, POLICY, incumbent)["decision"], "fail")

    def test_contract_failure_blocks(self) -> None:
        candidate = artifacts({"Violence": (10, 10), "Task Adherence": (9, 10)})
        contracts = {"decision": "fail", "failed_rows": 1}
        self.assertEqual(
            evaluate_policy(candidate, POLICY, contracts=contracts)["decision"], "fail"
        )

    def test_category_hard_gate_failure_blocks(self) -> None:
        candidate = artifacts({"Violence": (10, 10), "Task Adherence": (9, 10)})
        candidate["summary"]["per_category_results"] = {
            "adversarial": {
                "Task Adherence": {
                    "passed": 0,
                    "failed": 1,
                    "unknown": 0,
                    "total": 1,
                    "pass_rate": 0.0,
                }
            }
        }
        policy = {
            "name": "category-test",
            "category_hard_gates": [
                {
                    "categories": ["adversarial"],
                    "evaluators": ["Task Adherence"],
                    "minimum_pass_rate": 1.0,
                }
            ],
        }
        self.assertEqual(evaluate_policy(candidate, policy)["decision"], "fail")


class ContractTests(unittest.TestCase):
    def test_validates_expected_tool_call(self) -> None:
        row = {
            "item": {
                "query": "Weather?",
                "expected_tool_calls": [
                    {"name": "get_weather", "arguments": {"location": "Truro"}}
                ],
                "tool_definitions": [
                    {
                        "name": "get_weather",
                        "parameters": {
                            "type": "object",
                            "properties": {"location": {"type": "string"}},
                            "required": ["location"],
                        },
                    }
                ],
            },
            "sample": {
                "output_items": [
                    {
                        "type": "function_call",
                        "name": "get_weather",
                        "arguments": json.dumps({"location": "Truro"}),
                    }
                ]
            },
        }
        self.assertEqual(validate_row(row, 1)["outcome"], "pass")

    def test_rejects_tool_on_no_tool_case(self) -> None:
        row = {
            "item": {
                "query": "Book a flight",
                "expect_no_tool": True,
                "tool_definitions": [],
            },
            "sample": {
                "output_items": [
                    {"type": "function_call", "name": "book_flight", "arguments": "{}"}
                ]
            },
        }
        codes = {entry["code"] for entry in validate_row(row, 1)["issues"]}
        self.assertEqual(codes, {"unknown_tool", "unexpected_tool_call"})

    def test_file_result_fails_argument_type_mismatch(self) -> None:
        row = {
            "item": {
                "query": "Forecast",
                "tool_definitions": [
                    {
                        "name": "get_forecast",
                        "parameters": {
                            "properties": {"days": {"type": "integer"}},
                            "required": ["days"],
                        },
                    }
                ],
            },
            "sample": {
                "output_items": [
                    {
                        "type": "function_call",
                        "name": "get_forecast",
                        "arguments": json.dumps({"days": "three"}),
                    }
                ]
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "responses.jsonl"
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            result = validate_file(path)
        self.assertEqual(result["decision"], "fail")
        self.assertEqual(result["rows"][0]["issues"][0]["code"], "argument_type_mismatch")


if __name__ == "__main__":
    unittest.main()