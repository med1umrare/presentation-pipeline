// Renders presentation-chart-spec/1.0 files into an editable PPTX.
// Native PowerPoint charts where the form allows it; vector shapes computed
// from data otherwise. Plot areas use a fixed inner layout so annotations can
// be placed at exact data coordinates.
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import pptxgen from "pptxgenjs";

const NBSP = " ";
const MINUS = "−";
// Number format comes from tokens.json dataviz.numberFormat (see loadTheme).
const NF = { thousands: NBSP, decimal: ",", minus: MINUS };

// ---------- data ----------

export function readCsv(file) {
  const lines = fs.readFileSync(file, "utf8").replace(/^﻿/, "").trim().split(/\r?\n/);
  const head = lines[0].split(",");
  return lines.slice(1).map((line) => {
    const cells = line.split(",");
    return Object.fromEntries(head.map((h, i) => [h, cells[i]]));
  });
}

const sha256 = (file) => crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
const num = (row, col) => Number(row[col]);

// ---------- formatting ----------

export function fmt(v, decimals = 0, { signed = false } = {}) {
  const fixed = Math.abs(v).toFixed(decimals);
  const [int, frac] = fixed.split(".");
  const body = int.replace(/\B(?=(\d{3})+(?!\d))/g, NF.thousands) + (frac ? `${NF.decimal}${frac}` : "");
  if (Number(fixed) === 0) return body;
  if (v < 0) return NF.minus + body;
  return signed ? `+${body}` : body;
}

function formatCode(decimals, { signed = false, percent = false } = {}) {
  const body = "#,##0" + (decimals ? "." + "0".repeat(decimals) : "") + (percent ? "%" : "");
  return signed ? `+${body};\\${MINUS}${body};${body}` : body;
}

function times(ratio) {
  return `в${NBSP}${fmt(ratio, 1).replace(`${NF.decimal}0`, "")}${NBSP}раза`;
}

// ---------- geometry ----------

function niceStep(range, ticks = 4) {
  const raw = range / ticks;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
  return step;
}

function niceMax(v, ticks = 4) {
  const step = niceStep(v, ticks);
  return Math.ceil(v / step) * step;
}

// Inner plot rectangle in slide inches plus value→coordinate mappers.
function plot(box, layout, min, max) {
  const X0 = box.x + layout.x * box.w;
  const Y0 = box.y + layout.y * box.h;
  const PW = layout.w * box.w;
  const PH = layout.h * box.h;
  return {
    X0, Y0, PW, PH,
    y: (v) => Y0 + PH * (1 - (v - min) / (max - min)),
    x: (v) => X0 + PW * ((v - min) / (max - min)),
    band: (i, n) => X0 + (PW / n) * (i + 0.5),
  };
}

function estimateLines(text, widthIn, sizePt, factor = 0.5) {
  const perLine = Math.max(1, Math.floor((widthIn * 72) / (sizePt * factor)));
  return text.split("\n").reduce((n, part) => n + Math.max(1, Math.ceil(part.length / perLine)), 0);
}

// Spread label centres so none are closer than `gap`, preserving order.
function spread(items, gap) {
  const sorted = [...items].sort((a, b) => a.y - b.y);
  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i].y - sorted[i - 1].y < gap) sorted[i].y = sorted[i - 1].y + gap;
  }
  return items;
}

// ---------- shared slide chrome ----------

const hex = (c) => c.replace("#", "").toUpperCase();

function chartBase(T) {
  const C = T.colors;
  return {
    showLegend: false,
    showTitle: false,
    chartArea: { roundedCorners: false },
    catAxisLabelColor: hex(C.text),
    catAxisLabelFontFace: T.fonts.body,
    catAxisLabelFontSize: T.sizesPt.axis,
    catAxisMajorTickMark: "none",
    valAxisMajorTickMark: "none",
    catAxisLineShow: false,
    valAxisLineShow: false,
    valAxisHidden: true,
    valGridLine: { style: "none" },
    dataLabelColor: hex(C.text),
    dataLabelFontFace: T.fonts.body,
    dataLabelFontSize: T.sizesPt.dataLabel,
  };
}

const STATUS_TAG = { synthetic: "ДЕМО-ДАННЫЕ", modelled: "МОДЕЛЬ", actual: "" };

