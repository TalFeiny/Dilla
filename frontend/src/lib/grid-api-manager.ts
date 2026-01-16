/**
 * GridAPIManager - Production-grade singleton for managing grid instances
 * Prevents re-render loops by maintaining stable references
 */

import React from 'react';

type CellValue = string | number | boolean | null | undefined;

interface CellStyle {
  fontWeight?: 'normal' | 'bold';
  fontStyle?: 'normal' | 'italic';
  textDecoration?: 'none' | 'underline';
  backgroundColor?: string;
  color?: string;
  fontSize?: number;
  textAlign?: 'left' | 'center' | 'right';
}

interface GridAPI {
  write: (cell: string, value: CellValue, options?: any) => string;
  formula: (cell: string, formula: string) => string;
  style: (cell: string, style: CellStyle) => string;
  format: (cell: string, format: string) => string;
  clear: (startCell: string, endCell?: string) => string;
  createChart: (type: string, options: any) => string;
  createChartBatch: (charts: Array<{type: string, options: any}>) => string;
  createFinancialChart: (type: string, data?: any) => string;
  link: (cell: string, text: string, url: string) => string;
  getValue: (cell: string) => any;
  getState: () => any;
  setState: (state: any) => string;
  setColumnWidth: (col: number, width: number) => string;
  setRowHeight: (row: number, height: number) => string;
  writeRange: (startCell: string, endCell: string, values: any[][]) => string;
  chart: (config: any) => string;
  createAdvancedChart: (type: string, range: string) => string;
}

interface GridInstance {
  id: string;
  api: GridAPI;
  proxy: GridAPI;
  setData: React.Dispatch<React.SetStateAction<any>>;
  dataRef: React.MutableRefObject<any>;
  setChartData?: React.Dispatch<React.SetStateAction<any[]>>;
  detectCellType: (value: any) => string;
}

type GridEventType = 'register' | 'unregister' | 'command' | 'error';

interface GridEvent {
  type: GridEventType;
  gridId: string;
  data?: any;
}

type GridEventListener = (event: GridEvent) => void;

class GridAPIManager {
  private static instance: GridAPIManager;
  private gridInstances: Map<string, GridInstance> = new Map();
  private listeners: Set<GridEventListener> = new Set();
  private commandQueue: Map<string, Array<() => void>> = new Map();

  private constructor() {
    // Singleton constructor
    console.log('[GridAPIManager] Initialized - singleton created');
    if (typeof window !== 'undefined') {
      console.log('[GridAPIManager] Window storage active');
    }
  }

  /**
   * Get singleton instance
   */
  public static getInstance(): GridAPIManager {
    // Store on global window object to survive HMR
    if (typeof window !== 'undefined') {
      if (!(window as any).__gridAPIManager) {
        (window as any).__gridAPIManager = new GridAPIManager();
      }
      return (window as any).__gridAPIManager;
    }
    
    // Fallback for SSR
    if (!GridAPIManager.instance) {
      GridAPIManager.instance = new GridAPIManager();
    }
    return GridAPIManager.instance;
  }

