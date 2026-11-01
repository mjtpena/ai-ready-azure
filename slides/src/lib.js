// Slide-building helpers for the course deck.
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const Md = require("react-icons/md");
const { THEME, LAYERS, HEX } = require("./theme");

const W = 13.333, H = 7.5; // LAYOUT_WIDE
const M = 0.6;             // outer margin
const CONTENT_Y = 1.55;    // top of content area on title-only slides
const CONTENT_H = 5.15;    // content height (leaves footer clear)
const FOOTER_Y = 6.95;

const iconCache = new Map();
async function iconPng(name, hex, px = 256) {
  const key = `${name}-${hex}-${px}`;
  if (iconCache.has(key)) return iconCache.get(key);
  const Cmp = Md[name];
  if (!Cmp) throw new Error(`Unknown icon ${name}`);
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Cmp, { color: `#${hex}`, size: px }));
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  const data = "image/png;base64," + buf.toString("base64");
  iconCache.set(key, data);
  return data;
}

function defineLayouts(pres, footerText) {
  const footer = (dark) => [
    {
      text: { text: footerText,
        options: { x: M, y: FOOTER_Y, w: 8, h: 0.3, fontSize: 12.5, color: dark ? "8A94A0" : HEX.muted, margin: 0, fontFace: THEME.bodyFontFace } },
    },
  ];
  pres.defineSlideMaster({
    title: "TITLE", background: { color: HEX.dark },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: M, y: 2.2, w: 9.5, h: 1.6, fontSize: 44, bold: true, color: HEX.white, fontFace: THEME.headFontFace, margin: 0, valign: "bottom", align: "left" } } },
      { placeholder: { options: { name: "body", type: "body", x: M, y: 3.95, w: 9.5, h: 1.2, fontSize: 20, color: "C9D1DA", fontFace: THEME.bodyFontFace, margin: 0, valign: "top", align: "left" } } },
    ],
  });
  pres.defineSlideMaster({
    title: "SECTION", background: { color: HEX.dark },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: M, y: 2.6, w: W - 2 * M, h: 1.4, fontSize: 40, bold: true, color: HEX.white, fontFace: THEME.headFontFace, margin: 0, valign: "bottom", align: "left" } } },
      { placeholder: { options: { name: "body", type: "body", x: M, y: 4.15, w: W - 2 * M, h: 1.4, fontSize: 22.5, color: "C9D1DA", fontFace: THEME.bodyFontFace, margin: 0, valign: "top", align: "left" } } },
      ...footer(true),
    ],
    slideNumber: { x: W - 1.2, y: FOOTER_Y, w: 0.6, h: 0.3, fontSize: 12.5, color: "8A94A0", align: "right" },
  });
  pres.defineSlideMaster({
    title: "CONTENT", background: { color: HEX.white },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: M, y: 0.45, w: 10.8, h: 0.95, fontSize: 28, bold: true, color: HEX.text, fontFace: THEME.headFontFace, margin: 0, valign: "middle", align: "left" } } },
      ...footer(false),
    ],
    slideNumber: { x: W - 1.2, y: FOOTER_Y, w: 0.6, h: 0.3, fontSize: 12.5, color: HEX.muted, align: "right" },
  });
  pres.defineSlideMaster({
    title: "CONTENT_DARK", background: { color: HEX.dark },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: M, y: 0.45, w: 10.8, h: 0.95, fontSize: 28, bold: true, color: HEX.white, fontFace: THEME.headFontFace, margin: 0, valign: "middle", align: "left" } } },
      ...footer(true),
    ],
    slideNumber: { x: W - 1.2, y: FOOTER_Y, w: 0.6, h: 0.3, fontSize: 12.5, color: "8A94A0", align: "right" },
  });
}

// ---- motif: the five-layer stack glyph (top-right), lit layers in colour -----------------
function layerGlyph(slide, lit, opts = {}) {
  const x = opts.x ?? W - M - 1.5, y = opts.y ?? 0.42, w = opts.w ?? 1.5, rowH = opts.rowH ?? 0.17, gap = 0.05;
  const dark = opts.dark ?? false;
  for (let i = 5; i >= 1; i--) {
    const idx = 5 - i; // layer 5 on top
    const on = lit.includes(i);
    slide.addShape("roundRect", {
      x, y: y + idx * (rowH + gap), w, h: rowH, rectRadius: 0.04,
      fill: { color: on ? LAYERS[i].hex : (dark ? "2A333E" : "E3E7EC") }, line: { color: on ? LAYERS[i].hex : (dark ? "2A333E" : "E3E7EC"), width: 0.5 },
      objectName: `layer-glyph-${i}`,
    });
  }
  if (opts.label !== false) {
    slide.addText(opts.labelText ?? "Layers lit", { x, y: y + 5 * (rowH + gap) + 0.02, w, h: 0.22, fontSize: 11, color: dark ? "8A94A0" : HEX.muted, align: "center", margin: 0, isTextBox: true, objectName: "layer-glyph-label" });
  }
}

