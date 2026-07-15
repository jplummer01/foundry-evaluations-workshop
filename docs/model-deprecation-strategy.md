# Managing LLM Deprecation with an Evaluation Strategy

Provider models deprecate and update on the provider's schedule, not yours. "High confidence before migration" is therefore achieved almost entirely through **your own continuously-run evaluation infrastructure** — not by trusting provider benchmark claims, which rarely reflect your specific task distribution.

This doc extends the workshop with a concrete application: **model migration as a controlled deployment, gated by evaluation at every stage.** The workshop teaches the machinery; this is one of the strongest business cases for building it.

## Core principle

Treat a model migration exactly like any other production deployment: candidate → evaluate → shadow → canary → promote → monitor, with automated gates between each stage. Nothing about "the provider is retiring gpt-x on date Y" changes the shape of this pipeline — it only sets the deadline.

## The six practices, mapped to Foundry evaluation features

| # | Practice | Foundry mechanism (workshop module) |
|---|---|---|
| 1 | **Versioned evaluation harness** — golden datasets, regression tests, task metrics, LLM-as-judge | Cloud evaluations with the built-in + custom evaluator catalog; datasets versioned as project data assets (Modules 1–2) |
| 2 | **Pin model versions explicitly** | Deployment-level pinning; never point production at a floating alias |
| 3 | **Abstract the model behind a gateway** | APIM AI gateway / adapter layer — swap via config, never in app code |
| 4 | **Shadow / mirror traffic before cutover** | **Trace-based evaluation**: grade the candidate's shadow outputs against real production inputs, no user exposure (Module 3C) |
| 5 | **Canary / progressive rollout with rollback triggers** | **Continuous evaluation + Azure Monitor alerts** on evaluator-score degradation per cohort (Module 4.2) |
| 6 | **Continuous production monitoring** | Continuous evaluation, Agent Monitoring Dashboard, eval↔trace linking for debugging regressions (Module 4.2) |

### 1. The evaluation harness is the migration asset

Everything in Labs 1–2 doubles as migration tooling:

