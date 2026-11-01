# What the demo environment costs

Everything the course deploys lives in one resource group (`rg-hbl-ops`, Australia East) and is tagged
`delete-after: recording`. List prices as of October 2026, idle, per day:

| Resource | Tier | Approx. per day |
|---|---|---|
| API Management | Basic v2, 1 unit | US$6 |
| Azure AI Search | Basic | US$2.40 |
| Log Analytics + Application Insights | Pay-as-you-go, a few MB | US$0.30 |
| Azure Container Instances | one 1-vCPU run per `az container start` | cents |
| Azure Functions (tools API, module 2 stage 2) | Flex Consumption | inside the free grant |
| Microsoft Foundry account, project, deployments | Global Standard, pay per token | US$0 idle |
| Red-team project `rg-hbl-ops-redteam` (East US 2: account, project, two deployments) | Global Standard, pay per token | US$0 idle; a red-team run is a few US dollars of judge and attacker tokens |
| **Idle total** | | **about US$9 a day (NZD 15)** |

Variable costs while you work:

- A full run of the five demo questions costs cents on `gpt-5-mini`.
- One evaluation run (12 cases, 5 evaluators, 3 judgements each on `gpt-5`) is about US$3 to US$5.
- The Azure Copilot Observability Agent bills in Azure Agent Credits (US$0.01 per credit); a handful of questions is cents.
- A cloud red-teaming run against the agent costs a few dollars in judge and target tokens.

Delete it all with `demos/02-identity-policy-ai-gateway/cleanup.sh`, which also purges the soft-deleted Foundry
account and API Management instance and removes the four `hbl-ops-*` policy definitions.