// ---- primitives ---------------------------------------------------------------------------
function text(slide, str, o) {
  const base = { fontSize: 20, color: HEX.text, fontFace: THEME.bodyFontFace, margin: 0, isTextBox: true, valign: "top" };
  slide.addText(str, Object.assign(base, o));
}

function bullets(slide, items, o) {
  const size = o.fontSize ?? 16;
  const arr = items.map((it, i) => {
    const isObj = typeof it === "object";
    const t = isObj ? it.text : it;
    const opt = { bullet: { indent: isObj && it.sub ? 14 : 12 }, paraSpaceAfter: o.spacing ?? 8, breakLine: i < items.length - 1, fontSize: isObj && it.sub ? size - 2 : size, color: o.color ?? HEX.text };
    if (isObj && it.sub) { opt.indentLevel = 1; opt.color = o.subColor ?? HEX.muted; }
    if (isObj && it.bold) opt.bold = true;
    return { text: t, options: opt };
  });
  slide.addText(arr, Object.assign({ fontFace: THEME.bodyFontFace, margin: 0, isTextBox: true, valign: "top" }, o, { fontSize: size }));
}

function rect(slide, o) {
  const { x, y, w, h, fill, line, radius, name, shadow } = o;
  slide.addShape(radius ? "roundRect" : "rect", {
    x, y, w, h, rectRadius: radius ?? 0, fill: { color: fill ?? HEX.tint }, line: line ? { color: line, width: 0.75 } : { color: fill ?? HEX.tint, width: 0 },
    objectName: name ?? "rect", shadow: shadow ? { type: "outer", blur: 6, offset: 2, angle: 90, color: "000000", opacity: 0.12 } : undefined,
  });
}

async function iconCircle(slide, { x, y, d = 0.6, color, icon, bg, name }) {
  slide.addShape("ellipse", { x, y, w: d, h: d, fill: { color: bg ?? color }, line: { color: bg ?? color, width: 0 }, objectName: name ?? `icon-bg-${icon}` });
  const pad = d * 0.22;
  slide.addImage({ data: await iconPng(icon, bg ? color : HEX.white), x: x + pad, y: y + pad, w: d - 2 * pad, h: d - 2 * pad, objectName: name ? `${name}-icon` : `icon-${icon}` });
}

// Card with optional icon circle, bold title and body text. dark=true for dark slides.
async function card(slide, { x, y, w, h, title, body, color, icon, dark = false, fill, titleSize = 19, bodySize = 15.5, bodyColor, iconD = 0.5 }) {
  rect(slide, { x, y, w, h, fill: fill ?? (dark ? HEX.darkCard : HEX.tint), radius: 0.08, name: `card-${title}` });
  let ty = y + 0.18;
  if (icon) {
    await iconCircle(slide, { x: x + 0.2, y: y + 0.18, d: iconD, color: color ?? HEX.amber, icon, name: `card-icon-${title}` });
    ty = y + 0.18 + iconD + 0.12;
  }
  const charsPerLine = Math.max(8, (w - 0.4) * (105 / titleSize));
  const titleLines = Math.max(1, Math.ceil(title.length / charsPerLine));
  const titleH = titleLines * titleSize * 0.0215 + 0.1;
  text(slide, title, { x: x + 0.2, y: ty, w: w - 0.4, h: titleH, fontSize: titleSize, bold: true, color: dark ? HEX.white : HEX.text, valign: "top" });
  if (body) {
    const bodyArr = Array.isArray(body) ? body : [body];
    const h2 = y + h - (ty + titleH + 0.05) - 0.12;
    if (bodyArr.length > 1 || (Array.isArray(body))) {
      bullets(slide, bodyArr, { x: x + 0.2, y: ty + titleH + 0.05, w: w - 0.4, h: h2, fontSize: bodySize, color: bodyColor ?? (dark ? "C9D1DA" : HEX.text), spacing: 4 });
    } else {
      text(slide, body, { x: x + 0.2, y: ty + titleH + 0.05, w: w - 0.4, h: h2, fontSize: bodySize, color: bodyColor ?? (dark ? "C9D1DA" : HEX.text) });
    }
  }
}

