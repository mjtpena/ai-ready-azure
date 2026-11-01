# AI-Ready Azure: the platform foundations agents actually need

The code behind the course of the same name. One idea runs through it: **AI changes the workload, not the
control plane.** An agent is a workload with a model inside it. Give it the four things your platform team already
knows how to run, an identity, one front door, context you own and a release gate, and the Azure you already operate
is what makes it safe to ship.

Every screen in the video is a real run of the code in this repository against an ordinary Azure subscription. The
scenario is fictional: **Harbourline Facilities**, a smart-building operator with 120 commercial sites, whose
**Site Operations Advisor** agent answers questions for site managers. All data is synthetic
([docs/SCENARIO.md](docs/SCENARIO.md), [docs/EXPECTED.md](docs/EXPECTED.md)).

## The four modules

| Module | Layer | What it builds | What goes wrong on purpose |
|---|---|---|---|
| [1 · The estate is ordinary Azure](demos/01-azure-ai-estate-tour) | Foundation | A tour of the AI estate from the control plane: regions, the model catalogue, quota, built-in guardrails | New Zealand North has no model catalogue |
| [2 · Identity, policy, one front door](demos/02-identity-policy-ai-gateway) | Trust and control | Entra-only Foundry, a managed identity calling a model with no secret, Azure Policy denying a non-compliant deployment, an API Management AI gateway with token budgets, content safety and metering, the Site API tools as an MCP server, the agent's Entra Agent ID | A deployment is refused; a budget runs out (429); a prompt is blocked (403) |
| [3 · A grounded agent in Foundry](demos/03-grounded-foundry-agent) | Data and context, Intelligence | An Azure AI Search index over the operations procedures, four Site API tools, a versioned Foundry agent that cites its sources and declines what it cannot ground | The agent's search tool fails on a missing role assignment |
| [4 · Trace, evaluate, gate](demos/04-trace-and-evaluate) | Operate | OpenTelemetry traces in Application Insights, Foundry evaluations (groundedness, relevance, intent resolution, task adherence, tool-call accuracy), a quality gate for CI, continuous evaluation and a red-teaming run | A candidate version starts giving legal advice and fails the gate |

## Run it yourself

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r demos/00-shared/requirements.txt
python scripts/check_env.py                                  # az login, providers, quota
python demos/00-shared/generate_data.py                      # the synthetic dataset
cd demos/02-identity-policy-ai-gateway && ./deploy.sh        # 15-20 minutes; writes demos/00-shared/.env
cd ../03-grounded-foundry-agent && python 01_create_index.py && python 02_create_agent.py && python 03_chat.py --script demo_questions.txt
cd ../04-trace-and-evaluate && python 01_traced_run.py && python 02_evaluate.py --run-agent && python 03_quality_gate.py eval/results.json
```

Every module also runs offline with `DEMO_MODE=mock` (canned answers whose figures come from the real tools). The
environment costs about US$9 a day while it exists ([docs/COST.md](docs/COST.md)); `cleanup.sh` removes it.

## The deck

`slides/src/deck.js` (pptxgenjs) builds `slides/dist/ai-ready-azure.pptx`: `cd slides && npm install && npm run build`.
The speaker notes carry the script of every slide (`slides/src/notes.json`), so the deck can be presented on its own.

## Keeping it fictional

`scripts/scrub_check.py` runs on every push: no real company, person, tenant, subscription or e-mail address may appear
in the tree. Keep it that way in pull requests ([CONTRIBUTING.md](CONTRIBUTING.md)).

## Licence

MIT. Microsoft, Azure, Microsoft Foundry and Entra are trademarks of Microsoft Corporation; this is an independent course.
