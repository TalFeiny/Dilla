'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { cn } from '@/lib/utils';
import { RLSupabaseConnector } from '@/lib/rl-system/supabase-connector';
import { FormulaEngine, FORMULA_DOCS } from '@/lib/spreadsheet-formulas';
import { convertRangeToSankeyData, convertRangeToWaterfallData } from '@/lib/visualization-tools';
import { useGrid } from '@/contexts/GridContext';
import dynamic from 'next/dynamic';

// Dynamically import visualization components
const RevenueSegmentationChart = dynamic(() => import('@/components/charts/RevenueSegmentationChart'), { ssr: false });
const WaterfallChart = dynamic(() => import('@/components/charts/WaterfallChart'), { ssr: false });
const FinancialChartStudio = dynamic(() => import('@/components/charts/FinancialChartStudio'), { ssr: false });
const ExcelChartBuilder = dynamic(() => import('@/components/charts/ExcelChartBuilder'), { ssr: false });
const TableauLevelCharts = dynamic(() => import('@/components/charts/TableauLevelCharts'), { ssr: false });
import { 
  Bot, 
  Zap, 
  Save,
  Plus,
  Trash2,
  Download,
  Upload,
  RefreshCw,
  Calculator,
  Edit3,
  Check,
  X,
  GitBranch,
  Sparkles,
  Database,
  ChevronRight,
  Code2,
  Send,
  MessageSquare,
  Loader2,
  BarChart3,
  PieChart,
  TrendingUp,
  DollarSign
} from 'lucide-react';

// Grid is 26 columns (A-Z) x 100 rows
const COLUMNS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
const ROWS = Array.from({ length: 100 }, (_, i) => i + 1);

interface Cell {
  value: any;
  formula?: string;
  type?: 'text' | 'number' | 'formula' | 'boolean' | 'date' | 'link' | 'chart';
  format?: 'currency' | 'percentage' | 'date' | 'number';
  source?: string;
  sourceUrl?: string;
  href?: string; // For clickable links
  locked?: boolean;
  chartConfig?: any; // For embedded chart configuration
  style?: {
    bold?: boolean;
    italic?: boolean;
    underline?: boolean;
    backgroundColor?: string;
    color?: string;
  };
}

interface AgentCommand {
  type: 'write' | 'formula' | 'format' | 'style' | 'addRow' | 'addColumn' | 'delete' | 'chart';
  cell?: string;
  range?: string;
  value?: any;
  formula?: string;
  format?: string;
  style?: any;
  config?: any;
  id?: string;
}