// Row of N equal cards across the content width.
async function cardRow(slide, cards, { y = CONTENT_Y, h = CONTENT_H, gap = 0.3, x0 = M, width = W - 2 * M, dark = false } = {}) {
  const n = cards.length, w = (width - gap * (n - 1)) / n;
  for (let i = 0; i < n; i++) await card(slide, Object.assign({ x: x0 + i * (w + gap), y, w, h, dark }, cards[i]));
}

// Grid of cards (cols x rows).
async function cardGrid(slide, cards, { cols = 3, y = CONTENT_Y, h = CONTENT_H, gap = 0.25, x0 = M, width = W - 2 * M, dark = false } = {}) {
  const rows = Math.ceil(cards.length / cols);
  const w = (width - gap * (cols - 1)) / cols, ch = (h - gap * (rows - 1)) / rows;
  for (let i = 0; i < cards.length; i++) {
    const c = i % cols, r = Math.floor(i / cols);
    await card(slide, Object.assign({ x: x0 + c * (w + gap), y: y + r * (ch + gap), w, h: ch, dark }, cards[i]));
  }
}

// Icon + heading + description rows (vertical list), optionally in two columns.
async function iconRows(slide, rows, { x = M, y = CONTENT_Y, w = W - 2 * M, rowH = 0.95, color, dark = false, titleSize = 20, bodySize = 16 } = {}) {
  for (let i = 0; i < rows.length; i++) {
    const r = rows[i], ry = y + i * rowH;
    await iconCircle(slide, { x, y: ry + 0.05, d: 0.55, color: r.color ?? color ?? HEX.amber, icon: r.icon, name: `row-icon-${i}` });
    text(slide, r.title, { x: x + 0.8, y: ry, w: w - 0.8, h: 0.32, fontSize: titleSize, bold: true, color: dark ? HEX.white : HEX.text });
    text(slide, r.body, { x: x + 0.8, y: ry + 0.33, w: w - 0.8, h: rowH - 0.38, fontSize: bodySize, color: dark ? "C9D1DA" : HEX.text });
  }
}

// Big-number stat callout.
function stat(slide, { x, y, w = 2.6, number, label, color = HEX.amber, dark = false, note }) {
  text(slide, number, { x, y, w, h: 0.95, fontSize: 48, bold: true, color, fontFace: THEME.headFontFace, valign: "bottom" });
  text(slide, label, { x, y: y + 1.0, w, h: 0.85, fontSize: 17.5, color: dark ? "C9D1DA" : HEX.text, bold: true });
  if (note) text(slide, note, { x, y: y + 1.9, w, h: 0.5, fontSize: 14, color: dark ? "8A94A0" : HEX.muted, italic: true });
}

// Labelled box for diagrams.
function box(slide, { x, y, w, h, label, sub, fill = HEX.tint, color = HEX.text, line, fontSize = 15, bold = true, radius = 0.06, name, align = "center" }) {
  slide.addShape("roundRect", { x, y, w, h, rectRadius: radius, fill: { color: fill }, line: { color: line ?? fill, width: 0.75 }, objectName: name ?? `box-${label}` });
  if (sub) {
    slide.addText([
      { text: label, options: { bold, fontSize, color, breakLine: true } },
      { text: sub, options: { fontSize: Math.max(fontSize - 3, 12), color, bold: false } },
    ], { x: x + 0.06, y, w: w - 0.12, h, align, valign: "middle", margin: 0, fontFace: THEME.bodyFontFace, isTextBox: true, objectName: `${name ?? label}-text` });
  } else {
    slide.addText(label, { x: x + 0.06, y, w: w - 0.12, h, align, valign: "middle", margin: 0, fontSize, bold, color, fontFace: THEME.bodyFontFace, isTextBox: true, objectName: `${name ?? label}-text` });
  }
}

// Straight connector with arrow head. Direction is from (x1,y1) to (x2,y2).
function arrow(slide, { x1, y1, x2, y2, color = HEX.muted, width = 1.5, dash, name }) {
  const x = Math.min(x1, x2), y = Math.min(y1, y2), w = Math.abs(x2 - x1), h = Math.abs(y2 - y1);
  const flipH = x2 < x1, flipV = y2 < y1;
  slide.addShape("line", { x, y, w: w || 0.001, h: h || 0.001, line: { color, width, endArrowType: "triangle", dashType: dash ? "dash" : "solid" }, flipH, flipV, objectName: name ?? "arrow" });
}

