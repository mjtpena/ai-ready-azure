# Azure's AI estate on one page

Organised by the five layers of the AI-Ready Platform. The "Harbourline lens" column is the fictional smart-building
operator the course uses as its worked example; nothing in it describes a real organisation.

| Layer | Azure service / capability | What it is for | Harbourline lens |
|---|---|---|---|
| **1 Foundation** | Management groups, subscriptions, Azure landing zones (platform and workload landing zones), the AI Landing Zones reference implementation (Bicep / Terraform, preview) | Where AI workloads live; isolation, quota and billing boundaries | One workload landing zone for the site operations platform; shared AI platform services in a platform subscription |
| | Regions: Australia East (the widest Foundry model range in Asia Pacific, mostly Global Standard), New Zealand North (data at rest; no Foundry model catalogue today) | Where models run and data rests | Building and tenant data residency in NZ against AU model availability: decide per data class |
| | Bicep / Terraform + Azure Verified Modules, Deployment Stacks | Repeatable platform | Everything in this repo is Bicep |
| **2 Trust and control** | Microsoft Entra ID: users and groups, PIM, managed identities, workload identity federation, **Entra Agent ID** (agents as first-class identities, blueprints, Conditional Access) | Identity for people, workloads and agents | No keys anywhere; the advisor agent has its own identity and an accountable sponsor |
| | Azure RBAC + Foundry roles (Foundry User, Foundry Project Manager, Cognitive Services OpenAI User) | Least privilege to models, projects, data | Platform team owns resources; the operations product team gets project-level roles |
| | Azure Policy (built-in: disable public network access, disable local auth, allowed locations; the course's four custom guardrails) | Guardrails that deny, audit or fix | Deny key-based auth and unapproved regions; allow-list models |
| | Private Link, Foundry network isolation, Azure Firewall / NAT egress | Keep model traffic on the private network | Same hub-spoke as today; private endpoints for Foundry, Search, Storage |
| | **Azure API Management AI gateway** (token limits, quotas, metrics, semantic cache, content safety, load balancing, MCP servers); the dedicated AI Gateway tier (preview) | One front door for models and tools | Per-team products, chargeback, protection for the shared model pool, the Site API tools as an MCP server |
| | Azure AI Content Safety, Prompt Shields; Defender for Cloud AI threat protection; Purview (sensitivity labels, network DLP covering agent traffic); Agent 365 and the Foundry Control Plane | Safety, security and governance controls for AI traffic and agents | Prompt injection and data-leak controls before a tenant-facing agent |
| **3 Data and context** | Microsoft Fabric: OneLake, Lakehouse, Real-Time Intelligence (Eventstream, Eventhouse/KQL), mirroring, shortcuts | Analytical and real-time data estate | BMS, lift, fire, access and meter events land once, serve analytics, APIs and AI |
| | Azure Event Hubs / IoT Hub / Azure IoT Operations, Stream Analytics | Ingest and process device events | Building telemetry streams from 120 sites |
| | **Azure AI Search** (hybrid + semantic ranking, integrated vectorisation, Foundry IQ knowledge bases with agentic retrieval) | Grounding over documents and structured content | Operations guidance: SOPs, inspection schedules, SLAs, contractor rules |
| | Azure Cosmos DB, Azure SQL, PostgreSQL (pgvector) | Operational stores and memory | Work orders, inspections, conversation memory |
| | Microsoft Purview | Catalogue, lineage, classification, sensitivity labels | Know what the agent is allowed to read |
| **4 Intelligence** | **Microsoft Foundry**: Foundry resource → projects and deployments (ARM child resources; agents live inside a project); model catalog (GPT-5.6 and Claude 5 families sold by Azure); deployment types (Standard, Data Zone, Global, Provisioned, Batch); model router; fine-tuning | Models as a managed service | Pick model per task; Provisioned for predictable tenant-facing load |
| | **Foundry Agent Service**: prompt agents (versioned), hosted agents, Routines, Toolboxes (one managed MCP endpoint), memory, tools (AI Search, functions, OpenAPI, MCP, code interpreter), conversations and responses | Agents as a managed runtime | The Site Operations Advisor in module 3 |
| | Microsoft Agent Framework 1.0, A2A, MCP | Build multi-agent systems in code | For when a managed prompt agent is not enough |
| | Foundry observability: tracing (OpenTelemetry), evaluation (quality, safety, agent evaluators), AI red teaming, continuous evaluation | Measure before and after release | Module 4 |
| | Azure Machine Learning | Classic ML training and MLOps | Energy anomaly and fault prediction models |
| **5 Experiences and agents** | Microsoft 365 Copilot, Copilot Studio, **Agent 365** | Agents for knowledge workers, governed centrally | Internal operations and support agents |
| | Azure App Service, Container Apps, AKS, Functions, Static Web Apps | Host AI apps and agent front ends | The building app and the operations desk tools |
| | GitHub Copilot, Azure Copilot (Observability Agent), **Azure SRE Agent** | AI in the engineering and operations loop | Platform team productivity; incident response |
| | Power Platform, Teams, Dynamics 365 | Low-code surfaces for agents | Contractor and tenant workflows |

**Cross-cutting**: Azure Monitor + Application Insights (OpenTelemetry GenAI spans, the Agents view), Log Analytics, Microsoft Cost Management (tokens as a cost line), Azure Key Vault (where a secret is unavoidable).

Status as of October 2026: the AI Landing Zones implementation, the APIM AI Gateway tier and answer synthesis in Foundry IQ knowledge bases are preview; hosted agents, knowledge bases with agentic retrieval, the Observability Agent and Agent 365 are generally available. Check model availability per region in the Foundry portal before relying on it.