function chrome(ctx, index, total) {
  const { slide, spec, T } = ctx;
  const C = T.colors;
  const S = T.slide;
  const contentW = S.widthIn - 2 * S.marginXIn;
  slide.background = { color: hex(C.background) };
  const meta = { fontFace: T.fonts.technical, fontSize: T.sizesPt.meta, color: hex(C.textMuted), margin: 0 };
  if (ctx.kicker) slide.addText(ctx.kicker, { ...meta, x: S.marginXIn, y: 0.28, w: 6, h: 0.22 });
  slide.addText(String(index + 1).padStart(2, "0"), { ...meta, x: S.widthIn - S.marginXIn - 1, y: 0.28, w: 1, h: 0.22, align: "right" });

  const titleLines = estimateLines(spec.title, contentW, T.sizesPt.title);
  const titleH = (titleLines * T.sizesPt.title * 1.18) / 72;
  slide.addText(spec.title, {
    x: S.marginXIn, y: 0.62, w: contentW, h: titleH,
    fontFace: T.fonts.display, fontSize: T.sizesPt.title, color: hex(C.text), margin: 0, valign: "top",
  });
  const subY = 0.62 + titleH + 0.1;
  slide.addText(spec.subtitle, {
    x: S.marginXIn, y: subY, w: contentW, h: 0.3,
    fontFace: T.fonts.body, fontSize: T.sizesPt.subtitle, color: hex(C.textMuted), margin: 0, valign: "top",
  });

  const footY = S.heightIn - 0.62;
  slide.addShape(ctx.pres.shapes.LINE, { x: S.marginXIn, y: footY, w: contentW, h: 0, line: { color: hex(C.axis), width: 0.75 } });
  slide.addText(`Источник: ${spec.sourceNote || spec.data.sourceIds.join(", ")}`, {
    x: S.marginXIn, y: footY + 0.1, w: contentW - 2.2, h: 0.25,
    fontFace: T.fonts.body, fontSize: T.sizesPt.source, color: hex(C.textMuted), margin: 0,
  });
  const tag = STATUS_TAG[spec.dataStatus];
  if (tag) {
    slide.addText(tag, {
      x: S.widthIn - S.marginXIn - 2.2, y: footY + 0.1, w: 2.2, h: 0.25, align: "right",
      fontFace: T.fonts.technical, fontSize: T.sizesPt.meta, color: hex(C.negative), margin: 0, bold: true,
    });
  }
  slide.addNotes([
    `chartId: ${spec.chartId}`,
    `slideId: ${spec.slideId}`,
    `claimIds: ${spec.claimIds.join(", ")}`,
    `type: ${spec.type}`,
    `data: ${spec.data.location} sha256=${spec.data.sha256}`,
    `dataStatus: ${spec.dataStatus}`,
  ].join("\n"));

  const top = subY + 0.3 + 0.35;
  const bottom = footY - 0.25;
  const hasNote = Boolean(spec.annotation);
  const noteW = 2.85;
  const box = { x: S.marginXIn, y: top, w: hasNote ? contentW - noteW - 0.45 : contentW, h: bottom - top };
  if (hasNote) annotation(ctx, { x: S.widthIn - S.marginXIn - noteW, y: top + 0.05, w: noteW });
  return box;
}

function annotation(ctx, { x, y, w }) {
  const { slide, spec, T, pres } = ctx;
  const size = T.sizesPt.annotation;
  const h = (estimateLines(spec.annotation, w - 0.2, size) * size * 1.35) / 72;
  slide.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.05, h, fill: { color: hex(T.colors.focus) }, line: { type: "none" } });
  slide.addText(spec.annotation, {
    x: x + 0.2, y, w: w - 0.2, h, fontFace: T.fonts.body, fontSize: size, color: hex(T.colors.text), margin: 0, valign: "top",
    lineSpacingMultiple: 1.1,
  });
}

// ---------- renderers ----------

function rankedBar(ctx, box) {
  const { slide, spec, rows, T, pres } = ctx;
  const C = T.colors;
  const e = spec.encoding;
  const totals = new Map();
  for (const r of rows) totals.set(r[e.category], (totals.get(r[e.category]) || 0) + num(r, e.value));
  const items = [...totals].map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value);
  const hl = new Set(spec.highlight || []);
  const h = Math.min(box.h, items.length * 0.78 + 0.2);
  const max = niceMax(Math.max(...items.map((i) => i.value)) * 1.15);
  slide.addChart(pres.charts.BAR, [{ name: spec.units.label, labels: items.map((i) => i.label), values: items.map((i) => i.value) }], {
    ...chartBase(T),
    x: box.x, y: box.y, w: box.w, h,
    layout: { x: 0.17, y: 0.02, w: 0.8, h: 0.96 },
    barDir: "bar",
    catAxisOrientation: "maxMin",
    barGapWidthPct: 55,
    chartColors: items.map((i) => hex(hl.has(i.label) ? C.focus : C.context)),
    showValue: true,
    dataLabelPosition: "outEnd",
    dataLabelFormatCode: formatCode(spec.units.decimals),
    valAxisMinVal: 0,
    valAxisMaxVal: max,
  });
}

