/**
 * SVG Chart String Generators for PDF Export
 *
 * Generates SVG markup as plain strings. These get converted to PNG via
 * resvg-js in the export route, then embedded as <Image> in react-pdf.
 * No react-pdf SVG primitives, no browser, no flakiness.
 */

// ─── Colour palette (Tableau 10) ────────────────────────────────
const PALETTE = [
  '#4E79A7', '#F28E2B', '#E15759', '#76B7B2', '#59A14F',
  '#EDC948', '#B07AA1', '#FF9DA7', '#9C755F', '#BAB0AC',
];
const BRAND = '#1a365d';
const TEXT_COLOR = '#4a5568';
const GRID_COLOR = '#e2e8f0';
const BG_COLOR = '#f7fafc';

// ─── Shared constants ───────────────────────────────────────────
const W = 480;
const H = 220;
const PAD = { top: 10, right: 20, bottom: 40, left: 60 };
const INNER_W = W - PAD.left - PAD.right;
const INNER_H = H - PAD.top - PAD.bottom;

// ─── Helpers ────────────────────────────────────────────────────
function esc(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function truncLabel(s: string, max = 12): string {
  if (!s) return '';
  return s.length > max ? s.slice(0, max - 1) + '\u2026' : s;
}

function fmtNum(v: number): string {
  if (Math.abs(v) >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (Math.abs(v) >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (Math.abs(v) >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
  if (Math.abs(v) < 1 && v !== 0) return v.toFixed(2);
  return v.toLocaleString();
}

function niceScale(min: number, max: number, ticks = 5) {
  if (min === max) { min -= 1; max += 1; }
  const range = max - min;
  const rough = range / ticks;
  const mag = Math.pow(10, Math.floor(Math.log10(rough)));
  const nice = rough / mag >= 5 ? 10 * mag : rough / mag >= 2 ? 5 * mag : rough / mag >= 1 ? 2 * mag : mag;
  return { min: Math.floor(min / nice) * nice, max: Math.ceil(max / nice) * nice, step: nice };
}

// ─── Bar / Waterfall Chart ──────────────────────────────────────
function svgBarChart(data: any[]): string {
  const items = data.slice(0, 15);
  const values = items.map((d: any) => d.value ?? 0);
  const maxVal = Math.max(...values, 0);
  const minVal = Math.min(...values, 0);
  const scale = niceScale(minVal, maxVal);
  const range = scale.max - scale.min || 1;

  const barH = Math.min(20, INNER_H / items.length - 2);
  const chartH = items.length * (barH + 4) + PAD.top + PAD.bottom;
  const zeroX = PAD.left + ((0 - scale.min) / range) * INNER_W;

  let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${chartH}" viewBox="0 0 ${W} ${chartH}">`;
  svg += `<rect x="0" y="0" width="${W}" height="${chartH}" fill="${BG_COLOR}" rx="3"/>`;

  // Grid lines + labels
  for (let i = 0; i < 6; i++) {
    const val = scale.min + scale.step * i;
    if (val > scale.max) break;
    const x = PAD.left + ((val - scale.min) / range) * INNER_W;
    svg += `<line x1="${x}" y1="${PAD.top}" x2="${x}" y2="${chartH - PAD.bottom}" stroke="${GRID_COLOR}" stroke-width="0.5"/>`;
    svg += `<text x="${x}" y="${chartH - PAD.bottom + 12}" fill="${TEXT_COLOR}" text-anchor="middle" font-size="7" font-family="Helvetica, Arial, sans-serif">${esc(fmtNum(val))}</text>`;
  }

  // Zero line
  svg += `<line x1="${zeroX}" y1="${PAD.top}" x2="${zeroX}" y2="${chartH - PAD.bottom}" stroke="${BRAND}" stroke-width="0.75"/>`;

  // Bars
  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    const val = item.value ?? 0;
    const barW = Math.abs(val / range) * INNER_W;
    const barX = val >= 0 ? zeroX : zeroX - barW;
    const barY = PAD.top + i * (barH + 4);
    const color = item.isSubtotal ? BRAND : val >= 0 ? PALETTE[0] : PALETTE[2];

    svg += `<rect x="${barX}" y="${barY}" width="${Math.max(barW, 1)}" height="${barH}" fill="${color}" rx="2"/>`;
    svg += `<text x="${PAD.left - 4}" y="${barY + barH / 2 + 3}" fill="${TEXT_COLOR}" text-anchor="end" font-size="7" font-family="Helvetica, Arial, sans-serif">${esc(truncLabel(item.name || '', 18))}</text>`;
    const labelX = val >= 0 ? barX + barW + 3 : barX - 3;
    const anchor = val >= 0 ? 'start' : 'end';
    svg += `<text x="${labelX}" y="${barY + barH / 2 + 3}" fill="${TEXT_COLOR}" text-anchor="${anchor}" font-size="6.5" font-family="Helvetica, Arial, sans-serif">${esc(fmtNum(val))}</text>`;
  }

  svg += '</svg>';
  return svg;
}

// ─── Line / Area Chart ──────────────────────────────────────────
function svgLineChart(data: any): string {
  const labels: string[] = data.labels || [];
  const datasets: any[] = data.datasets || [];
  if (!labels.length || !datasets.length) return '';

  const allValues = datasets.flatMap((ds: any) => (ds.data || []).filter((v: any) => typeof v === 'number'));
  if (!allValues.length) return '';

  const scale = niceScale(Math.min(...allValues), Math.max(...allValues));
  const range = scale.max - scale.min || 1;
  const xStep = labels.length > 1 ? INNER_W / (labels.length - 1) : INNER_W;

  const toX = (i: number) => PAD.left + (labels.length > 1 ? i * xStep : INNER_W / 2);
  const toY = (v: number) => PAD.top + INNER_H - ((v - scale.min) / range) * INNER_H;

  const totalH = H + 20;
  let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${totalH}" viewBox="0 0 ${W} ${totalH}">`;
  svg += `<rect x="0" y="0" width="${W}" height="${totalH}" fill="${BG_COLOR}" rx="3"/>`;

  // Y grid
  for (let v = scale.min; v <= scale.max; v += scale.step) {
    const y = toY(v);
    svg += `<line x1="${PAD.left}" y1="${y}" x2="${W - PAD.right}" y2="${y}" stroke="${GRID_COLOR}" stroke-width="0.5"/>`;
    svg += `<text x="${PAD.left - 4}" y="${y + 3}" fill="${TEXT_COLOR}" text-anchor="end" font-size="7" font-family="Helvetica, Arial, sans-serif">${esc(fmtNum(v))}</text>`;
  }

  // X labels
  for (let i = 0; i < labels.length; i++) {
    if (labels.length > 10 && i % Math.ceil(labels.length / 10) !== 0 && i !== labels.length - 1) continue;
    svg += `<text x="${toX(i)}" y="${H - PAD.bottom + 16}" fill="${TEXT_COLOR}" text-anchor="middle" font-size="6.5" font-family="Helvetica, Arial, sans-serif">${esc(truncLabel(String(labels[i]), 10))}</text>`;
  }

  // Axes
  svg += `<line x1="${PAD.left}" y1="${PAD.top}" x2="${PAD.left}" y2="${H - PAD.bottom}" stroke="${BRAND}" stroke-width="0.75"/>`;
  svg += `<line x1="${PAD.left}" y1="${H - PAD.bottom}" x2="${W - PAD.right}" y2="${H - PAD.bottom}" stroke="${BRAND}" stroke-width="0.75"/>`;

  // Lines + points
  for (let di = 0; di < datasets.length; di++) {
    const ds = datasets[di];
    const pts = (ds.data || []) as number[];
    const color = PALETTE[di % PALETTE.length];
    const d = pts.map((v, i) => `${i === 0 ? 'M' : 'L'}${toX(i).toFixed(1)},${toY(v).toFixed(1)}`).join(' ');
    svg += `<path d="${d}" stroke="${color}" stroke-width="1.5" fill="none"/>`;
    for (let i = 0; i < pts.length; i++) {
      svg += `<circle cx="${toX(i)}" cy="${toY(pts[i])}" r="2" fill="${color}"/>`;
    }
  }

  // Legend
  if (datasets.length > 1) {
    for (let di = 0; di < datasets.length; di++) {
      const lx = PAD.left + di * 100;
      const ly = H + 8;
      svg += `<rect x="${lx}" y="${ly - 4}" width="8" height="8" fill="${PALETTE[di % PALETTE.length]}" rx="1"/>`;
      svg += `<text x="${lx + 12}" y="${ly + 3}" fill="${TEXT_COLOR}" font-size="7" font-family="Helvetica, Arial, sans-serif">${esc(truncLabel(datasets[di].label || `Series ${di + 1}`, 16))}</text>`;
    }
  }

  svg += '</svg>';
  return svg;
}

// ─── Pie / Donut Chart ──────────────────────────────────────────
function svgPieChart(data: any): string {
  const segs: { name: string; value: number }[] = data.segments || data.slices || [];
  if (!segs.length) return '';

  const total = segs.reduce((sum: number, s: any) => sum + (Math.abs(s.value) || 0), 0);
  if (total === 0) return '';

  const cx = W / 2;
  const cy = 100;
  const r = 75;
  const legendY = cy + r + 20;
  const chartH = legendY + Math.ceil(segs.length / 3) * 14 + 10;

  let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${chartH}" viewBox="0 0 ${W} ${chartH}">`;
  svg += `<rect x="0" y="0" width="${W}" height="${chartH}" fill="${BG_COLOR}" rx="3"/>`;

  let angle = -Math.PI / 2;

  for (let i = 0; i < segs.length; i++) {
    const seg = segs[i];
    const pct = Math.abs(seg.value) / total;
    const sweep = pct * 2 * Math.PI;
    const startAngle = angle;
    angle += sweep;
    const endAngle = angle;

    const x1 = cx + r * Math.cos(startAngle);
    const y1 = cy + r * Math.sin(startAngle);
    const x2 = cx + r * Math.cos(endAngle);
    const y2 = cy + r * Math.sin(endAngle);
    const largeArc = sweep > Math.PI ? 1 : 0;
    const color = PALETTE[i % PALETTE.length];

    svg += `<path d="M${cx},${cy} L${x1.toFixed(2)},${y1.toFixed(2)} A${r},${r} 0 ${largeArc},1 ${x2.toFixed(2)},${y2.toFixed(2)} Z" fill="${color}" stroke="#ffffff" stroke-width="1"/>`;

    if (pct > 0.05) {
      const midAngle = startAngle + sweep / 2;
      const lx = cx + r * 0.6 * Math.cos(midAngle);
      const ly = cy + r * 0.6 * Math.sin(midAngle);
      svg += `<text x="${lx.toFixed(1)}" y="${(ly + 3).toFixed(1)}" fill="#ffffff" text-anchor="middle" font-size="7" font-weight="bold" font-family="Helvetica, Arial, sans-serif">${(pct * 100).toFixed(0)}%</text>`;
    }
  }

  // Legend
  for (let i = 0; i < segs.length; i++) {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const lx = 20 + col * 160;
    const ly = legendY + row * 14;
    svg += `<rect x="${lx}" y="${ly - 4}" width="8" height="8" fill="${PALETTE[i % PALETTE.length]}" rx="1"/>`;
    svg += `<text x="${lx + 12}" y="${ly + 3}" fill="${TEXT_COLOR}" font-size="7" font-family="Helvetica, Arial, sans-serif">${esc(truncLabel(segs[i].name || '', 14))}: ${esc(fmtNum(segs[i].value))}</text>`;
  }

  svg += '</svg>';
  return svg;
}

// ─── Heatmap ────────────────────────────────────────────────────
function svgHeatmap(data: any): string {
  const dims = (data.dimensions || []).slice(0, 8) as any[];
  const companies = (data.companies || []).slice(0, 10) as any[];
  const scores = (data.scores || []) as number[][];
  if (!dims.length || !companies.length) return '';

  const labelW = 100;
  const cellW = Math.min(50, (W - labelW - 20) / dims.length);
  const cellH = 20;
  const headerH = 30;
  const chartH = headerH + companies.length * cellH + PAD.top + 10;

  const allScores = scores.flat().filter((v: any) => typeof v === 'number');
  const minScore = allScores.length ? Math.min(...allScores) : 0;
  const maxScore = allScores.length ? Math.max(...allScores) : 10;
  const scoreRange = maxScore - minScore || 1;

  function scoreColor(v: number): string {
    const t = (v - minScore) / scoreRange;
    if (t < 0.5) {
      const red = Math.round(225 + (237 - 225) * (t * 2));
      const green = Math.round(87 + (201 - 87) * (t * 2));
      const blue = Math.round(89 + (72 - 89) * (t * 2));
      return `rgb(${red},${green},${blue})`;
    }
    const red = Math.round(237 + (89 - 237) * ((t - 0.5) * 2));
    const green = Math.round(201 + (161 - 201) * ((t - 0.5) * 2));
    const blue = Math.round(72 + (79 - 72) * ((t - 0.5) * 2));
    return `rgb(${red},${green},${blue})`;
  }

  let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${chartH}" viewBox="0 0 ${W} ${chartH}">`;
  svg += `<rect x="0" y="0" width="${W}" height="${chartH}" fill="${BG_COLOR}" rx="3"/>`;

  // Column headers
  for (let ci = 0; ci < dims.length; ci++) {
    const d = dims[ci];
    svg += `<text x="${labelW + ci * cellW + cellW / 2}" y="${PAD.top + 12}" fill="${BRAND}" text-anchor="middle" font-size="7" font-weight="bold" font-family="Helvetica, Arial, sans-serif">${esc(truncLabel(d.name || d.label || String(d), 8))}</text>`;
  }

  // Rows
  for (let ri = 0; ri < companies.length; ri++) {
    const co = companies[ri];
    const y = PAD.top + headerH + ri * cellH;
    svg += `<text x="4" y="${y + cellH / 2 + 3}" fill="${TEXT_COLOR}" font-size="7" font-family="Helvetica, Arial, sans-serif">${esc(truncLabel(co.name || co.label || String(co), 16))}</text>`;

    for (let ci = 0; ci < dims.length; ci++) {
      const val = scores[ri]?.[ci];
      const hasVal = val != null && typeof val === 'number';
      svg += `<rect x="${labelW + ci * cellW + 1}" y="${y + 1}" width="${cellW - 2}" height="${cellH - 2}" fill="${hasVal ? scoreColor(val) : '#e2e8f0'}" rx="2"/>`;
      if (hasVal) {
        svg += `<text x="${labelW + ci * cellW + cellW / 2}" y="${y + cellH / 2 + 3}" fill="#ffffff" text-anchor="middle" font-size="7" font-weight="bold" font-family="Helvetica, Arial, sans-serif">${val}</text>`;
      }
    }
  }

  svg += '</svg>';
  return svg;
}

// ─── Sankey (simplified flow) ───────────────────────────────────
function svgSankeyChart(data: any): string {
  const nodes: any[] = data.nodes || [];
  const links: any[] = data.links || [];
  if (!nodes.length || !links.length) return '';

  const nodeMap = new Map<string, { id: string; name: string }>();
  nodes.forEach((n: any, i: number) => {
    const id = String(n.id ?? n.name ?? i);
    nodeMap.set(id, { id, name: n.name || n.label || id });
  });

  const sourceIds = new Set(links.map((l: any) => String(l.source)));
  const targetIds = new Set(links.map((l: any) => String(l.target)));
  const pureTargets = [...targetIds].filter(id => !sourceIds.has(id));
  const pureSources = [...sourceIds].filter(id => !targetIds.has(id));
  const middleIds = [...sourceIds].filter(id => targetIds.has(id));

  const columns: string[][] = [];
  if (pureSources.length) columns.push(pureSources);
  if (middleIds.length) columns.push(middleIds);
  if (pureTargets.length) columns.push(pureTargets);
  if (!columns.length) columns.push([...nodeMap.keys()]);

  const colW = INNER_W / columns.length;
  const maxNodesInCol = Math.max(...columns.map(c => c.length));
  const chartH = Math.max(H, 30 * maxNodesInCol + PAD.top + PAD.bottom);
  const rectW = 80;

  const nodePositions = new Map<string, { x: number; y: number; h: number }>();
  columns.forEach((col, ci) => {
    const nodeH = Math.min(24, (chartH - PAD.top - PAD.bottom) / col.length - 4);
    col.forEach((id, ni) => {
      nodePositions.set(id, {
        x: PAD.left + ci * colW,
        y: PAD.top + ni * (nodeH + 4),
        h: nodeH,
      });
    });
  });

  const totalLinkValue = links.reduce((sum: number, l: any) => sum + (l.value || 0), 0) || 1;

  let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${chartH}" viewBox="0 0 ${W} ${chartH}">`;
  svg += `<rect x="0" y="0" width="${W}" height="${chartH}" fill="${BG_COLOR}" rx="3"/>`;

  // Links
  const topLinks = links.slice(0, 20);
  for (let i = 0; i < topLinks.length; i++) {
    const link = topLinks[i];
    const src = nodePositions.get(String(link.source));
    const tgt = nodePositions.get(String(link.target));
    if (!src || !tgt) continue;

    const x1 = src.x + rectW;
    const y1 = src.y + src.h / 2;
    const x2 = tgt.x;
    const y2 = tgt.y + tgt.h / 2;
    const midX = (x1 + x2) / 2;
    const thickness = Math.max(1, ((link.value || 0) / totalLinkValue) * 20);
    const op = (0.3 + ((link.value || 0) / totalLinkValue) * 0.5).toFixed(2);

    svg += `<path d="M${x1},${y1} C${midX},${y1} ${midX},${y2} ${x2},${y2}" stroke="${PALETTE[i % PALETTE.length]}" stroke-width="${thickness}" fill="none" opacity="${op}"/>`;
  }

  // Nodes
  for (let ci = 0; ci < columns.length; ci++) {
    for (let ni = 0; ni < columns[ci].length; ni++) {
      const id = columns[ci][ni];
      const pos = nodePositions.get(id);
      const node = nodeMap.get(id);
      if (!pos || !node) continue;
      svg += `<rect x="${pos.x}" y="${pos.y}" width="${rectW}" height="${pos.h}" fill="${PALETTE[ci % PALETTE.length]}" rx="3"/>`;
      svg += `<text x="${pos.x + rectW / 2}" y="${pos.y + pos.h / 2 + 3}" fill="#ffffff" text-anchor="middle" font-size="6.5" font-family="Helvetica, Arial, sans-serif">${esc(truncLabel(node.name, 12))}</text>`;
    }
  }

  svg += '</svg>';
  return svg;
}

// ─── Scatter Chart ──────────────────────────────────────────────
function svgScatterChart(data: any): string {
  const datasets: any[] = data.datasets || [];
  if (!datasets.length) return '';

  const allPts = datasets.flatMap((ds: any) => ds.data || []);
  const xs = allPts.map((p: any) => typeof p.x === 'number' ? p.x : 0);
  const ys = allPts.map((p: any) => typeof p.y === 'number' ? p.y : 0);
  if (!xs.length) return '';

  const xScale = niceScale(Math.min(...xs), Math.max(...xs));
  const yScale = niceScale(Math.min(...ys), Math.max(...ys));
  const xRange = xScale.max - xScale.min || 1;
  const yRange = yScale.max - yScale.min || 1;

  const toX = (v: number) => PAD.left + ((v - xScale.min) / xRange) * INNER_W;
  const toY = (v: number) => PAD.top + INNER_H - ((v - yScale.min) / yRange) * INNER_H;

  const totalH = H + 10;
  let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${totalH}" viewBox="0 0 ${W} ${totalH}">`;
  svg += `<rect x="0" y="0" width="${W}" height="${totalH}" fill="${BG_COLOR}" rx="3"/>`;

  // Y grid
  for (let i = 0; i < 6; i++) {
    const v = yScale.min + yScale.step * i;
    if (v > yScale.max) break;
    const y = toY(v);
    svg += `<line x1="${PAD.left}" y1="${y}" x2="${W - PAD.right}" y2="${y}" stroke="${GRID_COLOR}" stroke-width="0.5"/>`;
    svg += `<text x="${PAD.left - 4}" y="${y + 3}" fill="${TEXT_COLOR}" text-anchor="end" font-size="7" font-family="Helvetica, Arial, sans-serif">${esc(fmtNum(v))}</text>`;
  }

  // Axes
  svg += `<line x1="${PAD.left}" y1="${PAD.top}" x2="${PAD.left}" y2="${H - PAD.bottom}" stroke="${BRAND}" stroke-width="0.75"/>`;
  svg += `<line x1="${PAD.left}" y1="${H - PAD.bottom}" x2="${W - PAD.right}" y2="${H - PAD.bottom}" stroke="${BRAND}" stroke-width="0.75"/>`;

  // Points
  for (let di = 0; di < datasets.length; di++) {
    const color = PALETTE[di % PALETTE.length];
    const pts = datasets[di].data || [];
    for (let pi = 0; pi < pts.length; pi++) {
      const p = pts[pi];
      svg += `<circle cx="${toX(p.x)}" cy="${toY(p.y)}" r="3.5" fill="${color}" opacity="0.7"/>`;
    }
  }

  // Legend
  if (datasets.length > 1) {
    for (let di = 0; di < datasets.length; di++) {
      svg += `<circle cx="${PAD.left + di * 100 + 5}" cy="${H + 4}" r="3" fill="${PALETTE[di % PALETTE.length]}"/>`;
      svg += `<text x="${PAD.left + di * 100 + 12}" y="${H + 7}" fill="${TEXT_COLOR}" font-size="7" font-family="Helvetica, Arial, sans-serif">${esc(truncLabel(datasets[di].label || '', 14))}</text>`;
    }
  }

  svg += '</svg>';
  return svg;
}

// ─── Router: pick the right renderer for the data shape ─────────
/**
 * Returns an SVG string for the given chart data, or null if unrecognized.
 * The caller should convert this to PNG via resvg-js before embedding in react-pdf.
 */
export function renderSvgChartString(data: any, _title: string): string | null {
  if (!data) return null;

  try {
    // Waterfall / bar: [{name, value}]
    if (Array.isArray(data) && data.length > 0 && data[0]?.name !== undefined) {
      return svgBarChart(data) || null;
    }

    // Sankey: {nodes, links}
    if (data.nodes && data.links) {
      return svgSankeyChart(data) || null;
    }

    // Heatmap: {dimensions, companies, scores}
    if (data.dimensions && data.scores) {
      return svgHeatmap(data) || null;
    }

    // Pie / donut: {segments} or {slices}
    if (data.segments || data.slices) {
      return svgPieChart(data) || null;
    }

    // Scatter: {datasets: [{data: [{x,y}]}]}
    if (data.datasets?.[0]?.data?.[0]?.x !== undefined) {
      return svgScatterChart(data) || null;
    }

    // Chart.js line/bar: {labels, datasets}
    if (data.labels && data.datasets) {
      return svgLineChart(data) || null;
    }
  } catch (err) {
    console.error('[PDF_SVG_CHARTS] Render failed:', _title, err);
    return null;
  }

  return null;
}
