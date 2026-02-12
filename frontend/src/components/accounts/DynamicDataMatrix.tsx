'use client';

import React, { useState, useEffect, useMemo, useRef } from 'react';
import { cn } from '@/lib/utils';
import { formatCurrency, formatPercentage, formatNumber } from '@/lib/format-utils';
import { 
  Bot, 
  Zap, 
  Database,
  Download,
  RefreshCw,
  DollarSign,
  Percent,
  Link2,
  Sparkles,
  ExternalLink,
  FileText,
  Globe,
  Search,
  Plus,
  X,
  ChevronDown
} from 'lucide-react';

interface Citation {
  id: string;
  title: string;
  url: string;
  source: string;
  date: string;
  excerpt?: string;
}

interface CellData {
  id: string;
  value: any;
  displayValue?: string;
  type: 'number' | 'text' | 'currency' | 'percentage' | 'date' | 'link' | 'boolean' | 'json';
  citations?: Citation[];
  confidence?: number;
  metadata?: Record<string, any>;
  history?: Array<{
    value: any;
    timestamp: string;
    agent?: string;
    source?: string;
  }>;
}

interface GridColumn {
  id: string;
  name: string;
  type: 'number' | 'text' | 'currency' | 'percentage' | 'date' | 'link' | 'boolean' | 'json' | 'dynamic';
  width?: number;
  editable?: boolean;
  sortable?: boolean;
  filterable?: boolean;
}

interface GridRow {
  id: string;
  cells: Record<string, CellData>;
}

interface DataSource {
  type: 'database' | 'api' | 'web' | 'manual' | 'agent';
  name: string;
  lastUpdated: string;
  reliability: number;
}

