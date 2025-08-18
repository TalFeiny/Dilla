'use client';

import React, { useState, useMemo } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Download,
  Filter,
  ArrowUpDown,
  Copy,
  FileSpreadsheet,
  Search,
  ChevronLeft,
  ChevronRight,
  MoreHorizontal,
  Edit,
  Save,
  X,
  Plus,
  Trash2
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
  const [searchTerm, setSearchTerm] = useState('');
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [editingCell, setEditingCell] = useState<{ row: number; col: string } | null>(null);
  const [editValue, setEditValue] = useState('');

  // Auto-detect columns if not provided
  const columns = useMemo(() => {
    if (initialColumns) return initialColumns;
    if (!data || data.length === 0) return [];
    
    // Get all unique keys from all objects
    const allKeys = new Set<string>();
    data.forEach(item => {
      Object.keys(item).forEach(key => allKeys.add(key));
    });
    return Array.from(allKeys);
  }, [initialColumns, data]);

  // Filter data based on search
  const filteredData = useMemo(() => {
    if (!searchTerm) return data;
    
    return data.filter(row =>
      Object.values(row).some(value =>
        String(value).toLowerCase().includes(searchTerm.toLowerCase())
      )
    );
  }, [data, searchTerm]);

  // Sort data
  const sortedData = useMemo(() => {
    if (!sortColumn) return filteredData;
    
    return [...filteredData].sort((a, b) => {
      const aVal = a[sortColumn];
      const bVal = b[sortColumn];
      
      if (aVal === null || aVal === undefined) return 1;
      if (bVal === null || bVal === undefined) return -1;
      
      let comparison = 0;
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        comparison = aVal - bVal;
      } else {
        comparison = String(aVal).localeCompare(String(bVal));
      }
      
      return sortDirection === 'asc' ? comparison : -comparison;
    });
  }, [filteredData, sortColumn, sortDirection]);

  // Paginate data
  const paginatedData = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    const end = start + pageSize;
    return sortedData.slice(start, end);
  }, [sortedData, currentPage, pageSize]);

  const totalPages = Math.ceil(sortedData.length / pageSize);

  // Handle sorting
  const handleSort = (column: string) => {
    if (sortColumn === column) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
  };

  // Export to CSV
  const exportToCSV = () => {
    const headers = columns.join(',');
    const rows = sortedData.map(row =>
      columns.map(col => {
        const value = row[col];
        // Escape commas and quotes in CSV
        if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
          return `"${value.replace(/"/g, '""')}"`;
        }
        return value ?? '';
      }).join(',')
    );
    
    const csv = [headers, ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${exportFileName}-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Export to JSON
  const exportToJSON = () => {
    const json = JSON.stringify(sortedData, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${exportFileName}-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Copy to clipboard
  const copyToClipboard = () => {
    const headers = columns.join('\t');
    const rows = paginatedData.map(row =>
      columns.map(col => row[col] ?? '').join('\t')
    );
    const text = [headers, ...rows].join('\n');
    navigator.clipboard.writeText(text);
  };

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
  const handleEditStart = (rowIndex: number, column: string) => {
    if (!editable) return;
    setEditingCell({ row: rowIndex, col: column });
    setEditValue(String(paginatedData[rowIndex][column] ?? ''));
  };

  const handleEditSave = () => {
    if (!editingCell) return;
    
    const newData = [...data];
    const globalRowIndex = (currentPage - 1) * pageSize + editingCell.row;
    newData[globalRowIndex] = {
      ...newData[globalRowIndex],
      [editingCell.col]: editValue
    };
    
    setData(newData);
    onDataChange?.(newData);
    setEditingCell(null);
  };

  const handleEditCancel = () => {
    setEditingCell(null);
    setEditValue('');
  };

  // Add new row
  const handleAddRow = () => {
    const newRow = columns.reduce((acc, col) => {
      acc[col] = '';
      return acc;
    }, {} as any);
    
    const newData = [...data, newRow];
    setData(newData);
    onDataChange?.(newData);
  };

  // Delete row
  const handleDeleteRow = (rowIndex: number) => {
    const globalRowIndex = (currentPage - 1) * pageSize + rowIndex;
    const newData = data.filter((_, index) => index !== globalRowIndex);
    setData(newData);
    onDataChange?.(newData);
  };

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
              <Badge variant="outline">{sortedData.length} rows</Badge>
              <Badge variant="outline">{columns.length} columns</Badge>
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
            <Button
              onClick={exportToCSV}
              size="sm"
              variant="outline"
              className="gap-2"
            >
              <FileSpreadsheet className="h-4 w-4" />
              CSV
            </Button>
            <Button
              onClick={exportToJSON}
              size="sm"
              variant="outline"
              className="gap-2"
            >
              <Download className="h-4 w-4" />
              JSON
            </Button>
          </div>
        </div>

        {/* Search and filter bar */}
        <div className="flex items-center gap-4">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              placeholder="Search all columns..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>
          
          <Select value={pageSize.toString()} onValueChange={(val) => setPageSize(Number(val))}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="10">10 rows</SelectItem>
              <SelectItem value="25">25 rows</SelectItem>
              <SelectItem value="50">50 rows</SelectItem>
              <SelectItem value="100">100 rows</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Data table */}
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              {editable && (
                <TableHead className="w-12">
                  <MoreHorizontal className="h-4 w-4" />
                </TableHead>
              )}
              {columns.map((column) => (
                <TableHead
                  key={column}
                  className="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800"
                  onClick={() => handleSort(column)}
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium">
                      {column.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </span>
                    <ArrowUpDown className="h-4 w-4 text-gray-400" />
                  </div>
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginatedData.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={columns.length + (editable ? 1 : 0)}
                  className="text-center py-8 text-gray-500"
                >
                  No data found
                </TableCell>
              </TableRow>
            ) : (
              paginatedData.map((row, rowIndex) => (
                <TableRow key={rowIndex} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                  {editable && (
                    <TableCell>
                      <Button
                        onClick={() => handleDeleteRow(rowIndex)}
                        size="sm"
                        variant="ghost"
                        className="h-6 w-6 p-0"
                      >
                        <Trash2 className="h-3 w-3 text-red-500" />
                      </Button>
                    </TableCell>
                  )}
                  {columns.map((column) => (
                    <TableCell
                      key={column}
                      className="font-mono text-sm"
                      onDoubleClick={() => handleEditStart(rowIndex, column)}
                    >
                      {editingCell?.row === rowIndex && editingCell?.col === column ? (
                        <div className="flex items-center gap-1">
                          <Input
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleEditSave();
                              if (e.key === 'Escape') handleEditCancel();
                            }}
                            className="h-6 text-xs"
                            autoFocus
                          />
                          <Button
                            onClick={handleEditSave}
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
                      ) : (
                        <div className="flex items-center justify-between group">
                          <span>{formatCellValue(row[column])}</span>
                          {editable && (
                            <Edit className="h-3 w-3 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                          )}
                        </div>
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between p-4 border-t">
          <div className="text-sm text-gray-600">
            Showing {((currentPage - 1) * pageSize) + 1} to{' '}
            {Math.min(currentPage * pageSize, sortedData.length)} of {sortedData.length} results
          </div>
          
          <div className="flex items-center gap-2">
            <Button
              onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
              disabled={currentPage === 1}
              size="sm"
              variant="outline"
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            
            <div className="flex items-center gap-1">
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                let pageNum;
                if (totalPages <= 5) {
                  pageNum = i + 1;
                } else if (currentPage <= 3) {
                  pageNum = i + 1;
                } else if (currentPage >= totalPages - 2) {
                  pageNum = totalPages - 4 + i;
                } else {
                  pageNum = currentPage - 2 + i;
                }
                
                return (
                  <Button
                    key={pageNum}
                    onClick={() => setCurrentPage(pageNum)}
                    size="sm"
                    variant={currentPage === pageNum ? 'default' : 'outline'}
                    className="w-8"
                  >
                    {pageNum}
                  </Button>
                );
              })}
            </div>
            
            <Button
              onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
              disabled={currentPage === totalPages}
              size="sm"
              variant="outline"
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}