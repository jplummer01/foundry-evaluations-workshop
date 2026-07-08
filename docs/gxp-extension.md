# GxP Delivery Variant: Evaluations as Validation Evidence

This extension adapts the workshop for pharmaceutical / life-sciences audiences operating under **GxP** (Good Practice) regulations — GMP, GCP, GLP, GDP, GPvP, GAMP, and GDocP. It changes the framing, the lab scenario, and the dataset strategy, but **not the machinery**: everything in Modules 1–4 applies unchanged. What changes is *why* it matters — in a GxP environment, evaluation results are not engineering hygiene, they are **validation evidence** that must withstand regulatory inspection.

> The GxP primer this variant assumes: GxP is the umbrella family of quality standards governing the pharmaceutical lifecycle. Its compliance spine — documentation and data integrity (ALCOA+), SOPs, training, change control, and CAPA — applies to any computerised system that creates, modifies, or archives GxP-relevant data. An LLM agent operating in a regulated process **is such a system**.

## 1. The regulatory anchor points (as of July 2026)

| Anchor | What it says | What it means for LLM evaluation |
|---|---|---|
| **FDA draft guidance on AI in regulatory decision-making** (Jan 2025, finalisation expected 2026) | Risk-based, 7-step **credibility assessment framework**: define the question of interest, the context of use (COU), assess model risk, then develop a credibility assessment plan and evidence | Your evaluation plan *is* the credibility assessment plan. Evaluators, datasets, and thresholds must be justified against the stated context of use |
| **FDA–EMA Guiding Principles of Good AI Practice in Drug Development** (Jan 2026) | Ten lifecycle principles incl. human-centric design, risk-based performance assessment, data governance, life-cycle management | "Risk-based performance assessment" + "life-cycle management" = pre-deployment evaluation **plus continuous evaluation in production**. A one-time validation exercise no longer meets expectations |
| **GAMP 5 (2nd ed.)** incl. AI/ML appendix | Risk-based computerised system validation; shift toward critical thinking over documentation volume (aligned with FDA CSA) | Categorise the agent by GAMP software category and patient/product risk; scale evaluation rigour accordingly |
| **21 CFR Part 11 / EU Annex 11** | Electronic records & signatures: attributability, audit trails, access control | Evaluation runs, datasets, and promotion decisions are electronic records. Entra ID-only auth, RBAC, and persisted Foundry runs map directly |
| **ALCOA+** (GDocP) | Records must be Attributable, Legible, Contemporaneous, Original, Accurate + Complete, Consistent, Enduring, Available | Applies to eval datasets, run results, and judge configurations — see §3 |

## 2. Mapping GxP compliance pillars to Foundry evaluation capabilities

| GxP pillar | Foundry mechanism (workshop module) |
|---|---|
| **Validation / performance qualification** | Cloud evaluation runs against a versioned dataset with documented evaluators and thresholds; persisted in the project as evidence (Modules 2–3). Think of the eval suite as the executable PQ protocol and each run as a PQ execution record |
| **Data integrity (ALCOA+)** | Runs are attributable (Entra identity), contemporaneous (timestamps), original & complete (persisted results linked to underlying traces), available (portal + API export). Gaps to close yourself: retention policy and tamper-evidence — see §5 |
| **Change control** | A model/prompt/agent change = a controlled change. The CI/CD evaluation gate with pairwise statistical comparison (Module 4.1, `examples/`) produces the objective evidence a change-control record requires. `docs/model-deprecation-strategy.md` is a worked example: its decision-gate checklist is a change-control assessment in all but name |
| **CAPA** | Production evaluation failures → investigate via eval↔trace linking → Agent Optimizer proposals reviewed and dispositioned by a human. Optimizer output is *input to* CAPA, never auto-applied (see human oversight, §5) |
| **Continuous monitoring / GPvP analogy** | Continuous evaluation + Azure Monitor alerting (Module 4.2) is post-deployment surveillance for the agent — the same lifecycle logic pharmacovigilance applies to the product itself |
| **Training & competency** | The workshop itself, delivered with a documented attendance/assessment record, satisfies the role-specific training expectation for teams operating the evaluation system |
| **SOPs** | The facilitator guide's lab procedures convert readily into SOP drafts: "Creating and approving an evaluation dataset", "Executing a pre-deployment evaluation", "Responding to a continuous-evaluation alert" |

## 3. Synthetic datasets: why, and how to do it compliantly

### Why synthetic is the right default in GxP

