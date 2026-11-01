// The course deck: 23 slides. The script for every slide goes into the speaker notes, from notes.json (slide number ->
// paragraphs). Demo videos are spliced into the video after slides 7, 11, 15 and 19; the video slides also embed the
// rendered demo so the .pptx stands on its own.
const fs = require("fs");
const path = require("path");
const L = require("./lib");
const { W, M, CONTENT_Y, CONTENT_H, HEX, LAYERS, text, bullets, rect, box, arrow, table, pill, stat, card, cardRow, cardGrid, iconCircle, layerGlyph, videoSlide } = L;

// The author's working script (outside the public repository) refreshes notes.json whenever it is present
const NOTES_FILE = path.join(__dirname, "notes.json");
const SCRIPT_FILE = path.join(__dirname, "..", "..", "narration", "day1_rewrite.json");
if (fs.existsSync(SCRIPT_FILE)) {
  const script = JSON.parse(fs.readFileSync(SCRIPT_FILE, "utf8"));
  const out = Object.fromEntries(Object.keys(script).filter((k) => /^\d+$/.test(k)).map((k) => [k, script[k].text || []]));
  fs.writeFileSync(NOTES_FILE, JSON.stringify(out, null, 1) + "\n");
}
const NOTES = JSON.parse(fs.readFileSync(NOTES_FILE, "utf8"));
const notes = (n) => (NOTES[String(n)] || []).join("\n\n");
const LIGHT = "C9D1DA", DIM = "8A94A0";

