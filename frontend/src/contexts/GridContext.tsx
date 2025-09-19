'use client';

import React, { createContext, useContext, useRef, ReactNode, useMemo, useCallback } from 'react';
import { getGridAPIManager } from '@/lib/grid-api-manager';

type CommandResult = string | { error: string; queued?: boolean; command?: string };

interface GridContextType {
  executeCommand: (command: string) => Promise<CommandResult>;
  executeBatch: (commands: string[]) => Promise<CommandResult[]>;
}

const GridContext = createContext<GridContextType | undefined>(undefined);

export function GridProvider({ children }: { children: ReactNode }) {
  const managerRef = useRef(getGridAPIManager());
  const executeCommandRef = useRef<(command: string) => Promise<CommandResult>>();

  const executeCommand = useCallback(async (command: string): Promise<CommandResult> => {
    console.log('[GridContext] Executing command:', command.substring(0, 50) + '...');
    
    // Try multiple sources for grid API with better fallback logic
    let api = null;
    
    // First try window.gridApi (most reliable)
    if (typeof window !== 'undefined' && (window as any).gridApi) {
      api = (window as any).gridApi;
      console.log('[GridContext] Using window.gridApi');
    }
    
    // Then try window.grid
    if (!api && typeof window !== 'undefined' && (window as any).grid) {
      api = (window as any).grid;
      console.log('[GridContext] Using window.grid as fallback');
    }
    
    // Finally try the manager
    if (!api) {
      const manager = managerRef.current;
      api = manager.getDefaultGrid();
      if (api) {
        console.log('[GridContext] Using manager grid');
      }
    }
    
    if (!api) {
      console.warn('[GridContext] Grid API not available yet. Command will be retried.');
      // Try again after a short delay
      await new Promise(resolve => setTimeout(resolve, 100));
      
      // One more attempt
      if (typeof window !== 'undefined' && ((window as any).gridApi || (window as any).grid)) {
        api = (window as any).gridApi || (window as any).grid;
        console.log('[GridContext] Grid API available after retry');
      }
      
      if (!api) {
        return { error: 'Grid API not available', queued: true };
      }
    }

    try {
      // Parse command safely without eval
      // Format: grid.methodName(arg1, arg2, ...)
      const match = command.match(/grid\.(\w+)\((.*)\)$/);
      if (!match) {
        throw new Error(`Invalid command format: ${command}`);
      }

      const [, method, argsStr] = match;
      
      // Check if method exists (use api instead of gridApiRef.current)
      if (typeof api[method] !== 'function') {
        console.warn(`Method not found: ${method}. Available methods:`, Object.keys(api));
        throw new Error(`Method not found: ${method}`);
      }

      // Parse arguments safely
      const args = parseArguments(argsStr);
      
      // Execute method with error boundary
      try {
        const result = await api[method](...args);
        console.log(`[GridContext] Executed ${method} with args:`, args, 'Result:', result);
        return result || `Command executed: ${method}`;
      } catch (methodError) {
        console.error(`Error executing ${method}:`, methodError);
        return { error: `Failed to execute ${method}: ${methodError instanceof Error ? methodError.message : String(methodError)}` };
      }
    } catch (error) {
      console.error('Command execution error:', error);
      return { error: error instanceof Error ? error.message : String(error) };
    }
  }, []);

  // Store executeCommand in ref to break circular dependency
  executeCommandRef.current = executeCommand;

  const executeBatch = useCallback(async (commands: string[]): Promise<CommandResult[]> => {
    const results = [];
    
    // Check if API is available from manager
    const manager = managerRef.current;
    const api = manager.getDefaultGrid();
    
    if (!api) {
      console.warn('Grid API not available for batch execution');
      return commands.map(() => ({ error: 'Grid API not available', queued: true }));
    }
    
    // Use the ref to access executeCommand without creating a dependency
    const execCmd = executeCommandRef.current;
    if (!execCmd) {
      console.error('executeCommand not initialized');
      return commands.map(() => ({ error: 'System not initialized', queued: true }));
    }
    
    try {
      // Special handling for createChartBatch
      const chartCommands = commands.filter(cmd => cmd.includes('createChart('));
      const batchCommand = commands.find(cmd => cmd.includes('createChartBatch('));
      
      if (batchCommand) {
        // Execute batch command directly
        const batchResult = await execCmd(batchCommand);
        results.push(batchResult);
        
        // Filter out individual chart commands since they're handled by batch
        const nonChartCommands = commands.filter(
          cmd => !cmd.includes('createChart(') && !cmd.includes('createChartBatch(')
        );
        
        // Execute remaining commands with error handling
        for (const cmd of nonChartCommands) {
          try {
            const result = await execCmd(cmd);
            results.push(result);
          } catch (error) {
            console.error(`Failed to execute command: ${cmd}`, error);
            results.push({ error: error instanceof Error ? error.message : String(error), command: cmd });
          }
        }
      } else {
        // Execute all commands normally with error handling
        for (const cmd of commands) {
          try {
            const result = await execCmd(cmd);
            results.push(result);
          } catch (error) {
            console.error(`Failed to execute command: ${cmd}`, error);
            results.push({ error: error instanceof Error ? error.message : String(error), command: cmd });
          }
        }
      }
    } catch (error) {
      console.error('Batch execution error:', error);
      return commands.map(cmd => ({ error: error instanceof Error ? error.message : String(error), command: cmd }));
    }
    
    return results;
  }, []); // Empty deps - uses ref to access executeCommand

  // Memoize the context value to prevent re-renders
  // Stable references - these callbacks don't change
  const contextValue = useMemo(() => ({
    executeCommand,
    executeBatch
  }), []); // Empty deps - callbacks are stable due to useCallback

  return (
    <GridContext.Provider value={contextValue}>
      {children}
    </GridContext.Provider>
  );
}

