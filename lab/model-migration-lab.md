# Optional Lab 3: Gate a model migration

**Time:** 35-45 minutes. This lab assumes the standard weather lab already runs end to end and that two compatible model deployments are available. It rehearses a controlled migration; it does not route production traffic or promote a baseline automatically.

## 1. Create incumbent and candidate versions

Keep the same agent name and create one version against each deployment. Record the two version numbers printed by the script.

```bash
FOUNDRY_AGENT_MODEL=<incumbent-deployment> python create_agent.py
FOUNDRY_AGENT_MODEL=<candidate-deployment> python create_agent.py

export INCUMBENT_VERSION=<first-version>
export CANDIDATE_VERSION=<second-version>
```

If only one model deployment is available, create two versions with a reviewed instruction change and label the exercise a workflow rehearsal, not a model comparison.

## 2. Generate comparable responses

Run both versions against the same 20 input cases. The source rows carry stable case IDs, cohorts, and deterministic tool expectations.

```bash
python run_agent.py --dataset dataset.jsonl --output responses-incumbent.jsonl \
  --agent-name demo-weather-agent --agent-version "$INCUMBENT_VERSION"
python check_contracts.py --dataset responses-incumbent.jsonl \
  --output artifacts/incumbent-contract-results.json

python run_agent.py --dataset dataset.jsonl --output responses-candidate.jsonl \
  --agent-name demo-weather-agent --agent-version "$CANDIDATE_VERSION"
python check_contracts.py --dataset responses-candidate.jsonl \
  --output artifacts/candidate-contract-results.json
```

A contract failure is a hard failure even when natural-language evaluator scores look acceptable.

## 3. Score both runs in one evaluation group

```bash
python run_cloud_eval.py --precomputed --dataset responses-incumbent.jsonl \
  --agent-name demo-weather-agent --agent-version "$INCUMBENT_VERSION" \
  --run-name migration-incumbent --artifacts-dir artifacts/incumbent

export EVALUATION_ID=$(python -c \
  'import json; print(json.load(open("artifacts/incumbent/run.json"))["eval_id"])')

python run_cloud_eval.py --precomputed --dataset responses-candidate.jsonl \
  --agent-name demo-weather-agent --agent-version "$CANDIDATE_VERSION" \
  --evaluation-id "$EVALUATION_ID" --run-name migration-candidate \
  --artifacts-dir artifacts/candidate
```

Each directory contains `run.json`, `output-items.jsonl`, and `summary.json`. `run.json` separates the input-item hash from the generated response-file hash so model differences do not invalidate a legitimate comparison.

## 4. Compare, then gate

Open the shared evaluation in Foundry and inspect confidence intervals and pairwise statistical comparison. A 20-row teaching set may be inconclusive; that is an honest result, not a pipeline error.

Then apply the explicit repository policy:

```bash
python eval_gate.py --candidate artifacts/candidate \
  --incumbent artifacts/incumbent \
  --policy ../examples/eval-gate-policy-weather.json \
  --contracts artifacts/candidate-contract-results.json
```

Exit `0` means policy pass, `1` means policy failure, and `2` means `review_required` because evidence or provenance is incompatible. The gate does not calculate p-values; Foundry remains the source for statistical significance.

Read `artifacts/candidate/gate-summary.md`, then inspect every regressed or failed row and its judge reasoning. Do not promote the candidate automatically.

## GxP adaptation

Use one discipline agent and its reviewed dataset, substitute `eval-gate-policy-gxp.json`, and review `decision_refusal` and `data_integrity_trap` first. Task Adherence is a workshop proxy for the domain rubric; register the optional ALCOA+ evaluator before treating that behavior as domain evidence. Never evaluate rows whose `review_status` is not `approved`.

## Failure injection

Change `FOUNDRY_JUDGE_DEPLOYMENT`, then score the candidate again **without** `--evaluation-id` so a separate evaluation definition is created. Compare that artifact with the incumbent: the policy gate should return `review_required` because the evaluation group and judge differ. Discuss dual-scoring an overlap set and establishing a reviewed new baseline before restoring the original judge.