function waterfall(ctx, box) {
  const { slide, spec, rows, T, pres } = ctx;
  const C = T.colors;
  const e = spec.encoding;
  const d = spec.units.decimals;
  const hl = new Set(spec.highlight || []);
  const labels = rows.map((r) => r[e.step]);
  const n = rows.length;
  const series = { base: [], total: [], up: [], upOther: [], down: [] };
  const bars = [];
  let running = 0;
  rows.forEach((r) => {
    const kind = r[e.kind];
    const v = num(r, e.value);
    const zero = () => Object.values(series).forEach((s) => s.push(0));
    zero();
    const i = series.base.length - 1;
    if (kind === "start" || kind === "end") {
      series.total[i] = v;
      running = v;
      bars.push({ lo: 0, hi: v, label: fmt(v, d), kind });
    } else if (v >= 0) {
      series.base[i] = running;
      (hl.has(r[e.step]) ? series.up : series.upOther)[i] = v;
      bars.push({ lo: running, hi: running + v, label: fmt(v, d, { signed: true }), kind: "up" });
      running += v;
    } else {
      series.base[i] = running + v;
      series.down[i] = -v;
      bars.push({ lo: running + v, hi: running, label: fmt(v, d, { signed: true }), kind: "down" });
      running += v;
    }
  });
  const max = niceMax(Math.max(...bars.map((b) => b.hi)) * 1.12);
  const layout = { x: 0.01, y: 0.06, w: 0.98, h: 0.82 };
  const gap = 55;
  const names = ["База", "Итог", "Рост", "Рост (прочее)", "Снижение"];
  slide.addChart(pres.charts.BAR, Object.values(series).map((values, k) => ({ name: names[k], labels, values })), {
    ...chartBase(T),
    x: box.x, y: box.y, w: box.w, h: box.h,
    layout,
    barDir: "col",
    barGrouping: "stacked",
    barGapWidthPct: gap,
    chartColors: ["transparent", hex(C.text), hex(C.focus), hex(C.focusSoft), hex(C.negative)],
    catAxisLineShow: true,
    catAxisLineColor: hex(C.axis),
    valAxisMinVal: 0,
    valAxisMaxVal: max,
  });
  const p = plot(box, layout, 0, max);
  const band = p.PW / n;
  const barW = band / (1 + gap / 100);
  bars.forEach((b, i) => {
    const cx = p.band(i, n);
    const color = b.kind === "down" ? C.negative : b.kind === "up" ? C.text : C.text;
    const below = b.kind === "down";
    slide.addText(b.label, {
      x: cx - band / 2, y: below ? p.y(b.lo) + 0.05 : p.y(b.hi) - 0.34, w: band, h: 0.28, align: "center",
      fontFace: T.fonts.body, fontSize: T.sizesPt.dataLabel, bold: b.kind !== "up" && b.kind !== "down", color: hex(color), margin: 0,
    });
    if (i < n - 1) {
      const level = b.kind === "down" ? b.lo : b.hi;
      slide.addShape(pres.shapes.LINE, {
        x: cx + barW / 2, y: p.y(level), w: band - barW, h: 0,
        line: { color: hex(C.contextStrong), width: 0.75, dashType: "dash" },
      });
    }
  });
}

function variance(ctx, box) {
  const { slide, spec, rows, T, pres } = ctx;
  const C = T.colors;
  const e = spec.encoding;
  const hl = new Set(spec.highlight || []);
  const labels = rows.map((r) => r[e.category]);
  const values = rows.map((r) => (num(r, e.actual) - num(r, e.plan)) / num(r, e.plan));
  const thr = typeof e.threshold === "number" ? e.threshold / 100 : null;
  const colors = rows.map((r, i) => {
    const neg = values[i] < 0;
    if (hl.has(r[e.category])) return hex(neg ? C.negative : C.focus);
    return hex(neg ? C.negativeSoft : C.context);
  });
  const lo = Math.min(...values, thr ?? 0) * 1.4;
  const hi = Math.max(...values) * 1.35;
  const layout = { x: 0.01, y: 0.04, w: 0.98, h: 0.84 };
  slide.addChart(pres.charts.BAR, [{ name: "Отклонение", labels, values }], {
    ...chartBase(T),
    x: box.x, y: box.y, w: box.w, h: box.h,
    layout,
    barDir: "col",
    barGapWidthPct: 70,
    chartColors: colors,
    invertedColors: colors,
    showValue: true,
    dataLabelPosition: "outEnd",
    dataLabelFormatCode: formatCode(spec.units.decimals, { signed: true, percent: true }),
    catAxisLabelPos: "low",
    catAxisLineShow: true,
    catAxisLineColor: hex(C.text),
    valAxisMinVal: lo,
    valAxisMaxVal: hi,
  });
  if (thr !== null) {
    const p = plot(box, layout, lo, hi);
    slide.addShape(pres.shapes.LINE, {
      x: p.X0, y: p.y(thr), w: p.PW, h: 0, line: { color: hex(C.negative), width: 1, dashType: "dash" },
    });
    slide.addText(`порог ${fmt(thr * 100, 0, { signed: true })}%`, {
      x: p.X0 + p.PW - 2, y: p.y(thr) + 0.04, w: 2, h: 0.24, align: "right",
      fontFace: T.fonts.body, fontSize: T.sizesPt.axis - 1, color: hex(C.negative), margin: 0,
    });
  }
}

