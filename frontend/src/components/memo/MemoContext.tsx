'use client';

import React, { createContext, useContext, useCallback, useEffect, useMemo, useState, useRef, type ReactNode } from 'react';
import type { MatrixData, MatrixRow, MatrixCell } from '@/components/matrix/UnifiedMatrix';
import type { ScenarioBranch, ForecastMonth } from '@/hooks/useScenarioForkTree';
import type { ChartConfig } from '@/components/matrix/ChartViewport';
import {
  getAllPnlRows,
  getBalanceSheetRows as getBSRows,
  getCashFlowRows as getCFRows,
} from '@/lib/memo/grid-helpers';
import {
  requestNarrative as apiRequestNarrative,
  fetchDriverRegistry as apiFetchDriverRegistry,
  fetchMetrics as apiFetchMetrics,
} from '@/lib/memo/api-helpers';

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
  parentGroup?: string; // e.g. 'opex_rd' — groups subcategory drivers under a collapsible parent
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
  // Chart shapes keyed by chart type: { branched_line: { data, citations, explanation }, ... }
  fit_data?: Record<string, { data: any; citations?: any[]; explanation?: string }>;
  alternatives?: Array<{
    method: string;
    r_squared?: number;
    mape?: number;
  }>;
  // Extended metadata from regression service
  model_name?: string;
  business_interpretation?: string;
  extrapolation_risk?: string;
  confidence?: string;
  data_characteristics?: Record<string, any>;
  // Ripple effects — how driver changes cascade through the P&L
  ripple_paths?: Array<{ from: string; to: string; impact: number }>;
  driver_impacts?: Record<string, Record<string, number>>;
}

// ---------------------------------------------------------------------------
// MemoContext shape
// ---------------------------------------------------------------------------

export interface MemoContextValue {
  // Identity
  companyId: string;
  companyName: string;
  fundId: string;

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