export default function DynamicDataMatrix() {
  const [columns, setColumns] = useState<GridColumn[]>([]);
  const [rows, setRows] = useState<GridRow[]>([]);
  const [selectedCell, setSelectedCell] = useState<string | null>(null);
  const [showCitations, setShowCitations] = useState(true);
  // Removed formula support - this is a research tool, not Excel
  const [agentMode, setAgentMode] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [expandedCitations, setExpandedCitations] = useState<Set<string>>(new Set());
  const gridRef = useRef<HTMLDivElement>(null);

  // Load dynamic data based on user query
  const loadData = async (query: string) => {
    console.log('Loading data for query:', query);
    setIsLoading(true);
    try {
      const response = await fetch('/api/agent/dynamic-data-v2', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query,
          includesCitations: true,
          date: 'August 25, 2025'
        })
      });

      console.log('Response status:', response.status);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const response_data = await response.json();
      console.log('Received data:', response_data);
      
      // Handle unified-brain response format
      const data = response_data.success && response_data.result ? response_data.result : response_data;
      
      // Dynamically create columns based on data structure
      if (data.columns && data.columns.length > 0) {
        console.log('Setting columns:', data.columns.length);
        setColumns(data.columns);
      } else {
        console.error('No columns in response');
      }
      
      // Set rows with citations
      if (data.rows && data.rows.length > 0) {
        console.log('Setting rows:', data.rows.length);
        setRows(data.rows);
      } else {
        console.error('No rows in response');
      }
      
      // Update data sources
      if (data.sources && data.sources.length > 0) {
        console.log('Setting sources:', data.sources.length);
        setDataSources(data.sources);
      }
    } catch (error) {
      console.error('Failed to load data:', error);
      alert(`Error loading data: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Format cell value based on type with proper formatting
  const formatValue = (cell: CellData): JSX.Element => {
    if (!cell || cell.value === null || cell.value === undefined) {
      return <span className="text-gray-400">—</span>;
    }

    // Use displayValue if provided
    if (cell.displayValue) {
      return <span>{cell.displayValue}</span>;
    }
    
    switch (cell.type) {
      case 'currency':
        return (
          <span className="font-mono">
            {formatCurrency(Number(cell.value))}
          </span>
        );
      
      case 'percentage':
        return (
          <span className="font-mono">
            {formatPercentage(Number(cell.value) * 100)}
          </span>
        );
      
      case 'number':
        return (
          <span className="font-mono">
            {formatNumber(Number(cell.value))}
          </span>
        );
      
      case 'link':
        return (
          <a 
            href={String(cell.value)} 
            target="_blank" 
            rel="noopener noreferrer"
            className="text-blue-600 hover:text-blue-800 underline flex items-center gap-1"
          >
            <span className="truncate">{cell.metadata?.title || 'Link'}</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        );
      
      case 'boolean':
        return (
          <span className={cn(
            "px-2 py-0.5 rounded text-xs font-medium",
            cell.value ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-800"
          )}>
            {cell.value ? 'Yes' : 'No'}
          </span>
        );
      
      case 'json':
        return (
          <details className="cursor-pointer">
            <summary className="text-xs text-gray-600">
              {Object.keys(cell.value).length} fields
            </summary>
            <pre className="text-xs mt-1 p-1 bg-gray-50 rounded overflow-auto max-w-xs">
              {JSON.stringify(cell.value, null, 2)}
            </pre>
          </details>
        );
      
      case 'date':
        return (
          <span className="text-gray-700">
            {new Date(cell.value).toLocaleDateString('en-US', {
              year: 'numeric',
              month: 'short',
              day: 'numeric'
            })}
          </span>
        );
      
      default:
        return <span>{String(cell.value)}</span>;
    }
  };

  // Render citations for a cell
  const renderCitations = (cell: CellData) => {
    if (!cell.citations || cell.citations.length === 0) return null;
    
    const cellId = cell.id;
    const isExpanded = expandedCitations.has(cellId);
    
    return (
      <div className="mt-1">
        <button
          onClick={(e) => {
            e.stopPropagation();
            setExpandedCitations(prev => {
              const next = new Set(prev);
              if (next.has(cellId)) {
                next.delete(cellId);
              } else {
                next.add(cellId);
              }
              return next;
            });
          }}
          className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
        >
          <FileText className="w-3 h-3" />
          {cell.citations.length} source{cell.citations.length > 1 ? 's' : ''}
          <ChevronDown className={cn(
            "w-3 h-3 transition-transform",
            isExpanded && "transform rotate-180"
          )} />
        </button>
        
        {isExpanded && (
          <div className="mt-2 space-y-1">
            {cell.citations.map((citation, idx) => (
              <div key={citation.id} className="flex items-start gap-2 p-2 bg-blue-50 rounded text-xs">
                <span className="font-medium text-blue-900">{idx + 1}.</span>
                <div className="flex-1">
                  <a 
                    href={citation.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-blue-700 hover:text-blue-900 underline"
                  >
                    {citation.title}
                  </a>
                  <div className="text-gray-600 mt-0.5">
                    {citation.source} • {citation.date}
                  </div>
                  {citation.excerpt && (
                    <div className="text-gray-700 mt-1 italic">
                      "{citation.excerpt}"
                    </div>
                  )}
                </div>
                <ExternalLink className="w-3 h-3 text-blue-600" />
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // Add new column
  const addColumn = () => {
    const newColumn: GridColumn = {
      id: `col_${Date.now()}`,
      name: 'New Column',
      type: 'text',
      editable: true,
      sortable: true
    };
    setColumns([...columns, newColumn]);
  };

  // Remove column
  const removeColumn = (columnId: string) => {
    setColumns(columns.filter(col => col.id !== columnId));
    setRows(rows.map(row => {
      const { [columnId]: _, ...restCells } = row.cells;
      return { ...row, cells: restCells };
    }));
  };

  // Export to CSV with citations
  const exportData = () => {
    const headers = [...columns.map(col => col.name), 'Citations'].join(',');
    const data = rows.map(row => 
      [...columns.map(col => {
        const cell = row.cells[col.id];
        if (!cell) return '';
        
        // Get raw value for export
        let value = cell.value;
        if (cell.type === 'currency' || cell.type === 'number') {
          value = Number(value);
        }
        return JSON.stringify(value);
      }), 
      // Add citations column
      columns.map(col => {
        const cell = row.cells[col.id];
        if (cell?.citations?.length) {
          return cell.citations.map(c => c.url).join('; ');
        }
        return '';
      }).filter(Boolean).join('; ')
      ].join(',')
    ).join('\n');
    
    const csv = `${headers}\n${data}`;
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `data_matrix_${new Date().toISOString()}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  // Agent API for programmatic access
  const agentAPI = useMemo(() => ({
    loadData,
    addColumn,
    removeColumn,
    getValue: (rowId: string, columnId: string) => {
      const row = rows.find(r => r.id === rowId);
      return row?.cells[columnId];
    },
    setValue: (rowId: string, columnId: string, value: any, citations?: Citation[]) => {
      setRows(prevRows => prevRows.map(row => {
        if (row.id === rowId) {
          return {
            ...row,
            cells: {
              ...row.cells,
              [columnId]: {
                ...row.cells[columnId],
                value,
                citations: citations || row.cells[columnId]?.citations
              }
            }
          };
        }
        return row;
      }));
    },
    getCitations: (rowId: string, columnId: string) => {
      const row = rows.find(r => r.id === rowId);
      return row?.cells[columnId]?.citations || [];
    }
  }), [rows, columns]);

  // Expose API for agents
  useEffect(() => {
    if (typeof window !== 'undefined') {
      (window as any).dataMatrix = agentAPI;
    }
  }, [agentAPI]);

  // Load real data on component mount
  useEffect(() => {
    // Auto-load research data on mount - adapt columns to query
    loadData('Compare top AI companies by market position, technology differentiation, and growth metrics');
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  

  return (
    <div className="space-y-4">
      {/* Search Bar */}
      <div className="flex gap-2">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Research anything (e.g., 'Compare cloud providers by performance and pricing' or 'Analyze fintech market trends in Europe')"
            className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-900"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && e.currentTarget.value) {
                loadData(e.currentTarget.value);
              }
            }}
          />
        </div>
        <button
          onClick={addColumn}
          className="px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Add Column
        </button>
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-between p-3 bg-white border border-gray-200 rounded-lg">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowCitations(!showCitations)}
            className={cn(
              "px-3 py-1.5 text-sm font-medium rounded-md transition-colors",
              showCitations 
                ? "bg-gray-900 text-white" 
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            )}
          >
            <Link2 className="w-4 h-4 inline mr-1" />
            Citations
          </button>
          
          
          <button
            onClick={() => setAgentMode(!agentMode)}
            className={cn(
              "px-3 py-1.5 text-sm font-medium rounded-md transition-colors",
              agentMode 
                ? "bg-gray-900 text-white" 
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            )}
          >
            <Bot className="w-4 h-4 inline mr-1" />
            Agent API
          </button>
          
          <div className="w-px h-6 bg-gray-300 mx-1" />
          
          <button
            onClick={exportData}
            className="px-3 py-1.5 text-sm font-medium bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition-colors"
          >
            <Download className="w-4 h-4 inline mr-1" />
            Export
          </button>
        </div>
        
        <div className="flex items-center gap-3 text-sm">
          {/* Data Sources Indicator */}
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-gray-400" />
            <span className="text-gray-600">{dataSources.length} sources</span>
          </div>
          
          {isLoading && (
            <div className="flex items-center gap-2">
              <RefreshCw className="w-4 h-4 animate-spin text-gray-600" />
              <span className="text-gray-600">Loading...</span>
            </div>
          )}
          
          <Zap className="w-4 h-4 text-yellow-500" />
          <span className="text-gray-600">Live Data</span>
        </div>
      </div>

      {/* Main Grid */}
      <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
        <div className="overflow-auto max-h-96" ref={gridRef}>
          <table className="w-full">
            <thead className="sticky top-0 z-10 bg-gray-50 border-b border-gray-200">
              <tr>
                {columns.map(column => (
                  <th
                    key={column.id}
                    className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider group"
                    style={{ width: column.width || 'auto' }}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {column.type === 'currency' && <DollarSign className="w-3 h-3" />}
                        {column.type === 'percentage' && <Percent className="w-3 h-3" />}
                        {column.type === 'link' && <Globe className="w-3 h-3" />}
                        {column.name}
                      </div>
                      <button
                        onClick={() => removeColumn(column.id)}
                        className="opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <X className="w-3 h-3 text-gray-400 hover:text-red-600" />
                      </button>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {rows.map((row) => (
                <tr key={row.id} className="hover:bg-gray-50 transition-colors">
                  {columns.map(column => {
                    const cell = row.cells[column.id];
                    const cellId = `${row.id}_${column.id}`;
                    const isSelected = selectedCell === cellId;
                    
                    return (
                      <td
                        key={column.id}
                        className={cn(
                          "px-4 py-3 text-sm",
                          column.type === 'currency' || column.type === 'percentage' || column.type === 'number'
                            ? "text-right"
                            : "text-left",
                          isSelected && "ring-2 ring-gray-900 ring-inset",
                          "cursor-pointer"
                        )}
                        onClick={() => setSelectedCell(cellId)}
                      >
                        <div>
                          <div className="font-medium text-gray-900">
                            {cell ? formatValue(cell) : <span className="text-gray-400">—</span>}
                          </div>
                          
                          {/* Confidence Indicator */}
                          {cell?.confidence !== undefined && (
                            <div className="flex items-center gap-1 mt-1">
                              <div className="flex gap-0.5">
                                {[1, 2, 3, 4, 5].map(i => (
                                  <div
                                    key={i}
                                    className={cn(
                                      "w-1 h-3",
                                      i <= Math.round((cell.confidence || 0) * 5)
                                        ? "bg-green-500"
                                        : "bg-gray-200"
                                    )}
                                  />
                                ))}
                              </div>
                              <span className="text-xs text-gray-500">
                                {Math.round(cell.confidence * 100)}% confidence
                              </span>
                            </div>
                          )}
                          
                          {/* Citations */}
                          {showCitations && cell && renderCitations(cell)}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Minimal Data Source Indicator */}
      {dataSources.length > 0 && (
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <Globe className="w-3 h-3" />
          <span>Live data from {dataSources.length} source{dataSources.length > 1 ? 's' : ''}</span>
        </div>
      )}

      {/* Agent API Console */}
      {agentMode && (
        <div className="p-4 bg-gray-900 text-gray-100 rounded-lg font-mono text-xs">
          <div className="flex items-center gap-2 mb-3">
            <Bot className="w-4 h-4" />
            <span className="font-bold">Research Matrix API</span>
            <Sparkles className="w-3 h-3 text-yellow-400" />
          </div>
          <div className="space-y-2">
            <div className="text-green-400"># Research any topic - columns adapt to data</div>
            <div className="pl-4">dataMatrix.loadData("Compare AI infrastructure providers by performance metrics")</div>
            <div className="pl-4">dataMatrix.loadData("Market analysis of European fintech companies")</div>
            <div className="pl-4">dataMatrix.loadData("Technical comparison of LLM models with benchmarks")</div>
            
            <div className="text-green-400"># Get research data with citations</div>
            <div className="pl-4">dataMatrix.getValue('row1', 'market_share')</div>
            <div className="pl-8 text-gray-500">→ {`{ value: 0.34, displayValue: "34%", citations: [...], confidence: 85 }`}</div>
            
            <div className="text-green-400"># Access all sources for verification</div>
            <div className="pl-4">dataMatrix.getCitations('row1', 'competitive_advantage')</div>
            
            <div className="text-green-400"># Export research results</div>
            <div className="pl-4">dataMatrix.exportData()</div>
          </div>
        </div>
      )}
    </div>
  );
}