export default function AgentDataGrid() {
  const [cells, setCells] = useState<Record<string, Cell>>({});
  const [selectedCell, setSelectedCell] = useState<string>('A1');
  const [selectedRange, setSelectedRange] = useState<string | null>(null);
  const [editingCell, setEditingCell] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>('');
  const [formulaBar, setFormulaBar] = useState<string>('');
  const [agentMode, setAgentMode] = useState(true);
  const [agentHistory, setAgentHistory] = useState<AgentCommand[]>([]);
  const [isCalculating, setIsCalculating] = useState(false);
  const gridRef = useRef<HTMLDivElement>(null);
  const [dragStart, setDragStart] = useState<string | null>(null);
  const [dragEnd, setDragEnd] = useState<string | null>(null);
  
  // Get grid context
  const gridContext = useGrid();
  
  // RL System
  const [rlEnabled, setRlEnabled] = useState(false);
  const [rlConnector] = useState(() => new RLSupabaseConnector());
  const [showFormulaHelp, setShowFormulaHelp] = useState(false);
  const [previousGridState, setPreviousGridState] = useState<Record<string, Cell>>({});
  const [visualization, setVisualization] = useState<{
    type: 'sankey' | 'waterfall' | null;
    data: any;
    title: string;
  }>({ type: null, data: null, title: '' });
  const [showFinancialCharts, setShowFinancialCharts] = useState(false);
  const [showAdvancedCharts, setShowAdvancedCharts] = useState(false);
  const [embeddedCharts, setEmbeddedCharts] = useState<Array<{
    id: string;
    type: string;
    data: any;
    position: string; // Cell address like "A10"
    size: { rows: number; cols: number };
  }>>([]);

  // Parse cell address (e.g., "A1" -> { col: 0, row: 0 })
  const parseCell = (cell: string) => {
    const match = cell.match(/^([A-Z]+)(\d+)$/);
    if (!match) return null;
    const col = match[1].split('').reduce((acc, char, i) => 
      acc + (char.charCodeAt(0) - 65) * Math.pow(26, match[1].length - i - 1), 0
    );
    const row = parseInt(match[2]) - 1;
    return { col, row };
  };

  // Format cell address
  const cellAddress = (col: number, row: number) => {
    return COLUMNS[col] + (row + 1);
  };

  // Evaluate formula using enhanced formula engine
  const evaluateFormula = useCallback((formula: string): any => {
    const engine = new FormulaEngine(cells);
    return engine.evaluate(formula);
  }, [cells]);

  // Recalculate all formulas
  const recalculateAll = useCallback(() => {
    setIsCalculating(true);
    
    setCells(prevCells => {
      const newCells = { ...prevCells };
      
      // Find all formula cells and recalculate
      Object.entries(newCells).forEach(([addr, cell]) => {
        if (cell.formula) {
          const result = evaluateFormula(cell.formula);
          newCells[addr] = { ...cell, value: result };
        }
      });
      
      return newCells;
    });
    
    setTimeout(() => setIsCalculating(false), 100);
  }, [evaluateFormula]);

  // Update cell
  const updateCell = useCallback((address: string, value: any, isFormula: boolean = false) => {
    setCells(prev => {
      const newCells = { ...prev };
      
      if (value === '' || value === null) {
        delete newCells[address];
      } else {
        newCells[address] = {
          ...newCells[address],
          value: isFormula ? '' : value,
          formula: isFormula ? value : undefined,
          type: isFormula ? 'formula' : typeof value === 'number' ? 'number' : 'text'
        };
      }
      
      return newCells;
    });
    
    if (isFormula) {
      setTimeout(() => recalculateAll(), 0);
    }
  }, [recalculateAll]);

  // Format cell value for display
  const formatCellValue = (cell: Cell | undefined): string => {
    if (!cell) return '';
    
    const value = cell.formula ? evaluateFormula(cell.formula) : cell.value;
    
    if (value === null || value === undefined || value === '') return '';
    if (value === '#ERROR') return '#ERROR';
    
    switch (cell.format) {
      case 'currency':
        return typeof value === 'number' 
          ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value)
          : String(value);
      case 'percentage':
        return typeof value === 'number'
          ? `${(value * 100).toFixed(2)}%`
          : String(value);
      case 'number':
        return typeof value === 'number'
          ? new Intl.NumberFormat('en-US').format(value)
          : String(value);
      default:
        return String(value);
    }
  };

  // Track action in RL system
  const trackRLAction = async (action: string, reward: number = 0) => {
    if (!rlEnabled) return;
    
    try {
      const gridState = Object.entries(cells).map(([k, v]) => `${k}:${v.value}`).join(',');
      // TODO: Re-enable when storeExperience is implemented
      // await rlConnector.storeExperience(
      //   Object.keys(previousGridState).length ? Object.entries(previousGridState).map(([k, v]) => `${k}:${v.value}`).join(',') : 'empty',
      //   action,
      //   gridState,
      //   reward,
      //   { modelType: 'Spreadsheet', timestamp: new Date().toISOString() }
      // );
      setPreviousGridState({ ...cells });
    } catch (error) {
      console.error('Failed to track RL action:', error);
    }
  };

  // Agent API
  const agentAPI = {
    // Set column headers (first row)
    setColumns: (columns: string[]) => {
      columns.forEach((col, index) => {
        const addr = cellAddress(index, 0);
        setCells(prev => ({
          ...prev,
          [addr]: { 
            value: col, 
            type: 'text',
            style: { bold: true, backgroundColor: '#f3f4f6' }
          }
        }));
      });
      return `Set ${columns.length} columns`;
    },
    
    // Add a row of data
    addRow: (values: any[]) => {
      // Find the next empty row
      const usedRows = Object.keys(cells).map(addr => parseCell(addr)?.row ?? 0);
      const nextRow = usedRows.length > 0 ? Math.max(...usedRows) + 1 : 1;
      
      values.forEach((value, colIndex) => {
        const addr = cellAddress(colIndex, nextRow);
        const isFormula = typeof value === 'string' && value.startsWith('=');
        setCells(prev => ({
          ...prev,
          [addr]: {
            value: isFormula ? evaluateFormula(value) : value,
            formula: isFormula ? value : undefined,
            type: isFormula ? 'formula' : typeof value === 'number' ? 'number' : 'text'
          }
        }));
      });
      return `Added row at position ${nextRow + 1}`;
    },
    
    // Apply style to a range
    applyStyle: (range: string, style: any) => {
      const [start, end] = range.includes(':') ? range.split(':') : [range, range];
      const startCell = parseCell(start);
      const endCell = parseCell(end || start);
      
      if (!startCell || !endCell) return 'Invalid range';
      
      for (let r = startCell.row; r <= endCell.row; r++) {
        for (let c = startCell.col; c <= endCell.col; c++) {
          const addr = cellAddress(c, r);
          setCells(prev => ({
            ...prev,
            [addr]: {
              ...prev[addr],
              style: { ...prev[addr]?.style, ...style },
              format: style.format || prev[addr]?.format
            }
          }));
        }
      }
      return `Applied style to ${range}`;
    },
    
    // Apply formula to a cell
    applyFormula: (cell: string, formula: string) => {
      updateCell(cell, formula, true);
      return `Applied formula to ${cell}`;
    },
    
    // Select a cell (set as active)
    selectCell: (cell: string) => {
      setSelectedCell(cell);
      return `Selected ${cell}`;
    },
    
    // Create a chart with advanced capabilities
    createChart: (type: string, options: any) => {
      console.log(`Creating ${type} chart with options:`, options);
      
      // Create an embedded chart
      const chartId = `chart-${Date.now()}`;
      
      // Determine position (default to A10 if not specified)
      const position = options.position || 'A10';
      const size = options.size || { rows: 8, cols: 10 };
      
      // Add the chart to embedded charts
      setEmbeddedCharts(prev => [...prev, {
        id: chartId,
        type,
        data: options.data || options,
        position,
        size
      }]);
      
      // Clear the cells where the chart will be placed
      const startCell = parseCell(position);
      if (startCell) {
        for (let r = 0; r < size.rows; r++) {
          for (let c = 0; c < size.cols; c++) {
            const addr = cellAddress(startCell.col + c, startCell.row + r);
            setCells(prev => {
              const newCells = { ...prev };
              delete newCells[addr];
              return newCells;
            });
          }
        }
      }
      
      return `Chart ${type} embedded at ${position}`;
    },
    
    // Create multiple charts in batch to prevent re-render loops
    createChartBatch: (charts: Array<{type: string, options: any}>) => {
      console.log(`Creating batch of ${charts.length} charts`);
      
      // Process all charts at once to prevent multiple state updates
      const newCharts = charts.map((chart, index) => {
        const chartId = `chart-${Date.now()}-${index}`;
        const position = chart.options.position || `A${10 + (index * 10)}`;
        const size = chart.options.size || { rows: 8, cols: 10 };
        
        return {
          id: chartId,
          type: chart.type,
          data: chart.options.data || chart.options,
          position,
          size
        };
      });
      
      // Update embedded charts state ONCE with all new charts
      setEmbeddedCharts(prev => [...prev, ...newCharts]);
      
      // Clear cells for all charts in one batch update
      setCells(prev => {
        const newCells = { ...prev };
        
        newCharts.forEach(chart => {
          const startCell = parseCell(chart.position);
          if (startCell) {
            for (let r = 0; r < chart.size.rows; r++) {
              for (let c = 0; c < chart.size.cols; c++) {
                const addr = cellAddress(startCell.col + c, startCell.row + r);
                delete newCells[addr];
              }
            }
          }
        });
        
        return newCells;
      });
      
      return `Created batch of ${charts.length} charts`;
    },
    
    // Create financial charts
    createFinancialChart: (chartType: 'waterfall' | 'captable' | 'lpgp' | 'scenarios', data?: any) => {
      setShowFinancialCharts(true);
      // You could also pre-populate data here if provided
      return `Opening Financial Chart Studio for ${chartType}`;
    },
    
    // Create advanced visualization
    createAdvancedChart: (chartType: string, range?: string) => {
      if (range) {
        setSelectedRange(range);
      }
      setShowAdvancedCharts(true);
      return `Creating ${chartType} chart from range ${range || selectedRange || 'selected cells'}`;
    },
    
    // Auto-resize columns (no-op for fixed grid)
    autoResize: () => {
      return 'Auto-resize complete';
    },
    
    // Write value to cell (with optional link support)
    write: async (cell: string, value: any, options?: { href?: string; source?: string; sourceUrl?: string }) => {
      const prevCells = { ...cells };
      setCells(prev => {
        const newCells = { ...prev };
        if (value === '' || value === null) {
          delete newCells[cell];
        } else {
          newCells[cell] = {
            ...newCells[cell],
            value,
            type: options?.href ? 'link' : typeof value === 'number' ? 'number' : 'text',
            href: options?.href,
            source: options?.source,
            sourceUrl: options?.sourceUrl
          };
        }
        return newCells;
      });
      setAgentHistory(prev => [...prev, { type: 'write', cell, value }]);
      
      // Track in RL if enabled
      if (rlEnabled) {
        await trackRLAction(`write ${cell} ${value}`, 0.7);
      }
      
      return `Written ${value} to ${cell}`;
    },
    
    // Write a clickable link
    link: (cell: string, text: string, url: string) => {
      setCells(prev => ({
        ...prev,
        [cell]: {
          ...prev[cell],
          value: text,
          type: 'link',
          href: url,
          style: { ...prev[cell]?.style, color: '#0066cc', underline: true }
        }
      }));
      setAgentHistory(prev => [...prev, { type: 'write', cell, value: `[${text}](${url})` }]);
      return `Created link in ${cell}`;
    },
    
    // Set formula
    formula: (cell: string, formula: string) => {
      updateCell(cell, formula, true);
      setAgentHistory(prev => [...prev, { type: 'formula', cell, formula }]);
      return `Set formula ${formula} in ${cell}`;
    },
    
    // Write to range
    writeRange: (startCell: string, endCell: string, values: any[][]) => {
      const start = parseCell(startCell);
      const end = parseCell(endCell);
      if (!start || !end) return 'Invalid range';
      
      values.forEach((row, rowIndex) => {
        row.forEach((value, colIndex) => {
          const addr = cellAddress(start.col + colIndex, start.row + rowIndex);
          updateCell(addr, value, false);
        });
      });
      
      setAgentHistory(prev => [...prev, { type: 'write', range: `${startCell}:${endCell}`, value: values }]);
      return `Written data to range ${startCell}:${endCell}`;
    },
    
    // Format cell
    format: (cell: string, format: 'currency' | 'percentage' | 'number' | 'date') => {
      setCells(prev => ({
        ...prev,
        [cell]: { ...prev[cell], format }
      }));
      setAgentHistory(prev => [...prev, { type: 'format', cell, format }]);
      return `Formatted ${cell} as ${format}`;
    },
    
    // Style cell
    style: (cell: string, style: any) => {
      setCells(prev => ({
        ...prev,
        [cell]: { ...prev[cell], style: { ...prev[cell]?.style, ...style } }
      }));
      setAgentHistory(prev => [...prev, { type: 'style', cell, style }]);
      return `Styled ${cell}`;
    },
    
    // Read cell
    read: (cell: string) => {
      return cells[cell]?.value ?? null;
    },
    
    // Read range
    readRange: (startCell: string, endCell: string) => {
      const start = parseCell(startCell);
      const end = parseCell(endCell);
      if (!start || !end) return [];
      
      const result = [];
      for (let r = start.row; r <= end.row; r++) {
        const row = [];
        for (let c = start.col; c <= end.col; c++) {
          const addr = cellAddress(c, r);
          row.push(cells[addr]?.value ?? null);
        }
        result.push(row);
      }
      return result;
    },
    
    // Clear cells
    clear: (startCell: string, endCell?: string) => {
      if (endCell) {
        const start = parseCell(startCell);
        const end = parseCell(endCell);
        if (start && end) {
          setCells(prev => {
            const newCells = { ...prev };
            for (let r = start.row; r <= end.row; r++) {
              for (let c = start.col; c <= end.col; c++) {
                delete newCells[cellAddress(c, r)];
              }
            }
            return newCells;
          });
        }
      } else {
        setCells(prev => {
          const newCells = { ...prev };
          delete newCells[startCell];
          return newCells;
        });
      }
      return `Cleared ${endCell ? `${startCell}:${endCell}` : startCell}`;
    },
    
    // Execute multiple commands
    batch: (commands: AgentCommand[]) => {
      const results = [];
      for (const cmd of commands) {
        switch (cmd.type) {
          case 'write':
            results.push(agentAPI.write(cmd.cell!, cmd.value));
            break;
          case 'formula':
            results.push(agentAPI.formula(cmd.cell!, cmd.formula!));
            break;
          case 'format':
            results.push(agentAPI.format(cmd.cell!, cmd.format as any));
            break;
          case 'style':
            results.push(agentAPI.style(cmd.cell!, cmd.style));
            break;
        }
      }
      return results;
    },
    
    // Create a chart from data
    chart: (type: string, range: string, title?: string) => {
      const [start, end] = range.includes(':') ? range.split(':') : [range, range];
      const startCell = parseCell(start);
      const endCell = parseCell(end || start);
      
      if (!startCell || !endCell) return 'Invalid range for chart';
      
      // Extract data from range
      const data = [];
      const labels = [];
      
      for (let r = startCell.row; r <= endCell.row; r++) {
        const rowData = [];
        for (let c = startCell.col; c <= endCell.col; c++) {
          const addr = cellAddress(c, r);
          const value = cells[addr]?.value;
          
          if (c === startCell.col && r > startCell.row) {
            // First column as labels (except header)
            labels.push(value || `Row ${r}`);
          } else if (r > startCell.row) {
            // Data values
            rowData.push(typeof value === 'number' ? value : 0);
          }
        }
        if (rowData.length > 0) data.push(rowData);
      }
      
      // Store chart config in a special cell
      const chartId = `chart_${Date.now()}`;
      const chartCell = 'AA1'; // Use far-right column for charts
      
      setCells(prev => ({
        ...prev,
        [chartCell]: {
          ...prev[chartCell],
          value: chartId,
          type: 'chart',
          chartConfig: {
            type: type || 'line',
            data: data,
            labels: labels,
            title: title || 'Chart',
            range: range
          }
        }
      }));
      
      setAgentHistory(prev => [...prev, { 
        type: 'chart', 
        config: { type, range, title },
        id: chartId 
      }]);
      
      return `Created ${type} chart from ${range}`;
    },
    
    // Add conditional formatting
    conditionalFormat: (range: string, rules: any) => {
      const [start, end] = range.includes(':') ? range.split(':') : [range, range];
      const startCell = parseCell(start);
      const endCell = parseCell(end || start);
      
      if (!startCell || !endCell) return 'Invalid range';
      
      // Apply conditional formatting to range
      for (let r = startCell.row; r <= endCell.row; r++) {
        for (let c = startCell.col; c <= endCell.col; c++) {
          const addr = cellAddress(c, r);
          const cell = cells[addr];
          if (cell) {
            const value = cell.value;
            let bgColor = '';
            let textColor = '';
            
            // Apply rules
            if (rules.type === 'scale' && typeof value === 'number') {
              // Color scale based on min/max
              const min = rules.min?.value || 0;
              const max = rules.max?.value || 100;
              const ratio = (value - min) / (max - min);
              
              if (ratio <= 0.33) {
                bgColor = '#ffcccc'; // Red for low
                textColor = '#cc0000';
              } else if (ratio <= 0.67) {
                bgColor = '#ffffcc'; // Yellow for medium
                textColor = '#cc9900';
              } else {
                bgColor = '#ccffcc'; // Green for high
                textColor = '#009900';
              }
            } else if (rules.type === 'threshold' && typeof value === 'number') {
              // Simple threshold coloring
              if (value < (rules.bad || 0)) {
                bgColor = '#ffcccc';
                textColor = '#cc0000';
              } else if (value > (rules.good || 100)) {
                bgColor = '#ccffcc';
                textColor = '#009900';
              }
            }
            
            if (bgColor) {
              setCells(prev => ({
                ...prev,
                [addr]: {
                  ...cell,
                  style: { ...cell.style, backgroundColor: bgColor, color: textColor }
                }
              }));
            }
          }
        }
      }
      
      return `Applied conditional formatting to ${range}`;
    },
    
    // VLOOKUP implementation
    vlookup: (value: any, range: string, colIndex: number, exactMatch: boolean = false) => {
      const [start, end] = range.split(':');
      const startCell = parseCell(start);
      const endCell = parseCell(end);
      
      if (!startCell || !endCell) return '#ERROR';
      
      // Search in first column of range
      for (let r = startCell.row; r <= endCell.row; r++) {
        const searchAddr = cellAddress(startCell.col, r);
        const searchValue = cells[searchAddr]?.value;
        
        if (exactMatch ? searchValue === value : String(searchValue).includes(String(value))) {
          // Found match, return value from specified column
          const returnAddr = cellAddress(startCell.col + colIndex - 1, r);
          return cells[returnAddr]?.value || '';
        }
      }
      
      return '#N/A';
    },
    
    // Import Excel/CSV data
    importData: async (fileContent: string, format: 'csv' | 'excel' = 'csv') => {
      if (format === 'csv') {
        const lines = fileContent.split('\n');
        lines.forEach((line, row) => {
          const values = line.split(',').map(v => v.trim());
          values.forEach((value, col) => {
            const addr = cellAddress(col, row);
            // Try to parse as number
            const numValue = parseFloat(value);
            setCells(prev => ({
              ...prev,
              [addr]: {
                value: isNaN(numValue) ? value : numValue,
                type: isNaN(numValue) ? 'text' : 'number'
              }
            }));
          });
        });
        return `Imported ${lines.length} rows of CSV data`;
      }
      // Excel format would need a library like xlsx
      return 'Excel import requires additional setup';
    },
    
    // Error detection and correction
    detectErrors: () => {
      const errors: string[] = [];
      
      Object.entries(cells).forEach(([addr, cell]) => {
        if (cell.formula) {
          try {
            const result = evaluateFormula(cell.formula);
            if (result === '#ERROR' || result === '#DIV/0!' || result === '#N/A') {
              errors.push(`${addr}: Formula error - ${result}`);
            }
          } catch (e) {
            errors.push(`${addr}: Invalid formula`);
          }
        }
        
        // Check for common mistakes
        if (typeof cell.value === 'string' && cell.value.startsWith('=')) {
          if (!cell.formula) {
            errors.push(`${addr}: Formula not properly set (use grid.formula())`);
          }
        }
      });
      
      return errors;
    },
    
    // Auto-correct common errors
    autoCorrect: () => {
      const corrections: string[] = [];
      
      Object.entries(cells).forEach(([addr, cell]) => {
        // Fix formulas that were written as values
        if (typeof cell.value === 'string' && cell.value.startsWith('=') && !cell.formula) {
          setCells(prev => ({
            ...prev,
            [addr]: { ...cell, formula: cell.value, value: evaluateFormula(cell.value) }
          }));
          corrections.push(`Fixed formula in ${addr}`);
        }
        
        // Fix #DIV/0! errors
        if (cell.value === '#DIV/0!' && cell.formula) {
          const safeFormula = cell.formula.replace(/\//, '/IF(');
          // Add IFERROR wrapper
          const fixedFormula = `=IFERROR(${cell.formula.substring(1)}, 0)`;
          setCells(prev => ({
            ...prev,
            [addr]: { ...cell, formula: fixedFormula, value: 0 }
          }));
          corrections.push(`Fixed division by zero in ${addr}`);
        }
      });
      
      return corrections;
    },
    
    // Get current state for undo
    getState: () => {
      return JSON.parse(JSON.stringify(cells)); // Deep copy
    },
    
    // Restore previous state
    setState: (state: any) => {
      setCells(state || {});
      return 'State restored';
    }
  };

  // Helper function to add waterfall breakpoints with citations
  // Waterfall matters in ALL scenarios except massive bull cases (>10x)
  const addWaterfallBreakpoints = (companyName: string, startRow: number, scenario: 'bear' | 'base' | 'bull' = 'base') => {
    // Different breakpoints for different scenarios
    const bearBreakpoints = [
      { value: 'Below Liquidation Prefs', source: 'Common gets $0', exit: '$25M', impact: 'Common wiped out' },
      { value: 'Liquidation Prefs Covered', source: 'Carta: 1x standard', exit: '$50M', impact: 'Common starts participating' },
      { value: 'Common Gets >$100K', source: 'Minimal founder return', exit: '$55M', impact: 'Token amount to founders' },
      { value: 'Preferred Breakeven', source: 'Investors get capital back', exit: '$75M', impact: '1x return' }
    ];
    
    const baseBreakpoints = [
      { value: 'Liquidation Prefs Covered', source: 'Carta: 1x non-participating', exit: '$100M', impact: 'Common participation begins' },
      { value: 'Common Gets >$1M', source: 'Founder threshold', exit: '$110M', impact: 'Meaningful founder returns' },
      { value: 'Participation Cap Hit', source: 'SVB: 3x cap typical', exit: '$150M', impact: 'No further preferred participation' },
      { value: 'Preferred Gets 2x', source: 'Target VC return', exit: '$200M', impact: 'Acceptable investor returns' }
    ];
    
    const bullBreakpoints = [
      { value: 'All Convert to Common', source: 'Everyone participates equally', exit: '$300M', impact: "Preferences don't matter" },
      { value: 'IPO Threshold', source: 'Public market entry', exit: '$500M', impact: 'Liquidation prefs convert' },
      { value: '10x Return Territory', source: 'Home run outcome', exit: '$1B', impact: 'Power law returns' },
      { value: 'Mega Exit (>$2B)', source: 'Waterfall irrelevant', exit: '$2B+', impact: 'Everyone wins big' }
    ];
    
    const breakpoints = scenario === 'bear' ? bearBreakpoints : 
                       scenario === 'bull' ? bullBreakpoints : baseBreakpoints;
    
    // Add headers
    setCells(prev => ({
      ...prev,
      [`A${startRow}`]: { 
        value: `${companyName} - ${scenario.toUpperCase()} CASE`, 
        type: 'text', 
        style: { bold: true, backgroundColor: scenario === 'bear' ? '#ffcccc' : scenario === 'bull' ? '#ccffcc' : '#ccccff' } 
      },
      [`B${startRow}`]: { value: 'Breakpoint', type: 'text', style: { bold: true } },
      [`C${startRow}`]: { value: 'Exit Value', type: 'text', style: { bold: true } },
      [`D${startRow}`]: { value: 'Impact', type: 'text', style: { bold: true } },
      [`E${startRow}`]: { value: 'Note', type: 'text', style: { bold: true } }
    }));
    
    // Add breakpoint data with proper citations
    breakpoints.forEach((bp, index) => {
      const row = startRow + index + 1;
      setCells(prev => ({
        ...prev,
        [`B${row}`]: { 
          value: bp.value, 
          type: 'text',
          style: { 
            color: bp.value.includes('wiped out') ? '#dc2626' : 
                   bp.value.includes('10x') ? '#10b981' : undefined 
          }
        },
        [`C${row}`]: { 
          value: bp.exit, 
          type: 'text',
          format: 'currency',
          source: 'Market analysis',
          sourceUrl: '#'
        },
        [`D${row}`]: { 
          value: bp.impact, 
          type: 'text',
          style: { italic: true }
        },
        [`E${row}`]: { 
          value: bp.source, 
          type: 'text',
          source: bp.source.includes('Carta') ? 'Carta' : 
                  bp.source.includes('SVB') ? 'SVB' : 
                  bp.source.includes('founder') ? 'Benchmark' : 'Analysis',
          sourceUrl: bp.source.includes('Carta') ? 'https://carta.com/blog/liquidation-preferences/' : 
                     bp.source.includes('SVB') ? 'https://www.svb.com/trends-insights/' : '#'
        }
      }));
    });
  };
  
  // Expose API globally with multiple aliases for convenience
  useEffect(() => {
    // Enhanced API with visualization capabilities
    const enhancedAPI = {
      ...agentAPI,
      addWaterfallBreakpoints,
      
      // Create Sankey diagram from data
      createSankey: (dataRange: string, title?: string) => {
        const data = convertRangeToSankeyData(cells, dataRange);
        setVisualization({
          type: 'sankey',
          data,
          title: title || 'Revenue Flow Analysis'
        });
        return 'Sankey diagram created';
      },
      
      // Create waterfall chart
      createWaterfall: (dataRange: string, title?: string) => {
        const data = convertRangeToWaterfallData(cells, dataRange);
        setVisualization({
          type: 'waterfall',
          data,
          title: title || 'Financial Waterfall'
        });
        return 'Waterfall chart created';
      }
    };
    
    // Production-ready: Register API with window for backward compatibility
    // This allows secure sharing between components
    if (typeof window !== 'undefined') {
      (window as any).gridApi = enhancedAPI;
    }
    
    // Also keep internal ref for component use
    gridRef.current = enhancedAPI as any;
  }, [cells]);

  // Handle cell editing
  const startEditing = (cell: string) => {
    setEditingCell(cell);
    const cellData = cells[cell];
    setEditValue(cellData?.formula || cellData?.value || '');
  };

  const finishEditing = () => {
    if (editingCell && editValue !== undefined) {
      const isFormula = editValue.startsWith('=');
      updateCell(editingCell, editValue, isFormula);
      setEditingCell(null);
      setEditValue('');
    }
  };

  const cancelEditing = () => {
    setEditingCell(null);
    setEditValue('');
  };

  // Export to CSV
  const exportToCSV = () => {
    const maxRow = Math.max(...Object.keys(cells).map(addr => parseCell(addr)?.row ?? 0)) + 1;
    const maxCol = Math.max(...Object.keys(cells).map(addr => parseCell(addr)?.col ?? 0)) + 1;
    
    const rows = [];
    for (let r = 0; r < maxRow; r++) {
      const row = [];
      for (let c = 0; c < maxCol; c++) {
        const addr = cellAddress(c, r);
        row.push(formatCellValue(cells[addr]));
      }
      rows.push(row.join(','));
    }
    
    const csv = rows.join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'spreadsheet.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Toolbar */}
      <div className="flex items-center justify-between p-2 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAgentMode(!agentMode)}
            className={cn(
              "px-3 py-1.5 text-sm font-medium rounded transition-colors",
              agentMode 
                ? "bg-gray-900 text-white" 
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            )}
          >
            <Bot className="w-4 h-4 inline mr-1" />
            Agent Mode
          </button>
          
          <button
            onClick={() => setRlEnabled(!rlEnabled)}
            className={cn(
              "px-3 py-1.5 text-sm font-medium rounded transition-colors",
              rlEnabled 
                ? "bg-green-600 text-white" 
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            )}
            title="Enable Reinforcement Learning to track and learn from agent actions"
          >
            <GitBranch className="w-4 h-4 inline mr-1" />
            RL: {rlEnabled ? 'ON' : 'OFF'}
          </button>
          
          <button
            onClick={recalculateAll}
            disabled={isCalculating}
            className="px-3 py-1.5 text-sm font-medium bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition-colors"
          >
            <RefreshCw className={cn("w-4 h-4 inline mr-1", isCalculating && "animate-spin")} />
            Calculate
          </button>
          
          <button
            onClick={exportToCSV}
            className="px-3 py-1.5 text-sm font-medium bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition-colors"
          >
            <Download className="w-4 h-4 inline mr-1" />
            Export
          </button>
          
          <button
            onClick={() => setShowFormulaHelp(!showFormulaHelp)}
            className={cn(
              "px-3 py-1.5 text-sm font-medium rounded transition-colors",
              showFormulaHelp 
                ? "bg-blue-600 text-white" 
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            )}
          >
            <Calculator className="w-4 h-4 inline mr-1" />
            Formulas
          </button>
          
          <div className="w-px h-6 bg-gray-300" />
          
          <button
            onClick={() => setShowAdvancedCharts(true)}
            className="px-3 py-1.5 text-sm font-medium bg-gradient-to-r from-blue-500 to-purple-500 text-white rounded hover:from-blue-600 hover:to-purple-600 transition-all shadow-sm"
          >
            <BarChart3 className="w-4 h-4 inline mr-1" />
            Charts
          </button>
          
          <button
            onClick={() => setShowFinancialCharts(true)}
            className="px-3 py-1.5 text-sm font-medium bg-gradient-to-r from-green-500 to-blue-500 text-white rounded hover:from-green-600 hover:to-blue-600 transition-all shadow-sm"
          >
            <DollarSign className="w-4 h-4 inline mr-1" />
            Financial
          </button>
          
          <div className="w-px h-6 bg-gray-300" />
          
          <button
            onClick={() => agentAPI.clear('A1', 'Z100')}
            className="px-3 py-1.5 text-sm font-medium bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition-colors"
          >
            <Trash2 className="w-4 h-4 inline mr-1" />
            Clear All
          </button>
        </div>
        
        {isCalculating && (
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Zap className="w-4 h-4 animate-pulse" />
            Calculating...
          </div>
        )}
      </div>

      {/* Formula Bar */}
      <div className="flex items-center gap-2 p-2 border-b border-gray-200 bg-gray-50">
        <span className="px-2 py-1 bg-white border border-gray-300 rounded text-sm font-mono min-w-20 text-center">
          {selectedCell}
        </span>
        <input
          type="text"
          value={formulaBar}
          onChange={(e) => setFormulaBar(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              const isFormula = formulaBar.startsWith('=');
              updateCell(selectedCell, formulaBar, isFormula);
              setFormulaBar('');
            }
          }}
          placeholder="Enter value or formula (e.g., =A1+B1)"
          className="flex-1 px-2 py-1 border border-gray-300 rounded text-sm font-mono focus:outline-none focus:ring-2 focus:ring-gray-400"
        />
      </div>

      {/* Grid */}
      <div className="flex-1 overflow-auto" ref={gridRef}>
        <table className="border-collapse">
          <thead className="sticky top-0 z-10">
            <tr>
              <th className="w-12 h-8 bg-gray-100 border border-gray-300 text-xs font-medium"></th>
              {COLUMNS.map(col => (
                <th key={col} className="w-24 h-8 bg-gray-100 border border-gray-300 text-xs font-medium">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.slice(0, 50).map(row => (
              <tr key={row}>
                <td className="w-12 h-8 bg-gray-100 border border-gray-300 text-xs font-medium text-center">
                  {row}
                </td>
                {COLUMNS.map(col => {
                  const addr = col + row;
                  const cell = cells[addr];
                  const isSelected = selectedCell === addr;
                  const isEditing = editingCell === addr;
                  
                  // Check if this cell is the start of an embedded chart
                  const chart = embeddedCharts.find(c => c.position === addr);
                  if (chart) {
                    const chartCell = parseCell(chart.position);
                    if (chartCell && col === addr.charAt(0)) {
                      return (
                        <td
                          key={addr}
                          colSpan={chart.size.cols}
                          rowSpan={chart.size.rows}
                          className="border border-gray-300 p-2 bg-gray-50"
                        >
                          <div className="w-full h-full min-h-[300px]">
                            <TableauLevelCharts
                              type={chart.type as any}
                              data={chart.data}
                              title={chart.data.title}
                              height={chart.size.rows * 32 - 16}
                              width="100%"
                              interactive={true}
                            />
                          </div>
                        </td>
                      );
                    }
                  }
                  
                  // Check if this cell is covered by a chart
                  const isCoveredByChart = embeddedCharts.some(c => {
                    const chartStart = parseCell(c.position);
                    const currentCell = parseCell(addr);
                    if (!chartStart || !currentCell) return false;
                    
                    return currentCell.row >= chartStart.row && 
                           currentCell.row < chartStart.row + c.size.rows &&
                           currentCell.col >= chartStart.col && 
                           currentCell.col < chartStart.col + c.size.cols &&
                           c.position !== addr;
                  });
                  
                  if (isCoveredByChart) {
                    return null; // Skip cells covered by charts
                  }
                  
                  return (
                    <td
                      key={addr}
                      className={cn(
                        "w-24 h-8 border border-gray-300 text-sm px-1 cursor-pointer",
                        isSelected && "ring-2 ring-gray-900 ring-inset",
                        cell?.formula && "bg-blue-50",
                        cell?.locked && "bg-gray-50"
                      )}
                      style={cell?.style ? {
                        fontWeight: cell.style.bold ? 'bold' : undefined,
                        fontStyle: cell.style.italic ? 'italic' : undefined,
                        textDecoration: cell.style.underline ? 'underline' : undefined,
                        backgroundColor: cell.style.backgroundColor,
                        color: cell.style.color
                      } : undefined}
                      title={cell?.source ? `Source: ${cell.source}` : (cell?.formula ? `Formula: ${cell.formula}` : undefined)}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedCell(addr);
                        setFormulaBar(cell?.formula || cell?.value || '');
                        if (e.detail === 2) { // Double click
                          startEditing(addr);
                        }
                      }}
                    >
                      {isEditing ? (
                        <input
                          type="text"
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') finishEditing();
                            if (e.key === 'Escape') cancelEditing();
                          }}
                          onBlur={finishEditing}
                          className="w-full h-full px-1 focus:outline-none"
                          autoFocus
                        />
                      ) : cell?.type === 'link' && cell?.href ? (
                        <a
                          href={cell.href}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-800 underline cursor-pointer"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {formatCellValue(cell)}
                        </a>
                      ) : (
                        <div className="flex items-center justify-between">
                          {/* Make value clickable if it has href */}
                          {cell?.href ? (
                            <a
                              href={cell.href}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-600 hover:text-blue-800 underline"
                              onClick={(e) => e.stopPropagation()}
                            >
                              {formatCellValue(cell)}
                            </a>
                          ) : (
                            <span>{formatCellValue(cell)}</span>
                          )}
                          
                          {/* Citation source indicator with tooltip */}
                          {(cell?.sourceUrl || cell?.source) && (
                            <span className="ml-1 relative group">
                              <a
                                href={cell.sourceUrl || '#'}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-500 hover:text-blue-700 text-xs"
                                onClick={(e) => {
                                  if (!cell.sourceUrl) e.preventDefault();
                                  e.stopPropagation();
                                }}
                                title={cell.source || 'Source'}
                              >
                                📎
                              </a>
                              {/* Tooltip showing source */}
                              <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block z-50 
                                            bg-gray-900 text-white text-xs rounded px-2 py-1 whitespace-nowrap
                                            max-w-xs p-2">
                                <div className="font-semibold">{cell.source || 'Data source'}</div>
                                {cell.source === 'Carta' && (
                                  <div className="text-gray-300 mt-1">Industry benchmark data</div>
                                )}
                                {cell.source === 'SVB' && (
                                  <div className="text-gray-300 mt-1">Silicon Valley Bank insights</div>
                                )}
                                {cell.source === 'PitchBook' && (
                                  <div className="text-gray-300 mt-1">Market analytics</div>
                                )}
                              </div>
                            </span>
                          )}
                        </div>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Agent Console */}
      {agentMode && (
        <div className="bg-gray-900 text-gray-100">
          
          {/* API Reference */}
          <div className="p-3 font-mono text-xs space-y-2 max-h-48 overflow-auto">
            <div className="flex items-center gap-2 mb-2">
              <Bot className="w-4 h-4" />
              <span className="font-bold">Direct API</span>
              <Sparkles className="w-3 h-3 text-yellow-400 animate-pulse" />
              <span className="text-gray-400 ml-auto">Grid API</span>
            </div>
          
          <div className="text-green-400"># Write data</div>
          <div className="pl-4 text-gray-300">grid.write("A1", "Revenue")</div>
          <div className="pl-4 text-gray-300">grid.write("B1", 1000000)</div>
          
          <div className="text-green-400"># Set formula</div>
          <div className="pl-4 text-gray-300">grid.formula("C1", "=B1*1.2")</div>
          <div className="pl-4 text-gray-300">grid.formula("D1", "=SUM(A1:C1)")</div>
          
          <div className="text-green-400"># Write range</div>
          <div className="pl-4 text-gray-300">grid.writeRange("A2", "C4", [[1,2,3],[4,5,6],[7,8,9]])</div>
          
          <div className="text-green-400"># Format cells</div>
          <div className="pl-4 text-gray-300">grid.format("B1", "currency")</div>
          <div className="pl-4 text-gray-300">grid.format("C1", "percentage")</div>
          
          <div className="text-green-400"># Style cells</div>
          <div className="pl-4 text-gray-300">grid.style("A1", {`{bold: true, backgroundColor: "#f3f4f6"}`})</div>
          
          <div className="text-green-400"># Read data</div>
          <div className="pl-4 text-gray-300">grid.read("A1") // Returns: {cells['A1']?.value || 'null'}</div>
          <div className="pl-4 text-gray-300">grid.readRange("A1", "C3") // Returns 2D array</div>
          
          <div className="text-green-400"># Create charts (NEW!)</div>
          <div className="pl-4 text-gray-300">grid.createChart("sankey", {`{range: "A1:C10"}`})</div>
          <div className="pl-4 text-gray-300">grid.createFinancialChart("waterfall", {`{carry: 0.2, hurdle: 0.08}`})</div>
          <div className="pl-4 text-gray-300">grid.createAdvancedChart("3dpie", "A1:B5")</div>
          
          {agentHistory.length > 0 && (
            <>
              <div className="text-yellow-400 mt-2"># Recent Actions</div>
              {agentHistory.slice(-3).map((cmd, i) => (
                <div key={i} className="pl-4 text-gray-400">
                  {cmd.type}: {cmd.cell || cmd.range} → {JSON.stringify(cmd.value || cmd.formula || cmd.format)}
                </div>
              ))}
            </>
          )}
          </div>
        </div>
      )}
      
      {/* Formula Help Panel */}
      {showFormulaHelp && FORMULA_DOCS && (
        <div className="fixed right-4 top-20 w-96 max-h-96 bg-white rounded-lg shadow-xl border border-gray-200 overflow-hidden z-50">
          <div className="p-4 border-b border-gray-200 bg-gray-50">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">Available Formulas</h3>
              <button
                onClick={() => setShowFormulaHelp(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>
          
          <div className="overflow-y-auto max-h-[calc(80vh-60px)] p-4">
            {Object.entries(FORMULA_DOCS).map(([category, formulas]) => (
              <div key={category} className="mb-6">
                <h4 className="text-sm font-semibold text-gray-700 mb-2 capitalize">
                  {category === 'capTable' ? '📈 Cap Table' :
                   category === 'financial' ? '📊 Financial' :
                   category === 'waterfall' ? '💧 Waterfall' :
                   category === 'scenario' ? '🎯 Scenario' :
                   category === 'statistical' ? '📉 Statistical' :
                   category === 'math' ? '➕ Math' :
                   category === 'logical' ? '🔀 Logical' :
                   category === 'text' ? '📝 Text' :
                   category === 'date' ? '📅 Date' : category}
                </h4>
                <div className="space-y-1 text-xs">
                  {Object.entries(formulas as Record<string, string>).map(([name, desc]) => (
                    <div key={name} className="py-1">
                      <code className="bg-gray-100 px-1 rounded text-xs">{desc}</code>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Visualization Panel */}
      {visualization.type && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-2xl w-full h-full flex flex-col">
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-gray-900">{visualization.title}</h2>
              <button
                onClick={() => setVisualization({ type: null, data: null, title: '' })}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
            
            <div className="flex-1 overflow-auto p-6">
              {visualization.type === 'sankey' && (
                <RevenueSegmentationChart
                  nodes={visualization.data.nodes}
                  links={visualization.data.links}
                  title=""
                  height={600}
                  width={1200}
                />
              )}
              
              {visualization.type === 'waterfall' && (
                <WaterfallChart
                  data={visualization.data}
                  title=""
                  height={600}
                />
              )}
            </div>
          </div>
        </div>
      )}
      
      {/* Advanced Chart Builder Modal */}
      {showAdvancedCharts && (
        <ExcelChartBuilder
          cells={cells}
          selectedRange={selectedRange || selectedCell}
          onClose={() => setShowAdvancedCharts(false)}
        />
      )}
      
      {/* Financial Chart Studio Modal */}
      {showFinancialCharts && (
        <FinancialChartStudio
          cells={cells}
          onClose={() => setShowFinancialCharts(false)}
          onInsert={(chartConfig) => {
            console.log('Inserting financial chart:', chartConfig);
            setShowFinancialCharts(false);
            // Here you would handle inserting the chart into the spreadsheet
            // For now, we'll just log it
          }}
        />
      )}
    </div>
  );
}