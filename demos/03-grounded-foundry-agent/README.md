# Module 3 · A grounded agent in Foundry

**Layers:** Data and context, Intelligence. **Point:** numbers from tools, rules from the index, and an honest no when neither covers it.

| Script | What it does |
|---|---|
| `01_create_index.py` | Chunks the eight operations documents by `##` section, embeds them with `text-embedding-3-small` and builds the `hbl-site-knowledge` index (hybrid + semantic) in Azure AI Search |
| `02_create_agent.py` | Creates a new immutable version of the `hbl-site-ops-advisor` prompt agent (instructions in `agent_definition.py`, the AI Search tool, the four Site API tools) and points the endpoint at it. `--candidate --variant helpful` publishes the regression module 4 catches |
| `03_chat.py` | Talks to the agent through the Responses and Conversations APIs, resolves function calls, and prints a grounding panel per answer. `--script demo_questions.txt` replays the five demo questions |
| `04_show_agent_identity.sh` | Shows the Entra agent identity Foundry provisioned for the project (`az rest`, `az ad sp show`, Graph) |
| `99_cleanup.py` | Deletes the agent versions and, optionally, the index |

```bash
python 01_create_index.py
python 02_create_agent.py
python 03_chat.py --script demo_questions.txt
DEMO_MODE=mock python 03_chat.py --script demo_questions.txt   # offline, figures from the real tools
```

The five questions, and what each proves:

1. *What is the SOP when a chiller trips twice in a day?* The index alone; no tool is called.
2. *Is Site HBL-AKL-017 due a fire-system inspection this month?* One tool, `get_inspection_schedule`, plus the schedule document.
3. *Which sites have HVAC faults open more than 48 hours and are due a fire-system inspection this month?* Two tools joined, three documents, six sites, three in both sets.
4. *Summarise lift incidents at the Wellington sites in the last 7 days.* One tool, the entrapment procedure.
5. *Can we evict a tenant for late rent?* Neither source covers it: the fixed three-line refusal, `Sources: none`.

## The thing that goes wrong

The project's managed identity needs **Search Index Data Contributor** and **Search Service Contributor** on the search
service, not just Reader, for the agent's AI Search tool to run. `infra/modules/search.bicep` grants them; the video
removes one first to show the failure (`Access denied ... managed identity access to the search service`) and the
fix (`az role assignment create`). Every hop is a role assignment.

## Tools: local or through the gateway

`AGENT_TOOLS=local` (default) attaches the four functions as strict function tools executed by the client.
`AGENT_TOOLS=mcp` attaches the same four tools as an MCP tool served by the API Management MCP server from module 2
(`APIM_MCP_URL`, project connection `MCP_CONNECTION_NAME`), so the gateway's identity, budget and logs apply to the agent
and the agent can run server-side (portal playground, continuous evaluation, red teaming).
