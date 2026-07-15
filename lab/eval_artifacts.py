"""Normalize Foundry evaluation output into stable workshop artifacts."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


def to_jsonable(value: Any) -> Any:
    """Convert SDK models and nested values to JSON-compatible objects."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value


def canonical_sha256(value: Any) -> str:
    """Return a stable SHA-256 digest for a JSON-compatible value."""
    payload = json.dumps(
        to_jsonable(value),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file without loading it all at once."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def jsonl_items_sha256(path: Path) -> str:
    """Hash the ordered input items in a precomputed evaluation JSONL file."""
    items: list[Any] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or not isinstance(row.get("item"), dict):
                raise ValueError(f"Expected an item object at {path}:{line_number}.")
            items.append(row["item"])
    return canonical_sha256(items)


def comparison_mismatches(
    candidate: dict[str, Any], incumbent: dict[str, Any]
) -> list[dict[str, Any]]:
    """Identify provenance fields that make direct score comparison invalid."""
    fields = {
        "eval_id": (
            candidate.get("eval_id"),
            incumbent.get("eval_id"),
        ),
        "dataset.sha256": (
            candidate.get("dataset", {}).get("sha256"),
            incumbent.get("dataset", {}).get("sha256"),
        ),
        "criteria_sha256": (
            candidate.get("criteria_sha256"),
            incumbent.get("criteria_sha256"),
        ),
        "judge_deployment": (
            candidate.get("judge_deployment"),
            incumbent.get("judge_deployment"),
        ),
    }
    return [
        {"field": field, "candidate": values[0], "incumbent": values[1]}
        for field, values in fields.items()
        if values[0] != values[1]
    ]


def normalize_output_item(value: Any) -> dict[str, Any]:
    """Normalize one SDK output item and retain evaluator reasoning."""
    item = to_jsonable(value)
    if not isinstance(item, dict):
        raise TypeError("Evaluation output items must serialize to JSON objects.")

    datasource_item = item.get("datasource_item")
    source = datasource_item if isinstance(datasource_item, dict) else {}
    source_item = source.get("item") if isinstance(source.get("item"), dict) else source

    results: list[dict[str, Any]] = []
    for raw_result in item.get("results") or []:
        result = to_jsonable(raw_result)
        if not isinstance(result, dict):
            continue
        passed = result.get("passed")
        if passed is None and isinstance(result.get("label"), str):
            passed = result["label"].lower() == "pass"
        results.append(
            {
                "name": result.get("name") or result.get("metric") or "unknown",
                "metric": result.get("metric"),
                "passed": passed if isinstance(passed, bool) else None,
                "label": result.get("label"),
                "score": result.get("score"),
                "threshold": result.get("threshold"),
                "reason": result.get("reason"),
                "details": result.get("details"),
            }
        )

    return {
        "id": item.get("id"),
        "eval_id": item.get("eval_id"),
        "run_id": item.get("run_id"),
        "status": item.get("status"),
        "case_id": source_item.get("case_id"),
        "category": source_item.get("category"),
        "query": source_item.get("query"),
        "datasource_item": datasource_item,
        "results": results,
    }


def build_summary(output_items: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate normalized output items by evaluator and dataset category."""
    items = list(output_items)
    criteria: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"passed": 0, "failed": 0, "unknown": 0, "total": 0}
    )
    categories: dict[str, dict[str, dict[str, Any]]] = defaultdict(
        lambda: defaultdict(lambda: {"passed": 0, "failed": 0, "unknown": 0, "total": 0})
    )

    for item in items:
        category = item.get("category") or "uncategorized"
        for result in item.get("results") or []:
            name = str(result.get("name") or "unknown")
            passed = result.get("passed")
            for bucket in (criteria[name], categories[category][name]):
                bucket["total"] += 1
                if passed is True:
                    bucket["passed"] += 1
                elif passed is False:
                    bucket["failed"] += 1
                else:
                    bucket["unknown"] += 1

    for bucket in list(criteria.values()) + [
        metric for category in categories.values() for metric in category.values()
    ]:
        known = bucket["passed"] + bucket["failed"]
        bucket["pass_rate"] = bucket["passed"] / known if known else None

    return {
        "row_count": len(items),
        "result_counts": {
            "passed": sum(
                1
                for item in items
                if item.get("results")
                and all(result.get("passed") is True for result in item["results"])
            ),
            "failed": sum(
                1
                for item in items
                if any(result.get("passed") is False for result in item.get("results") or [])
            ),
            "total": len(items),
        },
        "per_testing_criteria_results": dict(sorted(criteria.items())),
        "per_category_results": {
            category: dict(sorted(metrics.items()))
            for category, metrics in sorted(categories.items())
        },
    }


def write_json(path: Path, value: Any) -> None:
    """Write deterministic, readable JSON and create parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_jsonable(value), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, values: Iterable[Any]) -> None:
    """Write JSONL and create parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as destination:
        for value in values:
            destination.write(
                json.dumps(to_jsonable(value), ensure_ascii=True, sort_keys=True) + "\n"
            )