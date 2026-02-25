import { NextRequest, NextResponse } from 'next/server';
import React from 'react';
import {
  Document,
  Page,
  Text,
  View,
  StyleSheet,
  renderToBuffer,
  Link,
} from '@react-pdf/renderer';
import { normalizeSections } from '@/lib/normalize-memo-sections';

// ─── Colour tokens ──────────────────────────────────────────────
const C = {
  brand:     '#1a365d',  // Deep navy
  accent:    '#4E79A7',  // Tableau blue
  text:      '#1a202c',
  textLight: '#4a5568',
  muted:     '#a0aec0',
  border:    '#e2e8f0',
  bg:        '#f7fafc',
  bgDark:    '#edf2f7',
  bull:      '#c6f6d5',
  bear:      '#fed7d7',
  base:      '#bee3f8',
  white:     '#ffffff',
};

// ─── Styles ─────────────────────────────────────────────────────
const s = StyleSheet.create({
  page: {
    paddingTop: 56,
    paddingBottom: 56,
    paddingHorizontal: 56,
    fontFamily: 'Helvetica',
    fontSize: 9.5,
    color: C.text,
    lineHeight: 1.45,
  },

  // Cover
  coverPage: {
    paddingTop: 180,
    paddingHorizontal: 56,
    paddingBottom: 56,
    fontFamily: 'Helvetica',
    color: C.text,
  },
  coverTitle: {
    fontSize: 28,
    fontFamily: 'Helvetica-Bold',
    color: C.brand,
    marginBottom: 12,
    letterSpacing: -0.5,
  },
  coverSubtitle: {
    fontSize: 13,
    color: C.textLight,
    marginBottom: 40,
  },
  coverMeta: {
    fontSize: 9,
    color: C.muted,
    marginTop: 6,
  },
  coverRule: {
    height: 3,
    backgroundColor: C.accent,
    width: 60,
    marginBottom: 24,
  },

  // Headings
  h1: {
    fontSize: 18,
    fontFamily: 'Helvetica-Bold',
    color: C.brand,
    marginTop: 24,
    marginBottom: 10,
    letterSpacing: -0.3,
  },
  h2: {
    fontSize: 13,
    fontFamily: 'Helvetica-Bold',
    color: C.brand,
    marginTop: 18,
    marginBottom: 8,
    paddingBottom: 4,
    borderBottomWidth: 0.75,
    borderBottomColor: C.border,
  },
  h3: {
    fontSize: 11,
    fontFamily: 'Helvetica-Bold',
    color: C.textLight,
    marginTop: 12,
    marginBottom: 6,
  },

  // Body
  p: {
    fontSize: 9.5,
    lineHeight: 1.55,
    marginBottom: 8,
    color: C.text,
  },
  listItem: {
    fontSize: 9.5,
    lineHeight: 1.5,
    marginBottom: 3,
    paddingLeft: 14,
    color: C.text,
  },
  quote: {
    fontSize: 9.5,
    fontStyle: 'italic',
    color: C.textLight,
    borderLeftWidth: 2.5,
    borderLeftColor: C.accent,
    paddingLeft: 12,
    marginVertical: 8,
    paddingVertical: 4,
  },
  code: {
    fontSize: 8,
    fontFamily: 'Courier',
    backgroundColor: C.bg,
    padding: 8,
    marginVertical: 6,
    borderWidth: 0.5,
    borderColor: C.border,
    borderRadius: 2,
    color: C.textLight,
  },

  // Tables
  tableWrapper: {
    marginVertical: 8,
    borderWidth: 0.5,
    borderColor: C.border,
    borderRadius: 3,
    overflow: 'hidden',
  },
  tableCaption: {
    fontSize: 8,
    fontStyle: 'italic',
    color: C.textLight,
    marginBottom: 4,
  },
  tableHeader: {
    flexDirection: 'row' as const,
    backgroundColor: C.brand,
    paddingVertical: 5,
    paddingHorizontal: 2,
  },
  tableHeaderCell: {
    fontSize: 8,
    fontFamily: 'Helvetica-Bold',
    color: C.white,
    padding: 4,
    flex: 1,
  },
  tableRow: {
    flexDirection: 'row' as const,
    borderBottomWidth: 0.5,
    borderBottomColor: C.border,
    paddingVertical: 3,
    paddingHorizontal: 2,
  },
  tableRowAlt: {
    flexDirection: 'row' as const,
    borderBottomWidth: 0.5,
    borderBottomColor: C.border,
    backgroundColor: C.bg,
    paddingVertical: 3,
    paddingHorizontal: 2,
  },
  tableCell: {
    fontSize: 8,
    padding: 4,
    flex: 1,
    color: C.text,
  },
  tableCellRight: {
    fontSize: 8,
    padding: 4,
    flex: 1,
    color: C.text,
    textAlign: 'right' as const,
  },

  // Charts (rendered as data summary)
  chartBox: {
    marginVertical: 8,
    padding: 10,
    backgroundColor: C.bg,
    borderWidth: 0.5,
    borderColor: C.border,
    borderRadius: 3,
  },
  chartTitle: {
    fontSize: 9,
    fontFamily: 'Helvetica-Bold',
    color: C.accent,
    marginBottom: 6,
  },
  chartNote: {
    fontSize: 7.5,
    color: C.muted,
    fontStyle: 'italic',
    marginTop: 4,
  },

  // Footer
  footer: {
    position: 'absolute' as const,
    bottom: 28,
    left: 56,
    right: 56,
    flexDirection: 'row' as const,
    justifyContent: 'space-between' as const,
    borderTopWidth: 0.5,
    borderTopColor: C.border,
    paddingTop: 6,
    fontSize: 7.5,
    color: C.muted,
  },
});

