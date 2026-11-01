# Module 4 · Trace, evaluate, gate

**Layer:** Operate (every layer). **Point:** trace everything, evaluate as a release gate, promote on evidence.

| Script | What it does |
|---|---|
| `01_traced_run.py` | Runs the five demo questions with Azure Monitor OpenTelemetry tracing. Each question is a parent span `hbl.site_ops_advisor.demo` with `hbl.region`, `hbl.question_id`, tool-call and search counts; the SDK emits the `gen_ai.*` spans the Application Insights **Agents (Preview)** view reads |
| `02_evaluate.py` | Records the twelve cases in `eval_cases.py` (or replays `eval/responses.jsonl`), builds three datasets and runs Foundry cloud evaluations: groundedness, relevance, intent resolution and task adherence; tool-call accuracy on the four tool cases; task adherence plus a deterministic refusal check on the out-of-scope case. The judge (`gpt-5`) scores each case five times (`--judgements 5`); the median counts |
| `03_quality_gate.py` | The gate: groundedness mean ≥ 4.5 with every case ≥ 4; relevance, intent resolution and tool-call accuracy ≥ 4 on every case; task adherence on every case; every out-of-scope case declined. Exit 0 or 1 |
| `04_continuous_eval.py` | Creates a continuous-evaluation rule on the production agent: a sample of real responses is scored as they happen and lands on the agent's Monitor tab |
| `05_red_team.py` | Starts a cloud red-teaming run against the agent (jailbreak, indirect prompt injection, data exfiltration objectives) and reads the attack success rate; `--schedule weekly` registers it as a recurring run |
| `red_team_region.sh` | Cloud red teaming runs only from a project in East US 2 or North Central US (October 2026); this stands up a minimal project there, publishes an instructions-only copy of the agent (the cloud red team cannot run function tools) and starts the run. `down` deletes it |

```bash
python 01_traced_run.py
python 02_evaluate.py --run-agent --snapshot            # record live turns, then evaluate (10-15 min)
python 03_quality_gate.py eval/results.json             # PASS, exit 0
python 02_evaluate.py --agent hbl-site-ops-advisor-candidate --run-agent --out eval/candidate
python 03_quality_gate.py eval/candidate/results.json   # FAIL on out_of_scope (and task_adherence), exit 1
python 04_continuous_eval.py                            # --delete removes the rule
python 05_red_team.py                                   # --status <name> to read a finished run
```

`.github/workflows/agent-eval.yml.example` (repository root) is the pull-request version: federated identity with
OIDC, publish the candidate version, evaluate, gate. `kql/` has the token and latency queries behind the traces.

## The story

`agent_definition.HELPFUL_RULE` is a one-line edit any reviewer could wave through: "if neither source covers the
question, be helpful anyway". The candidate agent built from it answers the eviction question instead of declining it.
The gate fails `out_of_scope`, the pull-request check goes red, and production never sees it.