function slope(ctx, box) {
  const { slide, spec, rows, T, pres } = ctx;
  const C = T.colors;
  const e = spec.encoding;
  const d = spec.units.decimals;
  const hl = new Set(spec.highlight || []);
  const ordered = [...rows].sort((a, b) => hl.has(a[e.category]) - hl.has(b[e.category]));
  const max = niceMax(Math.max(...rows.flatMap((r) => [num(r, e.from), num(r, e.to)])) * 1.08);
  const layout = { x: 0.14, y: 0.04, w: 0.72, h: 0.86 };
  slide.addChart(pres.charts.LINE, ordered.map((r) => ({
    name: r[e.category], labels: [e.fromLabel, e.toLabel], values: [num(r, e.from), num(r, e.to)],
  })), {
    ...chartBase(T),
    x: box.x, y: box.y, w: box.w, h: box.h,
    layout,
    chartColors: ordered.map((r) => hex(hl.has(r[e.category]) ? C.focus : C.context)),
    lineSize: T.stroke.linePt,
    lineDataSymbol: "circle",
    lineDataSymbolSize: 9,
    catAxisLabelFontSize: T.sizesPt.axis + 1,
    valAxisMinVal: 0,
    valAxisMaxVal: max,
  });
  const p = plot(box, layout, 0, max);
  const xL = p.band(0, 2);
  const xR = p.band(1, 2);
  const left = spread(rows.map((r) => ({ r, y: p.y(num(r, e.from)) })), 0.3);
  const right = spread(rows.map((r) => ({ r, y: p.y(num(r, e.to)) })), 0.3);
  const size = T.sizesPt.dataLabel;
  const style = (r) => ({ color: hex(hl.has(r[e.category]) ? C.focus : C.textMuted), bold: hl.has(r[e.category]) });
  left.forEach(({ r, y }) => {
    slide.addText([
      { text: `${r[e.category]}  `, options: style(r) },
      { text: fmt(num(r, e.from), d), options: { ...style(r), color: hex(C.text) } },
    ], { x: xL - 2.35, y: y - 0.14, w: 2.2, h: 0.28, align: "right", fontFace: T.fonts.body, fontSize: size, margin: 0 });
  });
  right.forEach(({ r, y }) => {
    const change = num(r, e.to) / num(r, e.from) - 1;
    slide.addText([
      { text: fmt(num(r, e.to), d), options: { ...style(r), color: hex(C.text) } },
      { text: `  ${r[e.category]}  `, options: style(r) },
      { text: `${fmt(change * 100, 0, { signed: true })}%`, options: style(r) },
    ], { x: xR + 0.15, y: y - 0.14, w: 2.4, h: 0.28, align: "left", fontFace: T.fonts.body, fontSize: size, margin: 0 });
  });
}

