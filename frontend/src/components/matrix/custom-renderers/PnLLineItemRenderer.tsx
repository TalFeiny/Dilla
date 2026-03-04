'use client';

import React from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

interface PnLLineItemRendererProps {
  value: string;
  data: any;
  /** Set of collapsed section IDs — managed by parent AGGridMatrix */
  collapsedSections: Set<string>;
  /** Toggle a section open/closed */
  onToggleSection: (rowId: string) => void;
}

/**
 * Custom AG Grid cell renderer for the P&L "Line Item" column.
 * Handles:
 * - Indentation via depth * 24px
 * - Chevron toggle for rows with childIds
 * - Bold styling for headers
 * - Top-border + semibold for totals
 * - Subtle background for computed rows (Gross Profit, EBITDA)
 */
export function PnLLineItemRenderer(props: PnLLineItemRendererProps) {
  const { value, data, collapsedSections, onToggleSection } = props;

  if (!data) return <span>{value}</span>;

  const depth: number = data.depth ?? data._originalRow?.depth ?? 0;
  const isHeader: boolean = data.isHeader ?? data._originalRow?.isHeader ?? false;
  const isTotal: boolean = data.isTotal ?? data._originalRow?.isTotal ?? false;
  const isComputed: boolean = data.isComputed ?? data._originalRow?.isComputed ?? false;
  const childIds: string[] = data.childIds ?? data._originalRow?.childIds ?? [];
  const rowId: string = data.id ?? '';
  const hasChildren = childIds.length > 0;
  const isCollapsed = collapsedSections.has(rowId);

  const paddingLeft = depth * 24;

  const style: React.CSSProperties = {
    paddingLeft: `${paddingLeft}px`,
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    width: '100%',
    height: '100%',
    fontWeight: isHeader || isTotal ? 600 : isComputed ? 500 : 400,
    borderTop: isTotal ? '2px solid var(--border, #d1d5db)' : undefined,
    backgroundColor: isComputed ? 'var(--muted, rgba(0,0,0,0.03))' : undefined,
    fontSize: depth === 0 ? '13px' : '12px',
    color: depth >= 2 ? 'var(--muted-foreground, #6b7280)' : undefined,
  };

  return (
    <div style={style}>
      {hasChildren ? (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggleSection(rowId);
          }}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: '2px',
            display: 'flex',
            alignItems: 'center',
            color: 'inherit',
            opacity: 0.6,
          }}
        >
          {isCollapsed ? (
            <ChevronRight className="h-3.5 w-3.5" />
          ) : (
            <ChevronDown className="h-3.5 w-3.5" />
          )}
        </button>
      ) : (
        <span style={{ width: '20px', flexShrink: 0 }} />
      )}
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {value}
      </span>
    </div>
  );
}