module.exports = async function build(pres) {
  for (const sec of ["Open", "Trust and control", "Data and intelligence", "Operate", "Close"]) pres.addSection({ title: sec });
  const slideFn = L.makeSlideFn(pres);
  const slide = (master, sec, title, lit, n) => slideFn(master, sec, title, lit, notes(n));

  // ---------------------------------------------------------------- 1 · title (the cold-open montage follows it)
  {
    const s = pres.addSlide({ masterName: "TITLE", sectionTitle: "Open" });
    s.addText("AI-Ready Azure", { placeholder: "title" });
    s.addText("the platform foundations agents actually need", { placeholder: "body" });
    pill(s, { x: M, y: 1.55, w: 2.1, label: "A DEMO-LED COURSE", fill: HEX.amber });
    layerGlyph(s, [1, 2, 3, 4, 5], { dark: true, x: W - M - 2.2, y: 2.2, w: 2.2, rowH: 0.3, label: false });
    text(s, "Fictional scenario, synthetic data, real runs.", { x: M, y: 6.5, w: 11, h: 0.4, fontSize: 14, color: DIM });
    s.addNotes(notes(1));
  }

  // ---------------------------------------------------------------- 2 · name card
  {
    const s = pres.addSlide({ masterName: "TITLE", sectionTitle: "Open" });
    s.addText("Michael John Pena", { placeholder: "title" });
    s.addText("Cloud and AI architect. Everything in this course runs from one public repository.", { placeholder: "body" });
    rect(s, { x: M, y: 5.4, w: 8.6, h: 0.9, fill: HEX.darkCard, radius: 0.08, name: "course-at-a-glance" });
    text(s, "Four demos · chapters in the description · github.com/mjtpena/ai-ready-azure", { x: M + 0.25, y: 5.4, w: 8.1, h: 0.9, fontSize: 16, color: LIGHT, valign: "middle" });
    s.addNotes(notes(2));
  }

  // ---------------------------------------------------------------- 3 · same platform, different physics
  {
    const s = slide("CONTENT", "Open", "Same platform, different physics", [1, 2, 3, 4, 5], 3);
    table(s, [
      ["", "A classic service", "An AI workload", "Whose job it becomes"],
      ["Output", "Deterministic: same input, same answer", "Probabilistic: a distribution of answers", "Evaluation, not assertions"],
      ["Unit of capacity", "Requests per second, CPU", "Tokens per minute, per model, per region", "Quota and budgets at the gateway"],
      ["Testing", "Unit tests pass or fail", "A judge scores a dataset; the median counts", "A release gate in CI"],
      ["Failure modes", "Exceptions, timeouts", "Hallucination, injection, leakage, over-permission", "Identity, grounding, content safety"],
      ["Data access", "Your code reads your database", "The model reads whatever the agent is allowed to", "An identity per agent, least privilege"],
    ], { fontSize: 15.5, colW: [1.6, 3.5, 3.75, 3.28], rowH: 0.68, firstColBold: true });
    text(s, "Every cell in the right-hand column is a platform job. None of them is fixed by a better model.", { x: M, y: 6.1, w: 12, h: 0.4, fontSize: 17.5, bold: true, color: HEX.amber });
  }

  // ---------------------------------------------------------------- 4 · five layers, one responsibility map
  {
    const s = slide("CONTENT", "Open", "Five layers, one responsibility map", [1, 2, 3, 4, 5], 4);
    const rows = [
      [5, "Experiences and agents", "The advisor in Teams, the building app, Copilot Studio, Agent 365"],
      [4, "Intelligence", "Foundry models and agents, Agent Framework, evaluation"],
      [3, "Data and context", "Telemetry in the lakehouse, Site APIs as tools, AI Search as the index"],
      [2, "Trust and control", "Entra ID and Agent ID, Azure Policy, the AI gateway, Content Safety, Purview"],
      [1, "Foundation", "Workload landing zone, regions and quota, Bicep, Azure Monitor"],
    ];
    rows.forEach(([n, name, what], i) => {
      const y = CONTENT_Y + i * 0.78;
      box(s, { x: M, y, w: 3.2, h: 0.66, label: `${n} · ${name}`, fill: LAYERS[n].hex, color: n === 2 || n === 5 ? HEX.dark : HEX.white, fontSize: 17.5, name: `layer-${n}` });
      text(s, what, { x: M + 3.4, y: y + 0.1, w: 5.4, h: 0.55, fontSize: 16 });
    });
    const risks = [["Prompt injection", 2], ["Data leakage", 3], ["Hallucination", 4], ["Over-permissioned agents", 2]];
    rect(s, { x: 9.5, y: CONTENT_Y, w: 3.25, h: 3.9, fill: HEX.dark, radius: 0.1, name: "risk-card" });
    text(s, "Four risks, and the layer that fixes each", { x: 9.7, y: CONTENT_Y + 0.15, w: 2.9, h: 0.5, fontSize: 16, bold: true, color: HEX.amber });
    risks.forEach(([r, layer], i) => {
      pill(s, { x: 9.7, y: CONTENT_Y + 0.85 + i * 0.72, w: 0.45, label: String(layer), fill: LAYERS[layer].hex, color: layer === 2 || layer === 5 ? HEX.dark : HEX.white });
      text(s, r, { x: 10.25, y: CONTENT_Y + 0.85 + i * 0.72, w: 2.4, h: 0.32, fontSize: 16, color: LIGHT, valign: "middle" });
    });
    text(s, "A responsibility map, not a deployment diagram.", { x: M, y: 6.0, w: 8, h: 0.4, fontSize: 17.5, bold: true, color: HEX.amber });
  }

  // ---------------------------------------------------------------- 5 · the scenario
  {
    const s = slide("CONTENT", "Open", "Harbourline Facilities: the scenario", [3, 5], 5);
    pill(s, { x: M, y: CONTENT_Y - 0.02, w: 1.2, label: "FICTIONAL", fill: HEX.amber });
    pill(s, { x: M + 1.35, y: CONTENT_Y - 0.02, w: 1.6, label: "SYNTHETIC DATA", fill: HEX.slate, color: HEX.white });
    const y = CONTENT_Y + 0.6;
    box(s, { x: M, y, w: 2.5, h: 1.1, label: "120 sites", sub: "AKL · WLG · SYD · MEL", fill: HEX.slate, color: HEX.white, fontSize: 19 });
    arrow(s, { x1: M + 2.5, y1: y + 0.55, x2: M + 3.1, y2: y + 0.55 });
    box(s, { x: M + 3.1, y, w: 2.9, h: 1.1, label: "Building telemetry", sub: "HVAC · lifts · fire · access · meters", fill: HEX.teal, color: HEX.white, fontSize: 17.5 });
    arrow(s, { x1: M + 6.0, y1: y + 0.55, x2: M + 6.6, y2: y + 0.55 });
    box(s, { x: M + 6.6, y, w: 2.9, h: 1.1, label: "Site APIs + SOP index", sub: "work orders · inspections · procedures", fill: HEX.teal, color: HEX.white, fontSize: 17.5 });
    arrow(s, { x1: M + 9.5, y1: y + 0.55, x2: M + 10.1, y2: y + 0.55 });
    box(s, { x: M + 10.1, y, w: 2.05, h: 1.1, label: "Site Operations Advisor", sub: "a Foundry agent", fill: HEX.violet, color: HEX.white, fontSize: 16 });
    rect(s, { x: M, y: y + 1.6, w: 7.2, h: 1.5, fill: HEX.tint, radius: 0.1, name: "q1" });
    text(s, "“Which sites have HVAC faults open more than 48 hours and are due a fire-system inspection this month?”", { x: M + 0.25, y: y + 1.75, w: 6.7, h: 0.8, fontSize: 19, bold: true });
    text(s, "Two tools, one procedure, three sites, with sources. The hero question of the course.", { x: M + 0.25, y: y + 2.55, w: 6.7, h: 0.4, fontSize: 15, color: HEX.muted });
    rect(s, { x: M + 7.5, y: y + 1.6, w: 4.65, h: 1.5, fill: HEX.dark, radius: 0.1, name: "q2" });
    text(s, "“Can we evict a tenant for late rent?”", { x: M + 7.75, y: y + 1.75, w: 4.2, h: 0.5, fontSize: 19, bold: true, color: HEX.white });
    text(s, "Neither source covers it. The right answer is a refusal, and the release gate defends it.", { x: M + 7.75, y: y + 2.3, w: 4.2, h: 0.7, fontSize: 15, color: LIGHT });
    text(s, "Orders of magnitude, illustrative: about a million sensor readings a day, 14 days hot, 8 procedures, 571 work orders in the window.", { x: M, y: 6.05, w: 12, h: 0.4, fontSize: 14.5, color: HEX.muted, italic: true });
  }

  // ---------------------------------------------------------------- 6 · four services the platform adds
  {
    const s = slide("CONTENT", "Open", "Four services the platform adds, one demo each", [2, 3, 4, 5], 6);
    await cardRow(s, [
      { title: "1 · An identity", body: ["Entra-only Foundry, no keys", "Managed identity on every hop", "Entra Agent ID for the agent"], icon: "MdBadge", color: LAYERS[2].hex },
      { title: "2 · One front door", body: ["API Management AI gateway", "Token budgets, content safety, metering", "Models and MCP tools through the same door"], icon: "MdMeetingRoom", color: LAYERS[2].hex },
      { title: "3 · Context you own", body: ["AI Search over the procedures", "Four Site API tools, strict schemas", "A versioned agent in Foundry"], icon: "MdStorage", color: LAYERS[3].hex },
      { title: "4 · A release gate", body: ["OpenTelemetry traces in App Insights", "Foundry evaluators, judged five times", "A gate in CI that fails a regression"], icon: "MdVerified", color: LAYERS[5].hex },
    ], { y: CONTENT_Y + 0.1, h: 3.9 });
    text(s, "In the order a platform team would build them. Demo 1 first shows that none of it needs a new kind of Azure.", { x: M, y: 5.8, w: 12, h: 0.5, fontSize: 17.5, bold: true, color: HEX.amber });
  }

  // ---------------------------------------------------------------- 7 · demo 1
  {
    const s = slide("CONTENT_DARK", "Open", "Demo 1 · The estate is ordinary Azure", [1], 7);
    await videoSlide(s, { demo: 1, minutes: 3, folder: "01-azure-ai-estate-tour", chapters: [{ t: "0:00", label: "The AI estate" }, { t: "0:40", label: "The model catalogue" }, { t: "1:20", label: "From the control plane" }] });
  }

  // ---------------------------------------------------------------- 8 · workload landing zone
  {
    const s = slide("CONTENT", "Trust and control", "Workload landing zone: AI needs no separate design", [1], 8);
    box(s, { x: M, y: CONTENT_Y + 0.2, w: 3.6, h: 1.0, label: "Management groups", sub: "policy inherited, Deny at the top", fill: HEX.slate, color: HEX.white });
    box(s, { x: M, y: CONTENT_Y + 1.5, w: 3.6, h: 1.0, label: "Platform landing zone", sub: "identity, connectivity, management", fill: HEX.slate, color: HEX.white });
    box(s, { x: M, y: CONTENT_Y + 2.8, w: 3.6, h: 1.0, label: "Shared AI platform subscription", sub: "central Foundry, quota, the gateway", fill: HEX.amber, color: HEX.dark });
    box(s, { x: M + 4.2, y: CONTENT_Y + 1.5, w: 3.6, h: 1.0, label: "Workload landing zone", sub: "rg-hbl-ops: the course's resource group", fill: HEX.amber, color: HEX.dark });
    box(s, { x: M + 4.2, y: CONTENT_Y + 2.8, w: 3.6, h: 1.0, label: "Another workload", sub: "same template, its own subscription", fill: HEX.tint, color: HEX.text, line: HEX.line });
    arrow(s, { x1: M + 1.8, y1: CONTENT_Y + 1.2, x2: M + 1.8, y2: CONTENT_Y + 1.5 });
    arrow(s, { x1: M + 3.6, y1: CONTENT_Y + 2.0, x2: M + 4.2, y2: CONTENT_Y + 2.0 });
    arrow(s, { x1: M + 3.6, y1: CONTENT_Y + 3.3, x2: M + 4.2, y2: CONTENT_Y + 3.3 });
    rect(s, { x: 9.0, y: CONTENT_Y + 0.2, w: 3.75, h: 3.6, fill: HEX.dark, radius: 0.1, name: "caf-card" });
    text(s, "What changed in October 2026", { x: 9.2, y: CONTENT_Y + 0.35, w: 3.4, h: 0.4, fontSize: 16, bold: true, color: HEX.amber });
    bullets(s, [
      "The Cloud Adoption Framework renamed “application landing zone” to workload landing zone; data landing zones folded into it",
      "AI workloads need no separate landing zone design: extend the existing governance baseline",
      "Azure/AI-Landing-Zones: Bicep and Terraform on Azure Verified Modules, deployable with or without a platform landing zone (preview)",
    ], { x: 9.2, y: CONTENT_Y + 0.85, w: 3.4, h: 2.9, fontSize: 14.5, color: LIGHT, spacing: 6 });
    text(s, "The landing zone is a template, not a ticket.", { x: M, y: 6.0, w: 8, h: 0.4, fontSize: 17.5, bold: true, color: HEX.amber });
  }

  // ---------------------------------------------------------------- 9 · three identity types
  {
    const s = slide("CONTENT", "Trust and control", "Three identity types. An agent is a principal.", [2], 9);
    rect(s, { x: M, y: CONTENT_Y + 0.15, w: 8.6, h: 0.5, fill: HEX.slate, radius: 0.06, name: "entra-bar" });
    text(s, "Microsoft Entra ID: one directory, three kinds of principal", { x: M + 0.2, y: CONTENT_Y + 0.22, w: 8.2, h: 0.36, fontSize: 17.5, bold: true, color: HEX.white });
    const cols = [
      ["People", "Users and groups, PIM, Conditional Access", "The site manager asking the question", HEX.tint, HEX.text],
      ["Workloads", "Managed identities, workload identity federation", "The container, the gateway, CI with OIDC", HEX.tint, HEX.text],
      ["Agents", "Entra Agent ID: blueprint → agent identities, a sponsor, Conditional Access", "hbl-site-ops-advisor, provisioned by Foundry", HEX.amber, HEX.dark],
    ];
    cols.forEach(([t, b, ex, fill, color], i) => {
      const x = M + i * 2.95;
      rect(s, { x, y: CONTENT_Y + 0.85, w: 2.7, h: 2.9, fill, radius: 0.08, name: `id-${t}` });
      text(s, t, { x: x + 0.2, y: CONTENT_Y + 1.0, w: 2.3, h: 0.4, fontSize: 20, bold: true, color });
      text(s, b, { x: x + 0.2, y: CONTENT_Y + 1.45, w: 2.3, h: 1.1, fontSize: 15, color });
      text(s, ex, { x: x + 0.2, y: CONTENT_Y + 2.7, w: 2.3, h: 0.9, fontSize: 14.5, italic: true, color });
    });
    rect(s, { x: 9.5, y: CONTENT_Y + 0.15, w: 3.25, h: 3.6, fill: HEX.dark, radius: 0.1, name: "control-planes" });
    text(s, "Two consoles, one directory", { x: 9.7, y: CONTENT_Y + 0.3, w: 2.9, h: 0.4, fontSize: 16, bold: true, color: HEX.amber });
    bullets(s, [
      { text: "Foundry Control Plane", bold: true }, { text: "for the teams that build and run agents: fleet view, tracing, evaluation", sub: true },
      { text: "Agent 365", bold: true }, { text: "for the teams that govern them: inventory, access reviews, lifecycle", sub: true },
      { text: "Purview", bold: true }, { text: "sensitivity labels and network DLP now cover agent traffic", sub: true },
    ], { x: 9.7, y: CONTENT_Y + 0.8, w: 2.9, h: 2.9, fontSize: 15, color: LIGHT, subColor: DIM, spacing: 4 });
    text(s, "Every tool call is an authorisation decision and a trace span: which principal, which scope, on whose behalf.", { x: M, y: 6.0, w: 12, h: 0.4, fontSize: 17, bold: true, color: HEX.amber });
  }

  // ---------------------------------------------------------------- 10 · one front door
  {
    const s = slide("CONTENT", "Trust and control", "One front door: the AI gateway", [2], 10);
    const chain = [
      ["validate-azure-ad-token", "who is calling", HEX.slate],
      ["llm-content-safety", "is it safe → 403", HEX.amber],
      ["llm-token-limit", "is there budget → 429", HEX.amber],
      ["llm-emit-token-metric", "meter it by team", HEX.slate],
      ["managed identity", "route with the gateway's own", HEX.slate],
    ];
    const bw = 2.25, gap = 0.22, y = CONTENT_Y + 0.75;
    chain.forEach(([label, sub, fill], i) => {
      const x = M + i * (bw + gap);
      box(s, { x, y, w: bw, h: 1.05, label, sub, fill, color: fill === HEX.amber ? HEX.dark : HEX.white, fontSize: 14.5, name: `chain-${i}` });
      if (i < chain.length - 1) arrow(s, { x1: x + bw, y1: y + 0.52, x2: x + bw + gap, y2: y + 0.52 });
    });
    box(s, { x: M, y: CONTENT_Y + 0.0, w: 2.6, h: 0.5, label: "Client: Entra token + team key", fill: HEX.tint, color: HEX.text, fontSize: 14, bold: false, line: HEX.line });
    box(s, { x: M + 4 * (bw + gap), y: CONTENT_Y + 2.1, w: bw, h: 0.75, label: "Foundry models", sub: "and MCP tool servers", fill: HEX.violet, color: HEX.white, fontSize: 15 });
    arrow(s, { x1: M + 4 * (bw + gap) + bw / 2, y1: y + 1.05, x2: M + 4 * (bw + gap) + bw / 2, y2: CONTENT_Y + 2.1 });
    rect(s, { x: M, y: CONTENT_Y + 2.1, w: 7.2, h: 1.7, fill: HEX.tint, radius: 0.08, name: "why-card" });
    bullets(s, [
      "Without a gateway: keys spread, quota is first come first served, nobody can say what a team spent",
      "With one: Entra in, managed identity out; a budget per site group; Prompt Shields before any tokens; tokens by team in Log Analytics",
      "Classic tiers run every one of these policies today, GA, in XML; MCP servers are exported from REST APIs the same way",
    ], { x: M + 0.2, y: CONTENT_Y + 2.25, w: 6.8, h: 1.5, fontSize: 14.5, spacing: 4 });
    rect(s, { x: 8.1, y: CONTENT_Y + 3.05, w: 4.65, h: 1.45, fill: HEX.dark, radius: 0.08, name: "tier-card" });
    pill(s, { x: 8.3, y: CONTENT_Y + 3.15, w: 2.4, label: "AI GATEWAY TIER · PREVIEW", fill: HEX.amber });
    text(s, "Policy cards instead of XML; one endpoint for OpenAI-compatible providers plus Anthropic; MCP servers at /toolservers. Preview in East US 2 and Sweden Central.", { x: 8.3, y: CONTENT_Y + 3.5, w: 4.25, h: 0.95, fontSize: 13, color: LIGHT });
    text(s, "The caller's token and key stop at the gateway. Foundry never sees them.", { x: M, y: 6.0, w: 8, h: 0.4, fontSize: 17.5, bold: true, color: HEX.amber });
  }

  // ---------------------------------------------------------------- 11 · demo 2
  {
    const s = slide("CONTENT_DARK", "Trust and control", "Demo 2 · Identity, policy, one front door", [2], 11);
    await videoSlide(s, { demo: 2, minutes: 8, folder: "02-identity-policy-ai-gateway", chapters: [{ t: "0:00", label: "Act 1 · Identity" }, { t: "2:10", label: "Act 2 · Policy" }, { t: "3:50", label: "Act 3 · The gateway" }] });
  }

  // ---------------------------------------------------------------- 12 · the model is rented, the context is owned
  {
    const s = slide("CONTENT_DARK", "Data and intelligence", "The model is rented. The context is owned.", [3], 12);
    pill(s, { x: M, y: CONTENT_Y - 0.02, w: 1.5, label: "ILLUSTRATIVE", fill: HEX.amber });
    stat(s, { x: M, y: CONTENT_Y + 0.5, number: "120", label: "sites", note: "four cities, five building types", dark: true });
    stat(s, { x: M + 3.1, y: CONTENT_Y + 0.5, number: "~10⁶", label: "sensor readings a day", note: "BMS, lifts, fire, access, meters", dark: true, color: HEX.teal });
    stat(s, { x: M + 6.2, y: CONTENT_Y + 0.5, number: "14 d", label: "hot in the real-time store", note: "the rest in the lakehouse", dark: true, color: HEX.teal });
    stat(s, { x: M + 9.3, y: CONTENT_Y + 0.5, number: "8", label: "procedures in the index", note: "35 chunks, cited by title", dark: true });
    rect(s, { x: M, y: CONTENT_Y + 3.2, w: 12.1, h: 1.45, fill: HEX.darkCard, radius: 0.1, name: "owned" });
    text(s, "Nobody can rent Harbourline's fault history. The platform's job is to make it reachable, governed and fresh: that is where the differentiation lives, not in the model.", { x: M + 0.3, y: CONTENT_Y + 3.4, w: 11.5, h: 1.1, fontSize: 21, bold: true, color: HEX.white });
  }

  // ---------------------------------------------------------------- 13 · four kinds of context
  {
    const s = slide("CONTENT", "Data and intelligence", "Four kinds of context, four access paths", [3], 13);
    box(s, { x: W / 2 - 1.4, y: CONTENT_Y + 1.6, w: 2.8, h: 1.1, label: "Site Operations Advisor", sub: "decides which path the question needs", fill: HEX.violet, color: HEX.white, fontSize: 16 });
    const spokes = [
      [M, CONTENT_Y + 0.2, "Numbers → tools", "Site APIs with strict schemas: work orders, incidents, inspections, a site summary", HEX.teal],
      [W - M - 3.6, CONTENT_Y + 0.2, "Words → retrieval", "Procedures chunked by section in Azure AI Search; the agent cites titles", HEX.teal],
      [M, CONTENT_Y + 3.0, "Now → KQL", "The real-time store for what is happening this minute; Fabric Real-Time Intelligence", HEX.slate],
      [W - M - 3.6, CONTENT_Y + 3.0, "Who → memory", "What this site manager asked last week; Foundry agent memory (preview)", HEX.slate],
    ];
    spokes.forEach(([x, y, t, b, fill], i) => {
      box(s, { x, y, w: 3.6, h: 1.15, label: t, sub: b, fill, color: HEX.white, fontSize: 16, name: `spoke-${i}` });
      const cx = x < W / 2 ? x + 3.6 : x, cy = y + 0.575;
      arrow(s, { x1: W / 2 + (x < W / 2 ? -1.4 : 1.4), y1: CONTENT_Y + 2.15, x2: cx, y2: cy, color: fill });
    });
    text(s, "Mixing them up is the most common cause of a bad agent: a rules question answered from telemetry, a figure guessed from a document.", { x: M, y: 6.0, w: 12, h: 0.45, fontSize: 17, bold: true, color: HEX.amber });
  }

  // ---------------------------------------------------------------- 14 · Foundry Agent Service, October 2026
  {
    const s = slide("CONTENT", "Data and intelligence", "Foundry Agent Service, October 2026", [4], 14);
    const y = CONTENT_Y + 0.3;
    box(s, { x: M, y, w: 2.9, h: 1.0, label: "Agent definition", sub: "instructions + tools, versioned", fill: HEX.violet, color: HEX.white, fontSize: 16 });
    arrow(s, { x1: M + 2.9, y1: y + 0.5, x2: M + 3.5, y2: y + 0.5 });
    box(s, { x: M + 3.5, y, w: 2.9, h: 1.0, label: "Endpoint", sub: "routes 100 % to one version", fill: HEX.violet, color: HEX.white, fontSize: 16 });
    arrow(s, { x1: M + 6.4, y1: y + 0.5, x2: M + 7.0, y2: y + 0.5 });
    box(s, { x: M + 7.0, y, w: 2.9, h: 1.0, label: "Responses + Conversations", sub: "the client protocol", fill: HEX.slate, color: HEX.white, fontSize: 16 });
    arrow(s, { x1: M + 9.9, y1: y + 0.5, x2: M + 10.5, y2: y + 0.5 });
    box(s, { x: M + 10.5, y, w: 1.65, h: 1.0, label: "Teams, app, CLI", fill: HEX.tint, color: HEX.text, fontSize: 15, line: HEX.line });
    const chips = [
      ["Hosted agents", "GA", "your Agent Framework code in Foundry's runtime"],
      ["Routines", "preview", "run an agent on a schedule or trigger"],
      ["Toolboxes", "preview", "one managed MCP endpoint for a curated set of tools"],
      ["Memory", "preview", "procedural, user and session scopes"],
      ["Agent Framework 1.0", "stable", "Python and .NET; Claude Agent SDK and GitHub Copilot SDK integrations"],
      ["Toolkit for VS Code", "GA", "create, debug, connect and deploy from the editor"],
    ];
    chips.forEach(([t, st, b], i) => {
      const col = i % 3, row = Math.floor(i / 3);
      const x = M + col * 4.05, cy = CONTENT_Y + 1.75 + row * 1.35;
      rect(s, { x, y: cy, w: 3.85, h: 1.2, fill: HEX.tint, radius: 0.08, name: `chip-${i}` });
      text(s, t, { x: x + 0.2, y: cy + 0.12, w: 2.6, h: 0.35, fontSize: 17, bold: true });
      pill(s, { x: x + 2.85, y: cy + 0.14, w: 0.85, h: 0.26, label: st.toUpperCase(), fill: st === "preview" ? HEX.slate : HEX.green, color: HEX.white, fontSize: 11 });
      text(s, b, { x: x + 0.2, y: cy + 0.52, w: 3.5, h: 0.6, fontSize: 14.5, color: HEX.text });
    });
    text(s, "What the demo builds is a prompt agent. The chip row is what you would reach for next.", { x: M, y: 6.05, w: 12, h: 0.4, fontSize: 17, bold: true, color: HEX.amber });
  }

  // ---------------------------------------------------------------- 15 · demo 3
  {
    const s = slide("CONTENT_DARK", "Data and intelligence", "Demo 3 · A grounded agent in Foundry", [3, 4], 15);
    await videoSlide(s, { demo: 3, minutes: 8, folder: "03-grounded-foundry-agent", chapters: [{ t: "0:00", label: "Build" }, { t: "2:30", label: "Ask" }, { t: "6:40", label: "Next" }] });
  }

  // ---------------------------------------------------------------- 16 · observability
  {
    const s = slide("CONTENT", "Operate", "Observability on OpenTelemetry GenAI conventions", [5], 16);
    const y = CONTENT_Y + 0.3;
    ["SDK spans: agent, model, tools (gen_ai.*)", "Gateway logs and token metrics (APIM)", "Foundry traces and evaluation scores"].forEach((t, i) => {
      box(s, { x: M, y: y + i * 1.15, w: 3.9, h: 0.95, label: t, fill: HEX.tint, color: HEX.text, fontSize: 15, bold: false, line: HEX.line, name: `src-${i}` });
      arrow(s, { x1: M + 3.9, y1: y + i * 1.15 + 0.47, x2: M + 4.7, y2: y + 1.15 + 0.47 });
    });
    box(s, { x: M + 4.7, y: y + 0.6, w: 3.0, h: 2.1, label: "Application Insights", sub: "+ Log Analytics", fill: HEX.green, color: HEX.dark, fontSize: 19 });
    const outs = [["Agents (Preview) view", "tool and model tiles, errors, the simple end-to-end story of a run"], ["Explore in Grafana", "prebuilt Agent Framework and Foundry dashboards"], ["Azure Copilot Observability Agent", "ask the telemetry in English; GA, billed in Azure Agent Credits"], ["Azure SRE Agent", "from read-only diagnosis to approve-to-act"]];
    outs.forEach(([t, b], i) => {
      const oy = CONTENT_Y + i * 1.0;
      arrow(s, { x1: M + 7.7, y1: y + 1.65, x2: M + 8.4, y2: oy + 0.4, color: HEX.muted });
      text(s, t, { x: M + 8.45, y: oy, w: 3.7, h: 0.32, fontSize: 16, bold: true });
      text(s, b, { x: M + 8.45, y: oy + 0.33, w: 3.7, h: 0.6, fontSize: 14, color: HEX.muted });
    });
    text(s, "Nothing bespoke. Content recording off in production; the Agents view is the first place to look.", { x: M, y: 6.0, w: 12, h: 0.4, fontSize: 17, bold: true, color: HEX.amber });
  }

  // ---------------------------------------------------------------- 17 · evaluation as a release gate
  {
    const s = slide("CONTENT", "Operate", "Evaluation as a release gate", [4, 5], 17);
    const loop = ["Build a version", "Evaluate (judge x5)", "Gate: exit 0 or 1", "Promote the endpoint", "Monitor in production", "Improve"];
    loop.forEach((t, i) => {
      const x = M + i * 2.05, y = CONTENT_Y + 0.3;
      box(s, { x, y, w: 1.85, h: 0.8, label: t, fill: i === 2 ? HEX.amber : HEX.slate, color: i === 2 ? HEX.dark : HEX.white, fontSize: 14.5, name: `loop-${i}` });
      if (i < loop.length - 1) arrow(s, { x1: x + 1.85, y1: y + 0.4, x2: x + 2.05, y2: y + 0.4 });
    });
    const fams = [
      ["Quality", "groundedness, relevance, coherence", HEX.teal],
      ["Safety", "violence, hate, self-harm, protected material", HEX.amber],
      ["Agent", "intent resolution, task adherence, tool-call accuracy (preview)", HEX.violet],
    ];
    fams.forEach(([t, b, fill], i) => {
      const x = M + i * 4.05, y = CONTENT_Y + 1.5;
      rect(s, { x, y, w: 3.85, h: 1.2, fill: HEX.tint, radius: 0.08, name: `fam-${i}` });
      pill(s, { x: x + 0.2, y: y + 0.15, w: 1.0, label: t.toUpperCase(), fill, color: fill === HEX.amber ? HEX.dark : HEX.white });
      text(s, b, { x: x + 0.2, y: y + 0.55, w: 3.5, h: 0.6, fontSize: 15 });
    });
    rect(s, { x: M, y: CONTENT_Y + 2.95, w: 12.1, h: 1.6, fill: HEX.dark, radius: 0.1, name: "prod-eval" });
    text(s, "In production (GA since March 2026 for evaluations, tracing and monitoring)", { x: M + 0.25, y: CONTENT_Y + 3.05, w: 11.5, h: 0.35, fontSize: 16, bold: true, color: HEX.amber });
    bullets(s, [
      "Continuous evaluation: a sampled share of real responses scored as they happen, on the agent's Monitor tab",
      "Scheduled evaluations against the test dataset to catch drift; scheduled red teaming with an attack success rate (AI Red Teaming Agent, PyRIT)",
    ], { x: M + 0.25, y: CONTENT_Y + 3.45, w: 11.5, h: 1.05, fontSize: 15, color: LIGHT, spacing: 4 });
    text(s, "Evaluation is the test suite and the SLO at once.", { x: M, y: 6.1, w: 8, h: 0.4, fontSize: 17.5, bold: true, color: HEX.amber });
  }

  // ---------------------------------------------------------------- 18 · Build 2026: policy to executable checks
  {
    const s = slide("CONTENT", "Operate", "Build 2026: from written policy to executable checks", [4, 5], 18);
    const steps = [
      ["Agent Control Specification", "controls as YAML at five agent checkpoints (open source)"],
      ["ASSERT", "a written policy becomes executable evaluations (open source)"],
      ["Rubric evaluator", "weighted, agent-specific criteria (preview)"],
      ["Guided Guardrail Setup", "PII filters and jailbreak protection from a questionnaire (preview)"],
      ["Agent Optimizer", "traces and evaluations into ranked fixes (coming)"],
    ];
    steps.forEach(([t, b], i) => {
      const x = M + i * 2.46, y = CONTENT_Y + 0.6;
      box(s, { x, y, w: 2.26, h: 1.0, label: t, fill: i === 1 ? HEX.amber : HEX.slate, color: i === 1 ? HEX.dark : HEX.white, fontSize: 15, name: `b26-${i}` });
      text(s, b, { x, y: y + 1.1, w: 2.26, h: 1.1, fontSize: 14, color: HEX.text });
      if (i < steps.length - 1) arrow(s, { x1: x + 2.26, y1: y + 0.5, x2: x + 2.46, y2: y + 0.5 });
    });
    rect(s, { x: M, y: CONTENT_Y + 3.1, w: 12.1, h: 1.3, fill: HEX.tint, radius: 0.1, name: "gate-today" });
    text(s, "Today the gate in demo 4 is a short script over a twelve-row dataset. The discipline is the dataset; these five turn the policy document itself into rows the gate can run.", { x: M + 0.25, y: CONTENT_Y + 3.25, w: 11.5, h: 1.0, fontSize: 17.5 });
  }

  // ---------------------------------------------------------------- 19 · demo 4
  {
    const s = slide("CONTENT_DARK", "Operate", "Demo 4 · Trace, evaluate, gate", [4, 5], 19);
    await videoSlide(s, { demo: 4, minutes: 8.5, folder: "04-trace-and-evaluate", chapters: [{ t: "0:00", label: "Trace" }, { t: "3:00", label: "Evaluate" }, { t: "5:30", label: "Gate" }, { t: "7:20", label: "Operate" }] });
  }

  // ---------------------------------------------------------------- 20 · which model
  {
    const s = slide("CONTENT", "Close", "Which model, in October 2026", [4], 20);
    table(s, [
      ["", "What it is", "Where it fits"],
      ["GPT-5.6 family (Sol, Terra, Luna)", "OpenAI's current line, sold by Azure; Data Zone SKUs on the newer ones", "The default for an agent that calls tools"],
      ["Claude 5 family (Sonnet 5, Opus 5, Fable 5.1)", "Anthropic's current line, sold directly by Azure, one Entra token", "A judge from a different family; long reasoning"],
      ["Model router (updated October 2026)", "One deployment that picks the model per request", "Cost control for mixed traffic"],
      ["What the demos ran", "gpt-5-mini as the agent, gpt-5 as the judge", "Small agent, stricter judge; baselined before recording"],
    ], { fontSize: 15.5, colW: [3.6, 4.9, 3.63], rowH: 0.72, firstColBold: true });
    rect(s, { x: M, y: 5.45, w: 12.1, h: 0.95, fill: HEX.dark, radius: 0.08, name: "model-reco" });
    text(s, "Never judge with the family you are judging. Re-baseline the dataset before you switch the judge, and switch the agent model only through the gate.", { x: M + 0.25, y: 5.55, w: 11.6, h: 0.75, fontSize: 17, bold: true, color: HEX.white });
  }

  // ---------------------------------------------------------------- 21 · what changes for the platform team
  {
    const s = slide("CONTENT", "Close", "What changes for the platform team", [1, 2, 3, 4, 5], 21);
    const rows = [
      [5, "Experiences and agents", "publish through Agent 365; nothing new to host"],
      [4, "Intelligence", "a central Foundry resource, projects per product team, versions and a gate"],
      [3, "Data and context", "one knowledge index with an owner; tools, not database access"],
      [2, "Trust and control", "the AI gateway, four policies, an identity per agent"],
      [1, "Foundation", "a workload landing zone, quota as a platform concern"],
    ];
    rows.forEach(([n, name, what], i) => {
      const y = CONTENT_Y + i * 0.62;
      box(s, { x: M, y, w: 2.9, h: 0.52, label: `${n} · ${name}`, fill: LAYERS[n].hex, color: n === 2 || n === 5 ? HEX.dark : HEX.white, fontSize: 15, name: `wc-${n}` });
      text(s, what, { x: M + 3.1, y: y + 0.1, w: 5.4, h: 0.45, fontSize: 15.5 });
    });
    stat(s, { x: 9.4, y: CONTENT_Y - 0.1, w: 3.3, number: "4", label: "new services; the rest is configuration of what you already run", color: HEX.amber });
    rect(s, { x: M, y: CONTENT_Y + 3.35, w: 12.1, h: 1.3, fill: HEX.dark, radius: 0.1, name: "ninety" });
    text(s, "First 90 days", { x: M + 0.25, y: CONTENT_Y + 3.45, w: 3, h: 0.35, fontSize: 16, bold: true, color: HEX.amber });
    const strip = ["Audit-mode policies and a gateway with one product", "Central Foundry and quota", "One knowledge index with an owner", "First read-only agent with its own Agent ID", "A 30-row dataset and a gate in CI"];
    strip.forEach((t, i) => text(s, `${i + 1}. ${t}`, { x: M + 0.25 + i * 2.4, y: CONTENT_Y + 3.85, w: 2.3, h: 0.75, fontSize: 14, color: LIGHT }));
  }

  // ---------------------------------------------------------------- 22 · the one point
  {
    const s = pres.addSlide({ masterName: "CONTENT_DARK", sectionTitle: "Close" });
    s.addText("The one point", { placeholder: "title" });
    text(s, "AI changes the workload, not the control plane. An agent is a workload with a model inside it. Give it an identity, one front door, context you own and a release gate, and the Azure you already operate is what makes it safe to ship.", { x: M, y: CONTENT_Y + 0.1, w: 12.1, h: 1.9, fontSize: 24, bold: true, color: HEX.white, fontFace: "Cambria" });
    const moments = [["RequestDisallowed\nByPolicy", "what may exist", HEX.amber], ["429 Too Many\nRequests", "how calls behave", HEX.amber], ["Sources:\nget_open_work_orders", "context you own", HEX.teal], ["QUALITY GATE FAILED\nexit 1", "the release gate", HEX.green]];
    moments.forEach(([t, b, fill], i) => {
      const x = M + i * 3.05, y = CONTENT_Y + 2.4;
      rect(s, { x, y, w: 2.85, h: 1.5, fill: HEX.darkCard, radius: 0.08, name: `moment-${i}` });
      text(s, t, { x: x + 0.2, y: y + 0.15, w: 2.5, h: 0.75, fontSize: 14, bold: true, color: fill, fontFace: "Consolas", valign: "top" });
      text(s, b, { x: x + 0.2, y: y + 0.98, w: 2.5, h: 0.4, fontSize: 15, color: LIGHT });
    });
    s.addNotes(notes(22));
  }

  // ---------------------------------------------------------------- 23 · end card
  {
    const s = pres.addSlide({ masterName: "TITLE", sectionTitle: "Close" });
    s.addText("Code, runbooks and the review log", { placeholder: "title" });
    s.addText("github.com/mjtpena/ai-ready-azure", { placeholder: "body" });
    bullets(s, [
      "Microsoft Learn: Cloud Adoption Framework · AI scenario and workload landing zones",
      "Azure/AI-Landing-Zones · API Management GenAI gateway policies · Microsoft Entra Agent ID",
      "Microsoft Foundry: Agent Service, observability, evaluation, AI red teaming · Azure Monitor Agents view",
    ], { x: M, y: 5.0, w: 9.5, h: 1.3, fontSize: 15.5, color: LIGHT, spacing: 4 });
    text(s, "Harbourline Facilities is fictional; all data is synthetic.", { x: M, y: 6.5, w: 11, h: 0.4, fontSize: 14, color: DIM });
    s.addNotes(notes(23));
  }
};
