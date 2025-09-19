'use client';

import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { cn } from '@/lib/utils';
import SpreadsheetChart from './SpreadsheetChart';
import {
  Table2,
  Calculator,
  Copy,
  ClipboardPaste as Paste,
  Undo,
  Redo,
  Download,
  Upload,
  Filter,
  SortAsc,
  SortDesc,
  ChevronDown,
  ChevronRight,
  Plus,
  Minus,
  X,
  Check,
  AlertCircle,
  Trash2,
  Info,
  TrendingUp,
  TrendingDown,
  BarChart3,
  PieChart,
  LineChart,
  Sigma,
  Hash,
  Type,
  Calendar,
  DollarSign,
  Percent,
  Link2,
  Search,
  Settings,
  Eye,
  EyeOff,
  Lock,
  Unlock,
  Palette,
  Bold,
  Italic,
  Underline,
  AlignLeft,
  AlignCenter,
  AlignRight,
  Sparkles,
  Bot,
  RefreshCw,
  Save,
  FolderOpen,
  FileSpreadsheet,
  Grid3x3,
  Columns,
  Rows,
  Merge,
  Split,
  Database,
  Globe,
  Zap,
  GitBranch,
  Command
} from 'lucide-react';

// Cell reference system (A1, B2, etc.)
const columnToLetter = (col: number): string => {
  let letter = '';
  while (col >= 0) {
    letter = String.fromCharCode((col % 26) + 65) + letter;
    col = Math.floor(col / 26) - 1;
  }
  return letter;
};

const letterToColumn = (letter: string): number => {
  let col = 0;
  for (let i = 0; i < letter.length; i++) {
    col = col * 26 + (letter.charCodeAt(i) - 64);
  }
  return col - 1;
};

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

interface ConditionalFormat {
  id: string;
  range: string;
  condition: 'equals' | 'greater' | 'less' | 'between' | 'contains' | 'duplicate' | 'unique';
  value?: any;
  value2?: any;
  style: CellStyle;
}

interface Cell {
  value: any;
  formula?: string;
  type: 'text' | 'number' | 'currency' | 'percentage' | 'date' | 'boolean' | 'formula' | 'link';
  style?: CellStyle;
  locked?: boolean;
  comment?: string;
  link?: string;  // For hyperlinks
  sourceUrl?: string;  // For citation URLs
  validation?: {
    type: 'list' | 'range' | 'custom';
    values?: any[];
    min?: number;
    max?: number;
    formula?: string;
    message?: string;
  };
  history?: Array<{
    value: any;
    timestamp: string;
    user?: string;
  }>;
}

interface SpreadsheetData {
  cells: Record<string, Cell>;
  columns: number;
  rows: number;
  frozenRows?: number;
  frozenColumns?: number;
  hiddenRows?: Set<number>;
  hiddenColumns?: Set<number>;
  rowHeights?: Record<number, number>;
  columnWidths?: Record<number, number>;
  mergedCells?: Array<{ start: string; end: string }>;
  conditionalFormats?: ConditionalFormat[];
  namedRanges?: Record<string, string>;
  filters?: Record<string, any>;
  sorting?: { column: string; direction: 'asc' | 'desc' }[];
}

interface UndoRedoState {
  past: SpreadsheetData[];
  present: SpreadsheetData;
  future: SpreadsheetData[];
}

