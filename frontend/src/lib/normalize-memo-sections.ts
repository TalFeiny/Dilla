/**
 * Normalize memo sections into a consistent DocumentSection[] format.
 *
 * The backend can emit sections in two shapes:
 *   1. LightweightMemoService format: { type, content, chart, table, items, ... }
 *   2. Legacy/markdown format:        { title, content, level }
 *
 * This module coerces both into the canonical DocumentSection shape used by
 * MemoEditor and the React-PDF export route.
 */

import type { DocumentSection } from '@/components/memo/MemoEditor';

/** Loose section shape that covers both backend formats */
export interface RawSection {
  type?: string;
  title?: string;
  content?: string;
  level?: number;
  items?: string[];
  chart?: {
    type: string;
    title?: string;
    data: Record<string, unknown> | unknown[];
    renderType?: string;
    responsive?: boolean;
  };
  table?: {
    headers: string[];
    rows: (string | number)[][];
    caption?: string;
    formatting?: Record<number, 'currency' | 'percentage' | 'number' | 'text'>;
  };
  todos?: any[];
  skill_chain?: any[];
  citations?: any[];
  is_context?: boolean;
  imageUrl?: string;
  imageCaption?: string;
}

/**
 * Convert a loosely-typed backend section into a canonical DocumentSection.
 * Handles both the new `{type, content}` format and the legacy `{title, content, level}` format.
 */
function normalizeOne(raw: RawSection): DocumentSection[] {
  // Already has a valid `type` field — pass through with minimal fixup
  if (raw.type && ['heading1', 'heading2', 'heading3', 'paragraph', 'chart', 'list', 'quote', 'code', 'table', 'image', 'todo_list', 'skill_chain'].includes(raw.type)) {
    return [raw as DocumentSection];
  }

  // Legacy format: { title, content, level }
  const results: DocumentSection[] = [];
  if (raw.title) {
    const level = raw.level ?? 2;
    const headingType = level === 1 ? 'heading1' : level === 3 ? 'heading3' : 'heading2';
    results.push({ type: headingType, content: raw.title } as DocumentSection);
  }

  if (raw.content) {
    // Check if content contains markdown tables — split them out
    const tableRegex = /(\|[^\n]+\|\n\|[\s:-]+\|\n(?:\|[^\n]+\|\n?)*)/g;
    let lastIdx = 0;
    let match: RegExpExecArray | null;
    let foundTable = false;

    while ((match = tableRegex.exec(raw.content)) !== null) {
      foundTable = true;
      const before = raw.content.slice(lastIdx, match.index).trim();
      if (before) {
        results.push({ type: 'paragraph', content: before } as DocumentSection);
      }
      // Parse the markdown table
      const tbl = parseSimpleTable(match[1]);
      if (tbl) {
        results.push({ type: 'table', table: tbl } as DocumentSection);
      }
      lastIdx = match.index + match[0].length;
    }

    if (foundTable) {
      const after = raw.content.slice(lastIdx).trim();
      if (after) {
        results.push({ type: 'paragraph', content: after } as DocumentSection);
      }
    } else {
      // Check if the content has bullet points
      const lines = raw.content.split('\n');
      const bulletLines = lines.filter(l => /^\s*[-*]\s+/.test(l) || /^\s*\d+[.)]\s+/.test(l));
      if (bulletLines.length > 0 && bulletLines.length >= lines.length * 0.5) {
        // Mostly bullets — treat as list
        const items = lines
          .filter(l => /^\s*[-*]\s+/.test(l) || /^\s*\d+[.)]\s+/.test(l))
          .map(l => l.replace(/^\s*[-*]\s+/, '').replace(/^\s*\d+[.)]\s+/, '').trim());
        results.push({ type: 'list', items } as DocumentSection);
      } else {
        results.push({ type: 'paragraph', content: raw.content } as DocumentSection);
      }
    }
  }

  if (raw.items?.length) {
    results.push({ type: 'list', items: raw.items } as DocumentSection);
  }

  if (raw.chart) {
    results.push({ type: 'chart', chart: raw.chart } as DocumentSection);
  }

  if (raw.table && !raw.content) {
    results.push({ type: 'table', table: raw.table } as DocumentSection);
  }

  return results.length > 0 ? results : [{ type: 'paragraph', content: raw.content || '' } as DocumentSection];
}

/** Simple markdown table parser */
function parseSimpleTable(md: string): { headers: string[]; rows: (string | number)[][] } | null {
  const lines = md.trim().split('\n').filter(l => l.trim());
  if (lines.length < 2) return null;
  if (!lines[0].includes('|') || !lines[1].match(/^[\s|:-]+$/)) return null;

  const parseCells = (line: string) => line.split('|').map(c => c.trim()).filter(Boolean);
  const headers = parseCells(lines[0]);
  if (!headers.length) return null;

  const rows: (string | number)[][] = [];
  for (let i = 2; i < lines.length; i++) {
    if (!lines[i].includes('|')) continue;
    const cells = parseCells(lines[i]);
    rows.push(cells.map(c => {
      const cleaned = c.replace(/[$,%]/g, '').trim();
      const num = Number(cleaned);
      return !isNaN(num) && cleaned.length > 0 ? num : c;
    }));
  }
  return rows.length > 0 ? { headers, rows } : null;
}

/**
 * Normalize an array of mixed-format sections into canonical DocumentSection[].
 *
 * Also merges separate charts (from docsCharts / chartPositions) into the
 * section stream so the PDF export sees them inline.
 */
export function normalizeSections(
  sections: RawSection[],
  charts?: Array<{ type: string; title?: string; data: any }>,
  chartPositions?: Array<{ afterParagraph: number; inline: boolean }>,
): DocumentSection[] {
  // Normalize all sections
  const normalized = sections.flatMap(normalizeOne);

  // Merge external charts into the section stream at the indicated positions
  if (charts?.length && chartPositions?.length) {
    // Work in reverse so splice indices stay valid
    const inserts = chartPositions
      .map((pos, i) => ({ pos: pos.afterParagraph, chart: charts[i] }))
      .filter(x => x.chart?.data)
      .sort((a, b) => b.pos - a.pos);

    for (const { pos, chart } of inserts) {
      const section: DocumentSection = {
        type: 'chart',
        chart: {
          type: chart.type,
          title: chart.title,
          data: chart.data,
        },
      } as DocumentSection;
      const insertAt = Math.min(pos, normalized.length);
      normalized.splice(insertAt, 0, section);
    }
  }

  return normalized;
}