function dumbbell(ctx, box) {
  const { slide, spec, rows, T, pres } = ctx;
  const C = T.colors;
  const e = spec.encoding;
  const d = spec.units.decimals;
  const hl = new Set(spec.highlight || []);
  const labelW = 1.7;
  const ratioW = 1.5;
  const x0 = box.x + labelW + 0.25;
  const x1 = box.x + box.w - ratioW - 0.2;
  const max = niceMax(Math.max(...rows.map((r) => Math.max(num(r, e.from), num(r, e.to)))) * 1.04);
  const step = niceStep(max);
  const sx = (v) => x0 + (v / max) * (x1 - x0);
  const top = box.y + 0.45;
  const rowH = Math.min(0.85, (box.h - 0.85) / rows.length);
  const bottom = top + rowH * rows.length;
  for (let v = 0; v <= max + 1e-9; v += step) {
    slide.addShape(pres.shapes.LINE, { x: sx(v), y: top, w: 0, h: bottom - top, line: { color: hex(C.grid), width: T.stroke.gridPt } });
    const last = v + step > max + 1e-9;
    slide.addText(`${fmt(v, 0)}${last ? NBSP + spec.units.label : ""}`, {
      x: sx(v) - 0.5, y: bottom + 0.08, w: 1, h: 0.24, align: "center",
      fontFace: T.fonts.body, fontSize: T.sizesPt.axis - 1, color: hex(C.textMuted), margin: 0,
    });
  }
  const dot = 0.2;
  rows.forEach((r, i) => {
    const cy = top + rowH * (i + 0.5);
    const a = num(r, e.from);
    const b = num(r, e.to);
    const isHl = hl.has(r[e.category]);
    slide.addText(r[e.category], {
      x: box.x, y: cy - 0.15, w: labelW, h: 0.3, align: "right",
      fontFace: T.fonts.body, fontSize: T.sizesPt.dataLabel + 1, bold: isHl, color: hex(isHl ? C.focus : C.text), margin: 0,
    });
    slide.addShape(pres.shapes.LINE, {
      x: sx(Math.min(a, b)), y: cy, w: Math.abs(sx(a) - sx(b)), h: 0, line: { color: hex(isHl ? C.focusSoft : C.context), width: 4 },
    });
    slide.addShape(pres.shapes.OVAL, { x: sx(a) - dot / 2, y: cy - dot / 2, w: dot, h: dot, fill: { color: hex(C.contextStrong) }, line: { type: "none" } });
    slide.addShape(pres.shapes.OVAL, { x: sx(b) - dot / 2, y: cy - dot / 2, w: dot, h: dot, fill: { color: hex(C.focus) }, line: { type: "none" } });
    const lab = { fontFace: T.fonts.body, fontSize: T.sizesPt.axis, margin: 0, h: 0.24 };
    slide.addText(fmt(a, d), { ...lab, x: sx(a) + dot / 2 + 0.06, y: cy - 0.12, w: 0.6, color: hex(C.textMuted) });
    slide.addText(fmt(b, d), { ...lab, x: sx(b) - dot / 2 - 0.66, y: cy - 0.12, w: 0.6, align: "right", color: hex(C.text), bold: true });
    slide.addText(times(a / b), {
      x: box.x + box.w - ratioW, y: cy - 0.15, w: ratioW, h: 0.3, align: "right",
      fontFace: T.fonts.body, fontSize: T.sizesPt.dataLabel + 1, bold: isHl, color: hex(isHl ? C.focus : C.text), margin: 0,
    });
    if (i === 0) {
      const leg = { fontFace: T.fonts.body, fontSize: T.sizesPt.axis - 1, margin: 0, h: 0.22, w: 1.6, align: "center", y: cy - rowH / 2 - 0.2 };
      slide.addText(e.fromLabel, { ...leg, x: sx(a) - 0.8, color: hex(C.contextStrong) });
      slide.addText(e.toLabel, { ...leg, x: sx(b) - 0.8, color: hex(C.focus), bold: true });
    }
  });
}