// Simple native table with consistent styling.
function table(slide, rows, { x = M, y = CONTENT_Y, w = W - 2 * M, colW, fontSize = 15, headFill = HEX.dark, headColor = HEX.white, rowH, dark = false, zebra = true, firstColBold = false } = {}) {
  const data = rows.map((r, ri) => r.map((c, ci) => {
    const isHead = ri === 0;
    const base = { fontSize, fontFace: THEME.bodyFontFace, color: isHead ? headColor : (dark ? "E6EAF0" : HEX.text), bold: isHead || (firstColBold && ci === 0), valign: "middle", margin: 0.06 };
    if (isHead) base.fill = { color: headFill };
    else base.fill = { color: dark ? (ri % 2 ? HEX.darkCard : "1B222B") : (zebra && ri % 2 === 0 ? HEX.tint : HEX.white) };
    if (typeof c === "object" && c !== null && c.text !== undefined) return { text: c.text, options: Object.assign(base, c.options) };
    return { text: String(c), options: base };
  }));
  slide.addTable(data, { x, y, w, colW, rowH, border: { type: "solid", color: dark ? "2A333E" : HEX.line, pt: 0.5 }, autoPage: false, objectName: "table" });
}

// Small "pill" tag.
function pill(slide, { x, y, w = 1.3, h = 0.3, label, fill = HEX.amber, color = HEX.dark, fontSize = 12.5 }) {
  slide.addShape("roundRect", { x, y, w, h, rectRadius: 0.15, fill: { color: fill }, line: { color: fill, width: 0 }, objectName: `pill-${label}` });
  slide.addText(label, { x, y, w, h, fontSize, bold: true, color, align: "center", valign: "middle", margin: 0, fontFace: THEME.bodyFontFace, isTextBox: true, objectName: `pill-${label}-text` });
}

// Demo slide: a standard frame used for the four live demos.
async function demoSlide(slide, { title, minutes, lit, steps, watchFor, folder }) {
  slide.addText(title, { placeholder: "title" });
  layerGlyph(slide, lit);
  pill(slide, { x: M, y: CONTENT_Y - 0.05, w: 1.6, label: `LIVE DEMO · ${minutes} MIN`, fill: HEX.amber });
  text(slide, `demos/${folder}`, { x: M + 1.75, y: CONTENT_Y - 0.03, w: 5, h: 0.3, fontSize: 15, color: HEX.muted, fontFace: "Courier New" });
  const leftW = 7.3;
  text(slide, "What you will see", { x: M, y: CONTENT_Y + 0.5, w: leftW, h: 0.35, fontSize: 20, bold: true });
  const stepArr = steps.map((s, i) => ({ text: `${i + 1}.  ${s}` }));
  slide.addText(stepArr.map((s, i) => ({ text: s.text, options: { breakLine: i < stepArr.length - 1, paraSpaceAfter: 8, fontSize: 17.5, color: HEX.text } })),
    { x: M, y: CONTENT_Y + 0.9, w: leftW, h: CONTENT_H - 1.0, margin: 0, fontFace: THEME.bodyFontFace, isTextBox: true, valign: "top", objectName: "demo-steps" });
  const rx = M + leftW + 0.4, rw = W - M - rx;
  rect(slide, { x: rx, y: CONTENT_Y + 0.5, w: rw, h: CONTENT_H - 0.6, fill: HEX.dark, radius: 0.1, name: "watch-card" });
  text(slide, "Watch for", { x: rx + 0.25, y: CONTENT_Y + 0.7, w: rw - 0.5, h: 0.35, fontSize: 19, bold: true, color: HEX.amber });
  bullets(slide, watchFor, { x: rx + 0.25, y: CONTENT_Y + 1.1, w: rw - 0.5, h: CONTENT_H - 1.4, fontSize: 16, color: "E6EAF0", spacing: 6 });
}

