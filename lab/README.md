# Foundry Evaluations Workshop — Lab Files

Runnable code for Labs 1–2 of the *Microsoft Foundry Evaluations Framework* half-day workshop.

## Contents

| File | Purpose |
|---|---|
| `check_setup.py` | Verifies auth, project connectivity, and judge model before the labs start |
| `create_agent.py` | Creates the demo **weather agent** with two function tools |
| `dataset.jsonl` | 20-row eval dataset (incl. out-of-scope + adversarial rows) |
| `run_cloud_eval.py` | Lab 1B / Lab 2A — cloud evaluation targeting the live agent |
| `run_local_eval.py` | Stretch — local evaluation on 3 rows with the Azure AI Evaluation SDK |
| `.env.example` | Environment variable template |
| `requirements.txt` | Pinned dependencies |

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env    # then fill in your values
az login
```

Required roles: **Foundry User** on the project (formerly *Azure AI User* — you may see either name during the rename rollout). Your project needs a deployed GPT judge model (e.g. `gpt-4.1-mini` or `gpt-5-mini`).

## Run order

```bash
python check_setup.py       # 0. everything green before you start
python create_agent.py      # 1. creates 'demo-weather-agent' in your project
python run_cloud_eval.py    # 2. submits the cloud evaluation and polls to completion
python run_local_eval.py    # 3. (stretch) local eval on a 3-row sample
```

Results appear under **Evaluation** in the Foundry portal; each result links to the underlying trace.

## Version caveat (read this)

The Foundry evaluations API surface is evolving quickly (the `client.evals.*` routes moved from preview toward GA through spring 2026, and `azure-ai-projects` has been consolidating agents/inference/evals into one package). These scripts target the **2.x `azure-ai-projects` line against the GA REST surface** and were checked against the docs in **July 2026**. If a call signature has drifted:

1. `pip install --upgrade azure-ai-projects` and check the package changelog,
2. compare against the current samples in the [evaluate-agent doc](https://learn.microsoft.com/azure/foundry/observability/how-to/evaluate-agent), and
3. keep the *shape* — evaluators + data mappings → eval definition → eval run → poll — which is stable even when parameter names move.

## Common failures

| Symptom | Fix |
|---|---|
| `DefaultAzureCredential` failure | `az login`; confirm the right tenant/subscription |
| 401/403 on project endpoint | Endpoint must include **account and project**: `https://<account>.services.ai.azure.com/api/projects/<project>`; confirm Foundry User role |
| Run status **Partial** | Usually a data-mapping problem — field names are **case-sensitive** against the JSONL |
| `429 Too Many Requests` | Tenant/subscription/project rate limits on eval-run creation. Honour `retry-after`, back off exponentially, shrink the dataset |
| Evaluator "pass" with a not-supported reason | The agent invoked a tool type the tool evaluators don't support — wrap it as a user-defined tool to make it evaluable |
