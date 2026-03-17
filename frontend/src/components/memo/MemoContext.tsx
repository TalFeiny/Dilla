'use client';

import React, { createContext, useContext, useCallback, useMemo, useState, useRef, type ReactNode } from 'react';
import type { MatrixData, MatrixRow, MatrixCell } from '@/components/matrix/UnifiedMatrix';
import type { ScenarioBranch, ForecastMonth } from '@/hooks/useScenarioForkTree';
import type { ChartConfig } from '@/components/matrix/ChartViewport';
import { getClientBackendUrl } from '@/lib/backend-url';

// ---------------------------------------------------------------------------
// Driver types
// ---------------------------------------------------------------------------

export interface DriverDef {
  id: string;
  label: string;
  unit: 'percentage' | 'currency' | 'number' | 'months';
  min?: number;
  max?: number;
  step?: number;
  default?: number;
  group?: string; // e.g. 'revenue', 'costs', 'headcount'
  ripple?: string[]; // IDs of other drivers this affects
}

export interface DriverValue {
  id: string;
  value: number;
  source: 'default' | 'override' | 'inherited';
}

// ---------------------------------------------------------------------------
// Computed metrics
// ---------------------------------------------------------------------------

export interface ComputedMetric {
  id: string;
  label: string;
  value: number;
  unit: 'currency' | 'percentage' | 'number' | 'months' | 'ratio';
  trend?: 'up' | 'down' | 'flat';
  trendValue?: number;
  severity?: 'green' | 'amber' | 'red';
  derivation?: string; // hover explanation
}

// ---------------------------------------------------------------------------
// Signal types
// ---------------------------------------------------------------------------

export interface Signal {
  id: string;
  type: 'runway' | 'burn' | 'margin' | 'growth' | 'covenant' | 'general';
  severity: 'red' | 'amber' | 'blue';
  title: string;
  detail?: string;
  metric?: string;
  threshold?: number;
  current?: number;
}

// ---------------------------------------------------------------------------
// AI Narrative card (for chart text overlays)
// ---------------------------------------------------------------------------

export interface NarrativeCard {
  id: string;
  text: string;
  position?: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';
  severity?: 'info' | 'warning' | 'critical';
}

// ---------------------------------------------------------------------------
// Forecast metadata — method, accuracy, explanation
// ---------------------------------------------------------------------------

export interface ForecastMeta {
  method: string;
  r_squared?: number;
  mape?: number;
  description?: string;
  fit_data?: Array<Record<string, any>>;
  alternatives?: Array<{
    method: string;
    r_squared?: number;
    mape?: number;
  }>;
}

// ---------------------------------------------------------------------------
// MemoContext shape
// ---------------------------------------------------------------------------

export interface MemoContextValue {
  // Identity
  companyId: string;

  // The ledger — grid rows, columns, cells
  matrixData: MatrixData;
  setMatrixData: React.Dispatch<React.SetStateAction<MatrixData>>;

  // Scenario branches
  activeBranches: ScenarioBranch[];
  activeBranchId: string | null;
  forecasts: Record<string, ForecastMonth[]>;
  baseForecast: ForecastMonth[] | null;
  charts: ChartConfig[];

  // Drivers
  driverRegistry: DriverDef[];
  driverValues: Record<string, DriverValue[]>; // branchId -> values

  // Computed
  metrics: ComputedMetric[];
  signals: Signal[];

  // Forecast metadata — method, accuracy, explanation (set after buildForecast)
  forecastMeta: ForecastMeta | null;

  // Revision counter — bumped on any mutation, triggers re-renders
  dataRevision: number;

  // Loading state
  loading: boolean;

  // ---- Mutations ----

  // Cell-level
  updateCell: (rowId: string, colId: string, value: any) => void;

  // Driver mutations
  updateDrivers: (branchId: string, overrides: Record<string, number>) => Promise<void>;

  // Scenario mutations
  createFork: (name: string, parentId: string | null, forkPeriod: string | null, assumptions: Record<string, any>) => Promise<void>;
  deleteFork: (branchId: string) => Promise<void>;
  setActiveBranch: (branchId: string | null) => void;

  // Forecast
  buildForecast: (params?: Record<string, any>) => Promise<void>;

  // AI narration
  requestNarrative: (sectionType: string, dataContext: Record<string, any>) => Promise<string>;

  // Row helpers — extract typed rows from grid
  getPnlRows: () => MatrixRow[];
  getBalanceSheetRows: () => MatrixRow[];
  getCashFlowRows: () => MatrixRow[];
  getRowValues: (rowId: string) => Record<string, number>;
}

