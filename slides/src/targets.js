// Element geometry for the video's focus marks. Every slide's addShape / addText / addTable / addImage call is recorded
// (inches, as laid out), so a mark in marks.js can name its target instead of carrying coordinates:
//   "row:2" / "col:3"      a row or column of the slide's table (row 0 is the header)
//   "<text>"               the card or box whose name or text contains it (case-insensitive), else any text element
//   "a&b"                  one box around both targets
//   [x, y, w, h]           a literal box
// resolve() turns marks.js into the {slide: [{say, boxes, label, tone, style, clear}]} that build.js writes as
// <deck>.marks.json for the video renderer.
const TARGETS = {};

const plain = (t) => (Array.isArray(t) ? t.map((r) => (typeof r === "string" ? r : r.text)).join(" ") : String(t ?? ""));

function record(pres) {
  const addSlide = pres.addSlide.bind(pres);
  pres.addSlide = (opts) => {
    const s = addSlide(opts);
    const n = pres.slides.length;
    const els = (TARGETS[n] = []);
    const keep = (kind, o, text) => {
      if (o && typeof o.x === "number" && typeof o.y === "number" && !o.placeholder)
        els.push({ kind, name: o.objectName ?? "", text: plain(text), box: [o.x, o.y, o.w ?? 0, o.h ?? 0] });
    };
    for (const [fn, kind] of [["addShape", "shape"], ["addImage", "image"]]) {
      const orig = s[fn].bind(s);
      s[fn] = (a, b) => { keep(kind, fn === "addShape" ? b : a, ""); return orig(a, b); };
    }
    const addText = s.addText.bind(s);
    s.addText = (t, o) => { keep("text", o, t); return addText(t, o); };
    const addTable = s.addTable.bind(s);
    s.addTable = (rows, o) => {
      const colW = o.colW ?? rows[0].map(() => (o.w ?? 0) / rows[0].length);
      const rowH = typeof o.rowH === "number" ? o.rowH : 0.5;
      els.push({ kind: "table", name: "table", text: "", box: [o.x, o.y, o.w, rowH * rows.length],
                 rows: rows.map((r, i) => ({ text: r.map((c) => plain(c.text ?? c)).join(" | "), box: [o.x, o.y + rowH * i, o.w, rowH] })),
                 cols: colW.map((cw, j) => ({ box: [o.x + colW.slice(0, j).reduce((a, b) => a + b, 0), o.y, cw, rowH * rows.length] })) });
      return addTable(rows, o);
    };
    return s;
  };
}

function find(n, sel) {
  if (Array.isArray(sel) && typeof sel[0] === "number") return sel;
  if (typeof sel === "string" && sel.includes("&")) {                  // "a&b": one box around both
    const bs = sel.split("&").map((s) => find(n, s.trim()));
    const x0 = Math.min(...bs.map((b) => b[0])), y0 = Math.min(...bs.map((b) => b[1]));
    const x1 = Math.max(...bs.map((b) => b[0] + b[2])), y1 = Math.max(...bs.map((b) => b[1] + b[3]));
    return [x0, y0, x1 - x0, y1 - y0];
  }
  const els = TARGETS[n] ?? [];
  const tbl = els.find((e) => e.kind === "table");
  let m;
  if ((m = /^row:(\d+)(?:-(\d+))?$/.exec(sel)) && tbl) {
    const a = tbl.rows[+m[1]], b = tbl.rows[+(m[2] ?? m[1])];
    if (a && b) return [a.box[0], a.box[1], a.box[2], b.box[1] + b.box[3] - a.box[1]];
  }
  if ((m = /^col:(\d+)$/.exec(sel)) && tbl && tbl.cols[+m[1]]) return tbl.cols[+m[1]].box;
  const want = String(sel).toLowerCase();
  const shape = els.find((e) => e.kind === "shape" && e.name.toLowerCase().includes(want) && e.box[2] > 0.3);
  if (shape) return shape.box;
  const txt = els.find((e) => e.kind === "text" && e.text.toLowerCase().includes(want));
  if (txt) return txt.box;
  throw new Error(`marks.js: slide ${n} has no target matching ${JSON.stringify(sel)}`);
}

function resolve(spec) {
  const out = {};
  for (const [n, list] of Object.entries(spec)) {
    out[n] = list.map(([say, sel, opts = {}]) => {
      if (opts.clear) return { say, clear: true };
      const sels = Array.isArray(sel) && typeof sel[0] !== "number" ? sel : [sel];
      return Object.assign({ say, boxes: sels.map((x) => find(+n, x)) }, opts);
    });
  }
  return out;
}

module.exports = { TARGETS, record, resolve };
