'use client';

import React, { useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { Button } from '@/components/ui/button';
import {
  Heading2, Bold, List, BarChart3, Download, Loader2, Table, X, Trash2
} from 'lucide-react';

const TableauLevelCharts = dynamic(
  () => import('@/components/charts/TableauLevelCharts'),
  { ssr: false, loading: () => <div className="h-[200px] animate-pulse bg-muted rounded" /> }
);

export interface DocumentSection {
  type: 'heading1' | 'heading2' | 'heading3' | 'paragraph' | 'chart' | 'list' | 'quote' | 'code' | 'image' | 'table';
  content?: string;
  chart?: {
    type: string;
    title?: string;
    data: Record<string, unknown> | unknown[];
    renderType?: string;
    responsive?: boolean;
  };
  items?: string[];
  imageUrl?: string;
  imageCaption?: string;
  table?: {
    headers: string[];
    rows: (string | number)[][];
    caption?: string;
    formatting?: Record<number, 'currency' | 'percentage' | 'number' | 'text'>;
  };
  citations?: Array<{
    type: 'source' | 'document' | 'reasoning';
    title: string;
    url?: string;
    document_id?: string;
    content?: string;
  }>;
}

export interface MemoEditorProps {
  sections: DocumentSection[];
  onChange: (sections: DocumentSection[]) => void;
  readOnly?: boolean;
  compact?: boolean;
  onExportPdf?: () => void;
  exportingPdf?: boolean;
}

function formatTableCell(value: string | number, format?: string): string {
  if (typeof value === 'number') {
    if (format === 'currency') {
      if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
      if (Math.abs(value) >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
      if (Math.abs(value) >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
      return `$${value.toLocaleString()}`;
    }
    if (format === 'percentage') return `${(value * 100).toFixed(1)}%`;
    return value.toLocaleString();
  }
  return String(value ?? '');
}

export function MemoEditor({ sections, onChange, readOnly = false, compact = false, onExportPdf, exportingPdf }: MemoEditorProps) {
  const [selectedIdx, setSelectedIdx] = useState<number>(0);

  const updateSection = useCallback((idx: number, updates: Partial<DocumentSection>) => {
    const next = [...sections];
    next[idx] = { ...next[idx], ...updates };
    onChange(next);
  }, [sections, onChange]);

  const addSection = useCallback((afterIdx: number, section: DocumentSection) => {
    const next = [...sections];
    next.splice(afterIdx + 1, 0, section);
    onChange(next);
    setSelectedIdx(afterIdx + 1);
  }, [sections, onChange]);

  const removeSection = useCallback((idx: number) => {
    if (sections.length <= 1) return;
    onChange(sections.filter((_, i) => i !== idx));
    setSelectedIdx(Math.max(0, idx - 1));
  }, [sections, onChange]);

  return (
    <div className={`flex flex-col h-full ${compact ? 'text-xs' : 'text-sm'}`}>
      {/* Toolbar */}
      {!readOnly && (
        <div className="flex items-center gap-1 px-2 py-1 border-b shrink-0 flex-wrap">
          <Button variant="ghost" size="sm" className="h-6 w-6 p-0" title="Add heading" onClick={() => addSection(selectedIdx, { type: 'heading2', content: 'New Section' })}>
            <Heading2 className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="sm" className="h-6 w-6 p-0" title="Add paragraph" onClick={() => addSection(selectedIdx, { type: 'paragraph', content: '' })}>
            <Bold className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="sm" className="h-6 w-6 p-0" title="Add list" onClick={() => addSection(selectedIdx, { type: 'list', items: [''] })}>
            <List className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="sm" className="h-6 w-6 p-0" title="Add chart" onClick={() => addSection(selectedIdx, { type: 'chart', chart: { type: 'bar', title: 'New Chart', data: {}, responsive: true } })}>
            <BarChart3 className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="sm" className="h-6 w-6 p-0" title="Add table" onClick={() => addSection(selectedIdx, { type: 'table', table: { headers: ['Column 1', 'Column 2'], rows: [['', '']], caption: '' } })}>
            <Table className="h-3 w-3" />
          </Button>
          <div className="flex-1" />
          {sections.length > 1 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0 hover:text-destructive"
              title="Clear all sections"
              onClick={() => onChange([{ type: 'paragraph', content: '' }])}
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          )}
          {onExportPdf && (
            <Button variant="ghost" size="sm" className="h-6 gap-1 text-xs" onClick={onExportPdf} disabled={exportingPdf}>
              {exportingPdf ? <Loader2 className="h-3 w-3 animate-spin" /> : <Download className="h-3 w-3" />}
              PDF
            </Button>
          )}
        </div>
      )}

      {/* Sections */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {sections.map((section, idx) => (
          <div
            key={idx}
            className={`group relative rounded px-2 py-1 cursor-text ${selectedIdx === idx ? 'ring-1 ring-primary/30' : ''} ${!readOnly ? 'hover:bg-muted/50' : ''}`}
            onClick={() => setSelectedIdx(idx)}
          >
            {/* Heading 1 */}
            {section.type === 'heading1' && (
              <h1
                className={`font-bold ${compact ? 'text-base' : 'text-lg'} outline-none`}
                contentEditable={!readOnly}
                suppressContentEditableWarning
                onBlur={(e) => updateSection(idx, { content: e.currentTarget.textContent || '' })}
              >
                {section.content}
              </h1>
            )}

            {/* Heading 2 */}
            {section.type === 'heading2' && (
              <h2
                className={`font-semibold ${compact ? 'text-sm' : 'text-base'} outline-none`}
                contentEditable={!readOnly}
                suppressContentEditableWarning
                onBlur={(e) => updateSection(idx, { content: e.currentTarget.textContent || '' })}
              >
                {section.content}
              </h2>
            )}

            {/* Heading 3 */}
            {section.type === 'heading3' && (
              <h3
                className={`font-medium ${compact ? 'text-xs' : 'text-sm'} outline-none`}
                contentEditable={!readOnly}
                suppressContentEditableWarning
                onBlur={(e) => updateSection(idx, { content: e.currentTarget.textContent || '' })}
              >
                {section.content}
              </h3>
            )}

            {/* Paragraph */}
            {section.type === 'paragraph' && (
              <p
                className="outline-none leading-relaxed"
                contentEditable={!readOnly}
                suppressContentEditableWarning
                onBlur={(e) => updateSection(idx, { content: e.currentTarget.textContent || '' })}
              >
                {section.content}
              </p>
            )}

            {/* Chart — responsive, embedded in document flow */}
            {section.type === 'chart' && section.chart && (
              <div className="w-full my-2 rounded border bg-card overflow-hidden" style={{ aspectRatio: '16/9', maxHeight: compact ? 220 : 320 }}>
                <div className="w-full h-full p-2">
                  <TableauLevelCharts
                    data={section.chart.data}
                    type={section.chart.type as any}
                    title={section.chart.title}
                  />
                </div>
                {section.chart.title && (
                  <p className="text-[10px] text-muted-foreground text-center pb-1">{section.chart.title}</p>
                )}
              </div>
            )}

            {/* List */}
            {section.type === 'list' && (
              <ul className="list-disc pl-4 space-y-0.5">
                {(section.items || []).map((item, j) => (
                  <li
                    key={j}
                    contentEditable={!readOnly}
                    suppressContentEditableWarning
                    onBlur={(e) => {
                      const items = [...(section.items || [])];
                      items[j] = e.currentTarget.textContent || '';
                      updateSection(idx, { items });
                    }}
                  >
                    {item}
                  </li>
                ))}
              </ul>
            )}

            {/* Quote */}
            {section.type === 'quote' && (
              <blockquote
                className="border-l-2 border-primary/40 pl-3 italic text-muted-foreground outline-none"
                contentEditable={!readOnly}
                suppressContentEditableWarning
                onBlur={(e) => updateSection(idx, { content: e.currentTarget.textContent || '' })}
              >
                {section.content}
              </blockquote>
            )}

            {/* Code */}
            {section.type === 'code' && (
              <pre className="bg-muted rounded p-2 font-mono text-xs overflow-x-auto">
                <code
                  contentEditable={!readOnly}
                  suppressContentEditableWarning
                  onBlur={(e) => updateSection(idx, { content: e.currentTarget.textContent || '' })}
                >
                  {section.content}
                </code>
              </pre>
            )}

            {/* Table */}
            {section.type === 'table' && section.table && (
              <div className="w-full my-2 overflow-x-auto">
                {section.table.caption && (
                  <p className="text-[10px] text-muted-foreground mb-1">{section.table.caption}</p>
                )}
                <table className="w-full text-xs border-collapse">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      {section.table.headers.map((h, hi) => (
                        <th key={hi} className="px-2 py-1 text-left font-medium">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {section.table.rows.map((row, ri) => (
                      <tr key={ri} className="border-b last:border-0 hover:bg-muted/30">
                        {row.map((cell, ci) => (
                          <td key={ci} className="px-2 py-1">
                            {formatTableCell(cell, section.table?.formatting?.[ci])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Image */}
            {section.type === 'image' && section.imageUrl && (
              <div className="my-2">
                <img src={section.imageUrl} alt={section.imageCaption || ''} className="max-w-full rounded" />
                {section.imageCaption && (
                  <p className="text-[10px] text-muted-foreground text-center mt-1">{section.imageCaption}</p>
                )}
              </div>
            )}

            {/* Citations */}
            {section.citations?.length ? (
              <div className="mt-1 flex flex-wrap gap-1">
                {section.citations.map((c, ci) => (
                  <span key={ci} className="text-[10px] bg-muted px-1 rounded text-muted-foreground">
                    {c.type === 'source' && c.url ? (
                      <a href={c.url} target="_blank" rel="noopener noreferrer" className="underline">{c.title}</a>
                    ) : (
                      c.title
                    )}
                  </span>
                ))}
              </div>
            ) : null}

            {/* Delete button */}
            {!readOnly && sections.length > 1 && (
              <button
                className="absolute -right-1 -top-1 opacity-0 group-hover:opacity-100 h-4 w-4 bg-destructive text-white rounded-full text-[10px] flex items-center justify-center"
                onClick={(e) => { e.stopPropagation(); removeSection(idx); }}
              >
                <X className="h-2.5 w-2.5" />
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
