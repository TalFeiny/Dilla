/**
 * useGridAPI - React hook for connecting components to GridAPIManager
 * Returns a stable GridAPI reference that won't cause re-renders
 */

import { useEffect, useRef, useCallback, useMemo, useState } from 'react';
import { getGridAPIManager, GridAPI } from '@/lib/grid-api-manager';

interface UseGridAPIOptions {
  gridId?: string;
  setData: React.Dispatch<React.SetStateAction<any>>;
  dataRef: React.MutableRefObject<any>;
  detectCellType: (value: any) => string;
  setChartData?: React.Dispatch<React.SetStateAction<any[]>>;
}

/**
 * Hook to get a stable GridAPI instance
 * @param options Configuration for the grid
 * @returns Stable GridAPI proxy that won't trigger re-renders
 */
export function useGridAPI(options: UseGridAPIOptions): GridAPI | null {
  const { 
    gridId = 'default', 
    setData, 
    dataRef, 
    detectCellType,
    setChartData 
  } = options;
  
  // Use useState to ensure stable reference across renders
  const [api, setApi] = useState<GridAPI | null>(null);
  const hasInitialized = useRef(false);
  
  // Initialize only once
  useEffect(() => {
    if (hasInitialized.current) return;
    hasInitialized.current = true;
    
    console.log(`[useGridAPI] Registering grid: ${gridId}`);
    const manager = getGridAPIManager();
    
    // Register and get stable proxy
    const gridApi = manager.registerGrid(
      gridId,
      setData,
      dataRef,
      detectCellType,
      setChartData
    );
    
    setApi(gridApi);
    
    // Cleanup on unmount
    return () => {
      console.log(`[useGridAPI] Cleaning up grid: ${gridId}`);
      manager.unregisterGrid(gridId);
      setApi(null);
      hasInitialized.current = false;
    };
  }, []); // Empty deps - only run once

  return api;
}

/**
 * Hook to get an existing grid API without registering
 * Useful for components that need to access the grid but don't create it
 */
export function useExistingGridAPI(gridId?: string): GridAPI | null {
  const manager = getGridAPIManager();
  const apiRef = useRef<GridAPI | null>(null);

  useEffect(() => {
    const checkForGrid = () => {
      const api = gridId 
        ? manager.getGrid(gridId) 
        : manager.getDefaultGrid();
      
      if (api && api !== apiRef.current) {
        apiRef.current = api;
      }
    };

    // Check immediately
    checkForGrid();

    // Listen for grid registration events
    const unsubscribe = manager.addEventListener((event) => {
      if (event.type === 'register' || event.type === 'unregister') {
        checkForGrid();
      }
    });

    return unsubscribe;
  }, [gridId]);

  return apiRef.current;
}

/**
 * Hook to execute grid commands
 * Returns a stable function that won't cause re-renders
 */
export function useGridCommand(gridId?: string) {
  const manager = getGridAPIManager();
  
  const executeCommand = useCallback((command: string) => {
    const api = gridId 
      ? manager.getGrid(gridId) 
      : manager.getDefaultGrid();
    
    if (!api) {
      console.warn(`[useGridCommand] Grid not found: ${gridId || 'default'}`);
      return { error: 'Grid not available' };
    }

    try {
      // Parse and execute command
      const match = command.match(/grid\.(\w+)\((.*)\)$/);
      if (!match) {
        throw new Error(`Invalid command format: ${command}`);
      }

      const [, method, argsStr] = match;
      
      if (typeof api[method] !== 'function') {
        throw new Error(`Method not found: ${method}`);
      }

      // Simple argument parsing (improve as needed)
      const args = argsStr ? JSON.parse(`[${argsStr}]`) : [];
      return api[method](...args);
    } catch (error) {
      console.error('[useGridCommand] Error:', error);
      return { error: error instanceof Error ? error.message : String(error) };
    }
  }, [gridId]);

  return executeCommand;
}