export function useGrid() {
  const context = useContext(GridContext);
  if (context === undefined) {
    // Return a safe fallback instead of throwing
    console.warn('useGrid called outside of GridProvider. Returning no-op implementation.');
    return {
      executeCommand: async () => ({ error: 'Grid context not available' }),
      executeBatch: async () => []
    };
  }
  return context;
}

// Safe argument parser without eval
function parseArguments(argsStr: string): unknown[] {
  if (!argsStr.trim()) return [];
  
  const args: unknown[] = [];
  let current = '';
  let inString = false;
  let stringChar = '';
  let depth = 0;
  let escapeNext = false;
  
  for (let i = 0; i < argsStr.length; i++) {
    const char = argsStr[i];
    
    if (escapeNext) {
      current += char;
      escapeNext = false;
      continue;
    }
    
    if (char === '\\') {
      escapeNext = true;
      continue;
    }
    
    if (!inString) {
      if (char === '"' || char === "'") {
        inString = true;
        stringChar = char;
      } else if (char === '{' || char === '[') {
        depth++;
        current += char;
      } else if (char === '}' || char === ']') {
        depth--;
        current += char;
      } else if (char === ',' && depth === 0) {
        args.push(parseValue(current.trim()));
        current = '';
        continue;
      } else {
        current += char;
      }
    } else {
      if (char === stringChar) {
        inString = false;
      } else {
        current += char;
      }
    }
  }
  
  if (current.trim()) {
    args.push(parseValue(current.trim()));
  }
  
  return args;
}

function parseValue(value: string): any {
  // Handle quoted strings
  if ((value.startsWith('"') && value.endsWith('"')) || 
      (value.startsWith("'") && value.endsWith("'"))) {
    return value.slice(1, -1);
  }
  
  // Parse numbers
  if (/^-?\d+(\.\d+)?$/.test(value)) {
    return parseFloat(value);
  }
  
  // Parse booleans
  if (value === 'true') return true;
  if (value === 'false') return false;
  if (value === 'null') return null;
  if (value === 'undefined') return undefined;
  
  // Parse JSON objects/arrays
  if (value.startsWith('{') || value.startsWith('[')) {
    try {
      // First try direct JSON parse
      return JSON.parse(value);
    } catch {
      // If that fails, try fixing common issues
      try {
        // Replace single quotes with double quotes for JSON
        const fixed = value
          .replace(/'/g, '"')
          .replace(/(\w+):/g, '"$1":');
        return JSON.parse(fixed);
      } catch {
        // Return as string if all parsing fails
        return value;
      }
    }
  }
  
  // Default to string
  return value;
}