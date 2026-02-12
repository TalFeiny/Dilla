'use client';

import React, { useState, useMemo, useCallback } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { DataTable } from '@/components/ui/data-table';
import {
  ColumnDef,
  Row,
} from '@tanstack/react-table';
import {
  Download,
  Copy,
  FileSpreadsheet,
  Plus,
  Trash2,
  Edit,
  Save,
  X,
} from 'lucide-react';

interface DataGridProps {
  data: any[];
  columns?: string[];
  title?: string;
  description?: string;
  exportFileName?: string;
  editable?: boolean;
  onDataChange?: (newData: any[]) => void;
}

export default function DataGrid({
  data: initialData,
  columns: initialColumns,
  title = 'Data Analysis',
  description,
  exportFileName = 'agent-data',
  editable = false,
  onDataChange
}: DataGridProps) {
  const [data, setData] = useState(initialData);
  const [editingCell, setEditingCell] = useState<{ rowId: string; columnId: string } | null>(null);
  const [editValue, setEditValue] = useState('');

  // Auto-detect columns if not provided
  const columnKeys = useMemo(() => {
    if (initialColumns) return initialColumns;
    if (!data || data.length === 0) return [];
    
    // Get all unique keys from all objects
    const allKeys = new Set<string>();
    data.forEach(item => {
      Object.keys(item).forEach(key => allKeys.add(key));
    });
    return Array.from(allKeys);
  }, [initialColumns, data]);

  // Format cell value for display
  const formatCellValue = (value: any) => {
    if (value === null || value === undefined) return '-';
    if (typeof value === 'boolean') return value ? '✓' : '✗';
    if (typeof value === 'number') {
      if (value > 1000000) return `${(value / 1000000).toFixed(1)}M`;
      if (value > 1000) return `${(value / 1000).toFixed(1)}K`;
      return value.toFixed(2);
    }
    if (value instanceof Date) return value.toLocaleDateString();
    return String(value);
  };

  // Handle cell editing
  const handleEditStart = useCallback((rowId: string, columnId: string, currentValue: any) => {
    if (!editable) return;
    setEditingCell({ rowId, columnId });
    setEditValue(String(currentValue ?? ''));
  }, [editable]);

  const handleEditSave = useCallback((rowId: string, columnId: string) => {
    if (!editingCell || editingCell.rowId !== rowId || editingCell.columnId !== columnId) return;
    
    const newData = data.map((row, index) => {
      // Use index as fallback row identifier if no id field
      const rowIdentifier = row.id ?? row._id ?? `row-${index}`;
      if (String(rowIdentifier) !== rowId) return row;
      
      return {
        ...row,
        [columnId]: editValue
      };
    });
    
    setData(newData);
    onDataChange?.(newData);
    setEditingCell(null);
    setEditValue('');
  }, [data, editingCell, editValue, onDataChange]);

  const handleEditCancel = useCallback(() => {
    setEditingCell(null);
    setEditValue('');
  }, []);

  // Add new row
  const handleAddRow = useCallback(() => {
    const newRow = columnKeys.reduce((acc, col) => {
      acc[col] = '';
      return acc;
    }, {} as any);
    
    const newData = [...data, newRow];
    setData(newData);
    onDataChange?.(newData);
  }, [data, columnKeys, onDataChange]);

  // Delete row
  const handleDeleteRow = useCallback((rowIndex: number, row: any) => {
    const newData = data.filter((_, index) => index !== rowIndex);
    setData(newData);
    onDataChange?.(newData);
  }, [data, onDataChange]);

  // Copy to clipboard
  const copyToClipboard = useCallback(() => {
    const headers = columnKeys.join('\t');
    const rows = data.map(row =>
      columnKeys.map(col => row[col] ?? '').join('\t')
    );
    const text = [headers, ...rows].join('\n');
    navigator.clipboard.writeText(text);
  }, [data, columnKeys]);

  // Build column definitions
  const columns = useMemo<ColumnDef<any>[]>(() => {
    const cols: ColumnDef<any>[] = [];

    // Add delete column if editable
    if (editable) {
      cols.push({
        id: '_actions',
        header: () => null,
        cell: ({ row, table }) => {
          const rowIndex = table.getRowModel().rows.findIndex(r => r.id === row.id);
          return (
            <Button
              onClick={() => handleDeleteRow(rowIndex, row.original)}
              size="sm"
              variant="ghost"
              className="h-6 w-6 p-0"
            >
              <Trash2 className="h-3 w-3 text-red-500" />
            </Button>
          );
        },
        enableSorting: false,
        enableHiding: false,
        size: 48,
      });
    }

    // Add data columns
    columnKeys.forEach((columnKey) => {
      cols.push({
        id: columnKey,
        accessorKey: columnKey,
        header: () => (
          <span className="font-medium">
            {columnKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
          </span>
        ),
        cell: ({ row, column }) => {
          const rowId = row.id;
          const columnId = column.id;
          const isEditing = editingCell?.rowId === rowId && editingCell?.columnId === columnId;
          const cellValue = row.getValue(columnKey);

          if (isEditing) {
            return (
              <div className="flex items-center gap-1">
                <Input
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      handleEditSave(rowId, columnId);
                    }
                    if (e.key === 'Escape') {
                      handleEditCancel();
                    }
                  }}
                  className="h-6 text-xs"
                  autoFocus
                  onBlur={() => handleEditSave(rowId, columnId)}
                />
                <Button
                  onClick={() => handleEditSave(rowId, columnId)}
                  size="sm"
                  variant="ghost"
                  className="h-6 w-6 p-0"
                >
                  <Save className="h-3 w-3" />
                </Button>
                <Button
                  onClick={handleEditCancel}
                  size="sm"
                  variant="ghost"
                  className="h-6 w-6 p-0"
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
            );
          }

          return (
            <div
              className="flex items-center justify-between group font-mono text-sm"
              onDoubleClick={() => editable && handleEditStart(rowId, columnId, cellValue)}
            >
              <span>{formatCellValue(cellValue)}</span>
              {editable && (
                <Edit className="h-3 w-3 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
              )}
            </div>
          );
        },
        enableSorting: true,
      });
    });

    return cols;
  }, [columnKeys, editable, editingCell, editValue, handleEditStart, handleEditSave, handleEditCancel, handleDeleteRow]);

  // Prepare data with row IDs
  const tableData = useMemo(() => {
    return data.map((row, index) => ({
      ...row,
      id: row.id ?? row._id ?? `row-${index}`,
    }));
  }, [data]);

  return (
    <Card className="w-full">
      <div className="p-6 border-b">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-xl font-semibold">{title}</h3>
            {description && (
              <p className="text-sm text-gray-600 mt-1">{description}</p>
            )}
            <div className="flex items-center gap-2 mt-2">
              <Badge variant="outline">{data.length} rows</Badge>
              <Badge variant="outline">{columnKeys.length} columns</Badge>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            {editable && (
              <Button
                onClick={handleAddRow}
                size="sm"
                variant="outline"
                className="gap-2"
              >
                <Plus className="h-4 w-4" />
                Add Row
              </Button>
            )}
            <Button
              onClick={copyToClipboard}
              size="sm"
              variant="outline"
              className="gap-2"
            >
              <Copy className="h-4 w-4" />
              Copy
            </Button>
          </div>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={tableData}
        searchable={true}
        searchPlaceholder="Search all columns..."
        enablePagination={true}
        pageSize={10}
        exportable={true}
        exportFileName={exportFileName}
      />
    </Card>
  );
}
