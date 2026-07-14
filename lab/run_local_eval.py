"""Stretch goal: local evaluation on a small sample with azure-ai-evaluation.

Why bother when cloud evals exist? Local runs give you second-scale iteration
while you're still designing rubrics and datasets - and local evaluators are
now aligned with the hosted evaluator catalog, so what you tune locally
transfers to cloud and continuous evaluation.

This scores a 3-row, pre-generated sample (no live agent calls) so it runs
fast and offline-ish. Only the judge model is called.
"""
import json
import os

from azure.ai.evaluation import FluencyEvaluator, RelevanceEvaluator
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

# Judge model config: the AI-assisted evaluators call this deployment.
judge_deployment = os.environ["FOUNDRY_JUDGE_DEPLOYMENT"]
model_config = {
    "azure_endpoint": os.environ["FOUNDRY_PROJECT_ENDPOINT"].split("/api/projects/")[0],
    "azure_deployment": judge_deployment,
}
uses_reasoning_parameters = judge_deployment.lower().startswith(("gpt-5", "o1", "o3", "o4"))

# Three canned rows: one good, one waffly, one off-topic - so the scores differ.
SAMPLE = [
    {
        "query": "What's the weather in Truro today?",
        "response": "It's partly cloudy in Truro, around 16 degrees C with a 12 mph breeze.",
    },
    {
        "query": "Will it rain in Penzance this weekend?",
        "response": "Weather is a complex system influenced by many atmospheric factors "
        "that meteorologists study carefully using various models and instruments.",
    },
    {
        "query": "Compare today's temperature in Exeter and Plymouth.",
        "response": "Exeter is a lovely cathedral city with a rich history dating to Roman times.",
    },
]


def main() -> None:
    credential = DefaultAzureCredential()
    relevance = RelevanceEvaluator(
        model_config=model_config,
        credential=credential,
        is_reasoning_model=uses_reasoning_parameters,
    )
    fluency = FluencyEvaluator(
        model_config=model_config,
        credential=credential,
        is_reasoning_model=uses_reasoning_parameters,
    )

    for i, row in enumerate(SAMPLE, start=1):
        rel = relevance(query=row["query"], response=row["response"])
        flu = fluency(response=row["response"])
        print(f"--- Row {i}: {row['query']}")
        print(json.dumps({"relevance": rel, "fluency": flu}, indent=2, default=str))
        print()

    print("Note how row 2 is fluent but irrelevant, and row 3 fails relevance")
    print("outright - fluency alone is a terrible quality gate. That's why the")
    print("workshop pairs quality evaluators with task adherence in CI.")


if __name__ == "__main__":
    main()