  /**
   * Register a grid instance with stable proxy
   */
  public registerGrid(
    id: string,
    setData: React.Dispatch<React.SetStateAction<any>>,
    dataRef: React.MutableRefObject<any>,
    detectCellType: (value: any) => string,
    setChartData?: React.Dispatch<React.SetStateAction<any[]>>
  ): GridAPI {
    // Check if already registered and return existing proxy
    const existing = this.gridInstances.get(id);
    if (existing) {
      console.log(`[GridAPIManager] Grid ${id} already registered, returning existing proxy`);
      return existing.proxy;
    }
    
    console.log(`[GridAPIManager] Registering new grid: ${id}`);

    // Create the actual API implementation
    const api: GridAPI = {
      write: (cellRef: string, value: any, options?: any) => {
        console.log(`[GridAPI ${id}] Writing to ${cellRef}:`, value, options);
        setData(prev => ({
          ...prev,
          cells: {
            ...prev.cells,
            [cellRef]: {
              value,
              type: detectCellType(value),
              ...(options?.href && { link: options.href }),
              ...(options?.source && { comment: options.source }),
              ...(options?.sourceUrl && { sourceUrl: options.sourceUrl }),
              ...(options?.citation && { citation: options.citation })
            }
          }
        }));
        return `Written ${value} to ${cellRef}`;
      },

      formula: (cellRef: string, formula: string) => {
        console.log(`[GridAPI ${id}] Setting formula for ${cellRef}:`, formula);
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
        return `Formula set in ${cellRef}: ${formula}`;
      },

      style: (cellRef: string, style: any) => {
        console.log(`[GridAPI ${id}] Styling ${cellRef}:`, style);
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
        return `Style applied to ${cellRef}`;
      },

      clear: (startCell: string, endCell: string) => {
        const [startCol, startRow] = this.parseCellRef(startCell);
        const [endCol, endRow] = this.parseCellRef(endCell);
        
        setData(prev => {
          const newCells = { ...prev.cells };
          for (let row = startRow; row <= endRow; row++) {
            for (let col = startCol; col <= endCol; col++) {
              const cellRef = `${this.columnToLetter(col)}${row}`;
              delete newCells[cellRef];
            }
          }
          return { ...prev, cells: newCells };
        });
        return `Cleared range ${startCell}:${endCell}`;
      },

      getValue: (cellRef: string) => {
        return dataRef.current.cells[cellRef]?.value;
      },

      getState: () => {
        return { cells: dataRef.current.cells };
      },

      setState: (state: any) => {
        if (state?.cells) {
          setData(prev => ({ ...prev, cells: state.cells }));
        }
        return 'State updated';
      },

      setColumnWidth: (col: number, width: number) => {
        setData(prev => ({
          ...prev,
          columnWidths: {
            ...prev.columnWidths,
            [col]: width
          }
        }));
        return `Column ${col} width set to ${width}px`;
      },

      setRowHeight: (row: number, height: number) => {
        setData(prev => ({
          ...prev,
          rowHeights: {
            ...prev.rowHeights,
            [row]: height
          }
        }));
        return `Row ${row} height set to ${height}px`;
      },

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
        return `Format ${format} applied to ${cellRef}`;
      },

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
        return `Link created in ${cellRef}`;
      },

      writeRange: (startCell: string, endCell: string, values: any[][]) => {
        const [startCol, startRow] = this.parseCellRef(startCell);
        
        setData(prev => {
          const newCells = { ...prev.cells };
          for (let i = 0; i < values.length; i++) {
            for (let j = 0; j < values[i].length; j++) {
              const cellRef = `${this.columnToLetter(startCol + j)}${startRow + i}`;
              newCells[cellRef] = {
                value: values[i][j],
                type: detectCellType(values[i][j])
              };
            }
          }
          return { ...prev, cells: newCells };
        });
        return `Range written ${startCell}:${endCell}`;
      },

      createChart: (type: string, options: any) => {
        console.log(`[GridAPI ${id}] Chart requested:`, type, options);
        const newChart = {
          id: `chart-${Date.now()}`,
          type,
          ...options,
          timestamp: Date.now()
        };
        
        // Update chart data state if available
        if (setChartData) {
          setChartData(prev => [...prev, newChart]);
        }
        
        // Store in window for backward compatibility
        if (typeof window !== 'undefined') {
          (window as any).lastChart = newChart;
        }
        
        this.emit({ type: 'command', gridId: id, data: { command: 'createChart', type, options } });
        return `Chart created: ${type}`;
      },

      createChartBatch: (charts: Array<{type: string, options: any}>) => {
        console.log(`[GridAPI ${id}] Creating batch of ${charts.length} charts`);
        const newCharts = charts.map((chart, index) => ({
          id: `chart-${Date.now()}-${index}`,
          type: chart.type,
          ...chart.options,
          timestamp: Date.now() + index,
          position: chart.options.position || `H${5 + (index * 15)}`
        }));
        
        // Update chart data state if available
        if (setChartData) {
          setChartData(prev => [...prev, ...newCharts]);
        }
        
        // Store in window for backward compatibility
        if (typeof window !== 'undefined') {
          (window as any).chartBatch = newCharts;
          window.dispatchEvent(new CustomEvent('chartBatchCreated', {
            detail: { count: charts.length }
          }));
        }
        
        this.emit({ type: 'command', gridId: id, data: { command: 'createChartBatch', charts } });
        return `Created batch of ${charts.length} charts`;
      },

      createFinancialChart: (type: string, data: any) => {
        console.log(`[GridAPI ${id}] Financial chart requested:`, type, data);
        if (typeof window !== 'undefined') {
          (window as any).lastFinancialChart = {
            type: `financial-${type}`,
            data,
            timestamp: Date.now()
          };
        }
        return `Financial chart created: ${type}`;
      },

      createAdvancedChart: (type: string, range: string) => {
        console.log(`[GridAPI ${id}] Advanced chart requested:`, type, range);
        if (typeof window !== 'undefined') {
          (window as any).lastAdvancedChart = {
            type: `advanced-${type}`,
            range,
            timestamp: Date.now()
          };
        }
        return `Advanced chart created: ${type}`;
      },

