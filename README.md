# Microsoft Foundry Evaluations Framework — Half-Day Workshop

A complete, ready-to-deliver workshop on evaluating AI agents in production with **Microsoft Foundry Evaluations**: facilitator guide, slide deck, runnable labs, and CI/CD reference pipelines.

> **Content baseline: July 2026** — post-Build 2026, including trace-based evaluation, the Rubric evaluator (preview), and Agent Optimizer. See [Keeping content current](#keeping-content-current) before delivering.

## Who this is for

- **Facilitators** delivering a 3.5–4 hour session to a mixed technical audience (developers, architects, platform/DevOps engineers)
- **Self-paced learners** who want to work through the labs on their own Foundry project
- **Teams** looking for a reference implementation of agent evaluation wired into CI/CD

## What attendees learn

1. Why agent quality erodes rather than crashes — and why evaluation is a lifecycle discipline, not a pre-ship checkbox
2. The Foundry evaluator taxonomy: quality, safety, and agent evaluators (system vs. process), plus custom and Rubric evaluators
3. Running evaluations hands-on: portal, SDK, live agents, and production traces
4. Wiring evaluation into CI/CD gates (Azure DevOps / GitHub Actions) and continuous production monitoring under governance controls

As an applied case study, [`docs/model-deprecation-strategy.md`](docs/model-deprecation-strategy.md) shows how the same evaluation machinery de-risks **LLM deprecation and migration** — eval harness, shadow traffic via trace-based evaluation, canary rollout with evaluation-driven rollback, and a promotion decision gate.

## Repository structure

```
foundry-evaluations-workshop/
├── README.md                    ← you are here
├── LICENSE
├── .gitignore
├── docs/
│   ├── facilitator-guide.md     ← full facilitator guide: agenda, talk tracks,
│   │                               lab walkthroughs, timing flex, appendices
│   └── model-deprecation-strategy.md   ← applying the evaluation strategy to
│                                          LLM deprecation & migration
├── slides/
│   └── foundry-evals-workshop-deck.pptx   ← 16 slides with speaker notes
├── lab/
│   ├── README.md                ← lab setup and run order
│   ├── requirements.txt
│   ├── .env.example
│   ├── check_setup.py           ← pre-lab environment verification
│   ├── create_agent.py          ← demo weather agent (2 function tools)
│   ├── dataset.jsonl            ← 20-row eval dataset incl. adversarial rows
│   ├── run_cloud_eval.py        ← Lab 1B / 2A: cloud evaluation vs. live agent
│   └── run_local_eval.py        ← stretch: local eval with azure-ai-evaluation
└── examples/
    ├── azure-pipelines-eval.yml     ← evaluation as an Azure DevOps gate
    └── github-actions-eval.yml      ← evaluation as a GitHub Actions gate
```

## Quick start

### Facilitators

1. Read [`docs/facilitator-guide.md`](docs/facilitator-guide.md) end to end — it contains the full agenda, per-module talk tracks, facilitator setup checklist, rate-limit mitigations, and timing flex options (including a 90-minute cut-down and a leadership variant).
2. Provision one Foundry project **per attendee pair** with a deployed GPT judge model (e.g. `gpt-4.1-mini` or `gpt-5-mini`) and the **Foundry User** role assigned. The guide's *Facilitator setup* section has the full checklist.
3. Do a dry run of the labs against a real project a few days before delivery — see [Keeping content current](#keeping-content-current).

### Self-paced learners

```bash
git clone https://github.com/<you>/foundry-evaluations-workshop.git
cd foundry-evaluations-workshop/lab
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # fill in your project endpoint and deployments
az login
python check_setup.py     # everything should print [OK]
python create_agent.py    # creates the demo weather agent
python run_cloud_eval.py  # submits an evaluation and polls to completion
```

Then open **Evaluation** in the Foundry portal, find a failing row, and read the judge's reasoning — that's the core exercise. Follow along with `docs/facilitator-guide.md` Modules 1–4 for the concepts.

## Prerequisites

| Requirement | Notes |
|---|---|
| Azure subscription | Contributor on a sandbox subscription or resource group |
| Microsoft Foundry project | With an Azure OpenAI GPT judge-model deployment |
| RBAC | **Foundry User** role on the project (recently renamed from *Azure AI User* — you may see either name) |
| Local tooling | Python 3.10+, Azure CLI (`az login`), VS Code recommended |
| For the trace demo (Lab 2C) | An Application Insights resource connected to the project, with some prior agent traffic |

Some evaluation features have regional restrictions — check the [supported regions](https://learn.microsoft.com/azure/foundry/) documentation when choosing where to provision projects.

## Keeping content current

The Foundry evaluations surface is evolving quickly. Two things to check before each delivery:

- **SDK drift.** The lab scripts target the 2.x `azure-ai-projects` line against the GA REST surface and were verified against the docs in July 2026. The *pattern* — evaluators + data mappings → evaluation definition → run → poll — is stable, but parameter names have moved between releases. `pip install --upgrade azure-ai-projects` and diff against the current [evaluate-agent samples](https://learn.microsoft.com/azure/foundry/observability/how-to/evaluate-agent) if anything breaks.
- **Feature status.** As of July 2026: Evaluations + continuous monitoring are GA; hosted-agent tracing/evaluation GA was expected June/July 2026; Rubric evaluator, trace-based evaluation for external agents, continuous-eval custom evaluators, and the Agent Monitoring Dashboard are in preview. Verify current status against the [Foundry blog](https://devblogs.microsoft.com/foundry/) before quoting GA/preview labels to a room.

Pull requests updating scripts or slides against newer SDK releases are welcome — see [Contributing](#contributing).

## Common failures (labs)

| Symptom | Fix |
|---|---|
| `DefaultAzureCredential` failure | `az login`; confirm the right tenant/subscription |
| 401/403 on project endpoint | Endpoint must include **account and project**: `https://<account>.services.ai.azure.com/api/projects/<project>`; confirm the Foundry User role |
| Run status **Partial** | Almost always a data-mapping issue — field names are **case-sensitive** against the JSONL |
| `429 Too Many Requests` | Eval-run creation is rate-limited at tenant/subscription/project level. Honour `retry-after`, back off exponentially. With a full room, stagger submissions by table |
| Tool evaluator returns "pass — not supported" | The agent invoked a tool type the evaluators don't support; wrap it as a user-defined tool |

## Contributing

Issues and PRs welcome — particularly SDK compatibility fixes, additional custom-evaluator examples, and translations. Keep lab scripts dependency-light and runnable end-to-end on a fresh Foundry project.

## License

MIT — see [LICENSE](LICENSE). Slide and guide content may be adapted for internal delivery; attribution appreciated.

## Disclaimer

This is an independent community workshop, not affiliated with or endorsed by Microsoft. Product names and feature statuses reflect public documentation at the content baseline date and may have changed.
