'use client';

/**
 * Standard Field Card Component
 * 
 * Default card for editable text/number/currency/percentage fields
 */

import React, { useState } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Check, X, Info, ExternalLink, List } from 'lucide-react';
import { cn } from '@/lib/utils';
import { MatrixColumn, MatrixCell } from './UnifiedMatrix';
import { formatCellValue } from '@/lib/matrix/cell-formatters';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';

interface StandardFieldCardProps {
  field: MatrixColumn;
  cell: MatrixCell;
  isEditing: boolean;
  editValue: string;
  onEditValueChange: (value: string) => void;
  onSave: () => void;
  onCancel: () => void;
  onDoubleClick: () => void;
}

export function StandardFieldCard({
  field,
  cell,
  isEditing,
  editValue,
  onEditValueChange,
  onSave,
  onCancel,
  onDoubleClick,
}: StandardFieldCardProps) {
  const [showCitations, setShowCitations] = useState(false);
  const formatValue = (value: any, type: string): string =>
    formatCellValue(value, type as import('@/lib/matrix/cell-formatters').CellColumnType);

  if (isEditing) {
    return (
      <div className="w-full space-y-2">
        <Input
          value={editValue}
          onChange={(e) => onEditValueChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              onSave();
            } else if (e.key === 'Escape') {
              onCancel();
            }
          }}
          autoFocus
          className="h-8 text-sm"
        />
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="ghost"
            className="h-6 w-6 p-0"
            onClick={onSave}
          >
            <Check className="h-3 w-3 text-green-600" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-6 w-6 p-0"
            onClick={onCancel}
          >
            <X className="h-3 w-3 text-red-600" />
          </Button>
        </div>
      </div>
    );
  }

  const displayValue = cell.displayValue || formatValue(cell.value, field.type);
  const hasExplanation = cell.metadata?.explanation || cell.metadata?.method;
  const citations = cell.metadata?.citations || [];
  const hasCitations = citations.length > 0;
  
  // Check if this is an array output (prefer structured_array from custom array structures)
  const isArrayOutput = cell.metadata?.output_type === 'array' || 
                        Array.isArray(cell.value) || 
                        Array.isArray(cell.metadata?.raw_output) ||
                        Array.isArray(cell.metadata?.structured_array);
  // Prefer structured_array if available (uses custom array structures from backend)
  const arrayData = cell.metadata?.structured_array || 
                    cell.metadata?.raw_output || 
                    cell.value;
  const arrayLength = Array.isArray(arrayData) ? arrayData.length : 
                      (cell.metadata?.array_length || 0);

  const CitationBadge = () => {
    if (!hasCitations) return null;

    return (
      <Badge
        variant="outline"
        className="h-5 px-1.5 text-xs cursor-pointer hover:bg-accent flex-shrink-0"
        onClick={(e) => {
          e.stopPropagation();
          setShowCitations(!showCitations);
        }}
      >
        {citations.length}
      </Badge>
    );
  };

  const ArraySummary = () => {
    if (!isArrayOutput || arrayLength === 0) return null;

    // Prefer structured_array from metadata if available (uses custom array structures)
    const displayData = cell.metadata?.structured_array || arrayData;
    const outputStructure = cell.metadata?.output_structure;
    const structureLabel = outputStructure 
      ? outputStructure.replace(/_array$/, '').replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
      : 'Array';

    return (
      <Dialog>
        <DialogTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-xs"
            onClick={(e) => e.stopPropagation()}
          >
            <List className="h-3 w-3 mr-1" />
            {arrayLength} {structureLabel.toLowerCase()}{arrayLength !== 1 ? 's' : ''}
          </Button>
        </DialogTrigger>
        <DialogContent className="sm:max-w-[600px] max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{structureLabel} Data ({arrayLength} items)</DialogTitle>
            <DialogDescription>
              {outputStructure 
                ? `Structured ${structureLabel.toLowerCase()} data from action result`
                : 'Full list of items from the action result'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 mt-4">
            {Array.isArray(displayData) && displayData.map((item, idx) => (
              <div
                key={idx}
                className="p-2 border rounded-md text-sm"
              >
                {typeof item === 'object' && item !== null ? (
                  <div className="space-y-1">
                    {/* For structured arrays, show key fields prominently */}
                    {outputStructure && item.company && (
                      <div className="font-semibold text-blue-600">{item.company}</div>
                    )}
                    {outputStructure && item.metric && (
                      <div className="font-semibold">{item.metric}: <span className="font-normal">{item.value}</span></div>
                    )}
                    {outputStructure && item.scenario && (
                      <div className="font-semibold">{item.scenario}</div>
                    )}
                    {outputStructure && item.round && (
                      <div className="font-semibold">{item.round}: ${item.amount?.toLocaleString()}</div>
                    )}
                    <pre className="text-xs overflow-x-auto mt-1">
                      {JSON.stringify(item, null, 2)}
                    </pre>
                  </div>
                ) : (
                  <span>{String(item)}</span>
                )}
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    );
  };

  return (
    <TooltipProvider>
      <div
        className={cn(
          "w-full text-sm font-medium flex flex-col gap-1",
          !cell.value && cell.value !== 0 && "text-muted-foreground",
          field.editable && "cursor-pointer hover:text-primary"
        )}
        onDoubleClick={onDoubleClick}
      >
        <div className="flex items-center gap-1.5">
          {isArrayOutput ? (
            <ArraySummary />
          ) : (
            <span className="flex-1">{displayValue}</span>
          )}
          {hasExplanation && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Info className="h-3 w-3 text-muted-foreground hover:text-primary cursor-help flex-shrink-0" />
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">
                <div className="space-y-1">
                  {cell.metadata?.method && (
                    <div className="font-semibold">{cell.metadata.method}</div>
                  )}
                  {cell.metadata?.explanation && (
                    <div className="text-xs">{cell.metadata.explanation}</div>
                  )}
                </div>
              </TooltipContent>
            </Tooltip>
          )}
          <CitationBadge />
        </div>
        
        {/* Inline Citations - expands within cell */}
        {showCitations && hasCitations && (
          <div 
            className="p-2 rounded-md border border-slate-200 bg-slate-50 text-xs"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="font-medium text-sm">Citations</h4>
                <button
                  onClick={() => setShowCitations(false)}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
              {hasExplanation && (
                <div className="text-xs text-muted-foreground pb-2 border-b">
                  {cell.metadata?.method && (
                    <div className="font-semibold mb-1">{cell.metadata.method}</div>
                  )}
                  {cell.metadata?.explanation && (
                    <div>{cell.metadata.explanation}</div>
                  )}
                </div>
              )}
              <div className="space-y-1 max-h-32 overflow-y-auto">
                {citations.map((citation, idx) => (
                  <div key={citation.id || idx} className="text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">
                        {citation.source || citation.title || 'Source'}
                      </span>
                      {citation.url && (
                        <a
                          href={citation.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary hover:underline ml-2"
                        >
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </TooltipProvider>
  );
}
