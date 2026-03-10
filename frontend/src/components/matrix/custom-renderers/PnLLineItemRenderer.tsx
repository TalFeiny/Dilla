'use client';

import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Plus } from 'lucide-react';

/** P&L sections that support adding subcategory line items */
const EXPANDABLE_SECTIONS = new Set(['revenue', 'cogs', 'opex']);
const EXPANDABLE_CATEGORIES = new Set(['revenue', 'cogs', 'opex_rd', 'opex_sm', 'opex_ga']);

interface PnLLineItemRendererProps {
  value: string;
  data: any;
  /** Set of collapsed section IDs — managed by parent AGGridMatrix */
  collapsedSections: Set<string>;
  /** Toggle a section open/closed */
  onToggleSection: (rowId: string) => void;
  /** Add a subcategory line item under this category row */
  onAddLineItem?: (parentRowId: string, section: string) => void;
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
  const { value, data, collapsedSections, onToggleSection, onAddLineItem } = props;
  const [isHovered, setIsHovered] = useState(false);

  if (!data) return <span>{value}</span>;

  const depth: number = data.depth ?? data._originalRow?.depth ?? 0;
  const isHeader: boolean = data.isHeader ?? data._originalRow?.isHeader ?? false;
  const isTotal: boolean = data.isTotal ?? data._originalRow?.isTotal ?? false;
  const isComputed: boolean = data.isComputed ?? data._originalRow?.isComputed ?? false;
  const childIds: string[] = data.childIds ?? data._originalRow?.childIds ?? [];
  const rowId: string = data.id ?? '';
  const section: string = data.section ?? data._originalRow?.section ?? '';
  const hasChildren = childIds.length > 0;
  const isCollapsed = collapsedSections.has(rowId);

  // Show "+" on category rows that can have subcategories
  const canAddSubcategory = onAddLineItem && !isHeader && !isComputed && !isTotal
    && (EXPANDABLE_CATEGORIES.has(rowId) || EXPANDABLE_SECTIONS.has(section))
    && depth <= 1;

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
    <div
      style={style}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
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
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
        {value}
      </span>
      {canAddSubcategory && isHovered && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onAddLineItem?.(rowId, section);
          }}
          title="Add line item"
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: '2px',
            display: 'flex',
            alignItems: 'center',
            color: 'inherit',
            opacity: 0.5,
            flexShrink: 0,
          }}
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}
