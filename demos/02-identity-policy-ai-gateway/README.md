# Module 2 · Identity, policy, one front door

**Layer:** Trust and control. **Point:** who may call (identity), what may exist (policy), how every call behaves (the gateway).

This folder also holds the infrastructure for the whole course: `infra/main.bicep` deploys the Foundry account
(Entra-only, keys disabled) with its project and three model deployments, API Management v2 as the AI gateway, Azure
AI Search for module 3, Log Analytics and Application Insights, a user-assigned managed identity with a container that
proves the identity story from inside Azure, four custom Azure Policy guardrails, and the project connections modules
3 and 4 use.

```bash
./deploy.sh                      # creates rg-hbl-ops, deploys, writes .env here and in ../00-shared (15-20 min first time)
./cleanup.sh                     # deletes the resource group, purges soft-deleted Foundry/APIM, removes the policy definitions
```

## Act 1 · Identity: no key anywhere

```bash
python client/call_model.py --via direct                      # DefaultAzureCredential -> Foundry; prints the token claims
az container logs -g rg-hbl-ops -n ci-hbl-ops-site-advisor    # the same call from a container with a managed identity
../03-grounded-foundry-agent/04_show_agent_identity.sh        # the agent's own Entra Agent ID (az rest + az ad sp show)
```

## Act 2 · Policy: what may exist

```bash
az deployment group create -g rg-hbl-ops --template-file policy/noncompliant.bicep 2>&1 | grep -oE 'Harbourline guardrail: [^"]*'
```

The deployment asks for a Foundry account in East US with keys enabled. Azure Policy refuses it at the front door with
`RequestDisallowedByPolicy` and two messages: approved regions, and Entra-only authentication. Nothing is created.
Definitions are in `policy/definitions/*.json` (also deployable alone with `policy/assign.bicep`). Deny enforcement can
take up to 30 minutes after a fresh deployment.

## Act 3 · The gateway: how every call behaves

`apim/policies/all.xml` is the policy on the `foundry-inference` API, in request order: `validate-azure-ad-token`
(who), team and site-group headers (which budget), `llm-content-safety` (is it safe, 403), `llm-token-limit`
(is there budget, 429), `llm-emit-token-metric` (meter it), then `authentication-managed-identity` (route with the
gateway's own identity; the caller's token and key stop here).

```bash
python client/call_model.py --via gateway                        # 200 with x-remaining-tokens
python client/call_model.py --via gateway --repeat 4 --sleep 0   # the 500-token budget for site group AKL runs out: 429 + Retry-After
python client/call_model.py --via gateway --site-group WLG       # another site group's budget is untouched
python client/call_model.py --via gateway --unsafe               # Prompt Shields block the jailbreak: 403, before any tokens are spent
```

`kql/` holds the Log Analytics and Application Insights queries behind the metering: tokens by team, 429s per minute
and site group, content-safety blocks, and the LLM prompt log.

The same gateway governs tools: stage 2 of this module publishes the four Site API functions as a REST API with an
Azure Functions backend and exports them as an **MCP server** (`infra/modules/mcp.bicep`, `apim/policies/mcp-server.xml`)
so the agent in module 3 reaches its tools through the same identity, budget and logs (`client/call_mcp.py`). The
dedicated **AI Gateway tier** of API Management (preview, East US 2 and Sweden Central) is where this is heading: policy
cards instead of XML, one endpoint for every OpenAI-compatible provider, MCP servers at `/toolservers/<name>/mcp`.

## Offline

`DEMO_MODE=mock python client/call_model.py --via gateway --repeat 4` prints a canned run with the same shape.