1. **You usually cannot use real data.** Real GxP records (batch records, deviation reports, ICSRs, clinical queries) contain patient data, proprietary process detail, or both. Putting them in an evaluation dataset creates GDPR/HIPAA exposure and turns your eval infrastructure into a GxP records system with far heavier controls.
2. **Coverage beats realism for validation.** A credibility assessment needs the *scenario space* covered — including rare, adversarial, and out-of-scope cases that real traffic under-represents. Synthetic generation lets you design coverage deliberately: happy paths, edge cases, refusal cases, data-integrity traps.
3. **Synthetic data is reviewable and shareable.** A synthetic dataset can be inspected, approved, versioned, and even published (as this repo's sample is) without confidentiality gymnastics.

### The compliant generation workflow

The lab script `lab/generate_synthetic_dataset.py` implements this pattern:

1. **Define the context of use first** (FDA 7-step framework language): what the agent does, what it must refuse, what risk class it sits in. The generation prompt is derived from the COU, not invented ad hoc.
2. **Generate by category, not in bulk.** The script generates against an explicit category matrix — in-scope procedural Q&A, deviation-triage scenarios, out-of-scope requests, data-integrity traps (e.g. requests to backdate or omit), and prompt-injection attempts — with a target row count per category. This makes coverage auditable.
3. **Capture generation provenance.** The script writes a metadata sidecar (generator model + version, prompt, parameters, timestamp, operator) alongside the JSONL. Under ALCOA+, the dataset's origin must be attributable and the record complete.
4. **Human review is the release gate.** Synthetic rows are *drafts* until a qualified reviewer approves them — checking factual correctness of ground truths, category assignment, and absence of real data leakage. The script marks output `review_status: pending` for exactly this reason. **An unreviewed synthetic dataset must never be used as validation evidence.**
5. **Version and freeze.** Approved datasets are uploaded to the Foundry project as versioned data assets and treated as controlled records. A dataset change is a change-control event (it invalidates comparability with prior runs).

### Trace-based evaluation still applies — carefully

Once in production, trace-based evaluation (Module 3C) evaluates *real* interactions. In GxP contexts, confirm with your privacy/quality functions that traces are scrubbed or pseudonymised before evaluation, and that the App Insights retention configuration meets your record-retention SOPs. Synthetic for pre-deployment validation, governed-real for post-deployment surveillance is the usual split.

## 4. The GxP lab scenario: SOP & deviation-triage assistant

Swap the weather agent for a **GMP SOP assistant**: an agent that answers procedural questions grounded in a small set of mock SOPs and helps classify deviations — but must **refuse** to make release decisions, approve changes, or assist with anything that violates data integrity.

Why this scenario teaches well:

- **Task Adherence and Intent Resolution become compliance behaviours.** "The agent must not answer batch-release questions" is a system-message constraint that Task Adherence directly scores.
- **The refusal rows are the point.** In the weather workshop, adversarial rows are seasoning; here they're the main course. Data-integrity traps ("just backdate the entry", "log it as within range anyway") test whether the agent upholds ALCOA+ — a failure here is a validation failure regardless of how good the procedural answers are.
- **Human oversight is built into the ground truths.** Per the FDA–EMA principles, final decisions remain with qualified professionals; the expected behaviour for anything decision-shaped is *escalate to QA*, not answer.

`lab/dataset_gxp_sample.jsonl` ships 12 pre-reviewed sample rows across the category matrix so facilitators can run the GxP variant without depending on live generation. Generate the full dataset with `generate_synthetic_dataset.py`, then review before use.

### Suggested evaluator set for the GxP labs

- `builtin.task_adherence` — hard gate (encodes the refusal constraints)
- `builtin.intent_resolution` — did it recognise decision-shaped requests as out of scope?
- `builtin.groundedness` — answers must be grounded in the provided SOP context, not model memory
- One **custom prompt-based evaluator**: "ALCOA+ adherence" — does the response refuse data-integrity violations and cite the correct escalation path? (Excellent Module 3B exercise: the rubric writes itself from §3 of any GDocP training deck)
- Safety evaluators as always-on hard gates

## 5. Gaps Foundry does not close for you (say this out loud in Module 4)

Be straight with a GxP audience about the boundary of the tooling:

1. **Foundry evaluation is not "GxP certified"** — there is no such certification. It provides *capabilities* (persistence, attributability, linkage, statistics) that support your validation approach; the validation responsibility, risk assessment, and documented rationale remain yours under GAMP 5.
2. **The judge model is itself software in your validated landscape.** Judge choice and rubric are part of the credibility assessment; a judge-model change invalidates score comparability and is a change-control event. Pin it, document it, re-baseline when it changes.
3. **Retention and tamper-evidence need explicit design.** Confirm evaluation-run retention against your record-retention SOPs; export run results to immutable storage (e.g. immutable blob with legal hold) if your interpretation of Part 11 requires it.
4. **Human oversight is a process control, not a product feature.** Agent Optimizer proposals, dataset approvals, and promotion decisions all need named, qualified humans in the loop — build that into SOPs, not hopes.
5. **Regulatory status is moving.** The FDA draft guidance was expected to finalise during 2026 — verify current status before presenting, exactly as with Foundry feature GA status.

## 6. Delivering the GxP variant: agenda deltas

| Slot | Change from the standard workshop |
|---|---|
| Module 1 (45') | Open with §1's anchor table instead of the generic "agents fail differently" framing — for this audience, the regulator has already made the case. Keep the taxonomy and LLM-as-judge sections; add the "judge is validated software too" point |
| Lab 1 (60') | Unchanged mechanics; run against `dataset_gxp_sample.jsonl` |
| Lab 2 (45') | Part A targets the SOP assistant; Part B builds the ALCOA+ custom evaluator (replaces the generic tone example); Part C unchanged but add the trace-scrubbing caveat |
| Module 4 (45') | Reframe 4.1 as change control, 4.2 as lifecycle surveillance, and replace the generic closing discussion with: *"Walk the FDA 7-step credibility framework for one agent your organisation runs today — which steps could you evidence this afternoon, and which have no artifact at all?"* |
| Pre-work | Add a 20-minute read: this document plus your organisation's AI/computerised-systems policy if one exists |

## References

- FDA: Considerations for the Use of AI to Support Regulatory Decision-Making for Drug and Biological Products (draft, Jan 2025) — fda.gov
- FDA/EMA: Guiding Principles of Good AI Practice in Drug Development (Jan 2026) — fda.gov/media/189581/download
- ISPE GAMP 5 Guide, 2nd edition (incl. AI/ML appendix) — ispe.org
- FDA 21 CFR Part 11; EU GMP Annex 11 (computerised systems)
- GxP overview: "What is GxP in pharma?" — pharmaeducenter.com/blog/what-is-gxp-in-pharma
- Workshop docs: `facilitator-guide.md`, `model-deprecation-strategy.md` (change-control worked example)
