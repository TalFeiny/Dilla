'use client';

/**
 * Matrix Field Card Component
 * 
 * Card-based representation of a matrix cell. Each field type maps to a specialized card:
 * - Valuation → ValuationCard
 * - Documents → DocumentsCard
 * - NAV → NAVCard (with sparkline)
 * - Analytics → AnalyticsCard
 * - Citations → CitationsCard
 * - Default → StandardFieldCard (editable text/number)
 */

import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { 
  Edit2, 
  Check, 
  X, 
  Calculator, 
  FileText, 
  TrendingUp, 
  BarChart3, 
  Sparkles,
  Clock,
  User
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { MatrixColumn, MatrixCell, MatrixRow } from './UnifiedMatrix';
import {
  ValuationCell,
  DocumentsCell,
  ChartsCell,
  AnalyticsCell,
  CitationsCell,
} from './MatrixCellFeatures';
import { NAVCard } from './NAVCard';
import { StandardFieldCard } from './StandardFieldCard';

import { ActionExecutionResponse } from '@/lib/matrix/cell-action-registry';

export interface MatrixFieldCardProps {
  field: MatrixColumn;
  row: MatrixRow;
  cell: MatrixCell;
  fundId?: string;
  /** When provided, ValuationCell uses cell-derived inputs (stage, revenue, valuation, etc.) so CFO overrides apply. */
  matrixData?: { rows: MatrixRow[]; columns: MatrixColumn[]; metadata?: { fundId?: string } };
  onEdit?: (rowId: string, columnId: string, value: any) => Promise<void>;
  onCellFeatureAction?: (action: string, rowId: string, columnId: string, data?: any) => Promise<void>;
  onCellActionResult?: (rowId: string, columnId: string, response: ActionExecutionResponse) => void | Promise<void>;
  /** When document extraction completes, call to refresh suggestions and optionally open ChartViewport. */
  onSuggestChanges?: (documentId: string, extractedData: any) => void;
  className?: string;
}

export function MatrixFieldCard({
  field,
  row,
  cell,
  fundId,
  matrixData,
  onEdit,
  onCellFeatureAction,
  onCellActionResult,
  onSuggestChanges,
  className,
}: MatrixFieldCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState('');

  const handleDoubleClick = () => {
    if (field.editable && !isEditing) {
      setIsEditing(true);
      setEditValue(String(cell.value || ''));
    }
  };

  const handleSave = async () => {
    if (!onEdit) return;

    const column = field;
    let parsedValue: any = editValue;

    // Parse based on column type
    if (column.type === 'number' || column.type === 'currency' || column.type === 'percentage') {
      { const n = parseFloat(editValue); parsedValue = isNaN(n) ? null : n; }
      if (column.type === 'percentage' && parsedValue != null) {
        parsedValue = parsedValue / 100; // Store as decimal
      }
    } else if (column.type === 'boolean') {
      parsedValue = editValue.toLowerCase() === 'true' || editValue === '1';
    }

    try {
      await onEdit(row.id, field.id, parsedValue);
      setIsEditing(false);
      setEditValue('');
    } catch (err) {
      console.error('[MatrixFieldCard] Save failed:', err);
      // Keep edit mode open so user can retry
    }
  };

  const handleCancel = () => {
    setIsEditing(false);
    setEditValue('');
  };

  const getSourceBadge = () => {
    if (!cell.source) return null;
    
    const sourceColors: Record<string, string> = {
      manual: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
      document: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
      api: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
      formula: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
      agent: 'bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200',
    };

    return (
      <Badge 
        variant="secondary" 
        className={cn("text-xs", sourceColors[cell.source] || "bg-gray-100 text-gray-800")}
      >
        {cell.source}
      </Badge>
    );
  };

  // Map field type to specialized card component
  const renderFieldContent = () => {
    // Special field types that use feature components
    if (field.id === 'valuation') {
      return (
        <ValuationCell
          value={cell.value}
          companyId={row.companyId}
          companyName={row.companyName}
          fundId={fundId}
          matrixData={matrixData}
          row={row}
          metadata={cell.metadata}
          onUpdate={async (value, method) => {
            if (onEdit) {
              await onEdit(row.id, field.id, value);
            }
            if (onCellFeatureAction) {
              await onCellFeatureAction('valuation', row.id, field.id, { method, value });
            }
          }}
          onCellActionResult={onCellActionResult}
          rowId={row.id}
          columnId={field.id}
        />
      );
    }

    if (field.id === 'documents') {
      return (
        <DocumentsCell
          companyId={row.companyId}
          fundId={fundId}
          documentCount={cell.metadata?.documentCount || 0}
          documents={cell.metadata?.documents || []}
          onUpload={async (file) => {
            // Use uploadDocumentInCell to get document_id
            const { uploadDocumentInCell } = await import('@/lib/matrix/matrix-api-service');
            const result = await uploadDocumentInCell({
              file,
              companyId: row.companyId,
              fundId: fundId,
            });
            
            if (onCellFeatureAction) {
              await onCellFeatureAction('document_upload', row.id, field.id, { 
                file,
                documentId: result.documentId,
              });
            }
            
            return { document_id: result.documentId };
          }}
          onCellActionResult={onCellActionResult}
          rowId={row.id}
          columnId={field.id}
          onSuggestChanges={onSuggestChanges}
          onViewDocument={(documentId) => {
            // Navigate to document view or open in modal
            window.open(`/documents/${documentId}/analysis`, '_blank');
          }}
        />
      );
    }

    if (field.id === 'nav' || field.type === 'sparkline') {
      return (
        <NAVCard
          value={cell.value}
          sparkline={cell.sparkline}
          metadata={cell.metadata}
          companyId={row.companyId}
          fundId={fundId}
          onUpdate={async (value) => {
            if (onEdit) {
              await onEdit(row.id, field.id, value);
            }
          }}
        />
      );
    }

    if (field.id === 'charts') {
      return (
        <ChartsCell
          chartData={cell.metadata?.chartData}
          chartType={cell.metadata?.chartType}
          chartConfig={cell.metadata?.chart_config}
          onGenerate={async (prompt) => {
            if (onCellFeatureAction) {
              await onCellFeatureAction('chart_generate', row.id, field.id, { prompt });
            }
          }}
          onCellActionResult={onCellActionResult}
          rowId={row.id}
          columnId={field.id}
          companyId={row.companyId}
          fundId={fundId}
        />
      );
    }

    if (field.id === 'analytics') {
      return (
        <AnalyticsCell
          companyId={row.companyId}
          onRunAnalysis={async (type) => {
            if (onCellFeatureAction) {
              await onCellFeatureAction('analytics', row.id, field.id, { type });
            }
          }}
        />
      );
    }

    if (field.id === 'citations') {
      const raw = cell.metadata?.citations || [];
      const citations = raw.map((c: { id?: string; source?: string; url?: string; title?: string }, i: number) => ({
        id: c.id ?? String(i),
        source: c.source ?? c.title ?? 'Source',
        url: c.url,
      }));
      return (
        <CitationsCell
          citations={citations}
        />
      );
    }

    // Default: Standard editable field
    return (
      <StandardFieldCard
        field={field}
        cell={cell}
        isEditing={isEditing}
        editValue={editValue}
        onEditValueChange={setEditValue}
        onSave={handleSave}
        onCancel={handleCancel}
        onDoubleClick={handleDoubleClick}
      />
    );
  };

  return (
    <Card
      className={cn(
        "matrix-field-card group hover:shadow-md",
        "border-2 hover:border-primary/20",
        isEditing && "ring-2 ring-primary",
        className
      )}
      onDoubleClick={handleDoubleClick}
      data-field-id={field.id}
      data-row-id={row.id}
    >
      <CardHeader className="pb-2 space-y-1">
        <div className="flex items-center justify-between">
          <CardTitle className="text-xs font-medium text-muted-foreground truncate">
            {field.name}
          </CardTitle>
          {getSourceBadge()}
        </div>
      </CardHeader>
      
      <CardContent className="py-2 min-h-[60px] flex items-center">
        {renderFieldContent()}
      </CardContent>

      <CardFooter className="pt-2 pb-2 flex items-center justify-between text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          {cell.lastUpdated && (
            <div className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              <span className="truncate">
                {new Date(cell.lastUpdated).toLocaleDateString()}
              </span>
            </div>
          )}
          {cell.editedBy && (
            <div className="flex items-center gap-1">
              <User className="h-3 w-3" />
              <span className="truncate">{cell.editedBy}</span>
            </div>
          )}
        </div>
        {field.editable && !isEditing && (
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100"
            onClick={handleDoubleClick}
          >
            <Edit2 className="h-3 w-3" />
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
