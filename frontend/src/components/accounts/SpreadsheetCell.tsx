'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import { Link2 } from 'lucide-react';

interface CellStyle {
  backgroundColor?: string;
  color?: string;
  fontWeight?: 'normal' | 'bold';
  fontStyle?: 'normal' | 'italic';
  textDecoration?: 'none' | 'underline';
  textAlign?: 'left' | 'center' | 'right';
  fontSize?: number;
  borderColor?: string;
  borderWidth?: number;
}

interface Cell {
  value: any;
  formula?: string;
  type: 'text' | 'number' | 'currency' | 'percentage' | 'date' | 'boolean' | 'formula' | 'link';
  style?: CellStyle;
  locked?: boolean;
  comment?: string;
  link?: string;
  sourceUrl?: string;
  citation?: {
    source: string;
    url: string;
    date?: string;
    excerpt?: string;
  };
}

interface SpreadsheetCellProps {
  cellRef: string;
  cell: Cell | undefined;
  isSelected: boolean;
  isActive: boolean;
  conditionalStyle?: CellStyle;
  showGridLines: boolean;
  rowHeight?: number;
  columnWidth?: number;
  evaluatedValue?: any;
  onCellClick: () => void;
  onCellMouseDown: (e: React.MouseEvent) => void;
  onCellDoubleClick: () => void;
}

const SpreadsheetCell = React.memo(({
  cellRef,
  cell,
  isSelected,
  isActive,
  conditionalStyle,
  showGridLines,
  rowHeight = 24,
  columnWidth = 80,
  evaluatedValue,
  onCellClick,
  onCellMouseDown,
  onCellDoubleClick
}: SpreadsheetCellProps) => {
  const cellStyle = { ...cell?.style, ...conditionalStyle };
  
  const renderCellContent = () => {
    if (!cell) return null;
    
    // Use pre-evaluated value if provided (for formulas)
    const displayValue = cell.formula && evaluatedValue !== undefined ? evaluatedValue : cell.value;
    
    // Handle hyperlink result
    if (displayValue && typeof displayValue === 'object' && displayValue.type === 'hyperlink') {
      return (
        <a 
          href={displayValue.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 hover:underline cursor-pointer"
        >
          {displayValue.text}
        </a>
      );
    }
    
    // Handle citation or source URL
    if (cell.citation || cell.sourceUrl || cell.link) {
      return (
        <div className="relative inline-flex items-center group">
          <a 
            href={cell.citation?.url || cell.sourceUrl || cell.link} 
            target="_blank" 
            rel="noopener noreferrer" 
            className="text-blue-600 hover:underline cursor-pointer"
            title={cell.citation ? `Source: ${cell.citation.source}` : cell.sourceUrl ? `Source: ${cell.sourceUrl}` : ''}
          >
            {cell.type === 'currency' ? (
              <span>{typeof displayValue === 'number' ? `$${displayValue.toLocaleString()}` : displayValue}</span>
            ) : cell.type === 'percentage' ? (
              <span>{typeof displayValue === 'number' ? `${(displayValue * 100).toFixed(1)}%` : displayValue}</span>
            ) : (
              <span>{typeof displayValue === 'number' ? displayValue.toLocaleString() : displayValue}</span>
            )}
          </a>
          {cell.citation && (
            <>
              <sup className="text-xs text-blue-500 ml-0.5">[{cell.citation.source?.slice(0, 1) || 'C'}]</sup>
              <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block z-50 w-64 p-2 bg-white border border-gray-200 rounded shadow-lg text-xs">
                <div className="font-semibold">{cell.citation.source}</div>
                {cell.citation.date && <div className="text-gray-500">{cell.citation.date}</div>}
                {cell.citation.excerpt && <div className="mt-1 text-gray-600 italic">"{cell.citation.excerpt}"</div>}
                <a href={cell.citation.url} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline mt-1 block">
                  View source →
                </a>
              </div>
            </>
          )}
          {cell.sourceUrl && !cell.citation && <Link2 className="w-3 h-3 inline ml-1" />}
        </div>
      );
    }
    
    // Handle link type
    if (cell.type === 'link') {
      return (
        <a href={displayValue} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
          <Link2 className="w-3 h-3 inline mr-1" />
          {displayValue}
        </a>
      );
    }
    
    // Handle other types
    switch (cell.type) {
      case 'currency':
        return <span>{typeof displayValue === 'number' ? `$${displayValue.toLocaleString()}` : displayValue}</span>;
      case 'percentage':
        return <span>{typeof displayValue === 'number' ? `${(displayValue * 100).toFixed(1)}%` : displayValue}</span>;
      case 'number':
      case 'formula':
        return <span>{typeof displayValue === 'number' ? displayValue.toLocaleString() : displayValue}</span>;
      default:
        return <span>{displayValue}</span>;
    }
  };
  
  return (
    <td
      className={cn(
        "relative border text-sm p-1 cursor-cell",
        showGridLines ? "border-gray-300" : "border-transparent",
        isActive && "ring-2 ring-blue-500 ring-inset z-10",
        isSelected && !isActive && "bg-blue-50",
        cell?.type === 'formula' && "bg-gray-50"
      )}
      style={{
        ...cellStyle,
        height: rowHeight,
        width: columnWidth
      }}
      onClick={onCellClick}
      onMouseDown={onCellMouseDown}
      onDoubleClick={onCellDoubleClick}
    >
      {cell && (
        <div className={cn(
          "w-full h-full flex items-center",
          cellStyle?.textAlign === 'center' && "justify-center",
          cellStyle?.textAlign === 'right' && "justify-end"
        )}>
          {renderCellContent()}
        </div>
      )}
      {cell?.comment && (
        <div className="absolute top-0 right-0 w-0 h-0 border-t-8 border-t-yellow-400 border-l-8 border-l-transparent" />
      )}
    </td>
  );
}, (prevProps, nextProps) => {
  // Custom comparison for optimization
  return (
    prevProps.cellRef === nextProps.cellRef &&
    prevProps.cell === nextProps.cell &&
    prevProps.isSelected === nextProps.isSelected &&
    prevProps.isActive === nextProps.isActive &&
    prevProps.conditionalStyle === nextProps.conditionalStyle &&
    prevProps.showGridLines === nextProps.showGridLines &&
    prevProps.evaluatedValue === nextProps.evaluatedValue
  );
});

SpreadsheetCell.displayName = 'SpreadsheetCell';

export default SpreadsheetCell;