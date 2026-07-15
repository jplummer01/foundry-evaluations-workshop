# CI/CD evaluation patterns

The examples separate Foundry-native statistical comparison from deterministic repository policy. Public action/task documentation promises rendered comparison summaries, but does not document machine-readable score outputs or threshold-based job failure.

| Example | Agent/tool requirement | Statistics | Enforcing policy |
|---|---|---|---|
| `github-actions-eval.yml` | Hosted agent with service-executable tools | Native Foundry comparison | No; rendered report |
| `azure-pipelines-eval.yml` | Hosted agent with service-executable tools | Native confidence intervals and pairwise comparison | No documented threshold contract |
| `github-actions-migration-gate.yml` | Workshop prompt agent; executes local Python tools before scoring | Inspect shared evaluation in Foundry | Yes; contracts, floors, regressions, cohorts |
| `azure-pipelines-migration-gate.yml` | Workshop prompt agent; executes local Python tools before scoring | Inspect shared evaluation in Foundry | Yes; contracts, floors, regressions, cohorts |

The enforcing workflows run manually by default to control model cost and `429` pressure. In a production repository, add narrow path or release triggers only after measuring quota demand. Both workflows authenticate with Entra ID, publish evidence on failure, and deliberately avoid committing or promoting a new baseline.

Configure the variable names shown in each workflow. `AGENT_IDS` is a comma-separated list of `agent-name:version` values for native comparison; `BASELINE_AGENT_ID` identifies the incumbent. For the precomputed workflows, select one agent name, incumbent/candidate versions, dataset, and policy.

Artifact retention in GitHub or Azure DevOps is convenient operational evidence, not automatically immutable or compliant retention. Apply the organization's retention, access-control, and change-control requirements before treating it as an audit record.
