# Site operations platform: reference architecture overview

> **Course material, not legal or engineering advice.** Harbourline Facilities is a fictional operator and this document is a simplified summary written for the AI-Ready Azure course. Check your local building code and your own procedures before acting.

## From sensors to context

Building telemetry starts at the edge: BMS controllers, lift controllers, fire indicator panels, access control
readers and smart meters publish events to an ingestion tier. Stream processing validates and enriches each event with
the site and asset it belongs to, then lands it in two places: a lakehouse for history and a real-time store for the
last few days. Work orders, inspections and SOP documents sit beside the telemetry as the operations context.

## The Site APIs and the advisor's tools

The platform exposes the operations context as Site APIs. The Site Operations Advisor agent reaches them as four
tools: get_site_summary for one site, get_open_work_orders for work open longer than a number of hours, get_incidents
for incidents over a window of days, and get_inspection_schedule for statutory inspections due in a month. Every figure
the advisor states comes from one of these tools; it never reads raw telemetry itself. The tools are published through
the organisation's AI gateway so the same identity, budget and logging rules apply to agents as to applications.

## The knowledge index

Procedures such as this document are chunked by section, embedded and indexed in Azure AI Search. The advisor searches
that index for rules and guidance and cites the document titles it used. Figures come from tools, rules come from the
index.

## Identity, gateway, observability and evaluation

Every call the advisor makes carries an identity: the agent has its own Entra identity, the tools are reached through
one gateway with token and request budgets, every step is traced with OpenTelemetry into Application Insights, and
each new version of the advisor passes an evaluation gate before it is published. The five platform layers are
foundation, trust and control, data and context, intelligence, and experiences and agents.
