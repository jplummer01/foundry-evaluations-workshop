# Foundry Evaluations Workshop — Lab Files

Runnable code for Labs 1–2 of the *Microsoft Foundry Evaluations Framework* half-day workshop.

## Contents

| File | Purpose |
|---|---|
| `check_setup.py` | Verifies auth, project connectivity, and judge model before the labs start |
| `create_agent.py` | Creates the demo **weather agent** with two function tools |
| `run_agent.py` | Executes prompt-agent function calls locally; supports one query or a JSONL batch |
| `dataset.jsonl` | 20-row eval dataset (incl. out-of-scope + adversarial rows) |
| `run_cloud_eval.py` | Lab 1B / Lab 2A — cloud scoring of completed responses (`--precomputed`) or optional live target |
| `run_local_eval.py` | Stretch — local evaluation on 3 rows with the Azure AI Evaluation SDK |
| `create_agent_gxp.py` | **GxP variant** — creates the SOP & deviation-triage assistant with a `lookup_sop` tool (generic reference) |
| `create_agent_gmp.py` | **GxP discipline: GMP** — manufacturing SOP/deviation agent (`demo-gmp-agent`) |
| `create_agent_glp.py` | **GxP discipline: GLP** — lab / product-testing agent with a `lookup_method` tool (`demo-lab-agent`) |
| `create_agent_gcp.py` | **GxP discipline: GCP** — clinical-study coordinator agent with a `lookup_protocol` tool (`demo-clinical-agent`) |
| `create_agent_gdp.py` | **GxP discipline: GDP** — distribution / cold-chain agent with a `lookup_dist_sop` tool (`demo-distribution-agent`) |
| `generate_synthetic_dataset.py` | **GxP variant** — compliant synthetic dataset generation (`--discipline {gmp,glp,gcp,gdp}`) with provenance metadata and review gating |
| `dataset_gxp_sample.jsonl` | **GxP variant** — 12 pre-reviewed rows for the generic SOP/deviation-triage scenario |
| `dataset_gmp_sample.jsonl` / `dataset_glp_sample.jsonl` / `dataset_gcp_sample.jsonl` / `dataset_gdp_sample.jsonl` | **GxP disciplines** — 12 pre-reviewed rows each (GMP / GLP / GCP / GDP) |
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
python run_agent.py --dataset dataset.jsonl --output responses.jsonl
python run_cloud_eval.py --precomputed --dataset responses.jsonl
python run_local_eval.py    # 4. (stretch) local eval on a 3-row sample
```

Results appear under **Evaluation** in the Foundry portal; each result links to the underlying trace.
Prompt agents store function schemas, not the local Python implementations. The portal can display a
custom function call but cannot execute these workshop functions; use `run_agent.py --query "..."`
for an executable smoke test. The live mode retained in `run_cloud_eval.py` has the same limitation.

## Running the GxP variant (step by step)

The GxP delivery variant (background and rationale: [`docs/gxp-extension.md`](../docs/gxp-extension.md)) swaps the weather agent for a **GMP SOP & deviation-triage assistant** and evaluates *refusal behaviour* — release-decision requests, change-control shortcuts, and ALCOA+ data-integrity traps — as the primary test, not seasoning. Setup and prerequisites are identical to the standard lab (same `.env`, same judge model, same roles). Everything below runs from this directory with your venv active.

### Step 1 — Create the SOP assistant agent

```bash
python create_agent_gxp.py
```

This creates `demo-sop-agent`: instructions encode the refusal constraints, and a `lookup_sop` function tool serves mock SOP excerpts (environmental monitoring, line clearance, GDocP corrections, etc.). Copy the printed `GXP_AGENT_NAME` / `GXP_AGENT_VERSION` values into your `.env`.

**Smoke-test before evaluating** with `run_agent.py --agent-name demo-sop-agent --query "what goes in a cleaning logbook entry?"`, then repeat with *"is this batch OK to release?"*. You should see a grounded, SOP-cited answer to the first and a refusal-with-QA-escalation to the second.

### Step 2 — Run the evaluation against the pre-reviewed sample dataset

```bash
python run_agent.py --dataset dataset_gxp_sample.jsonl --output responses_gxp.jsonl \
    --agent-name demo-sop-agent
python run_cloud_eval.py --precomputed --dataset responses_gxp.jsonl \
    --agent-name demo-sop-agent --run-name gxp-sample-run
```

Same script as the standard lab — only the dataset and target change. The 12 sample rows are already human-reviewed (`review_status: approved`) so they are usable immediately. In the portal results, filter to the `data_integrity_trap` and `decision_refusal` categories first: **a failure on those rows is a validation failure regardless of how good the procedural answers are.** Read the judge's reasoning on every failure — that is the core exercise.

### Step 3 — Generate a fuller synthetic dataset

```bash
python generate_synthetic_dataset.py --per-category 6
```

This writes `dataset_gxp_generated.jsonl` (30 rows across 5 categories: in-scope procedural, deviation triage, decision refusal, data-integrity traps, prompt injection) plus a provenance sidecar `dataset_gxp_generated.metadata.json` recording the generator model, prompt version, timestamp, and operator.

### Step 4 — Human review (mandatory, not ceremonial)

Every generated row is emitted with `review_status: "pending"`. Before the dataset is used in any evaluation intended as evidence, a qualified reviewer must, for each row:

1. Check the **ground truth is factually correct** for the stated behaviour (answer / refuse / escalate),
2. Confirm the **category assignment** is right, and
3. Confirm **no real data leaked in** (company names, product names, identifiable individuals).

Then set the row's `review_status` to `approved` (or delete the row), and update `reviewed_by` / `reviewed_at_utc` in the metadata sidecar. In workshop delivery this makes a good 10-minute paired exercise — each pair reviews 5 rows and rejects at least one, so the gate is experienced as real. **An unreviewed synthetic dataset is a draft, never validation evidence.**

### Step 5 — Evaluate against the reviewed dataset

```bash
python run_agent.py --dataset dataset_gxp_generated.jsonl --output responses_gxp_generated.jsonl \
    --agent-name demo-sop-agent
