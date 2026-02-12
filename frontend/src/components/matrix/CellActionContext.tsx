'use client';

import React, { createContext, useContext, type ReactNode } from 'react';
import type { ActionExecutionRequest } from '@/lib/matrix/cell-action-registry';

/** Per-cell status: loading, success, or error. Key = rowId_columnId. */
export type CellActionStatusMap = Record<string, { state: 'loading' | 'success' | 'error'; message: string }>;

export interface CellActionContextValue {
  /** Run a cell action from parent (POST survives cell unmount). */
  onRunCellAction?: (request: ActionExecutionRequest) => Promise<void>;
  /** Open valuation method picker in parent (survives cell unmount). */
  onOpenValuationPicker?: (rowId: string, columnId: string, rowData: any, matrixData: any) => void;
  /** Request file upload from parent (survives cell unmount). */
  onRequestUploadDocument?: (rowId: string, columnId: string) => void;
  /** Per-cell status for in-cell display (replaces toast). Key = rowId_columnId. */
  cellActionStatus?: CellActionStatusMap;
}

const CellActionContext = createContext<CellActionContextValue | null>(null);

export function CellActionProvider({
  children,
  value,
}: {
  children: ReactNode;
  value: CellActionContextValue;
}) {
  return (
    <CellActionContext.Provider value={value}>
      {children}
    </CellActionContext.Provider>
  );
}

/**
 * Hook to access cell action callbacks from parent. Throws if used outside provider.
 * Use when CellDropdownRenderer is inside UnifiedMatrix (has provider).
 */
export function useCellActionContext(): CellActionContextValue {
  const ctx = useContext(CellActionContext);
  if (ctx === null) {
    throw new Error('useCellActionContext must be used within CellActionProvider');
  }
  return ctx;
}

/**
 * Optional hook that returns null if outside provider (for components that may render outside matrix).
 */
export function useCellActionContextOptional(): CellActionContextValue | null {
  return useContext(CellActionContext);
}
