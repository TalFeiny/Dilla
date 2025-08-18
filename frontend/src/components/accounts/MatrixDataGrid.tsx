'use client';

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { cn } from '@/lib/utils';
import { 
  Bot, 
  Zap, 
  Database,
  Download,
  Upload,
  RefreshCw,
  ChevronRight,
  Hash,
  Type,
  Calendar,
  DollarSign,
  Percent,
  Link2,
  Eye,
  EyeOff,
  Sparkles,
  GitBranch,
  Calculator
} from 'lucide-react';

interface CellData {
  id: string;
  value: any;
  formula?: string;
  type: 'number' | 'text' | 'formula' | 'currency' | 'percentage' | 'date';
  source?: string;
  confidence?: number;
  dependencies?: string[];
  history?: Array<{
    value: any;
    timestamp: string;
    agent?: string;
  }>;
}

interface GridColumn {
  id: string;
  name: string;
  type: 'number' | 'text' | 'formula' | 'currency' | 'percentage' | 'date';
  width?: number;
  formula?: string;
  editable?: boolean;
}

interface GridRow {
  id: string;
  cells: Record<string, CellData>;
}

interface CausalLink {
  from: string;
  to: string;
  strength: number;
  type: 'drives' | 'inhibits' | 'correlates';
}

export default function MatrixDataGrid() {
  const [columns, setColumns] = useState<GridColumn[]>([
    { id: 'period', name: 'Period', type: 'text', width: 100 },
    { id: 'revenue', name: 'Revenue', type: 'currency', width: 120 },
    { id: 'expenses', name: 'Expenses', type: 'currency', width: 120 },
    { id: 'netIncome', name: 'Net Income', type: 'formula', width: 120, formula: '=revenue-expenses' },
    { id: 'margin', name: 'Margin %', type: 'formula', width: 100, formula: '=netIncome/revenue' },
    { id: 'growth', name: 'Growth', type: 'percentage', width: 100 },
  ]);

  const [rows, setRows] = useState<GridRow[]>([
    {
      id: 'q1_2024',
      cells: {
        period: { id: 'q1_2024_period', value: 'Q1 2024', type: 'text' },
        revenue: { id: 'q1_2024_revenue', value: 2250000, type: 'currency', source: 'Financial Statement' },
        expenses: { id: 'q1_2024_expenses', value: 1450000, type: 'currency', source: 'Financial Statement' },
        netIncome: { id: 'q1_2024_netIncome', value: 800000, type: 'formula', dependencies: ['revenue', 'expenses'] },
        margin: { id: 'q1_2024_margin', value: 0.355, type: 'percentage', dependencies: ['netIncome', 'revenue'] },
        growth: { id: 'q1_2024_growth', value: 0, type: 'percentage' },
      }
    },
    {
      id: 'q2_2024',
      cells: {
        period: { id: 'q2_2024_period', value: 'Q2 2024', type: 'text' },
        revenue: { id: 'q2_2024_revenue', value: 2450000, type: 'currency', source: 'Financial Statement' },
        expenses: { id: 'q2_2024_expenses', value: 1580000, type: 'currency', source: 'Financial Statement' },
        netIncome: { id: 'q2_2024_netIncome', value: 870000, type: 'formula', dependencies: ['revenue', 'expenses'] },
        margin: { id: 'q2_2024_margin', value: 0.355, type: 'percentage', dependencies: ['netIncome', 'revenue'] },
        growth: { id: 'q2_2024_growth', value: 0.089, type: 'percentage' },
      }
    },
    {
      id: 'q3_2024',
      cells: {
        period: { id: 'q3_2024_period', value: 'Q3 2024', type: 'text' },
        revenue: { id: 'q3_2024_revenue', value: 2650000, type: 'currency', source: 'Financial Statement' },
        expenses: { id: 'q3_2024_expenses', value: 1720000, type: 'currency', source: 'Financial Statement' },
        netIncome: { id: 'q3_2024_netIncome', value: 930000, type: 'formula', dependencies: ['revenue', 'expenses'] },
        margin: { id: 'q3_2024_margin', value: 0.351, type: 'percentage', dependencies: ['netIncome', 'revenue'] },
        growth: { id: 'q3_2024_growth', value: 0.082, type: 'percentage' },
      }
    },
    {
      id: 'q4_2024',
      cells: {
        period: { id: 'q4_2024_period', value: 'Q4 2024', type: 'text' },
        revenue: { id: 'q4_2024_revenue', value: 2850000, type: 'currency', source: 'Financial Statement' },
        expenses: { id: 'q4_2024_expenses', value: 1850000, type: 'currency', source: 'Financial Statement' },
        netIncome: { id: 'q4_2024_netIncome', value: 1000000, type: 'formula', dependencies: ['revenue', 'expenses'] },
        margin: { id: 'q4_2024_margin', value: 0.351, type: 'percentage', dependencies: ['netIncome', 'revenue'] },
        growth: { id: 'q4_2024_growth', value: 0.075, type: 'percentage' },
      }
    }
  ]);

  const [selectedCell, setSelectedCell] = useState<string | null>(null);
  const [showFormulas, setShowFormulas] = useState(false);
  const [showSources, setShowSources] = useState(true);
  const [agentMode, setAgentMode] = useState(false);
  const [causalLinks, setCausalLinks] = useState<CausalLink[]>([
    { from: 'revenue', to: 'netIncome', strength: 1.0, type: 'drives' },
    { from: 'expenses', to: 'netIncome', strength: -1.0, type: 'inhibits' },
    { from: 'netIncome', to: 'margin', strength: 0.8, type: 'drives' },
  ]);
  const [isCalculating, setIsCalculating] = useState(false);
  const gridRef = useRef<HTMLDivElement>(null);

  // Format cell value based on type
  const formatValue = (value: any, type: string): string => {
    if (value === null || value === undefined) return '';
    
    switch (type) {
      case 'currency':
        return new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: 'USD',
          minimumFractionDigits: 0,
          maximumFractionDigits: 0,
        }).format(Number(value));
      case 'percentage':
        return `${(Number(value) * 100).toFixed(1)}%`;
      case 'number':
        return new Intl.NumberFormat('en-US').format(Number(value));
      default:
        return String(value);
    }
  };

  // Recalculate formulas
  const recalculate = useCallback(() => {
    setIsCalculating(true);
    
    setRows(prevRows => {
      return prevRows.map(row => {
        const newRow = { ...row };
        const newCells = { ...row.cells };
        
        // Calculate net income
        if (newCells.netIncome && newCells.revenue && newCells.expenses) {
          newCells.netIncome.value = newCells.revenue.value - newCells.expenses.value;
        }
        
        // Calculate margin
        if (newCells.margin && newCells.netIncome && newCells.revenue) {
          newCells.margin.value = newCells.revenue.value > 0 
            ? newCells.netIncome.value / newCells.revenue.value 
            : 0;
        }
        
        newRow.cells = newCells;
        return newRow;
      });
    });
    
    setTimeout(() => setIsCalculating(false), 300);
  }, []);

  // Update cell value
  const updateCell = (rowId: string, columnId: string, value: any) => {
    setRows(prevRows => {
      return prevRows.map(row => {
        if (row.id === rowId) {
          const newRow = { ...row };
          const newCells = { ...row.cells };
          
          if (newCells[columnId]) {
            newCells[columnId] = {
              ...newCells[columnId],
              value,
              history: [
                ...(newCells[columnId].history || []),
                {
                  value: newCells[columnId].value,
                  timestamp: new Date().toISOString(),
                  agent: agentMode ? 'AI Agent' : 'User'
                }
              ]
            };
          }
          
          newRow.cells = newCells;
          return newRow;
        }
        return row;
      });
    });
    
    // Trigger recalculation
    setTimeout(() => recalculate(), 0);
  };

  // Export to CSV
  const exportData = () => {
    const headers = columns.map(col => col.name).join(',');
    const data = rows.map(row => 
      columns.map(col => {
        const cell = row.cells[col.id];
        return cell ? formatValue(cell.value, cell.type) : '';
      }).join(',')
    ).join('\n');
    
    const csv = `${headers}\n${data}`;
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'matrix_data.csv';
    a.click();
    window.URL.revokeObjectURL(url);
  };

  // Agent API
  const agentAPI = useMemo(() => ({
    getValue: (rowId: string, columnId: string) => {
      const row = rows.find(r => r.id === rowId);
      return row?.cells[columnId]?.value;
    },
    setValue: (rowId: string, columnId: string, value: any) => {
      updateCell(rowId, columnId, value);
    },
    getFormula: (columnId: string) => {
      const column = columns.find(c => c.id === columnId);
      return column?.formula;
    },
    getCausalChain: (columnId: string) => {
      return causalLinks.filter(link => link.to === columnId || link.from === columnId);
    },
    runWhatIf: (changes: Array<{ rowId: string; columnId: string; value: any }>) => {
      // Simulate changes without applying them
      const tempRows = [...rows];
      changes.forEach(change => {
        const row = tempRows.find(r => r.id === change.rowId);
        if (row?.cells[change.columnId]) {
          row.cells[change.columnId].value = change.value;
        }
      });
      // Return predicted outcomes
      return tempRows;
    }
  }), [rows, columns, causalLinks]);

  // Expose API for agents
  useEffect(() => {
    if (agentMode) {
      (window as any).matrixAPI = agentAPI;
    }
  }, [agentMode, agentAPI]);

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between p-3 bg-white border border-gray-200 rounded-lg">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowFormulas(!showFormulas)}
            className={cn(
              "px-3 py-1.5 text-sm font-medium rounded-md transition-colors",
              showFormulas 
                ? "bg-gray-900 text-white" 
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            )}
          >
            <Calculator className="w-4 h-4 inline mr-1" />
            Formulas
          </button>
          
          <button
            onClick={() => setShowSources(!showSources)}
            className={cn(
              "px-3 py-1.5 text-sm font-medium rounded-md transition-colors",
              showSources 
                ? "bg-gray-900 text-white" 
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            )}
          >
            <Link2 className="w-4 h-4 inline mr-1" />
            Sources
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
            Agent Mode
          </button>
          
          <div className="w-px h-6 bg-gray-300 mx-1" />
          
          <button
            onClick={recalculate}
            disabled={isCalculating}
            className="px-3 py-1.5 text-sm font-medium bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={cn("w-4 h-4 inline mr-1", isCalculating && "animate-spin")} />
            Recalculate
          </button>
          
          <button
            onClick={exportData}
            className="px-3 py-1.5 text-sm font-medium bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition-colors"
          >
            <Download className="w-4 h-4 inline mr-1" />
            Export
          </button>
        </div>
        
        <div className="flex items-center gap-2 text-sm">
          {isCalculating && (
            <span className="text-gray-500 animate-pulse">Calculating...</span>
          )}
          <Zap className="w-4 h-4 text-gray-400" />
          <span className="text-gray-600">Live Engine</span>
        </div>
      </div>

      {/* Main Grid */}
      <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
        <div className="overflow-auto max-h-[600px]" ref={gridRef}>
          <table className="w-full">
            <thead className="sticky top-0 z-10 bg-gray-50 border-b border-gray-200">
              <tr>
                {columns.map(column => (
                  <th
                    key={column.id}
                    className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider"
                    style={{ width: column.width || 'auto' }}
                  >
                    <div className="flex items-center gap-2">
                      {column.type === 'currency' && <DollarSign className="w-3 h-3" />}
                      {column.type === 'percentage' && <Percent className="w-3 h-3" />}
                      {column.type === 'formula' && <Calculator className="w-3 h-3" />}
                      {column.type === 'text' && <Type className="w-3 h-3" />}
                      {column.name}
                    </div>
                    {showFormulas && column.formula && (
                      <div className="text-xs font-normal text-gray-500 mt-1">
                        {column.formula}
                      </div>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {rows.map((row, rowIndex) => (
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
                          cell?.type === 'formula' && "bg-gray-50",
                          isSelected && "ring-2 ring-gray-900 ring-inset",
                          "cursor-pointer"
                        )}
                        onClick={() => setSelectedCell(cellId)}
                      >
                        <div>
                          <div className="font-medium text-gray-900">
                            {cell ? formatValue(cell.value, cell.type) : ''}
                          </div>
                          {showSources && cell?.source && (
                            <div className="text-xs text-gray-500 mt-1">
                              {cell.source}
                            </div>
                          )}
                          {showFormulas && cell?.dependencies && (
                            <div className="text-xs text-gray-400 mt-1">
                              → {cell.dependencies.join(', ')}
                            </div>
                          )}
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

      {/* Causal Relationships */}
      <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg">
        <div className="flex items-center gap-2 mb-3">
          <GitBranch className="w-4 h-4 text-gray-600" />
          <h3 className="text-sm font-medium text-gray-900">Causal Relationships</h3>
        </div>
        <div className="flex flex-wrap gap-2">
          {causalLinks.map((link, index) => (
            <div
              key={index}
              className="px-3 py-1 bg-white border border-gray-200 rounded-full text-xs flex items-center gap-2"
            >
              <span className="font-medium">{link.from}</span>
              <ChevronRight className="w-3 h-3" />
              <span className={cn(
                "font-medium",
                link.type === 'drives' && "text-green-600",
                link.type === 'inhibits' && "text-red-600",
                link.type === 'correlates' && "text-blue-600"
              )}>
                {link.to}
              </span>
              <span className="text-gray-400">
                ({(link.strength * 100).toFixed(0)}%)
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Agent Console */}
      {agentMode && (
        <div className="p-4 bg-gray-900 text-gray-100 rounded-lg font-mono text-xs">
          <div className="flex items-center gap-2 mb-3">
            <Bot className="w-4 h-4" />
            <span className="font-bold">Agent API Console</span>
            <Sparkles className="w-3 h-3 text-yellow-400 animate-pulse" />
          </div>
          <div className="space-y-2">
            <div className="text-gray-400"># Get value</div>
            <div className="pl-4">matrixAPI.getValue('q4_2024', 'revenue') → {formatValue(2850000, 'currency')}</div>
            
            <div className="text-gray-400"># Set value</div>
            <div className="pl-4">matrixAPI.setValue('q4_2024', 'revenue', 3000000)</div>
            
            <div className="text-gray-400"># Get formula</div>
            <div className="pl-4">matrixAPI.getFormula('netIncome') → "=revenue-expenses"</div>
            
            <div className="text-gray-400"># What-if analysis</div>
            <div className="pl-4">matrixAPI.runWhatIf([{'{ rowId: "q4_2024", columnId: "revenue", value: 3500000 }'}])</div>
            
            <div className="text-gray-400"># Get causal chain</div>
            <div className="pl-4">matrixAPI.getCausalChain('margin') → [revenue → netIncome → margin]</div>
          </div>
        </div>
      )}
    </div>
  );
}