// ─── Helpers ────────────────────────────────────────────────────
function stripHtml(html: string): string {
  return html
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<[^>]*>/g, '')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, ' ')
    .trim();
}

function fmtCell(value: string | number, colIdx: number, formatting?: Record<number, string>): string {
  const fmt = formatting?.[colIdx];
  if (typeof value === 'number') {
    if (fmt === 'currency') {
      if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
      if (Math.abs(value) >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
      if (Math.abs(value) >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
      return `$${value.toLocaleString()}`;
    }
    if (fmt === 'percentage') return `${(value * 100).toFixed(1)}%`;
    return value.toLocaleString();
  }
  return String(value ?? '');
}

/** Detect if a column is numeric so we can right-align it */
function isNumericCol(rows: (string | number)[][], colIdx: number): boolean {
  let numCount = 0;
  for (const row of rows) {
    if (typeof row[colIdx] === 'number') numCount++;
  }
  return numCount > rows.length * 0.5;
}

// Section normalization is handled by the shared normalizeSections() from
// normalize-memo-sections.ts — it handles markdown tables, bullet detection,
// and both legacy and new section formats.

// ─── Chart data → mini table ────────────────────────────────────
function ChartDataTable({ chart }: { chart: any }) {
  const title = chart?.title || chart?.type || 'Chart';
  const data = chart?.data;

  if (!data) {
    return (
      <View style={s.chartBox}>
        <Text style={s.chartTitle}>{title}</Text>
        <Text style={s.chartNote}>Visual chart — see interactive version in app</Text>
      </View>
    );
  }

  // Chart.js format: { labels, datasets }
  if (data.labels && data.datasets) {
    const labels: string[] = data.labels;
    const datasets: any[] = data.datasets;
    // Build a small summary table: label | dataset1 | dataset2 ...
    const headers = ['', ...datasets.map((ds: any) => ds.label || 'Value')];
    const rows = labels.slice(0, 12).map((label: string, i: number) =>
      [label, ...datasets.map((ds: any) => {
        const v = ds.data?.[i];
        return typeof v === 'number' ? (Math.abs(v) >= 1e6 ? `$${(v / 1e6).toFixed(1)}M` : v.toLocaleString()) : String(v ?? '');
      })]
    );

    return (
      <View style={s.chartBox} wrap={false}>
        <Text style={s.chartTitle}>{title}</Text>
        <View style={s.tableHeader}>
          {headers.map((h, i) => <Text key={i} style={s.tableHeaderCell}>{h}</Text>)}
        </View>
        {rows.map((row, ri) => (
          <View key={ri} style={ri % 2 ? s.tableRowAlt : s.tableRow}>
            {row.map((cell: string, ci: number) => (
              <Text key={ci} style={ci > 0 ? s.tableCellRight : s.tableCell}>{cell}</Text>
            ))}
          </View>
        ))}
        {labels.length > 12 && (
          <Text style={s.chartNote}>{`... and ${labels.length - 12} more data points`}</Text>
        )}
        <Text style={s.chartNote}>Interactive chart available in Dilla AI</Text>
      </View>
    );
  }

  // Scatter: { datasets: [{ data: [{x, y}] }] }
  if (data.datasets?.[0]?.data?.[0]?.x !== undefined) {
    const ds = data.datasets[0];
    const points = ds.data.slice(0, 10);
    return (
      <View style={s.chartBox} wrap={false}>
        <Text style={s.chartTitle}>{title}</Text>
        {points.map((p: any, i: number) => (
          <Text key={i} style={{ fontSize: 8, marginBottom: 2, color: C.text }}>
            {`${p.label || `Point ${i + 1}`}: (${typeof p.x === 'number' ? p.x.toLocaleString() : p.x}, ${typeof p.y === 'number' ? p.y.toLocaleString() : p.y})`}
          </Text>
        ))}
        <Text style={s.chartNote}>Interactive chart available in Dilla AI</Text>
      </View>
    );
  }

  // Sankey: { nodes, links }
  if (data.nodes && data.links) {
    // Build a lookup map by node ID (links use string IDs, not array indices)
    const nodeMap: Record<string, string> = {};
    for (const node of data.nodes as any[]) {
      nodeMap[node.id] = node.label || node.name || node.id;
    }
    const topLinks = (data.links as any[]).sort((a: any, b: any) => (b.value || 0) - (a.value || 0)).slice(0, 8);
    return (
      <View style={s.chartBox} wrap={false}>
        <Text style={s.chartTitle}>{title}</Text>
        {topLinks.map((link: any, i: number) => {
          const src = nodeMap[link.source] || `Node ${link.source}`;
          const tgt = nodeMap[link.target] || `Node ${link.target}`;
          const val = typeof link.value === 'number'
            ? (Math.abs(link.value) >= 1e6 ? `$${(link.value / 1e6).toFixed(1)}M` : link.value.toLocaleString())
            : String(link.value ?? '');
          return <Text key={i} style={{ fontSize: 8, marginBottom: 2, color: C.text }}>{`${src} → ${tgt}: ${val}`}</Text>;
        })}
        <Text style={s.chartNote}>Flow diagram — see interactive version in app</Text>
      </View>
    );
  }

  // Segments / pie: { segments: [{name, value}] }
  if (data.segments || data.slices) {
    const segs = data.segments || data.slices;
    return (
      <View style={s.chartBox} wrap={false}>
        <Text style={s.chartTitle}>{title}</Text>
        {(segs as any[]).map((seg: any, i: number) => (
          <Text key={i} style={{ fontSize: 8, marginBottom: 2, color: C.text }}>
            {`${seg.name || seg.label}: ${typeof seg.value === 'number' ? seg.value.toLocaleString() : seg.value}${seg.value && typeof seg.value === 'number' && seg.value <= 100 ? '%' : ''}`}
          </Text>
        ))}
        <Text style={s.chartNote}>Interactive chart available in Dilla AI</Text>
      </View>
    );
  }

  // Generic object — show key/value pairs
  if (typeof data === 'object' && !Array.isArray(data)) {
    const entries = Object.entries(data).slice(0, 10);
    if (entries.length > 0) {
      return (
        <View style={s.chartBox} wrap={false}>
          <Text style={s.chartTitle}>{title}</Text>
          {entries.map(([k, v], i) => (
            <Text key={i} style={{ fontSize: 8, marginBottom: 2, color: C.text }}>
              {`${k}: ${typeof v === 'number' ? v.toLocaleString() : String(v ?? '')}`}
            </Text>
          ))}
          <Text style={s.chartNote}>Interactive chart available in Dilla AI</Text>
        </View>
      );
    }
  }

  // Fallback
  return (
    <View style={s.chartBox}>
      <Text style={s.chartTitle}>{title}</Text>
      <Text style={s.chartNote}>Visual chart — see interactive version in app</Text>
    </View>
  );
}

// ─── Markdown → React-PDF inline renderer ───────────────────────
/**
 * Parse simple markdown (bold, italic) into React-PDF <Text> children.
 * Handles **bold**, *italic*, and ***bold+italic*** within a single line.
 */
function renderMarkdownInline(text: string): React.ReactNode[] {
  const cleaned = stripHtml(text);
  if (!cleaned) return [];

  const parts: React.ReactNode[] = [];
  // Match **bold**, *italic*, ***bold+italic***
  const regex = /(\*{3})(.+?)\1|(\*{2})(.+?)\3|(\*{1})(.+?)\5/g;
  let lastIdx = 0;
  let match: RegExpExecArray | null;
  let keyIdx = 0;

  while ((match = regex.exec(cleaned)) !== null) {
    // Text before this match
    if (match.index > lastIdx) {
      parts.push(cleaned.slice(lastIdx, match.index));
    }
    if (match[1] === '***') {
      // Bold + italic
      parts.push(
        <Text key={`mi-${keyIdx++}`} style={{ fontFamily: 'Helvetica-BoldOblique' }}>{match[2]}</Text>
      );
    } else if (match[3] === '**') {
      // Bold
      parts.push(
        <Text key={`mi-${keyIdx++}`} style={{ fontFamily: 'Helvetica-Bold' }}>{match[4]}</Text>
      );
    } else if (match[5] === '*') {
      // Italic
      parts.push(
        <Text key={`mi-${keyIdx++}`} style={{ fontStyle: 'italic' }}>{match[6]}</Text>
      );
    }
    lastIdx = match.index + match[0].length;
  }

  // Remaining text after last match
  if (lastIdx < cleaned.length) {
    parts.push(cleaned.slice(lastIdx));
  }

  return parts.length > 0 ? parts : [cleaned];
}

// ─── Section renderer ───────────────────────────────────────────
function RenderSection({ section, idx }: { section: any; idx: number }) {
  const key = `s-${idx}`;

  switch (section.type) {
    case 'heading1':
      return <Text key={key} style={s.h1}>{stripHtml(section.content || '')}</Text>;

    case 'heading2':
      return <Text key={key} style={s.h2}>{stripHtml(section.content || '')}</Text>;

    case 'heading3':
      return <Text key={key} style={s.h3}>{stripHtml(section.content || '')}</Text>;

    case 'paragraph': {
      const text = stripHtml(section.content || '');
      if (!text) return null;
      return <Text key={key} style={s.p}>{renderMarkdownInline(section.content || '')}</Text>;
    }

    case 'list':
      return (
        <View key={key} style={{ marginBottom: 8 }}>
          {(section.items || []).map((item: string, j: number) => (
            <Text key={`${key}-${j}`} style={s.listItem}>{'\u2022  '}{renderMarkdownInline(item)}</Text>
          ))}
        </View>
      );

    case 'quote':
      return (
        <View key={key} style={s.quote}>
          <Text>{stripHtml(section.content || '')}</Text>
        </View>
      );

    case 'code':
      return (
        <View key={key} style={s.code}>
          <Text>{section.content || ''}</Text>
        </View>
      );

    case 'table': {
      if (!section.table) return null;
      const { headers, rows, caption, formatting } = section.table;
      const numericCols = new Set(
        headers.map((_: string, ci: number) => isNumericCol(rows, ci) ? ci : -1).filter((i: number) => i >= 0)
      );

      return (
        <View key={key} style={s.tableWrapper} wrap={false}>
          {caption && <Text style={s.tableCaption}>{caption}</Text>}
          <View style={s.tableHeader}>
            {headers.map((h: string, hi: number) => (
              <Text key={`h-${hi}`} style={s.tableHeaderCell}>{h}</Text>
            ))}
          </View>
          {rows.map((row: (string | number)[], ri: number) => {
            // Scenario row colouring
            const first = String(row[0] || '').toLowerCase();
            let bgColor: string | undefined;
            if (first === 'bull') bgColor = C.bull;
            else if (first === 'bear') bgColor = C.bear;
            else if (first === 'base') bgColor = C.base;
            else bgColor = ri % 2 ? C.bg : undefined;

            return (
              <View key={`r-${ri}`} style={[s.tableRow, bgColor ? { backgroundColor: bgColor } : {}]}>
                {row.map((cell: string | number, ci: number) => (
                  <Text
                    key={`c-${ci}`}
                    style={numericCols.has(ci) ? s.tableCellRight : s.tableCell}
                  >
                    {fmtCell(cell, ci, formatting)}
                  </Text>
                ))}
              </View>
            );
          })}
        </View>
      );
    }

    case 'chart':
      return <ChartDataTable key={key} chart={section.chart} />;

    default:
      if (section.content) {
        return <Text key={key} style={s.p}>{renderMarkdownInline(section.content)}</Text>;
      }
      return null;
  }
}

// ─── Main document component ────────────────────────────────────
function MemoDocument({ sections, title, date }: { sections: any[]; title: string; date?: string }) {
  const dateStr = date || new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

  // Use the shared normalizer which handles markdown tables, bullets, and both formats
  const flat: any[] = normalizeSections(sections) as any[];

  // Skip the first heading if it matches the title (avoid duplication on cover)
  let bodyStart = 0;
  if (flat.length > 0 && flat[0].type === 'heading1') {
    const h1Text = stripHtml(flat[0].content || '').toLowerCase();
    if (h1Text === title.toLowerCase() || title.toLowerCase().includes(h1Text)) {
      bodyStart = 1;
    }
  }

  return (
    <Document title={title} author="Dilla AI" creator="Dilla AI">
      {/* Cover page */}
      <Page size="A4" style={s.coverPage}>
        <View style={s.coverRule} />
        <Text style={s.coverTitle}>{title}</Text>
        <Text style={s.coverSubtitle}>Investment Analysis &amp; Portfolio Intelligence</Text>
        <Text style={s.coverMeta}>{dateStr}</Text>
        <Text style={s.coverMeta}>Confidential — Prepared by Dilla AI</Text>
        <View style={s.footer} fixed>
          <Text>Dilla AI — Confidential</Text>
          <Text render={({ pageNumber, totalPages }) => `Page ${pageNumber} of ${totalPages}`} />
        </View>
      </Page>

      {/* Body pages */}
      <Page size="A4" style={s.page} wrap>
        {flat.slice(bodyStart).map((section, i) => (
          <RenderSection key={`s-${i}`} section={section} idx={i} />
        ))}

        <View style={s.footer} fixed>
          <Text>Dilla AI — Confidential</Text>
          <Text render={({ pageNumber, totalPages }) => `Page ${pageNumber} of ${totalPages}`} />
        </View>
      </Page>
    </Document>
  );
}

// ─── Route handler ──────────────────────────────────────────────
export async function POST(request: NextRequest) {
  const body = await request.json();
  const { sections, charts, chartPositions, title, date } = body;

  if (!sections?.length) {
    return NextResponse.json({ error: 'No sections to export' }, { status: 400 });
  }

  // Merge external charts into sections at their indicated positions
  let mergedSections = [...sections];
  if (charts?.length) {
    if (chartPositions?.length) {
      // Insert charts at indicated positions (reverse order to keep indices valid)
      const inserts = chartPositions
        .map((pos: any, i: number) => ({ pos: pos.afterParagraph, chart: charts[i] }))
        .filter((x: any) => x.chart?.data)
        .sort((a: any, b: any) => b.pos - a.pos);

      for (const { pos, chart } of inserts) {
        mergedSections.splice(
          Math.min(pos, mergedSections.length),
          0,
          { type: 'chart', chart: { type: chart.type, title: chart.title, data: chart.data } },
        );
      }
    } else {
      // No positions specified — append charts at the end
      for (const chart of charts) {
        if (chart?.data) {
          mergedSections.push({ type: 'chart', chart: { type: chart.type, title: chart.title, data: chart.data } });
        }
      }
    }
  }

  try {
    const buffer = await renderToBuffer(
      <MemoDocument sections={mergedSections} title={title || 'Portfolio Memo'} date={date} />
    );

    const filename = title
      ? `${title.replace(/[^a-zA-Z0-9 ]/g, '').replace(/\s+/g, '_').substring(0, 50)}.pdf`
      : 'memo.pdf';

    return new NextResponse(new Uint8Array(buffer), {
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': `attachment; filename="${filename}"`,
      },
    });
  } catch (err) {
    console.error('[MEMO_EXPORT] React PDF render error:', err);
    return NextResponse.json({ error: 'PDF export failed', details: String(err) }, { status: 500 });
  }
}