function smallMultiples(ctx, box) {
  const { slide, spec, rows, T, pres } = ctx;
  const C = T.colors;
  const e = spec.encoding;
  const d = spec.units.decimals;
  const hl = new Set(spec.highlight || []);
  const groups = [...new Set(rows.map((r) => r[e.series]))];
  const cols = groups.length <= 4 ? 2 : 3;
  const nRows = Math.ceil(groups.length / cols);
  const gapX = 0.45;
  const gapY = 0.3;
  const pw = (box.w - gapX * (cols - 1)) / cols;
  const ph = (box.h - gapY * (nRows - 1)) / nRows;
  const max = niceMax(Math.max(...rows.map((r) => num(r, e.value))) * 1.15, 3);
  const layout = { x: 0.06, y: 0.06, w: 0.82, h: 0.72 };
  groups.forEach((g, k) => {
    const gx = box.x + (k % cols) * (pw + gapX);
    const gy = box.y + Math.floor(k / cols) * (ph + gapY);
    const isHl = hl.has(g);
    const pts = rows.filter((r) => r[e.series] === g);
    const values = pts.map((r) => num(r, e.value));
    slide.addText(g, {
      x: gx, y: gy, w: pw, h: 0.28, fontFace: T.fonts.body, fontSize: T.sizesPt.subtitle, bold: true,
      color: hex(isHl ? C.focus : C.text), margin: 0,
    });
    const cbox = { x: gx, y: gy + 0.32, w: pw, h: ph - 0.32 };
    slide.addChart(pres.charts.LINE, [{ name: g, labels: pts.map((r) => r[e.x]), values }], {
      ...chartBase(T),
      ...cbox,
      layout,
      chartColors: [hex(isHl ? C.focus : C.contextStrong)],
      lineSize: isHl ? T.stroke.linePt : T.stroke.lineContextPt,
      lineDataSymbol: "none",
      valAxisMinVal: 0,
      valAxisMaxVal: max,
      valAxisMajorUnit: niceStep(max, 3),
      valGridLine: { color: hex(C.grid), size: T.stroke.gridPt },
      catAxisLabelFontSize: T.sizesPt.axis - 2,
      catAxisLabelColor: hex(C.textMuted),
      catAxisLabelFrequency: values.length - 1,
      catAxisLineShow: true,
      catAxisLineColor: hex(C.axis),
    });
    const p = plot(cbox, layout, 0, max);
    const n = values.length;
    const lab = { fontFace: T.fonts.body, fontSize: T.sizesPt.axis, margin: 0, h: 0.24 };
    slide.addText(fmt(values[0], d), { ...lab, x: p.band(0, n) - 0.55, y: p.y(values[0]) - 0.12, w: 0.48, align: "right", color: hex(C.textMuted) });
    const lx = p.band(n - 1, n);
    const ly = p.y(values[n - 1]);
    const dot = 0.11;
    slide.addShape(pres.shapes.OVAL, { x: lx - dot / 2, y: ly - dot / 2, w: dot, h: dot, fill: { color: hex(isHl ? C.focus : C.contextStrong) }, line: { type: "none" } });
    slide.addText(fmt(values[n - 1], d), { ...lab, x: lx + 0.09, y: ly - 0.12, w: 0.6, bold: true, color: hex(isHl ? C.focus : C.text) });
  });
}

function bullet(ctx, box) {
  const { slide, spec, rows, T, pres } = ctx;
  const C = T.colors;
  const e = spec.encoding;
  const d = spec.units.decimals;
  const hl = new Set(spec.highlight || []);
  const labelW = 2.6;
  const valueW = 1.75;
  const x0 = box.x + labelW + 0.25;
  const x1 = box.x + box.w - valueW - 0.25;
  const rowH = Math.min(1.25, box.h / rows.length);
  const bandH = 0.42;
  rows.forEach((r, i) => {
    const cy = box.y + rowH * (i + 0.5);
    const [a, t, poor, ok, max] = ["actual", "target", "poor", "ok", "max"].map((k) => num(r, e[k]));
    const unit = r[e.unit] || spec.units.label;
    const sx = (v) => x0 + (v / max) * (x1 - x0);
    const miss = a < t;
    const isHl = hl.has(r[e.metric]);
    slide.addText([
      { text: r[e.metric], options: { bold: isHl, color: hex(C.text), breakLine: true } },
      { text: `цель ${fmt(t, d)}${unit}`, options: { fontSize: T.sizesPt.axis - 1, color: hex(C.textMuted) } },
    ], { x: box.x, y: cy - 0.32, w: labelW, h: 0.64, fontFace: T.fonts.body, fontSize: T.sizesPt.dataLabel, margin: 0, valign: "middle", align: "right" });
    [[0, poor, C.bandPoor], [poor, ok, C.bandOk], [ok, max, C.bandGood]].forEach(([from, to, color]) => {
      slide.addShape(pres.shapes.RECTANGLE, { x: sx(from), y: cy - bandH / 2, w: sx(to) - sx(from), h: bandH, fill: { color: hex(color) }, line: { type: "none" } });
    });
    const barH = bandH * 0.38;
    slide.addShape(pres.shapes.RECTANGLE, {
      x: sx(0), y: cy - barH / 2, w: sx(a) - sx(0), h: barH, fill: { color: hex(miss ? C.negative : C.text) }, line: { type: "none" },
    });
    slide.addShape(pres.shapes.LINE, { x: sx(t), y: cy - bandH * 0.42, w: 0, h: bandH * 0.84, line: { color: hex(C.text), width: 2.5 } });
    const tick = { y: cy + bandH / 2 + 0.04, h: 0.2, w: 0.8, fontFace: T.fonts.body, fontSize: T.sizesPt.axis - 2, color: hex(C.textMuted), margin: 0 };
    slide.addText(fmt(0, 0), { ...tick, x: sx(0) });
    slide.addText(`${fmt(max, 0)}${unit}`, { ...tick, x: sx(max) - 0.8, align: "right" });
    const diffUnit = unit === "%" ? `${NBSP}п.п.` : unit;
    slide.addText([
      { text: `${fmt(a, d)}${unit}`, options: { fontSize: 22, bold: true, color: hex(miss ? C.negative : C.text), breakLine: true } },
      { text: `${fmt(a - t, d, { signed: true })}${diffUnit} к цели`, options: { fontSize: T.sizesPt.axis - 1, color: hex(C.textMuted) } },
    ], { x: box.x + box.w - valueW, y: cy - 0.36, w: valueW, h: 0.72, fontFace: T.fonts.body, margin: 0, valign: "middle", align: "right" });
  });
}

