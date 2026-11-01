// Build the course deck: node src/build.js
// The script for each slide (src/notes.json) is copied into the speaker notes so the .pptx carries what the video says.
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require("./apply-theme");
const { THEME } = require("./theme");
const { defineLayouts, W, H } = require("./lib");
const { TARGETS, record, resolve } = require("./targets");

const DECK = {
  file: "ai-ready-azure.pptx",
  title: "AI-Ready Azure: the platform foundations agents actually need",
  footer: "AI-Ready Azure · the platform foundations agents actually need",
  mod: "./deck",
};

async function build() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  pres.title = DECK.title;
  pres.author = "Michael John Pena";
  pres.subject = "AI-Ready Azure course (fictional Harbourline Facilities scenario; synthetic data)";
  defineLayouts(pres, DECK.footer);
  record(pres);
  await require(DECK.mod)(pres);
  const out = path.join(__dirname, "..", "dist", DECK.file);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  const marks = resolve(require("./marks"));                     // the video's focus marks
  fs.writeFileSync(out.replace(/\.pptx$/, ".marks.json"), JSON.stringify({ slide_in: [W, H], slides: marks }, null, 1) + "\n");
  fs.writeFileSync(out.replace(/\.pptx$/, ".targets.json"), JSON.stringify(TARGETS, null, 1) + "\n");
  console.log("built", out, `(${Object.keys(marks).length} slide(s) with focus marks)`);
}

build().catch((e) => { console.error(e); process.exit(1); });
