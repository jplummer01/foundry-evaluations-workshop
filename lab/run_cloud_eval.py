"""Lab 1B / Lab 2A: run a cloud evaluation against the live demo agent.

Pattern (stable even as parameter names evolve):
  1. Upload the dataset to the project.
  2. Define testing criteria: evaluators + data mappings.
  3. Create the evaluation definition.
  4. Create the run with an azure_ai_target_completions data source pointing
     at the agent, then poll to completion.

Data-mapping syntax (the concept this lab exists to teach):
  {{item.X}}              -> a field from your test data, e.g. {{item.query}}
  {{sample.output_items}} -> the FULL agent/model response including tool calls
  {{sample.output_text}}  -> just the response message text

Usage:
  python run_cloud_eval.py                                   # weather agent, dataset.jsonl
  python run_cloud_eval.py --dataset dataset_gxp_sample.jsonl \
      --agent-name demo-sop-agent --run-name gxp-sample-run  # GxP variant
"""
import argparse
import os
import time
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

parser = argparse.ArgumentParser(description="Run a cloud evaluation against a live agent.")
parser.add_argument("--dataset", default="dataset.jsonl",
                    help="JSONL dataset file in this directory (default: dataset.jsonl)")
parser.add_argument("--agent-name", default=os.environ.get("DEMO_AGENT_NAME", "demo-weather-agent"),
                    help="Agent to evaluate (default: DEMO_AGENT_NAME env var or demo-weather-agent)")
parser.add_argument("--agent-version", default=os.environ.get("DEMO_AGENT_VERSION"),
                    help="Agent version (default: DEMO_AGENT_VERSION env var; omit for latest)")
parser.add_argument("--run-name", default="workshop-run", help="Name for the evaluation run")
args = parser.parse_args()

ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
JUDGE = os.environ["FOUNDRY_JUDGE_DEPLOYMENT"]
AGENT_NAME = args.agent_name
AGENT_VERSION = args.agent_version
DATASET_PATH = Path(__file__).parent / args.dataset
if not DATASET_PATH.exists():
    raise SystemExit(f"Dataset not found: {DATASET_PATH}")

project_client = AIProjectClient(endpoint=ENDPOINT, credential=DefaultAzureCredential())
client = project_client.get_openai_client()

# --- 1. Upload the dataset -----------------------------------------------------
dataset = project_client.datasets.upload_file(
    name=f"{AGENT_NAME}-eval-data",
    version="1",
    file_path=str(DATASET_PATH),
)
print(f"Dataset uploaded: {dataset.name} v{dataset.version}")

# --- 2. Testing criteria: one system, two process, one safety ------------------
# Intent Resolution (system): did the agent understand what was asked?
# Tool Call Accuracy (process): right tools, right parameters, no redundancy?
# Task Adherence (system): does the final answer do the job per its instructions?
# Violence (safety): hard-gate material; should trivially pass for this agent.
def ai_evaluator(name: str, evaluator: str, mapping: dict) -> dict:
    return {
        "type": "azure_ai_evaluator",
        "name": name,
        "evaluator_name": evaluator,
        "initialization_parameters": {"deployment_name": JUDGE},
        "data_mapping": mapping,
    }


testing_criteria = [
    ai_evaluator(
        "Intent Resolution",
        "builtin.intent_resolution",
        {"query": "{{item.query}}", "response": "{{sample.output_items}}"},
    ),
    ai_evaluator(
        "Tool Call Accuracy",
        "builtin.tool_call_accuracy",
        {"query": "{{item.query}}", "response": "{{sample.output_items}}"},
    ),
    ai_evaluator(
        "Task Adherence",
        "builtin.task_adherence",
        {"query": "{{item.query}}", "response": "{{sample.output_text}}"},
    ),
    {
        "type": "azure_ai_evaluator",
        "name": "Violence",
        "evaluator_name": "builtin.violence",
        "data_mapping": {"query": "{{item.query}}", "response": "{{sample.output_text}}"},
    },
]

# --- 3. Evaluation definition ---------------------------------------------------
evaluation = client.evals.create(
    name=f"{AGENT_NAME} - Workshop Lab 2A",
    data_source_config={
        "type": "azure_ai_source",
        "scenario": "responses",  # agent response evaluation
    },
    testing_criteria=testing_criteria,
)
print(f"Evaluation definition created: {evaluation.id}")

# --- 4. Run against the live agent ----------------------------------------------
target: dict = {"type": "azure_ai_agent", "name": AGENT_NAME}
if AGENT_VERSION:
    target["version"] = AGENT_VERSION

eval_run = client.evals.runs.create(
    eval_id=evaluation.id,
    name=args.run_name,
    data_source={
        "type": "azure_ai_target_completions",
        "source": {"type": "file_id", "id": dataset.id},
        "input_messages": {
            "type": "template",
            "template": [
                {
                    "type": "message",
                    "role": "user",
                    "content": {"type": "input_text", "text": "{{item.query}}"},
                }
            ],
        },
        "target": target,
    },
)
print(f"Evaluation run started: {eval_run.id}")

# --- 5. Poll --------------------------------------------------------------------
TERMINAL = {"completed", "failed", "canceled", "partial"}
status = eval_run.status
while status not in TERMINAL:
    time.sleep(15)
    eval_run = client.evals.runs.retrieve(eval_id=evaluation.id, run_id=eval_run.id)
    status = eval_run.status
    print(f"  status: {status}")

print(f"\nRun finished with status: {status}")
print("Open Evaluation in the Foundry portal to inspect per-row results.")
print("For each FAIL, read the judge's reasoning field - that's the lab exercise.")
print("Each result links back to the underlying agent trace for debugging.")
if status == "partial":
    print("\nPARTIAL usually means a data-mapping problem for one evaluator:")
    print("field names in data_mapping are case-sensitive against the dataset.")