function kpiSparkline(ctx, box) {
  const { slide, spec, rows, T, pres } = ctx;
  const C = T.colors;
  const e = spec.encoding;
  const hl = new Set(spec.highlight || []);
  const tiles = [...new Set(rows.map((r) => r[e.metric]))].map((g) => {
    const pts = rows.filter((r) => r[e.metric] === g);
    return { g, pts, values: pts.map((r) => num(r, e.value)), unit: pts[0][e.unit] || spec.units.label };
  });
  // Derived metrics are computed from raw series, never typed in as rounded values.
  for (const dm of e.derived || []) {
    const a = tiles.find((t) => t.g === dm.numerator);
    const b = tiles.find((t) => t.g === dm.denominator);
    tiles.push({ g: dm.name, pts: a.pts, values: a.values.map((v, i) => v / b.values[i]), unit: dm.unit, decimals: dm.decimals });
  }
  const gap = 0.45;
  const tw = (box.w - gap * (tiles.length - 1)) / tiles.length;
  tiles.forEach(({ g, pts, values, unit, decimals: fixedDecimals }, k) => {
    const decimals = fixedDecimals ?? (values.every(Number.isInteger) ? 0 : spec.units.decimals);
    const isHl = hl.has(g);
    const x = box.x + k * (tw + gap);
    const y = box.y + 0.1;
    slide.addShape(pres.shapes.RECTANGLE, { x, y, w: tw, h: isHl ? 0.06 : 0.02, fill: { color: hex(isHl ? C.focus : C.axis) }, line: { type: "none" } });
    slide.addText(g, { x, y: y + 0.22, w: tw, h: 0.3, fontFace: T.fonts.body, fontSize: T.sizesPt.subtitle, color: hex(C.textMuted), margin: 0 });
    const last = values[values.length - 1];
    slide.addText([
      { text: fmt(last, decimals), options: { fontSize: T.sizesPt.metric, bold: true, color: hex(isHl ? C.focus : C.text) } },
      { text: `${NBSP}${unit}`, options: { fontSize: T.sizesPt.subtitle + 2, color: hex(C.textMuted) } },
    ], { x, y: y + 0.55, w: tw, h: 0.75, fontFace: T.fonts.body, margin: 0, valign: "bottom" });
    const change = last / values[0] - 1;
    slide.addText(`${pts[0][e.x]} → ${pts[pts.length - 1][e.x]}: ${fmt(change * 100, 1, { signed: true })}%`, {
      x, y: y + 1.38, w: tw, h: 0.28, fontFace: T.fonts.body, fontSize: T.sizesPt.dataLabel, color: hex(C.text), margin: 0,
    });
    // Honest sparkline scale: the visible span is at least 30% of the mean,
    // so a few percent of noise does not read as a trend.
    const mean = values.reduce((s, v) => s + v, 0) / values.length;
    const mid = (Math.min(...values) + Math.max(...values)) / 2;
    const span = Math.max(Math.max(...values) - Math.min(...values), 0.3 * Math.abs(mean));
    const lo = mid - span / 2;
    const hi = mid + span / 2;
    const pad = span * 0.15;
    const sbox = { x, y: y + 1.85, w: tw, h: Math.min(1.5, box.h - 2.25) };
    const layout = { x: 0.02, y: 0.1, w: 0.9, h: 0.8 };
    slide.addChart(pres.charts.LINE, [{ name: g, labels: pts.map((r) => r[e.x]), values }], {
      ...chartBase(T),
      ...sbox,
      layout,
      catAxisHidden: true,
      chartColors: [hex(isHl ? C.focus : C.contextStrong)],
      lineSize: T.stroke.linePt,
      lineDataSymbol: "none",
      valAxisMinVal: lo - pad,
      valAxisMaxVal: hi + pad,
    });
    const p = plot(sbox, layout, lo - pad, hi + pad);
    const n = values.length;
    const dot = 0.12;
    slide.addShape(pres.shapes.OVAL, {
      x: p.band(n - 1, n) - dot / 2, y: p.y(last) - dot / 2, w: dot, h: dot, fill: { color: hex(isHl ? C.focus : C.contextStrong) }, line: { type: "none" },
    });
    const per = { y: sbox.y + sbox.h + 0.02, h: 0.22, w: 1, fontFace: T.fonts.body, fontSize: T.sizesPt.axis - 2, color: hex(C.textMuted), margin: 0 };
    slide.addText(pts[0][e.x], { ...per, x: p.band(0, n) - 0.5, align: "center" });
    slide.addText(pts[n - 1][e.x], { ...per, x: p.band(n - 1, n) - 0.5, align: "center" });
  });
}