export default function EnhancedSpreadsheet() {
  // Helper to detect cell type
  const detectCellType = (value: any): Cell['type'] => {
    if (typeof value === 'number') return 'number';
    if (typeof value === 'boolean') return 'boolean';
    if (typeof value === 'string') {
      if (value.startsWith('=')) return 'formula';
      if (value.startsWith('http')) return 'link';
      if (value.match(/^\d{4}-\d{2}-\d{2}/)) return 'date';
      if (value.match(/^\$[\d,]+\.?\d*/)) return 'currency';
      if (value.match(/^\d+\.?\d*%$/)) return 'percentage';
    }
    return 'text';
  };

  const [data, setData] = useState<SpreadsheetData>({
    cells: {},
    columns: 26,
    rows: 100,
    frozenRows: 1,
    frozenColumns: 1,
    hiddenRows: new Set(),
    hiddenColumns: new Set(),
    rowHeights: {},
    columnWidths: {},
    mergedCells: [],
    conditionalFormats: [],
    namedRanges: {},
    filters: {},
    sorting: []
  });

  const [selectedCells, setSelectedCells] = useState<Set<string>>(new Set());
  const [activeCell, setActiveCell] = useState<string>('A1');
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState('');
  const [showFormulaBar, setShowFormulaBar] = useState(true);
  const [showGridLines, setShowGridLines] = useState(true);
  const [showHeaders, setShowHeaders] = useState(true);
  const [clipboard, setClipboard] = useState<Record<string, Cell>>({});
  const [undoRedoState, setUndoRedoState] = useState<UndoRedoState>({
    past: [],
    present: data,
    future: []
  });
  const [searchQuery, setSearchQuery] = useState('');
  const [findResults, setFindResults] = useState<string[]>([]);
  const [currentFindIndex, setCurrentFindIndex] = useState(0);
  const [isCalculating, setIsCalculating] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showChartPanel, setShowChartPanel] = useState(false);
  const [selectedChart, setSelectedChart] = useState<'bar' | 'line' | 'pie' | null>(null);
  const [chartData, setChartData] = useState<any[]>([]);
  const [chartConfig, setChartConfig] = useState<any>({});
  const gridRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dataRef = useRef(data);
  
  // Keep dataRef in sync with data
  useEffect(() => {
    dataRef.current = data;
  }, [data]);


  // Formula evaluation engine
  const evaluateFormula = useCallback((formula: string, cellRef: string): any => {
    if (!formula.startsWith('=')) return formula;
    
    try {
      const expr = formula.substring(1);
      
      // Replace cell references with values
      const cellPattern = /([A-Z]+)(\d+)/g;
      let evaluatedExpr = expr.replace(cellPattern, (match, col, row) => {
        const ref = `${col}${row}`;
        if (ref === cellRef) throw new Error('Circular reference');
        const cell = data.cells[ref];
        if (!cell) return '0';
        if (cell.formula) {
          return evaluateFormula(cell.formula, ref);
        }
        return String(cell.value || 0);
      });

      // Replace common functions
      evaluatedExpr = evaluatedExpr
        .replace(/SUM\((.*?)\)/gi, (match, range) => {
          const values = getRangeValues(range);
          return String(values.reduce((sum, val) => sum + Number(val), 0));
        })
        .replace(/AVERAGE\((.*?)\)/gi, (match, range) => {
          const values = getRangeValues(range);
          const sum = values.reduce((acc, val) => acc + Number(val), 0);
          return String(sum / values.length);
        })
        .replace(/COUNT\((.*?)\)/gi, (match, range) => {
          const values = getRangeValues(range);
          return String(values.filter(val => val !== null && val !== '').length);
        })
        .replace(/MAX\((.*?)\)/gi, (match, range) => {
          const values = getRangeValues(range);
          return String(Math.max(...values.map(Number)));
        })
        .replace(/MIN\((.*?)\)/gi, (match, range) => {
          const values = getRangeValues(range);
          return String(Math.min(...values.map(Number)));
        })
        .replace(/IF\((.*?),(.*?),(.*?)\)/gi, (match, condition, trueVal, falseVal) => {
          return eval(condition) ? trueVal : falseVal;
        })
        .replace(/CONCATENATE\((.*?)\)/gi, (match, args) => {
          return args.split(',').map((s: string) => s.trim().replace(/"/g, '')).join('');
        })
        .replace(/TODAY\(\)/gi, () => new Date().toISOString().split('T')[0])
        .replace(/NOW\(\)/gi, () => new Date().toISOString())
        .replace(/LEN\((.*?)\)/gi, (match, text) => String(text.length))
        .replace(/UPPER\((.*?)\)/gi, (match, text) => text.toUpperCase())
        .replace(/LOWER\((.*?)\)/gi, (match, text) => text.toLowerCase())
        .replace(/ROUND\((.*?),(.*?)\)/gi, (match, num, decimals) => {
          return String(Math.round(Number(num) * Math.pow(10, Number(decimals))) / Math.pow(10, Number(decimals)));
        })
        // Financial formulas
        .replace(/NPV\((.*?),(.*?)\)/gi, (match, rate, range) => {
          const r = Number(rate);
          const values = getRangeValues(range);
          let npv = 0;
          for (let i = 0; i < values.length; i++) {
            npv += Number(values[i]) / Math.pow(1 + r, i + 1);
          }
          return String(npv);
        })
        .replace(/IRR\((.*?)\)/gi, (match, range) => {
          const values = getRangeValues(range).map(Number);
          // Newton-Raphson method for IRR
          let rate = 0.1; // Initial guess 10%
          for (let i = 0; i < 100; i++) {
            let npv = 0, dnpv = 0;
            for (let j = 0; j < values.length; j++) {
              npv += values[j] / Math.pow(1 + rate, j);
              dnpv -= j * values[j] / Math.pow(1 + rate, j + 1);
            }
            const newRate = rate - npv / dnpv;
            if (Math.abs(newRate - rate) < 0.00001) {
              return String(newRate); // Return as decimal (0.15 = 15%)
            }
            rate = newRate;
          }
          return String(rate);
        })
        .replace(/PMT\((.*?),(.*?),(.*?)\)/gi, (match, rate, nper, pv) => {
          const r = Number(rate);
          const n = Number(nper);
          const p = Number(pv);
          if (r === 0) return String(-p / n);
          const payment = (p * r) / (1 - Math.pow(1 + r, -n));
          return String(-payment);
        })
        .replace(/PV\((.*?),(.*?),(.*?)\)/gi, (match, rate, nper, pmt) => {
          const r = Number(rate);
          const n = Number(nper);
          const payment = Number(pmt);
          if (r === 0) return String(-payment * n);
          const pv = payment * (1 - Math.pow(1 + r, -n)) / r;
          return String(-pv);
        })
        .replace(/FV\((.*?),(.*?),(.*?),(.*?)\)/gi, (match, rate, nper, pmt, pv) => {
          const r = Number(rate);
          const n = Number(nper);
          const payment = Number(pmt);
          const presentValue = Number(pv || 0);
          if (r === 0) return String(-(presentValue + payment * n));
          const fv = -presentValue * Math.pow(1 + r, n) - payment * ((Math.pow(1 + r, n) - 1) / r);
          return String(fv);
        })
        .replace(/CAGR\((.*?),(.*?),(.*?)\)/gi, (match, beginVal, endVal, years) => {
          const start = Number(beginVal);
          const end = Number(endVal);
          const y = Number(years);
          const cagr = Math.pow(end / start, 1 / y) - 1;
          return String(cagr);
        })
        .replace(/MOIC\((.*?),(.*?)\)/gi, (match, exitVal, invested) => {
          return String(Number(exitVal) / Number(invested));
        });

      // Evaluate the expression
      const result = Function('"use strict"; return (' + evaluatedExpr + ')')();
      return result;
    } catch (error) {
      setErrors(prev => ({ ...prev, [cellRef]: (error as Error).message }));
      return '#ERROR!';
    }
  }, [data.cells]);

  // Get values from a range (A1:B10)
  const getRangeValues = useCallback((range: string): any[] => {
    const values: any[] = [];
    const rangePattern = /([A-Z]+)(\d+):([A-Z]+)(\d+)/;
    const match = range.match(rangePattern);
    
    if (match) {
      const [, startCol, startRow, endCol, endRow] = match;
      const startColNum = letterToColumn(startCol);
      const endColNum = letterToColumn(endCol);
      const startRowNum = parseInt(startRow);
      const endRowNum = parseInt(endRow);
      
      for (let row = startRowNum; row <= endRowNum; row++) {
        for (let col = startColNum; col <= endColNum; col++) {
          const cellRef = `${columnToLetter(col)}${row}`;
          const cell = data.cells[cellRef];
          if (cell) {
            values.push(cell.formula ? evaluateFormula(cell.formula, cellRef) : cell.value);
          }
        }
      }
    } else {
      // Single cell
      const cell = data.cells[range];
      if (cell) {
        values.push(cell.formula ? evaluateFormula(cell.formula, range) : cell.value);
      }
    }
    
    return values;
  }, [data.cells, evaluateFormula]);

  // Update cell value
  const updateCell = useCallback((cellRef: string, value: any, formula?: string) => {
    setUndoRedoState(prev => ({
      past: [...prev.past, prev.present],
      present: data,
      future: []
    }));

    setData(prev => {
      const newCells = { ...prev.cells };
      
      if (!value && !formula) {
        delete newCells[cellRef];
      } else {
        newCells[cellRef] = {
          ...newCells[cellRef],
          value: formula ? evaluateFormula(formula, cellRef) : value,
          formula: formula,
          type: detectCellType(value),
          history: [
            ...(newCells[cellRef]?.history || []),
            { value: newCells[cellRef]?.value, timestamp: new Date().toISOString() }
          ]
        };
      }
      
      return { ...prev, cells: newCells };
    });
    
    setErrors(prev => {
      const newErrors = { ...prev };
      delete newErrors[cellRef];
      return newErrors;
    });
  }, [data, evaluateFormula]);

  // Copy cells
  const copyCells = useCallback(() => {
    const cellsToCopy: Record<string, Cell> = {};
    selectedCells.forEach(cellRef => {
      if (data.cells[cellRef]) {
        cellsToCopy[cellRef] = data.cells[cellRef];
      }
    });
    setClipboard(cellsToCopy);
  }, [selectedCells, data.cells]);

  // Paste cells
  const pasteCells = useCallback(() => {
    if (Object.keys(clipboard).length === 0) return;
    
    setUndoRedoState(prev => ({
      past: [...prev.past, prev.present],
      present: data,
      future: []
    }));
    
    // Calculate offset from first clipboard cell to active cell
    const clipboardRefs = Object.keys(clipboard).sort();
    const firstClipboardRef = clipboardRefs[0];
    const [clipCol, clipRow] = firstClipboardRef.match(/([A-Z]+)(\d+)/)!.slice(1);
    const [activeCol, activeRow] = activeCell.match(/([A-Z]+)(\d+)/)!.slice(1);
    
    const colOffset = letterToColumn(activeCol) - letterToColumn(clipCol);
    const rowOffset = parseInt(activeRow) - parseInt(clipRow);
    
    setData(prev => {
      const newCells = { ...prev.cells };
      
      Object.entries(clipboard).forEach(([cellRef, cell]) => {
        const [col, row] = cellRef.match(/([A-Z]+)(\d+)/)!.slice(1);
        const newCol = columnToLetter(letterToColumn(col) + colOffset);
        const newRow = parseInt(row) + rowOffset;
        const newRef = `${newCol}${newRow}`;
        
        newCells[newRef] = { ...cell };
      });
      
      return { ...prev, cells: newCells };
    });
  }, [clipboard, activeCell, data]);

  // Undo
  const undo = useCallback(() => {
    if (undoRedoState.past.length === 0) return;
    
    setUndoRedoState(prev => ({
      past: prev.past.slice(0, -1),
      present: prev.past[prev.past.length - 1],
      future: [prev.present, ...prev.future]
    }));
    
    setData(undoRedoState.past[undoRedoState.past.length - 1]);
  }, [undoRedoState]);

  // Redo
  const redo = useCallback(() => {
    if (undoRedoState.future.length === 0) return;
    
    setUndoRedoState(prev => ({
      past: [...prev.past, prev.present],
      present: prev.future[0],
      future: prev.future.slice(1)
    }));
    
    setData(undoRedoState.future[0]);
  }, [undoRedoState]);

  // Find and replace
  const findCells = useCallback((query: string) => {
    const results: string[] = [];
    
    Object.entries(data.cells).forEach(([cellRef, cell]) => {
      const value = cell.formula || cell.value;
      if (value?.toString().toLowerCase().includes(query.toLowerCase())) {
        results.push(cellRef);
      }
    });
    
    setFindResults(results);
    setCurrentFindIndex(0);
    if (results.length > 0) {
      setActiveCell(results[0]);
    }
  }, [data.cells]);

  // Apply conditional formatting
  const applyConditionalFormatting = useCallback((cellRef: string): CellStyle => {
    let style: CellStyle = {};
    
    data.conditionalFormats?.forEach(format => {
      // Check if cell is in range
      const rangePattern = /([A-Z]+)(\d+):([A-Z]+)(\d+)/;
      const match = format.range.match(rangePattern);
      
      if (match) {
        const [, startCol, startRow, endCol, endRow] = match;
        const [cellCol, cellRow] = cellRef.match(/([A-Z]+)(\d+)/)!.slice(1);
        
        const cellColNum = letterToColumn(cellCol);
        const cellRowNum = parseInt(cellRow);
        const startColNum = letterToColumn(startCol);
        const endColNum = letterToColumn(endCol);
        const startRowNum = parseInt(startRow);
        const endRowNum = parseInt(endRow);
        
        if (cellColNum >= startColNum && cellColNum <= endColNum &&
            cellRowNum >= startRowNum && cellRowNum <= endRowNum) {
          
          const cell = data.cells[cellRef];
          if (!cell) return;
          
          const value = cell.formula ? evaluateFormula(cell.formula, cellRef) : cell.value;
          
          let conditionMet = false;
          switch (format.condition) {
            case 'equals':
              conditionMet = value === format.value;
              break;
            case 'greater':
              conditionMet = Number(value) > Number(format.value);
              break;
            case 'less':
              conditionMet = Number(value) < Number(format.value);
              break;
            case 'between':
              conditionMet = Number(value) >= Number(format.value) && Number(value) <= Number(format.value2);
              break;
            case 'contains':
              conditionMet = value?.toString().includes(format.value);
              break;
            case 'duplicate':
              // Check for duplicates in range
              const values = getRangeValues(format.range);
              conditionMet = values.filter(v => v === value).length > 1;
              break;
            case 'unique':
              // Check for unique values in range
              const uniqueValues = getRangeValues(format.range);
              conditionMet = uniqueValues.filter(v => v === value).length === 1;
              break;
          }
          
          if (conditionMet) {
            style = { ...style, ...format.style };
          }
        }
      }
    });
    
    return style;
  }, [data.conditionalFormats, data.cells, evaluateFormula, getRangeValues]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (isEditing) return;
      
      const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
      const ctrlKey = isMac ? e.metaKey : e.ctrlKey;
      
      if (ctrlKey) {
        switch (e.key) {
          case 'c':
            e.preventDefault();
            copyCells();
            break;
          case 'v':
            e.preventDefault();
            pasteCells();
            break;
          case 'z':
            e.preventDefault();
            undo();
            break;
          case 'y':
            e.preventDefault();
            redo();
            break;
          case 'f':
            e.preventDefault();
            // Show find dialog
            break;
          case 's':
            e.preventDefault();
            // Save spreadsheet
            break;
          case 'b':
            e.preventDefault();
            // Bold
            break;
          case 'i':
            e.preventDefault();
            // Italic
            break;
          case 'u':
            e.preventDefault();
            // Underline
            break;
        }
      } else {
        switch (e.key) {
          case 'Enter':
            if (activeCell) {
              setIsEditing(true);
              const cell = data.cells[activeCell];
              setEditValue(cell?.formula || cell?.value || '');
            }
            break;
          case 'Delete':
          case 'Backspace':
            selectedCells.forEach(cellRef => {
              updateCell(cellRef, '');
            });
            break;
          case 'ArrowUp':
          case 'ArrowDown':
          case 'ArrowLeft':
          case 'ArrowRight':
            e.preventDefault();
            navigateCell(e.key);
            break;
        }
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isEditing, activeCell, selectedCells, copyCells, pasteCells, undo, redo, updateCell, data.cells]);

  // Apply style to selected cells
  const applyCellStyle = (style: CellStyle) => {
    selectedCells.forEach(cellRef => {
      setData(prev => ({
        ...prev,
        cells: {
          ...prev.cells,
          [cellRef]: {
            ...prev.cells[cellRef],
            style: {
              ...prev.cells[cellRef]?.style,
              ...style
            }
          }
        }
      }));
    });
  };

  // Navigate cells with arrow keys
  const navigateCell = (key: string) => {
    const [col, row] = activeCell.match(/([A-Z]+)(\d+)/)!.slice(1);
    const colNum = letterToColumn(col);
    const rowNum = parseInt(row);
    
    let newCol = colNum;
    let newRow = rowNum;
    
    switch (key) {
      case 'ArrowUp':
        newRow = Math.max(1, rowNum - 1);
        break;
      case 'ArrowDown':
        newRow = Math.min(data.rows, rowNum + 1);
        break;
      case 'ArrowLeft':
        newCol = Math.max(0, colNum - 1);
        break;
      case 'ArrowRight':
        newCol = Math.min(data.columns - 1, colNum + 1);
        break;
    }
    
    const newCellRef = `${columnToLetter(newCol)}${newRow}`;
    setActiveCell(newCellRef);
    setSelectedCells(new Set([newCellRef]));
  };

  // Export to CSV
  const exportToCSV = () => {
    const rows: string[][] = [];
    
    for (let r = 1; r <= data.rows; r++) {
      const row: string[] = [];
      for (let c = 0; c < data.columns; c++) {
        const cellRef = `${columnToLetter(c)}${r}`;
        const cell = data.cells[cellRef];
        const value = cell?.formula ? evaluateFormula(cell.formula, cellRef) : cell?.value || '';
        row.push(String(value));
      }
      rows.push(row);
    }
    
    const csv = rows.map(row => row.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `spreadsheet_${new Date().toISOString()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Import from CSV
  const importFromCSV = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      const rows = text.split('\n');
      const newCells: Record<string, Cell> = {};
      
      rows.forEach((row, r) => {
        const cols = row.split(',');
        cols.forEach((value, c) => {
          if (value) {
            const cellRef = `${columnToLetter(c)}${r + 1}`;
            newCells[cellRef] = {
              value: value.trim(),
              type: detectCellType(value.trim())
            };
          }
        });
      });
      
      setData(prev => ({ ...prev, cells: newCells }));
    };
    reader.readAsText(file);
  };

  // Initialize with empty spreadsheet - no dummy data
  useEffect(() => {
    // Start with empty cells
    setData(prev => ({
      ...prev,
      cells: {},
      conditionalFormats: []
    }));
  }, []);

  // Set up the grid API for the agent to use
  useEffect(() => {
    if (typeof window !== 'undefined') {
      console.log('🎯 Setting up grid API for agent');
      (window as any).grid = {
        // Write value to a cell with optional citation/source
        write: (cellRef: string, value: any, options?: { href?: string; source?: string; sourceUrl?: string }) => {
          console.log(`Grid API: Writing to ${cellRef}:`, value, options);
          setData(prev => ({
            ...prev,
            cells: {
              ...prev.cells,
              [cellRef]: {
                value,
                type: detectCellType(value),
                ...(options?.href && { link: options.href }),
                ...(options?.source && { comment: options.source }),
                ...(options?.sourceUrl && { sourceUrl: options.sourceUrl })
              }
            }
          }));
        },
        
        // Set formula for a cell
        formula: (cellRef: string, formula: string) => {
          console.log(`Grid API: Setting formula for ${cellRef}:`, formula);
          setData(prev => ({
            ...prev,
            cells: {
              ...prev.cells,
              [cellRef]: {
                value: 0,
                formula,
                type: 'formula'
              }
            }
          }));
        },
        
        // Apply style to a cell
        style: (cellRef: string, style: any) => {
          console.log(`Grid API: Styling ${cellRef}:`, style);
          setData(prev => ({
            ...prev,
            cells: {
              ...prev.cells,
              [cellRef]: {
                ...prev.cells[cellRef],
                style
              }
            }
          }));
        },
        
        // Clear cells
        clear: (startCell: string, endCell: string) => {
          const [startCol, startRow] = startCell.match(/([A-Z]+)(\d+)/)!.slice(1);
          const [endCol, endRow] = endCell.match(/([A-Z]+)(\d+)/)!.slice(1);
          const startColNum = letterToColumn(startCol);
          const endColNum = letterToColumn(endCol);
          const startRowNum = parseInt(startRow);
          const endRowNum = parseInt(endRow);
          
          setData(prev => {
            const newCells = { ...prev.cells };
            for (let row = startRowNum; row <= endRowNum; row++) {
              for (let col = startColNum; col <= endColNum; col++) {
                const cellRef = `${columnToLetter(col)}${row}`;
                delete newCells[cellRef];
              }
            }
            return { ...prev, cells: newCells };
          });
        },
        
        // Get cell value
        getValue: (cellRef: string) => {
          return dataRef.current.cells[cellRef]?.value;
        },
        
        // Get current state
        getState: () => {
          return { cells: dataRef.current.cells };
        },
        
        // Set state
        setState: (state: any) => {
          if (state?.cells) {
            setData(prev => ({ ...prev, cells: state.cells }));
          }
        },
        
        // Set column width
        setColumnWidth: (col: number, width: number) => {
          setData(prev => ({
            ...prev,
            columnWidths: {
              ...prev.columnWidths,
              [col]: width
            }
          }));
        },
        
        // Set row height
        setRowHeight: (row: number, height: number) => {
          setData(prev => ({
            ...prev,
            rowHeights: {
              ...prev.rowHeights,
              [row]: height
            }
          }));
        },
        
        // Format cell (currency, percentage, number, etc.)
        format: (cellRef: string, format: string) => {
          setData(prev => ({
            ...prev,
            cells: {
              ...prev.cells,
              [cellRef]: {
                ...prev.cells[cellRef],
                type: format as any
              }
            }
          }));
        },
        
        // Create a link in a cell
        link: (cellRef: string, text: string, url: string) => {
          setData(prev => ({
            ...prev,
            cells: {
              ...prev.cells,
              [cellRef]: {
                value: text,
                type: 'link',
                link: url
              }
            }
          }));
        },
        
        // Write range of values
        writeRange: (startCell: string, endCell: string, values: any[][]) => {
          const [startCol, startRow] = startCell.match(/([A-Z]+)(\d+)/)!.slice(1);
          const [endCol, endRow] = endCell.match(/([A-Z]+)(\d+)/)!.slice(1);
          const startColNum = letterToColumn(startCol);
          const startRowNum = parseInt(startRow);
          
          setData(prev => {
            const newCells = { ...prev.cells };
            for (let i = 0; i < values.length; i++) {
              for (let j = 0; j < values[i].length; j++) {
                const cellRef = `${columnToLetter(startColNum + j)}${startRowNum + i}`;
                newCells[cellRef] = {
                  value: values[i][j],
                  type: detectCellType(values[i][j])
                };
              }
            }
            return { ...prev, cells: newCells };
          });
        },
        
        // Create chart
        createChart: (type: string, options: any) => {
          console.log('Chart requested:', type, options);
          // Store chart data for rendering
          const chartData = {
            type,
            ...options,
            timestamp: Date.now()
          };
          
          // Store in a charts array (you'll need to add this to state)
          if (typeof window !== 'undefined') {
            (window as any).lastChart = chartData;
          }
          
          // Trigger chart panel if needed
          if (type === 'waterfall' || type === 'sankey' || type === 'heatmap') {
            console.log(`Advanced chart ${type} requested with data:`, options);
          }
        },
        
        // Create financial chart
        createFinancialChart: (type: string, data: any) => {
          console.log('Financial chart requested:', type, data);
          const chartData = {
            type: `financial-${type}`,
            data,
            timestamp: Date.now()
          };
          
          if (typeof window !== 'undefined') {
            (window as any).lastFinancialChart = chartData;
          }
        },
        
        // Create advanced chart
        createAdvancedChart: (type: string, range: string) => {
          console.log('Advanced chart requested:', type, range);
          const chartData = {
            type: `advanced-${type}`,
            range,
            timestamp: Date.now()
          };
          
          if (typeof window !== 'undefined') {
            (window as any).lastAdvancedChart = chartData;
          }
        },
        
        // Add chart (legacy)
        chart: (config: any) => {
          console.log('Chart requested:', config);
          // TODO: Implement chart rendering
        }
      };
    }
    
    // Cleanup
    return () => {
      if (typeof window !== 'undefined') {
        delete (window as any).grid;
      }
    };
  }, []); // Only create once on mount

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Toolbar */}
      <div className="border-b border-gray-200 p-2">
        <div className="flex items-center gap-2">
          {/* File operations */}
          <div className="flex items-center gap-1 px-2 border-r border-gray-200">
            <button className="p-1.5 hover:bg-gray-100 rounded" title="New">
              <FileSpreadsheet className="w-4 h-4" />
            </button>
            <button className="p-1.5 hover:bg-gray-100 rounded" title="Open">
              <FolderOpen className="w-4 h-4" />
            </button>
            <button className="p-1.5 hover:bg-gray-100 rounded" title="Save">
              <Save className="w-4 h-4" />
            </button>
            <button onClick={exportToCSV} className="p-1.5 hover:bg-gray-100 rounded" title="Export">
              <Download className="w-4 h-4" />
            </button>
            <label className="p-1.5 hover:bg-gray-100 rounded cursor-pointer" title="Import">
              <Upload className="w-4 h-4" />
              <input 
                type="file" 
                accept=".csv" 
                className="hidden" 
                onChange={(e) => e.target.files?.[0] && importFromCSV(e.target.files[0])}
              />
            </label>
          </div>

          {/* Edit operations */}
          <div className="flex items-center gap-1 px-2 border-r border-gray-200">
            <button onClick={undo} disabled={undoRedoState.past.length === 0} className="p-1.5 hover:bg-gray-100 rounded disabled:opacity-50" title="Undo">
              <Undo className="w-4 h-4" />
            </button>
            <button onClick={redo} disabled={undoRedoState.future.length === 0} className="p-1.5 hover:bg-gray-100 rounded disabled:opacity-50" title="Redo">
              <Redo className="w-4 h-4" />
            </button>
            <button onClick={copyCells} className="p-1.5 hover:bg-gray-100 rounded" title="Copy">
              <Copy className="w-4 h-4" />
            </button>
            <button onClick={pasteCells} className="p-1.5 hover:bg-gray-100 rounded" title="Paste">
              <Paste className="w-4 h-4" />
            </button>
            <div className="w-px h-6 bg-gray-300 mx-1" />
            <button 
              onClick={() => {
                if (confirm('Clear all data?')) {
                  setData({
                    cells: {},
                    columns: 26,
                    rows: 100,
                    frozenRows: 1,
                    frozenColumns: 1,
                    hiddenRows: new Set(),
                    hiddenColumns: new Set(),
                    rowHeights: {},
                    columnWidths: {},
                    mergedCells: [],
                    conditionalFormats: [],
                    namedRanges: {},
                    filters: {},
                    sorting: []
                  });
                  setChartData([]);
                  setChartConfig({});
                  setSelectedCells(new Set());
                  setActiveCell('A1');
                }
              }}
              className="p-1.5 hover:bg-red-50 rounded text-red-600" 
              title="Clear All"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>

          {/* Format operations */}
          <div className="flex items-center gap-1 px-2 border-r border-gray-200">
            <button 
              onClick={() => applyCellStyle({ fontWeight: 'bold' })}
              className="p-1.5 hover:bg-gray-100 rounded" 
              title="Bold"
            >
              <Bold className="w-4 h-4" />
            </button>
            <button 
              onClick={() => applyCellStyle({ fontStyle: 'italic' })}
              className="p-1.5 hover:bg-gray-100 rounded" 
              title="Italic"
            >
              <Italic className="w-4 h-4" />
            </button>
            <button 
              onClick={() => applyCellStyle({ textDecoration: 'underline' })}
              className="p-1.5 hover:bg-gray-100 rounded" 
              title="Underline"
            >
              <Underline className="w-4 h-4" />
            </button>
            <button 
              onClick={() => {
                const color = prompt('Enter text color (e.g., #000000 or red):');
                if (color) applyCellStyle({ color });
              }}
              className="p-1.5 hover:bg-gray-100 rounded" 
              title="Text Color"
            >
              <Palette className="w-4 h-4" />
            </button>
            <button 
              onClick={() => {
                const color = prompt('Enter background color (e.g., #fef3c7 or yellow):');
                if (color) applyCellStyle({ backgroundColor: color });
              }}
              className="p-1.5 hover:bg-gray-100 rounded" 
              title="Background Color"
            >
              <div className="w-4 h-4 border border-gray-400 rounded" style={{ backgroundColor: '#fef3c7' }} />
            </button>
          </div>

          {/* Alignment */}
          <div className="flex items-center gap-1 px-2 border-r border-gray-200">
            <button 
              onClick={() => applyCellStyle({ textAlign: 'left' })}
              className="p-1.5 hover:bg-gray-100 rounded" 
              title="Align Left"
            >
              <AlignLeft className="w-4 h-4" />
            </button>
            <button 
              onClick={() => applyCellStyle({ textAlign: 'center' })}
              className="p-1.5 hover:bg-gray-100 rounded" 
              title="Align Center"
            >
              <AlignCenter className="w-4 h-4" />
            </button>
            <button 
              onClick={() => applyCellStyle({ textAlign: 'right' })}
              className="p-1.5 hover:bg-gray-100 rounded" 
              title="Align Right"
            >
              <AlignRight className="w-4 h-4" />
            </button>
          </div>

          {/* Data operations */}
          <div className="flex items-center gap-1 px-2 border-r border-gray-200">
            <button className="p-1.5 hover:bg-gray-100 rounded" title="Sort Ascending">
              <SortAsc className="w-4 h-4" />
            </button>
            <button className="p-1.5 hover:bg-gray-100 rounded" title="Sort Descending">
              <SortDesc className="w-4 h-4" />
            </button>
            <button className="p-1.5 hover:bg-gray-100 rounded" title="Filter">
              <Filter className="w-4 h-4" />
            </button>
            <button className="p-1.5 hover:bg-gray-100 rounded" title="Sum">
              <Sigma className="w-4 h-4" />
            </button>
          </div>

          {/* View operations */}
          <div className="flex items-center gap-1 px-2 border-r border-gray-200">
            <button onClick={() => setShowChartPanel(!showChartPanel)} className="p-1.5 hover:bg-gray-100 rounded" title="Charts">
              <BarChart3 className="w-4 h-4" />
            </button>
            <button className="p-1.5 hover:bg-gray-100 rounded" title="Freeze Panes">
              <Lock className="w-4 h-4" />
            </button>
            <button onClick={() => setShowGridLines(!showGridLines)} className="p-1.5 hover:bg-gray-100 rounded" title="Grid Lines">
              <Grid3x3 className="w-4 h-4" />
            </button>
            <button onClick={() => setShowHeaders(!showHeaders)} className="p-1.5 hover:bg-gray-100 rounded" title="Headers">
              <Hash className="w-4 h-4" />
            </button>
          </div>

          {/* Search */}
          <div className="flex-1 flex items-center gap-2 px-2">
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Find..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  findCells(e.target.value);
                }}
                className="w-full pl-8 pr-2 py-1 text-sm border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-gray-400"
              />
              {findResults.length > 0 && (
                <div className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-500">
                  {currentFindIndex + 1}/{findResults.length}
                </div>
              )}
            </div>
          </div>

          {/* Status */}
          <div className="flex items-center gap-2 px-2 text-xs text-gray-600">
            {isCalculating && (
              <div className="flex items-center gap-1">
                <RefreshCw className="w-3 h-3 animate-spin" />
                <span>Calculating...</span>
              </div>
            )}
            <span>{Object.keys(data.cells).length} cells</span>
            <span>{selectedCells.size} selected</span>
          </div>
        </div>
      </div>

      {/* Formula Bar */}
      {showFormulaBar && (
        <div className="border-b border-gray-200 p-2 flex items-center gap-2">
          <div className="px-3 py-1 bg-gray-100 rounded text-sm font-mono min-w-20 text-center">
            {activeCell}
          </div>
          <Calculator className="w-4 h-4 text-gray-400" />
          <input
            ref={inputRef}
            type="text"
            value={isEditing ? editValue : (data.cells[activeCell]?.formula || data.cells[activeCell]?.value || '')}
            onChange={(e) => setEditValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                updateCell(activeCell, editValue.startsWith('=') ? '' : editValue, editValue.startsWith('=') ? editValue : undefined);
                setIsEditing(false);
              } else if (e.key === 'Escape') {
                setIsEditing(false);
                setEditValue('');
              }
            }}
            onFocus={() => {
              setIsEditing(true);
              setEditValue(data.cells[activeCell]?.formula || data.cells[activeCell]?.value || '');
            }}
            onBlur={() => {
              if (editValue !== (data.cells[activeCell]?.formula || data.cells[activeCell]?.value || '')) {
                updateCell(activeCell, editValue.startsWith('=') ? '' : editValue, editValue.startsWith('=') ? editValue : undefined);
              }
              setIsEditing(false);
            }}
            className="flex-1 px-2 py-1 text-sm border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-gray-400 font-mono"
          />
          {errors[activeCell] && (
            <div className="flex items-center gap-1 text-red-600 text-xs">
              <AlertCircle className="w-3 h-3" />
              <span>{errors[activeCell]}</span>
            </div>
          )}
        </div>
      )}

      {/* Main Grid Area */}
      <div className="flex-1 flex">
        {/* Spreadsheet Grid */}
        <div className="flex-1 overflow-auto" ref={gridRef}>
          <table className={cn("w-full border-collapse", !showGridLines && "border-0")}>
            {showHeaders && (
              <thead className="sticky top-0 z-20">
                <tr>
                  <th className="sticky left-0 z-30 w-12 h-8 bg-gray-100 border border-gray-300 text-xs" style={{ minWidth: '48px', maxWidth: '48px' }}></th>
                  {Array.from({ length: data.columns }).map((_, i) => (
                    <th 
                      key={i} 
                      className="h-8 bg-gray-100 border border-gray-300 text-xs font-medium min-w-20"
                      style={{ width: data.columnWidths?.[i] || 80 }}
                    >
                      {columnToLetter(i)}
                    </th>
                  ))}
                </tr>
              </thead>
            )}
            <tbody>
              {Array.from({ length: data.rows }).map((_, rowIndex) => {
                const row = rowIndex + 1;
                if (data.hiddenRows?.has(row)) return null;
                
                return (
                  <tr key={row}>
                    {showHeaders && (
                      <th className="sticky left-0 z-10 bg-gray-100 border border-gray-300 text-xs font-medium" style={{ minWidth: '48px', maxWidth: '48px', width: '48px' }}>
                        {row}
                      </th>
                    )}
                    {Array.from({ length: data.columns }).map((_, colIndex) => {
                      if (data.hiddenColumns?.has(colIndex)) return null;
                      
                      const cellRef = `${columnToLetter(colIndex)}${row}`;
                      const cell = data.cells[cellRef];
                      const isSelected = selectedCells.has(cellRef);
                      const isActive = activeCell === cellRef;
                      const conditionalStyle = applyConditionalFormatting(cellRef);
                      const cellStyle = { ...cell?.style, ...conditionalStyle };
                      
                      return (
                        <td
                          key={cellRef}
                          className={cn(
                            "relative border text-sm p-1 cursor-cell",
                            showGridLines ? "border-gray-300" : "border-transparent",
                            isActive && "ring-2 ring-blue-500 ring-inset z-10",
                            isSelected && !isActive && "bg-blue-50",
                            cell?.type === 'formula' && "bg-gray-50"
                          )}
                          style={{
                            ...cellStyle,
                            height: data.rowHeights?.[row] || 24,
                            width: data.columnWidths?.[colIndex] || 80
                          }}
                          onClick={() => {
                            setActiveCell(cellRef);
                            setSelectedCells(new Set([cellRef]));
                          }}
                          onMouseDown={(e) => {
                            // Start selection
                            if (e.shiftKey) {
                              // Range selection
                              const [startCol, startRow] = activeCell.match(/([A-Z]+)(\d+)/)!.slice(1);
                              const [endCol, endRow] = cellRef.match(/([A-Z]+)(\d+)/)!.slice(1);
                              
                              const startColNum = letterToColumn(startCol);
                              const endColNum = letterToColumn(endCol);
                              const startRowNum = parseInt(startRow);
                              const endRowNum = parseInt(endRow);
                              
                              const minCol = Math.min(startColNum, endColNum);
                              const maxCol = Math.max(startColNum, endColNum);
                              const minRow = Math.min(startRowNum, endRowNum);
                              const maxRow = Math.max(startRowNum, endRowNum);
                              
                              const newSelection = new Set<string>();
                              for (let r = minRow; r <= maxRow; r++) {
                                for (let c = minCol; c <= maxCol; c++) {
                                  newSelection.add(`${columnToLetter(c)}${r}`);
                                }
                              }
                              setSelectedCells(newSelection);
                            } else if (e.ctrlKey || e.metaKey) {
                              // Multi-selection
                              const newSelection = new Set(selectedCells);
                              if (newSelection.has(cellRef)) {
                                newSelection.delete(cellRef);
                              } else {
                                newSelection.add(cellRef);
                              }
                              setSelectedCells(newSelection);
                            } else {
                              setActiveCell(cellRef);
                              setSelectedCells(new Set([cellRef]));
                            }
                          }}
                          onDoubleClick={() => {
                            setIsEditing(true);
                            setEditValue(cell?.formula || cell?.value || '');
                            setTimeout(() => inputRef.current?.focus(), 0);
                          }}
                        >
                          {cell && (
                            <div className={cn(
                              "w-full h-full flex items-center",
                              cellStyle?.textAlign === 'center' && "justify-center",
                              cellStyle?.textAlign === 'right' && "justify-end"
                            )}>
                              {/* If cell has sourceUrl (citation), make it clickable */}
                              {cell.sourceUrl || cell.link ? (
                                <a 
                                  href={cell.sourceUrl || cell.link} 
                                  target="_blank" 
                                  rel="noopener noreferrer" 
                                  className="text-blue-600 hover:underline cursor-pointer"
                                  title={cell.sourceUrl ? `Source: ${cell.sourceUrl}` : ''}
                                >
                                  {cell.type === 'currency' ? (
                                    <span>{typeof cell.value === 'number' ? `$${cell.value.toLocaleString()}` : cell.value}</span>
                                  ) : cell.type === 'percentage' ? (
                                    <span>{typeof cell.value === 'number' ? `${(cell.value * 100).toFixed(1)}%` : cell.value}</span>
                                  ) : cell.formula ? (
                                    <span>{evaluateFormula(cell.formula, cellRef)}</span>
                                  ) : (
                                    <span>{cell.value}</span>
                                  )}
                                  {cell.sourceUrl && <Link2 className="w-3 h-3 inline ml-1" />}
                                </a>
                              ) : cell.type === 'link' ? (
                                <a href={cell.value} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                                  <Link2 className="w-3 h-3 inline mr-1" />
                                  {cell.value}
                                </a>
                              ) : cell.type === 'currency' ? (
                                <span>{typeof cell.value === 'number' ? `$${cell.value.toLocaleString()}` : cell.value}</span>
                              ) : cell.type === 'percentage' ? (
                                <span>{typeof cell.value === 'number' ? `${(cell.value * 100).toFixed(1)}%` : cell.value}</span>
                              ) : cell.formula ? (
                                <span>{evaluateFormula(cell.formula, cellRef)}</span>
                              ) : (
                                <span>{cell.value}</span>
                              )}
                            </div>
                          )}
                          {cell?.comment && (
                            <div className="absolute top-0 right-0 w-0 h-0 border-t-8 border-t-yellow-400 border-l-8 border-l-transparent" />
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Chart Panel */}
        {showChartPanel && (
          <div className="w-80 border-l border-gray-200 p-4 bg-gray-50 overflow-y-auto">
            <h3 className="text-sm font-medium mb-3">Insert Chart</h3>
            <div className="grid grid-cols-3 gap-2 mb-4">
              <button
                onClick={() => setSelectedChart('bar')}
                className={cn(
                  "p-3 rounded border bg-white hover:bg-gray-100",
                  selectedChart === 'bar' && "ring-2 ring-blue-500"
                )}
              >
                <BarChart3 className="w-6 h-6 mx-auto mb-1" />
                <span className="text-xs">Bar</span>
              </button>
              <button
                onClick={() => setSelectedChart('line')}
                className={cn(
                  "p-3 rounded border bg-white hover:bg-gray-100",
                  selectedChart === 'line' && "ring-2 ring-blue-500"
                )}
              >
                <LineChart className="w-6 h-6 mx-auto mb-1" />
                <span className="text-xs">Line</span>
              </button>
              <button
                onClick={() => setSelectedChart('pie')}
                className={cn(
                  "p-3 rounded border bg-white hover:bg-gray-100",
                  selectedChart === 'pie' && "ring-2 ring-blue-500"
                )}
              >
                <PieChart className="w-6 h-6 mx-auto mb-1" />
                <span className="text-xs">Pie</span>
              </button>
            </div>
            
            {/* Show chart if we have data */}
            {chartData.length > 0 && chartConfig.type && (
              <div className="mb-4">
                <SpreadsheetChart
                  data={chartData}
                  type={chartConfig.type}
                  xKey={chartConfig.xKey}
                  yKeys={chartConfig.yKeys}
                  title={chartConfig.title}
                  height={250}
                />
              </div>
            )}
            
            {selectedChart && (
              <div>
                <div className="mb-3">
                  <label className="text-xs font-medium text-gray-700">Data Range</label>
                  <input
                    type="text"
                    placeholder="e.g., A1:D10"
                    className="w-full mt-1 px-2 py-1 text-sm border border-gray-200 rounded"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        const range = (e.target as HTMLInputElement).value;
                        if (range && (window as any).grid) {
                          (window as any).grid.createChart(selectedChart, { range, title: 'Chart' });
                        }
                      }
                    }}
                  />
                </div>
                <button 
                  className="w-full px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
                  onClick={() => {
                    const input = document.querySelector('.chart-range-input') as HTMLInputElement;
                    if (input?.value && (window as any).grid) {
                      (window as any).grid.createChart(selectedChart, { range: input.value, title: 'Chart' });
                    }
                  }}
                >
                  Insert Chart
                </button>
              </div>
            )}
            
            <div className="mt-6">
              <h4 className="text-xs font-medium text-gray-700 mb-2">Quick Analysis</h4>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between p-2 bg-white rounded">
                  <span>Selected Cells:</span>
                  <span className="font-mono">{selectedCells.size}</span>
                </div>
                {selectedCells.size > 0 && (
                  <>
                    <div className="flex justify-between p-2 bg-white rounded">
                      <span>Sum:</span>
                      <span className="font-mono">
                        {Array.from(selectedCells).reduce((sum, cellRef) => {
                          const cell = data.cells[cellRef];
                          const value = cell?.formula ? evaluateFormula(cell.formula, cellRef) : cell?.value;
                          return sum + (typeof value === 'number' ? value : 0);
                        }, 0).toLocaleString()}
                      </span>
                    </div>
                    <div className="flex justify-between p-2 bg-white rounded">
                      <span>Average:</span>
                      <span className="font-mono">
                        {(Array.from(selectedCells).reduce((sum, cellRef) => {
                          const cell = data.cells[cellRef];
                          const value = cell?.formula ? evaluateFormula(cell.formula, cellRef) : cell?.value;
                          return sum + (typeof value === 'number' ? value : 0);
                        }, 0) / selectedCells.size).toFixed(2)}
                      </span>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Status Bar */}
      <div className="border-t border-gray-200 px-4 py-1 flex items-center justify-between text-xs text-gray-600">
        <div className="flex items-center gap-4">
          <span>Ready</span>
          {activeCell && data.cells[activeCell] && (
            <span className="font-mono">
              {data.cells[activeCell].type} | {data.cells[activeCell].formula || data.cells[activeCell].value}
            </span>
          )}
        </div>
        <div className="flex items-center gap-4">
          <span>{data.rows} × {data.columns}</span>
          <span>100%</span>
        </div>
      </div>
    </div>
  );
}