// Demo video slide (CONTENT_DARK): the recorded demo plays in a 16:9 frame on the left, its chapters on the right.
// Media comes from video/media/demo<N>.mp4 (+ -poster.png, + .json chapters written by the recorder); until the
// recording exists the frame shows a placeholder so the deck still builds.
const MEDIA_DIR = require("path").join(__dirname, "..", "..", "video", "media");
async function videoSlide(slide, { demo, minutes, folder, chapters: fallbackChapters = [] }) {
  const fs = require("fs"), path = require("path");
  const mp4 = path.join(MEDIA_DIR, `demo${demo}.mp4`);
  const poster = path.join(MEDIA_DIR, `demo${demo}-poster.png`);
  const meta = path.join(MEDIA_DIR, `demo${demo}.json`);
  const vx = M, vy = 1.5, vw = 9.6, vh = vw * 9 / 16; // bottom edge 6.9, clear of the footer
  // Right column starts below the layer glyph (top-right, ends ~1.8"), so nothing touches the title or the glyph.
  const cx = vx + vw + 0.35, cw = W - M - cx;
  const info = fs.existsSync(meta) ? JSON.parse(fs.readFileSync(meta, "utf8")) : null;
  const length = info ? `${Math.floor(info.duration / 60)}:${String(Math.round(info.duration % 60)).padStart(2, "0")}` : `${minutes} MIN`;
  pill(slide, { x: cx, y: 1.95, w: cw, label: `${info && info.narrated ? "NARRATED DEMO" : "DEMO VIDEO"} · ${length}`, fill: HEX.amber });
  // the path breaks after "demos/", never inside the folder name
  text(slide, `demos/\n${folder}`, { x: cx, y: 2.33, w: cw, h: 0.42, fontSize: 11, color: "8A94A0", fontFace: "Courier New" });
  if (fs.existsSync(mp4)) {
    const cover = fs.existsSync(poster) ? "image/png;base64," + fs.readFileSync(poster).toString("base64") : undefined;
    slide.addMedia({ type: "video", path: mp4, cover, x: vx, y: vy, w: vw, h: vh, objectName: `demo${demo}-video` });
  } else {
    rect(slide, { x: vx, y: vy, w: vw, h: vh, fill: HEX.darkCard, radius: 0.06, name: `demo${demo}-video-placeholder` });
    await iconCircle(slide, { x: vx + vw / 2 - 0.5, y: vy + vh / 2 - 0.75, d: 1.0, color: HEX.amber, icon: "MdPlayArrow", name: "video-placeholder-play" });
    text(slide, "Recording pending", { x: vx, y: vy + vh / 2 + 0.4, w: vw, h: 0.4, fontSize: 20, color: "C9D1DA", align: "center" });
  }
  const chapters = info ? info.chapters : fallbackChapters;
  const cy = 2.85;
  text(slide, "Chapters", { x: cx, y: cy, w: cw, h: 0.32, fontSize: 17.5, bold: true, color: HEX.amber });
  const rowH = Math.min(0.55, (vy + vh - cy - 0.4) / Math.max(1, chapters.length));
  const chFs = chapters.length > 7 ? 12.5 : chapters.length > 5 ? 13 : 14.5; // long lists get a smaller face so labels keep to two lines
  chapters.forEach((ch, i) => {
    const y = cy + 0.4 + i * rowH;
    text(slide, ch.t ?? "", { x: cx, y, w: 0.6, h: rowH, fontSize: Math.min(11, chFs), color: HEX.amber, fontFace: "Courier New", bold: true });
    text(slide, ch.label, { x: cx + 0.62, y, w: cw - 0.62, h: rowH, fontSize: chFs, color: "E6EAF0" });
  });
}

// Section divider helper
function section(pres, title, sub, sectionTitle) {
  const s = pres.addSlide({ masterName: "SECTION", sectionTitle });
  s.addText(title, { placeholder: "title" });
  if (sub) s.addText(sub, { placeholder: "body" });
  return s;
}

// Agenda table (timings).
function agendaTable(slide, rows, opts = {}) {
  table(slide, [["NZDT", "Min", "Format", "Segment"], ...rows], Object.assign({ colW: [1.5, 0.7, 1.9, 8.0], fontSize: 15.5, firstColBold: true }, opts));
}

// Factory for the common "titled content slide" call.
function makeSlideFn(pres) {
  return (master, sec, title, lit, notes) => {
    const sl = pres.addSlide({ masterName: master, sectionTitle: sec });
    if (title) sl.addText(title, { placeholder: "title" });
    if (lit) layerGlyph(sl, lit, { dark: master === "CONTENT_DARK" });
    if (notes) sl.addNotes(notes);
    return sl;
  };
}

module.exports = { makeSlideFn, W, H, M, CONTENT_Y, CONTENT_H, FOOTER_Y, THEME, LAYERS, HEX, iconPng, defineLayouts, layerGlyph, text, bullets, rect, iconCircle, card, cardRow, cardGrid, iconRows, stat, box, arrow, table, pill, demoSlide, videoSlide, section, agendaTable };