      chart: (config: any) => {
        console.log(`[GridAPI ${id}] Chart requested:`, config);
        return 'Chart created';
      }
    };

    // Create a stable proxy that won't change
    const proxy = new Proxy(api, {
      get: (target, prop) => {
        if (typeof target[prop] === 'function') {
          return (...args: any[]) => {
            try {
              return target[prop](...args);
            } catch (error) {
              console.error(`[GridAPI ${id}] Error in ${String(prop)}:`, error);
              this.emit({ type: 'error', gridId: id, data: { method: prop, error } });
              throw error;
            }
          };
        }
        return target[prop];
      }
    });

    // Store the instance
    const instance: GridInstance = {
      id,
      api,
      proxy,
      setData,
      dataRef,
      setChartData,
      detectCellType
    };

    this.gridInstances.set(id, instance);

    // Process any queued commands for this grid
    const queue = this.commandQueue.get(id);
    if (queue && queue.length > 0) {
      console.log(`[GridAPIManager] Processing ${queue.length} queued commands for grid ${id}`);
      queue.forEach(cmd => cmd());
      this.commandQueue.delete(id);
    }

    // Emit registration event
    this.emit({ type: 'register', gridId: id });

    // Also expose globally for backward compatibility
    if (typeof window !== 'undefined') {
      (window as any).grid = proxy;
      (window as any).gridApi = proxy;
      console.log(`[GridAPIManager] Grid ${id} exposed globally as window.grid`);
    }

    return proxy;
  }

  /**
   * Unregister a grid instance
   */
  public unregisterGrid(id: string): void {
    console.log(`[GridAPIManager] Unregistering grid: ${id}`);
    
    const instance = this.gridInstances.get(id);
    if (instance) {
      this.gridInstances.delete(id);
      this.emit({ type: 'unregister', gridId: id });

      // Clean up global references if this was the last grid
      if (this.gridInstances.size === 0 && typeof window !== 'undefined') {
        (window as any).grid = null;
        (window as any).gridApi = null;
      }
    }
  }

  /**
   * Get a grid instance by ID
   */
  public getGrid(id: string): GridAPI | null {
    const instance = this.gridInstances.get(id);
    return instance ? instance.proxy : null;
  }

  /**
   * Get the default grid (first registered or 'default')
   */
  public getDefaultGrid(): GridAPI | null {
    // Try 'default' ID first
    const defaultGrid = this.gridInstances.get('default');
    if (defaultGrid) return defaultGrid.proxy;

    // Return first grid if any
    const firstGrid = this.gridInstances.values().next().value;
    return firstGrid ? firstGrid.proxy : null;
  }

  /**
   * Queue a command for a grid that hasn't been registered yet
   */
  public queueCommand(gridId: string, command: () => void): void {
    if (!this.commandQueue.has(gridId)) {
      this.commandQueue.set(gridId, []);
    }
    this.commandQueue.get(gridId)!.push(command);
  }

  /**
   * Add event listener
   */
  public addEventListener(listener: GridEventListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  /**
   * Emit event to all listeners
   */
  private emit(event: GridEvent): void {
    this.listeners.forEach(listener => {
      try {
        listener(event);
      } catch (error) {
        console.error('[GridAPIManager] Error in event listener:', error);
      }
    });
  }

  /**
   * Helper: Parse cell reference
   */
  private parseCellRef(cellRef: string): [number, number] {
    const match = cellRef.match(/([A-Z]+)(\d+)/);
    if (!match) throw new Error(`Invalid cell reference: ${cellRef}`);
    
    const col = this.letterToColumn(match[1]);
    const row = parseInt(match[2]);
    return [col, row];
  }

  /**
   * Helper: Convert column letter to number
   */
  private letterToColumn(letter: string): number {
    let col = 0;
    for (let i = 0; i < letter.length; i++) {
      col = col * 26 + (letter.charCodeAt(i) - 64);
    }
    return col - 1;
  }

  /**
   * Helper: Convert column number to letter
   */
  private columnToLetter(col: number): string {
    let letter = '';
    while (col >= 0) {
      letter = String.fromCharCode((col % 26) + 65) + letter;
      col = Math.floor(col / 26) - 1;
    }
    return letter;
  }

  /**
   * Get all registered grid IDs
   */
  public getGridIds(): string[] {
    return Array.from(this.gridInstances.keys());
  }

  /**
   * Check if a grid is registered
   */
  public hasGrid(id: string): boolean {
    return this.gridInstances.has(id);
  }
}

// Export singleton instance getter
export const getGridAPIManager = () => GridAPIManager.getInstance();

// Export types
export type { GridAPI, GridEvent, GridEventListener, GridEventType };