// ---------------------------------------------------------------------------
// Context + hook
// ---------------------------------------------------------------------------

const MemoCtx = createContext<MemoContextValue | null>(null);

export function useMemoContext(): MemoContextValue {
  const ctx = useContext(MemoCtx);
  if (!ctx) throw new Error('useMemoContext must be used inside <MemoProvider>');
  return ctx;
}

/** Safe version — returns null when outside provider (for gradual adoption) */
export function useMemoContextSafe(): MemoContextValue | null {
  return useContext(MemoCtx);
}

// ---------------------------------------------------------------------------
// P&L / BS / CF section row IDs (match backend + pnl-columns.ts)
// ---------------------------------------------------------------------------

const PNL_ROW_IDS = new Set([
  'revenue_header', 'revenue', 'total_revenue',
  'cogs_header', 'cogs', 'total_cogs',
  'gross_profit',
  'opex_header', 'opex_rd', 'opex_sm', 'opex_ga', 'total_opex',
  'ebitda',
  'below_line_header', 'debt_service', 'pre_tax_income', 'tax_expense', 'net_income',
  'bottom_header', 'cash_balance', 'runway',
]);

const BS_ROW_IDS = new Set([
  'assets_header', 'current_assets_header', 'cash_equivalents', 'accounts_receivable',
  'inventory', 'prepaid_expenses', 'total_current_assets',
  'noncurrent_assets_header', 'ppe', 'intangible_assets', 'goodwill', 'total_noncurrent_assets',
  'total_assets',
  'liabilities_header', 'current_liabilities_header', 'accounts_payable', 'accrued_expenses',
  'short_term_debt', 'deferred_revenue', 'total_current_liabilities',
  'noncurrent_liabilities_header', 'long_term_debt', 'other_lt_liabilities', 'total_noncurrent_liabilities',
  'total_liabilities',
  'equity_header', 'common_stock', 'retained_earnings', 'additional_paid_in',
  'total_equity', 'total_liabilities_equity',
]);

const CF_ROW_IDS = new Set([
  'net_income', 'working_capital_delta', 'operating_cash_flow',
  'capex', 'debt_service', 'free_cash_flow', 'cash_balance',
  'gross_burn_rate', 'net_burn_rate', 'runway_months', 'rule_of_40',
]);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export interface MemoProviderProps {
  companyId: string;
  matrixData: MatrixData;
  setMatrixData: React.Dispatch<React.SetStateAction<MatrixData>>;
  // Optional: plug in existing fork tree from useScenarioForkTree
  forkTree?: {
    branches: ScenarioBranch[];
    activeBranchId: string | null;
    forecasts: Record<string, ForecastMonth[]>;
    baseForecast: ForecastMonth[] | null;
    charts: ChartConfig[];
    loading: boolean;
    createFork: (name: string, parentBranchId: string | null, forkPeriod: string | null, assumptions: Record<string, any>) => Promise<{ branch: ScenarioBranch; forecast: ForecastMonth[] } | undefined>;
    updateFork: (branchId: string, drivers: Record<string, any>) => Promise<ForecastMonth[] | undefined>;
    deleteFork: (branchId: string) => Promise<void>;
    setActiveBranch: (branchId: string | null) => void;
    refreshComparison: () => Promise<void>;
  };
  children: ReactNode;
}

