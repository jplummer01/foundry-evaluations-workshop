# Copilot instructions — Foundry Evaluations Workshop

This repo is **workshop content**, not a shipping application: a facilitator guide, a slide deck, runnable Python labs, and CI/CD reference pipelines for teaching **Microsoft Foundry Evaluations**. There is no build system, no test suite, and no linter. Treat correctness as "the lab scripts run end-to-end against a real Foundry project" and "the prose is technically accurate against the content baseline."

## Content baseline

All content targets a **July 2026** baseline (post-Build 2026): trace-based evaluation, the Rubric evaluator (preview), and Agent Optimizer. When editing prose, keep GA/preview feature labels consistent with this date — do not silently "update" feature status. The Foundry evaluations SDK surface drifts fast; the lab scripts target the **2.x `azure-ai-projects` line against the GA REST surface**. Preserve the stable *shape* — `evaluators + data mappings → evaluation definition → run → poll` — even when SDK parameter names have moved.

## Running the labs

Everything runs from `lab/` with a virtualenv active:

```bash
cd lab
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # fill in endpoint + deployment names
az login
python check_setup.py     # every line should print [OK] before proceeding
```

Standard run order: `check_setup.py` → `create_agent.py` → `run_cloud_eval.py` → `run_local_eval.py` (stretch). Requires an actual Foundry project, a deployed judge model, and the **Foundry User** role — there is no offline/mock mode, so scripts cannot be "tested" without Azure access. `az login` and the `.env` values (`FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_JUDGE_DEPLOYMENT`, `FOUNDRY_AGENT_MODEL`) are mandatory. The endpoint **must include both account and project**: `https://<account>.services.ai.azure.com/api/projects/<project>`.

## Two parallel lab tracks share one codebase

- **Standard track** — a `demo-weather-agent` (`create_agent.py`) with `get_weather`/`get_forecast` mock tools, evaluated against `dataset.jsonl` (20 rows incl. out-of-scope + adversarial).
- **GxP track** — a `demo-sop-agent` (`create_agent_gxp.py`) for pharma/life-sciences delivery, where *refusal behaviour* (release decisions, data-integrity/ALCOA+ traps) is the primary test, evaluated against `dataset_gxp_sample.jsonl` / a generated `dataset_gxp_generated.jsonl`.

Both tracks use the **same** `run_cloud_eval.py`; the GxP track only changes `--dataset` and `--agent-name` so both agents coexist in one project. When adding features, keep this coexistence intact — don't hardcode the weather agent. Rationale lives in `docs/gxp-extension.md` and `lab/README.md`.

## Conventions specific to this repo

- **Data mappings are the teaching point.** In `run_cloud_eval.py`, `{{item.X}}` pulls a field from the JSONL row, `{{sample.output_items}}` is the full response incl. tool calls, `{{sample.output_text}}` is just the message text. JSONL field names are **case-sensitive** — a mismatch surfaces as a `Partial` run status, not an error.
- **Mock tool data is deterministic on purpose** — conditions are seeded by location name so eval runs are comparable. Keep any new mock tools deterministic.
- **Synthetic GxP datasets are draft until reviewed.** `generate_synthetic_dataset.py` emits every row with `review_status: "pending"` plus a `.metadata.json` provenance sidecar. Rows must be human-reviewed to `approved` before use as evaluation evidence — this gate is a deliberate lab exercise, do not bypass it.
- **Lab scripts stay dependency-light and runnable end-to-end** on a fresh Foundry project (see `requirements.txt` — four packages). Don't add heavy dependencies or framework scaffolding.
- Each lab script's module docstring explains its role and flags SDK-drift risk; keep those docstrings current when editing.

## Layout