  // Actual forecast rows — the computed ForecastMonth[] from the last buildForecast call
  forecastRows: ForecastMonth[];

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

// Row helpers now use dynamic section-based filtering from grid-helpers.ts
// (replaces hardcoded PNL_ROW_IDS, BS_ROW_IDS, CF_ROW_IDS)

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export interface MemoProviderProps {
  companyId: string;
  companyName?: string;
  fundId?: string;
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

export function MemoProvider({ companyId, companyName = '', fundId = '', matrixData, setMatrixData, forkTree, children }: MemoProviderProps) {

  // Internal state
  const [driverRegistry, setDriverRegistry] = useState<DriverDef[]>([]);
  const [driverValues, setDriverValues] = useState<Record<string, DriverValue[]>>({});
  const [metrics, setMetrics] = useState<ComputedMetric[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [forecastMeta, setForecastMeta] = useState<ForecastMeta | null>(null);
  const [forecastRows, setForecastRows] = useState<ForecastMonth[]>([]);
  const [dataRevision, setDataRevision] = useState(0);
  const [loading, setLoading] = useState(false);

  const bump = useCallback(() => setDataRevision(r => r + 1), []);

  // ---- Load driver registry + metrics on mount ----
  useEffect(() => {
    if (!companyId) return;
    let cancelled = false;

    apiFetchDriverRegistry(companyId)
      .then(data => {
        if (cancelled) return;
        const drivers = data?.drivers || data?.registry || (Array.isArray(data) ? data : []);
        if (drivers.length) setDriverRegistry(drivers);
      })
      .catch(() => {});

    apiFetchMetrics(companyId)
      .then(data => {
        if (cancelled) return;
        const m = data?.metrics || (Array.isArray(data) ? data : []);
        if (m.length) setMetrics(m);
      })
      .catch(() => {});

    return () => { cancelled = true; };
  }, [companyId]);

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

      // Build dynamic field→row map: static base + subcategory keys from first month
      const fieldMap: Record<string, string> = { ...FORECAST_FIELD_TO_ROW };
      const firstMonth = forecast[0] as any;
      const subs = firstMonth?.subcategories as Record<string, Record<string, number>> | undefined;
      if (subs) {
        for (const [parent, children] of Object.entries(subs)) {
          for (const subKey of Object.keys(children)) {
            // Map e.g. "opex_rd:engineering_salaries" → "opex_rd:engineering_salaries"
            const compositeKey = `${parent}:${subKey}`;
            fieldMap[compositeKey] = compositeKey;
          }
        }
      }

      for (const month of forecast) {
        const colId = month.period; // e.g. "2025-01"
        const mSubs = (month as any).subcategories as Record<string, Record<string, number>> | undefined;

        // Apply top-level fields
        for (const [field, rowId] of Object.entries(FORECAST_FIELD_TO_ROW)) {
          const val = month[field];
          if (val == null) continue;
          const row = rowMap.get(rowId);
          if (!row) continue;
          row.cells[colId] = { ...(row.cells[colId] || {}), value: val, source: 'scenario' as const };
        }

        // Apply subcategory fields
        if (mSubs) {
          for (const [parent, children] of Object.entries(mSubs)) {
            for (const [subKey, subVal] of Object.entries(children)) {
              const rowId = `${parent}:${subKey}`;
              let row = rowMap.get(rowId);
              if (!row) {
                // Auto-create child row for this subcategory
                row = {
                  id: rowId,
                  label: subKey.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
                  parentId: parent,
                  cells: {},
                } as any;
                rowMap.set(rowId, row);
              }
              row.cells[colId] = { ...(row.cells[colId] || {}), value: subVal, source: 'scenario' as const };
            }
          }
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
        const res = await fetch(`/api/fpa/scenarios/branch/${branchId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ drivers: overrides }),
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
  }, [forkTree, bump, applyForecastToGrid]);

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
  // All methods → /api/fpa/forecast (full P&L cascade with subcategories).
  // ForecastMethodRouter handles method selection backend-side.
  // /api/fpa/regression is kept only for MonteCarloSection & SensitivitySection.
  const buildForecast = useCallback(async (params?: Record<string, any>) => {
    setLoading(true);
    try {
      const method = params?.method || 'auto';
      const forecastPeriods = params?.forecast_periods ?? 12;
      const gran = params?.granularity || 'monthly';

      // Collect current driver overrides as assumptions
      const driverOverrides: Record<string, any> = {};
      const branchId = forkTree?.activeBranchId;
      if (branchId && driverValues[branchId]) {
        for (const dv of driverValues[branchId]) {
          if (dv.source === 'override') driverOverrides[dv.id] = dv.value;
        }
      }

      const res = await fetch(`/api/fpa/forecast`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_id: companyId,
          method,
          forecast_periods: forecastPeriods,
          granularity: gran,
          assumptions: driverOverrides,
        }),
      });
      if (!res.ok) throw new Error(`Forecast failed: ${res.status}`);
      const data = await res.json();

      // data.forecast is ForecastMonth[] with ALL metrics + subcategories per period
      const forecast: ForecastMonth[] = data.forecast || [];
      setForecastRows(forecast);
      if (forecast.length) {
        applyForecastToGrid(forecast);
      }

      const runway = data.runway_months;
      const runwayNote = runway ? ` Runway: ${runway} months.` : '';

      setForecastMeta({
        method: data.method || method,
        description: `Full P&L model — all metrics cascade from revenue through to cash.${runwayNote}`,
        fit_data: data.fit_data,
        model_name: data.model_name || 'Connected P&L',
        confidence: data.confidence || 'high',
        business_interpretation: `Full P&L projection with ${forecastPeriods} ${gran} periods.${runwayNote}`,
        ripple_paths: data.ripple_paths,
        driver_impacts: data.driver_impacts,
      });
      bump();
    } finally {
      setLoading(false);
    }
  }, [companyId, bump, applyForecastToGrid, forkTree?.activeBranchId, driverValues]);

  // ---- AI narrative — backend pulls all data server-side ----
  const requestNarrative = useCallback(async (sectionType: string, dataContext?: Record<string, any>): Promise<string> => {
    return apiRequestNarrative(companyId, sectionType, {
      ...dataContext,
      branch_id: forkTree?.activeBranchId || null,
    });
  }, [companyId, forkTree?.activeBranchId]);

  // ---- Row helpers (dynamic section-based, no hardcoded ID sets) ----
  const getPnlRows = useCallback(() => getAllPnlRows(matrixData), [matrixData]);
  const getBalanceSheetRows = useCallback(() => getBSRows(matrixData), [matrixData]);
  const getCashFlowRows = useCallback(() => getCFRows(matrixData), [matrixData]);

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
    companyName,
    fundId,
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
    forecastRows,
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
    companyId, companyName, fundId, matrixData, setMatrixData,
    forkTree?.branches, forkTree?.activeBranchId, forkTree?.forecasts, forkTree?.baseForecast, forkTree?.charts, forkTree?.loading,
    driverRegistry, driverValues, metrics, signals, forecastMeta, forecastRows, dataRevision,
    loading, updateCell, updateDrivers, createFork, deleteFork, setActiveBranch,
    buildForecast, requestNarrative, getPnlRows, getBalanceSheetRows, getCashFlowRows, getRowValues,
  ]);

  return <MemoCtx.Provider value={value}>{children}</MemoCtx.Provider>;
}