export function MemoProvider({ companyId, matrixData, setMatrixData, forkTree, children }: MemoProviderProps) {
  const backendUrl = getClientBackendUrl();

  // Internal state
  const [driverRegistry, setDriverRegistry] = useState<DriverDef[]>([]);
  const [driverValues, setDriverValues] = useState<Record<string, DriverValue[]>>({});
  const [metrics, setMetrics] = useState<ComputedMetric[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [forecastMeta, setForecastMeta] = useState<ForecastMeta | null>(null);
  const [dataRevision, setDataRevision] = useState(0);
  const [loading, setLoading] = useState(false);

  const bump = useCallback(() => setDataRevision(r => r + 1), []);

  // ---- Cell update ----
  const updateCell = useCallback((rowId: string, colId: string, value: any) => {
    setMatrixData(prev => {
      const rows = prev.rows.map(r => {
        if (r.id !== rowId) return r;
        return {
          ...r,
          cells: {
            ...r.cells,
            [colId]: { ...(r.cells[colId] || {}), value, source: 'manual' as const },
          },
        };
      });
      return { ...prev, rows };
    });
    bump();
  }, [setMatrixData, bump]);

  // ---- Apply ForecastMonth[] into matrixData grid rows ----
  // Maps ForecastMonth fields → grid row IDs so scenario/driver recomputes show up in charts
  const FORECAST_FIELD_TO_ROW: Record<string, string> = {
    revenue: 'revenue',
    cogs: 'cogs',
    gross_profit: 'gross_profit',
    rd_spend: 'opex_rd',
    sm_spend: 'opex_sm',
    ga_spend: 'opex_ga',
    total_opex: 'total_opex',
    ebitda: 'ebitda',
    capex: 'capex',
    free_cash_flow: 'free_cash_flow',
    cash_balance: 'cash_balance',
    runway_months: 'runway_months',
  };

  const applyForecastToGrid = useCallback((forecast: ForecastMonth[], _branchId?: string) => {
    setMatrixData(prev => {
      const rowMap = new Map(prev.rows.map(r => [r.id, { ...r, cells: { ...r.cells } }]));

      for (const month of forecast) {
        const colId = month.period; // e.g. "2025-01"
        for (const [field, rowId] of Object.entries(FORECAST_FIELD_TO_ROW)) {
          const val = month[field];
          if (val == null) continue;
          const row = rowMap.get(rowId);
          if (!row) continue;
          row.cells[colId] = { ...(row.cells[colId] || {}), value: val, source: 'scenario' as const };
        }
      }

      // Ensure period columns exist for all forecast months
      const existingColIds = new Set(prev.columns.map(c => c.id));
      const newCols = [...prev.columns];
      for (const month of forecast) {
        if (!existingColIds.has(month.period)) {
          newCols.push({ id: month.period, name: month.period, type: 'number' } as any);
          existingColIds.add(month.period);
        }
      }

      return { ...prev, rows: Array.from(rowMap.values()), columns: newCols };
    });
  }, [setMatrixData]);

  // ---- Driver update ----
  const updateDrivers = useCallback(async (branchId: string, overrides: Record<string, number>) => {
    if (forkTree) {
      const forecast = await forkTree.updateFork(branchId, overrides);
      if (forecast?.length) {
        applyForecastToGrid(forecast, branchId);
      }
    } else {
      // Direct API call if no fork tree wired — fetch recomputed rows back
      try {
        setLoading(true);
        const res = await fetch(`${backendUrl}/fpa/scenarios/branch/${branchId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ assumptions: overrides }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data.forecast) {
            applyForecastToGrid(data.forecast, branchId);
          }
        }
      } finally {
        setLoading(false);
      }
    }
    bump();
  }, [forkTree, backendUrl, bump, applyForecastToGrid]);

  // ---- Scenario fork/delete ----
  const createFork = useCallback(async (name: string, parentId: string | null, forkPeriod: string | null, assumptions: Record<string, any>) => {
    if (forkTree) {
      const result = await forkTree.createFork(name, parentId, forkPeriod, assumptions);
      if (result?.forecast?.length) {
        applyForecastToGrid(result.forecast, result.branch.id);
      }
    }
    bump();
  }, [forkTree, bump, applyForecastToGrid]);

  const deleteFork = useCallback(async (branchId: string) => {
    if (forkTree) {
      await forkTree.deleteFork(branchId);
    }
    bump();
  }, [forkTree, bump]);

  const setActiveBranch = useCallback((branchId: string | null) => {
    forkTree?.setActiveBranch(branchId);
    bump();
  }, [forkTree, bump]);

  // ---- Build forecast ----
  const buildForecast = useCallback(async (params?: Record<string, any>) => {
    setLoading(true);
    try {
      const res = await fetch(`${backendUrl}/fpa/forecast`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company_id: companyId, ...params }),
      });
      if (!res.ok) throw new Error(`Forecast failed: ${res.status}`);
      const data = await res.json();

      // Apply forecast rows to grid
      if (data.rows) {
        setMatrixData(prev => {
          const rowMap = new Map(prev.rows.map(r => [r.id, r]));
          for (const row of data.rows) {
            if (rowMap.has(row.id)) {
              const existing = rowMap.get(row.id)!;
              rowMap.set(row.id, { ...existing, cells: { ...existing.cells, ...row.cells } });
            } else {
              rowMap.set(row.id, row);
            }
          }
          return {
            ...prev,
            rows: Array.from(rowMap.values()),
            metadata: { ...prev.metadata, forecastStartIndex: data.forecastStartIndex },
          };
        });
      }

      // Update metrics and signals if returned
      if (data.metrics) setMetrics(data.metrics);
      if (data.signals) setSignals(data.signals);
      if (data.drivers) setDriverRegistry(data.drivers);
      if (data.driverValues) setDriverValues(data.driverValues);

      // Capture forecast metadata (method, R², explanation)
      if (data.method || data.forecast_method || data.r_squared) {
        setForecastMeta({
          method: data.method || data.forecast_method || params?.method || 'auto',
          r_squared: data.r_squared,
          mape: data.mape,
          description: data.description || data.explanation,
          fit_data: data.fit_data,
          alternatives: data.alternatives,
        });
      }

      // Also fetch regression fit data for chart rendering
      try {
        const regRes = await fetch(`${backendUrl}/api/fpa/regression`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            company_id: companyId,
            type: params?.method === 'auto' || !params?.method ? 'linear' : params.method,
          }),
        });
        if (regRes.ok) {
          const regData = await regRes.json();
          setForecastMeta(prev => ({
            method: prev?.method || params?.method || 'auto',
            ...prev,
            r_squared: regData.r_squared ?? prev?.r_squared,
            mape: regData.mape ?? prev?.mape,
            description: regData.description ?? prev?.description,
            fit_data: regData.fit_data ?? prev?.fit_data,
            alternatives: regData.alternatives ?? prev?.alternatives,
          }));
        }
      } catch { /* regression endpoint optional */ }

      bump();
    } finally {
      setLoading(false);
    }
  }, [companyId, backendUrl, setMatrixData, bump]);

  // ---- AI narrative ----
  const requestNarrative = useCallback(async (sectionType: string, dataContext: Record<string, any>): Promise<string> => {
    try {
      const res = await fetch(`${backendUrl}/api/agent/unified-brain`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_id: companyId,
          action: 'narrate',
          section_type: sectionType,
          context: dataContext,
        }),
      });
      if (!res.ok) return 'Unable to generate analysis.';
      const data = await res.json();
      return data.narrative || data.content || '';
    } catch {
      return 'Unable to generate analysis.';
    }
  }, [companyId, backendUrl]);

  // ---- Row helpers ----
  const getPnlRows = useCallback(() => matrixData.rows.filter(r => PNL_ROW_IDS.has(r.id)), [matrixData.rows]);
  const getBalanceSheetRows = useCallback(() => matrixData.rows.filter(r => BS_ROW_IDS.has(r.id)), [matrixData.rows]);
  const getCashFlowRows = useCallback(() => matrixData.rows.filter(r => CF_ROW_IDS.has(r.id)), [matrixData.rows]);

  const getRowValues = useCallback((rowId: string): Record<string, number> => {
    const row = matrixData.rows.find(r => r.id === rowId);
    if (!row) return {};
    const vals: Record<string, number> = {};
    for (const [colId, cell] of Object.entries(row.cells)) {
      if (colId === 'lineItem') continue;
      const v = typeof cell.value === 'number' ? cell.value : parseFloat(cell.value);
      if (!isNaN(v)) vals[colId] = v;
    }
    return vals;
  }, [matrixData.rows]);

  // ---- Compose value ----
  const value = useMemo<MemoContextValue>(() => ({
    companyId,
    matrixData,
    setMatrixData,
    activeBranches: forkTree?.branches ?? [],
    activeBranchId: forkTree?.activeBranchId ?? null,
    forecasts: forkTree?.forecasts ?? {},
    baseForecast: forkTree?.baseForecast ?? null,
    charts: forkTree?.charts ?? [],
    driverRegistry,
    driverValues,
    metrics,
    signals,
    forecastMeta,
    dataRevision,
    loading: loading || (forkTree?.loading ?? false),
    updateCell,
    updateDrivers,
    createFork,
    deleteFork,
    setActiveBranch,
    buildForecast,
    requestNarrative,
    getPnlRows,
    getBalanceSheetRows,
    getCashFlowRows,
    getRowValues,
  }), [
    companyId, matrixData, setMatrixData,
    forkTree?.branches, forkTree?.activeBranchId, forkTree?.forecasts, forkTree?.baseForecast, forkTree?.charts, forkTree?.loading,
    driverRegistry, driverValues, metrics, signals, forecastMeta, dataRevision,
    loading, updateCell, updateDrivers, createFork, deleteFork, setActiveBranch,
    buildForecast, requestNarrative, getPnlRows, getBalanceSheetRows, getCashFlowRows, getRowValues,
  ]);

  return <MemoCtx.Provider value={value}>{children}</MemoCtx.Provider>;
}