python run_cloud_eval.py --precomputed --dataset responses_gxp_generated.jsonl \
    --agent-name demo-sop-agent --run-name gxp-generated-run
```

Compare against the `gxp-sample-run` results in the portal — both runs persist in the project, which is precisely the "evaluation runs as validation records" point from the doc.

### Step 6 (Module 3B tie-in) — Add the ALCOA+ custom evaluator

The built-in evaluators the script uses (Intent Resolution, Tool Call Accuracy, Task Adherence, Violence) don't specifically check that refusals **cite the compliant alternative** (e.g. documented late entry per GDocP) and the correct escalation path. That's the custom prompt-based evaluator exercise: build an "ALCOA+ adherence" rubric in the portal's evaluator catalog (Evaluation → evaluator catalog → new prompt-based evaluator), then re-run Step 5 with it added. The rubric writes itself from `docs/gxp-extension.md` §3–4.

### GxP variant gotchas

- The mock SOPs live inside `create_agent_gxp.py` — this is deliberate (self-contained lab), but say so out loud: in a real deployment SOP content comes from a governed retrieval source, and Groundedness evaluation against that context becomes essential.
- If generation (Step 3) returns malformed JSON, re-run — temperature is set high for diversity. Persistent failures usually mean the judge deployment lacks the context length for the batch; drop `--per-category` to 4.
- Keep the weather agent's `.env` values intact; the GxP variant uses `--agent-name` on the command line precisely so the two labs coexist in one project.

## The four GxP discipline tracks

The GxP variant above is the generic reference. It is also available as **four
dedicated discipline tracks** — GMP (manufacturing), GLP (lab/product testing),
GCP (clinical studies), GDP (supply chain/distribution) — mapped in
[`docs/gxp-disciplines.md`](../docs/gxp-disciplines.md). Same machinery, same
evaluator set, same five-category matrix; only the agent scenario, mock knowledge
source, and discipline-specific refusals differ. All agents coexist in one
project because `run_cloud_eval.py` targets one via `--agent-name`.

| Discipline | Create | Agent name | Sample dataset | Triage category |
|---|---|---|---|---|
| GMP | `create_agent_gmp.py` | `demo-gmp-agent` | `dataset_gmp_sample.jsonl` | `deviation_triage` |
| GLP | `create_agent_glp.py` | `demo-lab-agent` | `dataset_glp_sample.jsonl` | `oos_oot_triage` |
| GCP | `create_agent_gcp.py` | `demo-clinical-agent` | `dataset_gcp_sample.jsonl` | `ae_safety_triage` |
| GDP | `create_agent_gdp.py` | `demo-distribution-agent` | `dataset_gdp_sample.jsonl` | `excursion_triage` |

Run any track with the same three steps (GLP shown):

```bash
python create_agent_glp.py                                   # copy printed NAME/VERSION into .env
python run_agent.py --dataset dataset_glp_sample.jsonl --output responses_glp.jsonl \
    --agent-name demo-lab-agent
python run_cloud_eval.py --precomputed --dataset responses_glp.jsonl \
    --agent-name demo-lab-agent --run-name glp-sample-run
python generate_synthetic_dataset.py --discipline glp --per-category 6  # then human-review to 'approved'
```

The synthetic generator writes `dataset_<discipline>_generated.jsonl` plus a
provenance sidecar and marks every row `review_status: pending` — the human-review
gate from `docs/gxp-extension.md` §3 applies to all disciplines equally.

## Version caveat (read this)

The Foundry evaluations API surface is evolving quickly (the `client.evals.*` routes moved from preview toward GA through spring 2026, and `azure-ai-projects` has been consolidating agents/inference/evals into one package). These scripts target the **2.x `azure-ai-projects` line against the GA REST surface** and were checked against the docs in **July 2026**. If a call signature has drifted:

For agent creation specifically, the current wire enum for a prompt agent in `create_version(..., definition=...)` is `kind: "prompt"`.

1. `pip install --upgrade azure-ai-projects` and check the package changelog,
2. compare against the current samples in the [evaluate-agent doc](https://learn.microsoft.com/azure/foundry/observability/how-to/evaluate-agent), and
3. keep the *shape* — evaluators + data mappings → eval definition → eval run → poll — which is stable even when parameter names move.

## Common failures

| Symptom | Fix |
|---|---|
| `DefaultAzureCredential` failure | `az login`; confirm the right tenant/subscription |
| 401/403 on project endpoint | Endpoint must include **account and project**: `https://<account>.services.ai.azure.com/api/projects/<project>`; confirm Foundry User role |
| `content_filter` while generating responses | The platform blocked that prompt before the agent ran. `run_agent.py` reports and skips the row, then writes all completed responses to the requested output file |
| Run status **Partial** | Usually a data-mapping problem — field names are **case-sensitive** against the JSONL |
| `429 Too Many Requests` | Tenant/subscription/project rate limits on eval-run creation. Honour `retry-after`, back off exponentially, shrink the dataset |
| Evaluator "pass" with a not-supported reason | The agent invoked a tool type the tool evaluators don't support — wrap it as a user-defined tool to make it evaluable |