- `docs/` — `facilitator-guide.md` (agenda, talk tracks, module walkthroughs), `attendee-guide.md` (self-paced learner walkthrough), `model-deprecation-strategy.md`, `gxp-extension.md`.
- `lab/` — runnable Python + datasets (see `lab/README.md` for per-file purpose and the step-by-step GxP walkthrough).
- `examples/` — `azure-pipelines-eval.yml` / `github-actions-eval.yml` + `eval-gate-dataset.json`: evaluation as a CI gate (see below).
- `slides/` — the `.pptx` deck.
- `.vscode/mcp.json` — recommended MCP servers for working in this repo (see below).

The README "Common failures" and `lab/README.md` tables are the canonical troubleshooting reference (auth, `429` rate limits, `Partial` runs, unsupported tool evaluators) — reuse them rather than re-deriving fixes.

## CI/CD examples (`examples/`)

Two reference pipelines run evaluation as a gate; both authenticate with **Entra ID / OIDC — no long-lived secrets in the pipeline**.

- **GitHub Actions** (`github-actions-eval.yml`) — logs in via `azure/login@v2` OIDC federation, then runs the *same* `lab/run_cloud_eval.py` as a portable fallback (works without any marketplace action). Reads `FOUNDRY_PROJECT_ENDPOINT` / `FOUNDRY_JUDGE_DEPLOYMENT` / `AGENT_NAME` from repo **variables** (`vars.*`), not secrets. Important nuance: as written the script polls to completion but **exits 0 regardless of scores** — it runs the eval, it does not yet *enforce* a gate. Making it block a merge requires retrieving run results and `exit 1` on a threshold breach.
- **Azure DevOps** (`azure-pipelines-eval.yml`) — uses the `AIAgentEvaluation@2` task (AI Agent Evaluation extension) after an `AzureCLI@2` login via an ARM service connection. Its input is `eval-gate-dataset.json` (schema: `{"name", "evaluators": ["builtin.*"], "data": [{"query": ...}]}`). This task's summary reports per-metric scores **with confidence intervals** and a **pairwise statistical comparison** across agent versions — the "is this difference real or noise" feature.

Recommended gating policy (keep this consistent across both files): **safety evaluators (`builtin.violence`) are hard gates; quality evaluators are regression-vs-baseline gates.** When editing an example, keep env/variable names aligned with `lab/.env.example` so the fallback path stays runnable.

## Facilitator vs. attendee framing

`docs/facilitator-guide.md` is the delivery source of truth; align any workshop-facing edit with it. Its structure is a four-module arc — **1. Concepts & the evaluator taxonomy** (quality / safety / agent (system vs. process) / Rubric / custom) → **2. Lab 1: portal then SDK** → **3. Lab 2: live-agent, custom evaluators, trace-based eval** → **4. Governance, CI/CD & continuous evaluation** — plus a wrap-up and appendices (dataset starter, timing-flex). When touching workshop content, respect these facilitator realities:

- **Provision one Foundry project per attendee pair**, each with a deployed judge model and the **Foundry User** role.
- **`429` rate limits are the #1 lab failure** — eval-run creation is throttled at tenant/subscription/project level; guidance is stagger starts by table, raise judge-model TPM quota, and back off on `retry-after` (never "your code is broken").
- **Timing flex** (Appendix B) matters: there is a 90-minute cut-down and a labs-free leadership variant — don't add content that assumes the full 3.5–4h run.

`docs/attendee-guide.md` is the learner-facing counterpart (self-paced setup + run order for both the weather and GxP tracks, with the "read the judge's reasoning on every failure" core exercise). Keep the two guides consistent when either changes; the README "Self-paced learners" section links the attendee guide.

## MCP servers

`.vscode/mcp.json` recommends two HTTP MCP servers well-suited to keeping this fast-moving content accurate:

- **Microsoft Learn** (`https://learn.microsoft.com/api/mcp`) — authoritative Foundry/Azure docs and **GA/preview feature status**. Use it before changing any feature-status label away from the July 2026 baseline.
- **Context7** (`https://mcp.context7.com/mcp`) — current library/SDK docs (e.g. `azure-ai-projects`) for **checking call signatures when the SDK has drifted** — the exact failure mode the labs warn about.

Both are keyless public endpoints — do not add secrets to `mcp.json`.
