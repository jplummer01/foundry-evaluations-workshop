"""Pre-lab setup check: auth, project connectivity, judge model, dataset.

Run this before Lab 1. Everything should print [OK].
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

FAILURES = 0


def check(label: str, ok: bool, hint: str = "") -> None:
    global FAILURES
    print(f"[{'OK' if ok else 'FAIL'}] {label}" + (f"  -> {hint}" if not ok and hint else ""))
    if not ok:
        FAILURES += 1


# --- 1. Environment variables -------------------------------------------------
endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
judge = os.environ.get("FOUNDRY_JUDGE_DEPLOYMENT", "")
agent_model = os.environ.get("FOUNDRY_AGENT_MODEL", "")

check("FOUNDRY_PROJECT_ENDPOINT set", bool(endpoint), "copy from your project's overview page")
check(
    "Endpoint includes account AND project",
    ".services.ai.azure.com/api/projects/" in endpoint,
    "expected form: https://<account>.services.ai.azure.com/api/projects/<project>",
)
check("FOUNDRY_JUDGE_DEPLOYMENT set", bool(judge), "e.g. gpt-4.1-mini")
check("FOUNDRY_AGENT_MODEL set", bool(agent_model), "e.g. gpt-4.1-mini")

# --- 2. Credential ------------------------------------------------------------
try:
    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential()
    token = credential.get_token("https://ai.azure.com/.default")
    check("DefaultAzureCredential can acquire a token", bool(token.token))
except Exception as exc:  # noqa: BLE001
    check("DefaultAzureCredential can acquire a token", False, f"run `az login` ({exc})")
    credential = None

# --- 3. Project connectivity --------------------------------------------------
if credential and endpoint:
    try:
        from azure.ai.projects import AIProjectClient

        project_client = AIProjectClient(endpoint=endpoint, credential=credential)
        # Listing connections is a cheap read that exercises RBAC on the project.
        _ = list(project_client.connections.list())
        check("Project reachable with your role", True)
    except Exception as exc:  # noqa: BLE001
        check(
            "Project reachable with your role",
            False,
            f"confirm the Foundry User role on this project ({type(exc).__name__}: {exc})",
        )

# --- 4. Dataset sanity --------------------------------------------------------
dataset_path = Path(__file__).parent / "dataset.jsonl"
if dataset_path.exists():
    bad_lines = []
    with dataset_path.open() as fh:
        for i, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                if "query" not in row:
                    bad_lines.append(i)
            except json.JSONDecodeError:
                bad_lines.append(i)
    check(
        "dataset.jsonl is valid JSONL with a 'query' field per row",
        not bad_lines,
        f"check line(s): {bad_lines}",
    )
else:
    check("dataset.jsonl present", False, "run from the lab directory")

print()
if FAILURES:
    print(f"{FAILURES} check(s) failed - fix these before Lab 1.")
    sys.exit(1)
print("All checks passed. You're ready for Lab 1.")