- **Golden dataset** = the workshop's JSONL pattern, grown from real production traffic (trace-based evaluation makes harvesting representative cases nearly free).
- **Regression rows** = every case that previously failed and was fixed. A migration must never silently reintroduce one.
- **The comparison unit is the full configuration**, not just the model name. Record the incumbent and candidate model snapshots, agent version, prompt/system-message version, tool-schema version, inference settings, dataset version or hash, evaluator/rubric version, judge deployment/version, and Foundry run IDs. Without that manifest, a regression is difficult to attribute or reproduce.
- **Same evaluators, held constant** — run candidate vs. incumbent on the *same* dataset with the *same* judge model, and compare **deltas, not absolute scores**. If the judge model must change, score an overlap set with both judges, document the discontinuity, and establish a new baseline; do not treat scores from different judges as one continuous series. In a GxP context, that judge change is itself a change-control event.
- **Migration-specific criteria** — use built-in and custom evaluators for known contracts; the Rubric evaluator (public preview in the workshop's July 2026 baseline) can propose weighted criteria from the agent definition and use case. Review generated criteria before treating them as a gate.
- **Statistical comparison where the pipeline supports it** — the Azure DevOps `AIAgentEvaluation@2` and GitHub `microsoft/ai-agent-evals@v3-beta` examples render native comparison reports for hosted agents. Public documentation does not define machine-readable threshold outputs for those tasks. The separate precomputed-response workflows retrieve normalized results and enforce explicit repository policy for this workshop's local-tool agents; Foundry remains the source for confidence intervals and statistical significance.

### 2–3. Pinning and abstraction make migration a config change

Pin dated/versioned snapshots so a provider-side update can't change behaviour underneath you — deprecation then becomes a scheduled event you control rather than a surprise. Route all calls through a gateway/adapter layer (APIM AI gateway with model routing fits naturally here): no app code should name a model directly, and the cutover itself becomes a routing-policy change with an instant rollback path.

Do not leave that rollback path theoretical. Exercise a "primary unavailable" scenario before cutover and verify that the gateway selects the intended fallback, preserves authentication and request contracts, and still produces acceptable evaluated responses.

### Compatibility is broader than answer quality

A candidate can score well on natural-language quality while breaking the surrounding application. Add deterministic gates for the contracts the application depends on:

- Tool selection, argument names/types, call ordering, and handling of tool errors
- Structured-output or JSON-schema validity, citations, and grounding requirements
- Context-window and truncation behaviour, token/stop settings, and streaming where clients depend on it
- Intended refusal behaviour and safety-filter changes, especially for the GxP datasets where refusing release decisions and data-integrity traps is the primary requirement

The workshop's tool evaluators and code-based custom evaluator pattern are the right mechanisms. Treat a tool-evaluator result marked "not supported" as missing evidence, not as proof of compatibility.

### 4. Shadow traffic: where trace-based evaluation shines

Mirror live production requests to the candidate model without serving its responses. Then:

1. Both incumbent and candidate emit OpenTelemetry traces into Application Insights.
2. Run **trace-based evaluations** over each stream — same evaluators, same window.
3. Diff evaluator scores *and* read the judge reasoning on divergent rows. Shadow traffic surfaces the real-world edge cases your golden dataset misses, at zero user risk.

Because trace-based evaluation keys off OpenTelemetry conventions, this can cover candidates running on different frameworks or serving infrastructure. Trace-based evaluation for external/any-framework agents is preview in the workshop's July 2026 baseline, so verify current support before making it a production dependency.

Define the shadow exit criteria before starting: required risk-bearing workflows and cohorts must be represented, divergent rows must be reviewed, and the agreed quality, safety, cost, and latency bounds must hold. There is no universal sample count; choose the evidence volume and observation window from traffic diversity, metric variance, and consequence of failure.

### 5–6. Canary with evaluation-driven rollback, then keep watching

Ramp 1% → 5% → 25% → 100%, with an explicit observation window and promotion/rollback criteria at each stage. Segment evaluation by risk-bearing cohort — for example language, region, user tier, workflow, or GxP discipline — so an aggregate average cannot hide a serious local regression. Early, low-volume cohorts may need a higher evaluation sampling rate than the steady-state service.

Wire Azure Monitor alerts on:

- Evaluator score degradation (continuous evaluation on the canary cohort)
- Operational drift — latency, token consumption, cost per request (models often change token efficiency between generations)
- **Refusal/safety-filter rate changes**, which frequently shift between model generations and are easy to miss with quality metrics alone
- User signals: escalations, correction rate, thumbs

Name the person or team authorised to roll back, and make the routing reversal a rehearsed operation. Capacity is part of readiness too: shadowing adds candidate-model calls while evaluation consumes separate judge-model TPM and cost. Request quota early, use `retry-after` backoff, and plan concurrency — `429` throttling is already the workshop's most common lab failure.

Post-migration, continuous evaluation keeps running — the new model becomes the incumbent baseline for the *next* migration. The Agent Monitoring Dashboard is preview in the July 2026 baseline. Agent Optimizer can turn trace and evaluation evidence into ranked improvement proposals, but those proposals require human review and a new gated version; they are never an automatic production change, especially in GxP workflows.

## Prompts migrate too

Prompts are usually overfit to a specific model's quirks. Budget for **prompt re-tuning as part of every migration**, and version prompts alongside models so an eval result is always attributable to a (model version, prompt version) pair. Evaluate the incumbent prompt/candidate model before tuning, then the tuned prompt/candidate model, so the evidence distinguishes model effects from prompt effects. Keep prompts model-agnostic where feasible, but expect the eval harness — not hope — to tell you when re-tuning is done.

## The decision gate

Promote a candidate only when **all** of the following clear:

- [ ] Comparison manifest captures the model, agent, prompt, tool schema, inference settings, dataset, evaluators/rubrics, judge, and run IDs
- [ ] Eval suite ≥ incumbent on every priority metric; no statistically significant regression on any (use the pairwise comparison, not eyeballs)
- [ ] Tool calls, structured outputs, citations, truncation, and other application contracts remain compatible
- [ ] Shadow-traffic diffs reviewed, divergent-row judge reasoning read, and every risk-bearing cohort has sufficient evidence
- [ ] Cost, latency, token use, and serving/evaluation quota are within budget
- [ ] Safety/refusal behaviour acceptable (safety evaluators are **hard gates**)
- [ ] Prompts re-validated against the candidate
- [ ] Gateway fallback and routing rollback rehearsed; rollback owner and triggers named
- [ ] Promotion decision approved and retained with the Foundry run references; retention, deletion control, and tamper-evident export meet organisational policy (and regulated-record requirements where applicable)

## Deprecation timeline hygiene

- Track provider deprecation notices; record each model's announced retirement date in your service catalog.
- Treat announcement-to-shutdown as a **hard project deadline**, not aspirational.
- Track the judge model's retirement independently and leave enough overlap to dual-score and re-baseline before either model disappears.
- Maintain a fallback chain so a deprecated or unavailable primary degrades gracefully to a known-good alternative — enforced at the gateway, verified by the eval harness.

## Workshop tie-in

If delivering the workshop to a team facing a live deprecation, this doc makes a strong Module 4 closing discussion: *"You have 90 days until your primary model retires — walk the pipeline above and identify which stage you couldn't execute today."* The gaps that surface are the evaluation investments to prioritise.

Be explicit about the boundary of the repository: the labs make batch evaluation, data mappings, agent execution, normalized run artifacts, deterministic tool-contract checks, and incumbent/candidate policy enforcement runnable. The optional migration lab and precomputed CI examples reuse one evaluation group for native Foundry comparison and block on explicit repository policy. Trace-based evaluation is a facilitator demo that requires existing telemetry. Continuous-evaluation alerting, APIM routing, canary traffic, automated rollback, immutable retention, and baseline promotion remain production architecture patterns, not capabilities implemented by these lab scripts.