const RENDERERS = {
  "ranked-bar": rankedBar,
  waterfall,
  variance,
  slope,
  dumbbell,
  "small-multiples": smallMultiples,
  bullet,
  "kpi-sparkline": kpiSparkline,
};

// ---------- theme ----------

const firstFamily = (stack) => String(stack).split(",")[0].trim().replace(/^["']|["']$/g, "");
const camel = (key) => key.replace(/-([a-z])/g, (_, c) => c.toUpperCase());

// Visual DNA tokens.json (presentation-visual-dna-tokens/1.2 with a dataviz
// section) -> the flat theme the renderers use.
export function loadTheme(tokensPath) {
  const tokens = JSON.parse(fs.readFileSync(tokensPath, "utf8"));
  const dv = tokens.dataviz;
  if (!dv) throw new Error(`${tokensPath}: no dataviz section — add it with presentation-style-kit first`);
  const base = tokens.colors;
  const c = dv.colors;
  const colors = {
    background: base.background,
    text: base.text,
    textMuted: base["text-muted"],
    focus: c.focus,
    focusSoft: c["focus-soft"],
    context: c.context,
    contextStrong: c["context-strong"],
    negative: c.negative,
    negativeSoft: c["negative-soft"],
    grid: c.grid,
    axis: c.axis,
    bandPoor: c["band-poor"] || c.context,
    bandOk: c["band-ok"] || c.grid,
    bandGood: c["band-good"] || base.surface,
  };
  for (const [role, value] of Object.entries(colors)) {
    if (!/^#[0-9a-f]{6}$/i.test(String(value))) throw new Error(`${tokensPath}: color '${role}' must be #RRGGBB, got ${value}`);
  }
  const nf = dv.numberFormat || {};
  NF.thousands = nf.thousandsSeparator ?? NBSP;
  NF.decimal = nf.decimalSeparator ?? ",";
  NF.minus = nf.minusSign ?? MINUS;
  return {
    colors,
    fonts: {
      display: firstFamily(tokens.typography.display),
      body: firstFamily(tokens.typography.body),
      technical: firstFamily(tokens.typography.technical),
    },
    sizesPt: Object.fromEntries(Object.entries(dv.sizesPt).map(([k, v]) => [camel(k), Number(v)])),
    stroke: Object.fromEntries(Object.entries(dv.strokePt).map(([k, v]) => [`${camel(k)}Pt`, Number(v)])),
    slide: { widthIn: 13.333, heightIn: 7.5, marginXIn: 0.6, marginTopIn: 0.45 },
  };
}

// ---------- deck ----------

export async function buildDeck({ specsDir, root, tokensPath, out, kicker = "", title = "Charts" }) {
  const T = loadTheme(tokensPath);
  const specFiles = fs.readdirSync(specsDir).filter((f) => f.endsWith(".chart.json")).sort();
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";
  pres.title = title;
  const report = [];
  specFiles.forEach((file, index) => {
    const spec = JSON.parse(fs.readFileSync(path.join(specsDir, file), "utf8"));
    if (spec.contract !== "presentation-chart-spec/1.0") throw new Error(`${file}: contract must be presentation-chart-spec/1.0`);
    const dataPath = path.join(root, spec.data.location);
    const digest = sha256(dataPath);
    if (digest !== spec.data.sha256) {
      throw new Error(`${file}: data sha256 mismatch — run validate_chart_spec.py first`);
    }
    const render = RENDERERS[spec.type];
    if (!render) throw new Error(`${file}: no renderer for type ${spec.type}`);
    const slide = pres.addSlide();
    const ctx = { pres, slide, spec, rows: readCsv(dataPath), T, kicker };
    const box = chrome(ctx, index, specFiles.length);
    render(ctx, box);
    report.push({ slide: index + 1, chartId: spec.chartId, type: spec.type, data: spec.data.location });
  });
  await pres.writeFile({ fileName: out });
  return report;
}
