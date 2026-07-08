# Attendee Guide — Foundry Evaluations Workshop (self-paced)

A hands-on walkthrough for working through the labs on your own Foundry project. If you are *delivering* the workshop, use [`facilitator-guide.md`](facilitator-guide.md) instead — this guide is the learner-facing counterpart and stays consistent with it.

> **Content baseline: July 2026.** Feature GA/preview status and SDK signatures move quickly — if a script call has drifted, see [Keeping current](#keeping-current).

## What you'll do

1. Verify your environment, create a demo agent, and run a cloud evaluation against it.
2. Open the failing rows in the portal and **read the judge's reasoning** — that is the core exercise, not just getting a green run.
3. (Optional) Run a local evaluation, and/or work the **GxP variant** where agent *refusal behaviour* is the main test.

## Prerequisites

| Requirement | Notes |
|---|---|
| Azure subscription | Contributor on a sandbox subscription or resource group |
| Microsoft Foundry project | With an Azure OpenAI GPT **judge-model** deployment (e.g. `gpt-4.1-mini` or `gpt-5-mini`) |
| RBAC | **Foundry User** role on the project (recently renamed from *Azure AI User* — you may see either name) |
| Local tooling | Python 3.10+, Azure CLI (`az login`), VS Code recommended |
| For the trace demo | An Application Insights resource connected to the project, with some prior agent traffic |

There is **no offline/mock mode** — every lab script talks to a real Foundry project, so `az login` and a filled-in `.env` are mandatory.

## Setup

Everything runs from the `lab/` directory with a virtualenv active:

```bash
cd lab
python -m venv .venv && source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env      # then fill in the values below
az login
```

Fill in `.env`:

- `FOUNDRY_PROJECT_ENDPOINT` — **must include account AND project**: `https://<account>.services.ai.azure.com/api/projects/<project>`
- `FOUNDRY_JUDGE_DEPLOYMENT` — the judge model deployment name (AI-assisted evaluators)
- `FOUNDRY_AGENT_MODEL` — the model your agent runs on
- `DEMO_AGENT_NAME` / `DEMO_AGENT_VERSION` — set after `create_agent.py` prints them

## Run order — standard (weather) track

```bash
python check_setup.py     # 0. every line must print [OK] before you continue
python create_agent.py    # 1. creates 'demo-weather-agent' (two mock tools)
python run_cloud_eval.py  # 2. uploads dataset.jsonl, submits the eval, polls to completion
python run_local_eval.py  # 3. (stretch) local eval on a 3-row sample
```

The weather agent answers UK weather questions via `get_weather` / `get_forecast` and is *meant* to decline out-of-scope and adversarial requests — `dataset.jsonl` (20 rows) deliberately includes those so the abstention and safety evaluators have something to catch.

### The core exercise

When `run_cloud_eval.py` finishes, open **Evaluation** in the Foundry portal, find a **failing row**, and read the judge's reasoning field. Each result links back to the underlying agent trace. Understanding *why* the judge scored a row is the point of the whole lab — a green run tells you nothing you didn't already assume.

The evaluation applies four evaluators: **Intent Resolution** (system), **Tool Call Accuracy** (process), **Task Adherence** (system), and **Violence** (safety). The data mappings are the concept to internalise: `{{item.query}}` is a dataset field, `{{sample.output_items}}` is the full response including tool calls, `{{sample.output_text}}` is just the message text.

## Run order — GxP variant (optional)

The GxP track (rationale in [`gxp-extension.md`](gxp-extension.md)) swaps in a **GMP SOP & deviation-triage assistant** and makes *refusal behaviour* — release-decision requests, change-control shortcuts, and ALCOA+ data-integrity traps — the primary test. Same `.env`, same judge model, same roles; both agents coexist in one project because the eval script takes `--agent-name`.

```bash
python create_agent_gxp.py                                   # creates 'demo-sop-agent'; copy printed name/version into .env

python run_cloud_eval.py --dataset dataset_gxp_sample.jsonl \
    --agent-name demo-sop-agent --run-name gxp-sample-run    # 12 pre-reviewed rows

python generate_synthetic_dataset.py --per-category 6        # writes dataset_gxp_generated.jsonl + .metadata.json sidecar
# --- mandatory human review: set each row's review_status to "approved" before using it as evidence ---

python run_cloud_eval.py --dataset dataset_gxp_generated.jsonl \
    --agent-name demo-sop-agent --run-name gxp-generated-run
```

Two things to hold onto in this track:

- In the portal, **filter to the `data_integrity_trap` and `decision_refusal` categories first** — a failure there is a validation failure no matter how good the procedural answers are.
- **A synthetic dataset is a draft until reviewed.** `generate_synthetic_dataset.py` emits every row as `review_status: "pending"`; a qualified reviewer must confirm the ground truth, category, and that no real data leaked before the dataset counts as evaluation evidence.

Full step-by-step, including the custom ALCOA+ evaluator exercise, is in [`../lab/README.md`](../lab/README.md).

## Troubleshooting

Use the canonical tables rather than guessing — the top offenders and fixes are in the repo **[README "Common failures"](../README.md#common-failures-labs)** and **[`lab/README.md`](../lab/README.md#common-failures)**. The usual suspects:

- `DefaultAzureCredential` failure → `az login`; confirm the right tenant/subscription.
- `401/403` → your endpoint is missing the account/project path, or you lack the **Foundry User** role.
- Run status **Partial** → almost always a data-mapping issue; field names are **case-sensitive** against the JSONL.
- `429 Too Many Requests` → eval-run creation is rate-limited; honour `retry-after` and back off (this is expected, not a bug in your code).

## Keeping current

If a script call signature has drifted: `pip install --upgrade azure-ai-projects`, then diff against the current [evaluate-agent samples](https://learn.microsoft.com/azure/foundry/observability/how-to/evaluate-agent). Keep the *shape* — evaluators + data mappings → evaluation definition → run → poll — which is stable even when parameter names move.
