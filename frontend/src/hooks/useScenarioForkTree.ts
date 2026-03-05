'use client';

import { useState, useCallback, useRef } from 'react';
import { getClientBackendUrl } from '@/lib/backend-url';
import type { ChartConfig } from '@/components/matrix/ChartViewport';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ScenarioBranch {
  id: string;
  name: string;
  parent_branch_id: string | null;
  fork_period: string | null;
  probability: number | null;
  assumptions: Record<string, any>;
  computed?: {
    final_revenue: number;
    final_ebitda: number;
    final_cash: number;
    final_runway: number;
  };
}

export interface ForecastMonth {
  period: string;
  source?: string;
  revenue?: number;
  cogs?: number;
  gross_profit?: number;
  rd_spend?: number;
  sm_spend?: number;
  ga_spend?: number;
  total_opex?: number;
  ebitda?: number;
  capex?: number;
  free_cash_flow?: number;
  cash_balance?: number;
  runway_months?: number;
  [key: string]: any;
}

export interface ForkTreeState {
  companyId: string;
  branches: ScenarioBranch[];
  activeBranchId: string | null;
  forecasts: Record<string, ForecastMonth[]>;
  baseForecast: ForecastMonth[] | null;
  charts: ChartConfig[];
  loading: boolean;
  error: string | null;
}

export interface UseScenarioForkTreeReturn extends ForkTreeState {
  loadTree: () => Promise<void>;
  createFork: (name: string, parentBranchId: string | null, forkPeriod: string | null, assumptions: Record<string, any>) => Promise<void>;
  updateFork: (branchId: string, drivers: Record<string, any>) => Promise<void>;
  deleteFork: (branchId: string) => Promise<void>;
  setActiveBranch: (branchId: string | null) => void;
  refreshComparison: () => Promise<void>;
  addBranchFromAgentResponse: (result: any) => void;
  setChartsFromComparison: (result: any) => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useScenarioForkTree(companyId: string | undefined): UseScenarioForkTreeReturn {
  const [branches, setBranches] = useState<ScenarioBranch[]>([]);
  const [activeBranchId, setActiveBranchId] = useState<string | null>(null);
  const [forecasts, setForecasts] = useState<Record<string, ForecastMonth[]>>({});
  const [baseForecast, setBaseForecast] = useState<ForecastMonth[] | null>(null);
  const [charts, setCharts] = useState<ChartConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const backendUrl = getClientBackendUrl();
  // Ref to avoid stale closures in refreshComparison
  const branchesRef = useRef(branches);
  branchesRef.current = branches;

  // ----- loadTree -----
  const loadTree = useCallback(async () => {
    if (!companyId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${backendUrl}/fpa/scenarios/tree?company_id=${companyId}&enrich=true`);
      if (!res.ok) throw new Error(`Failed to load scenario tree: ${res.status}`);
      const data = await res.json();
      const tree: ScenarioBranch[] = data.branches ?? data.tree ?? [];
      setBranches(tree);
      // Cache any enriched forecasts returned inline
      if (data.forecasts) {
        setForecasts(prev => ({ ...prev, ...data.forecasts }));
      }
      if (data.base_forecast) {
        setBaseForecast(data.base_forecast);
      }
    } catch (err: any) {
      setError(err.message ?? 'Failed to load scenario tree');
    } finally {
      setLoading(false);
    }
  }, [companyId, backendUrl]);

  // ----- refreshComparison -----
  const refreshComparison = useCallback(async () => {
    if (!companyId) return;
    const currentBranches = branchesRef.current;
    if (currentBranches.length === 0) return;
    try {
      const res = await fetch(`${backendUrl}/fpa/scenarios/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_id: companyId,
          branch_ids: currentBranches.map(b => b.id),
        }),
      });
      if (!res.ok) return;
      const data = await res.json();
      if (data.charts) {
        setCharts(data.charts.map((c: any) => ({ ...c, source: 'mcp' as const })));
      }
    } catch {
      // Non-critical — charts just won't update
    }
  }, [companyId, backendUrl]);

  // ----- createFork -----
  const createFork = useCallback(async (
    name: string,
    parentBranchId: string | null,
    forkPeriod: string | null,
    assumptions: Record<string, any>,
  ) => {
    if (!companyId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${backendUrl}/fpa/scenarios/branch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_id: companyId,
          name,
          parent_branch_id: parentBranchId,
          fork_period: forkPeriod,
          assumptions,
        }),
      });
      if (!res.ok) throw new Error(`Failed to create fork: ${res.status}`);
      const data = await res.json();
      const branch: ScenarioBranch = data.branch ?? data;
      setBranches(prev => [...prev, branch]);
      if (data.forecast) {
        setForecasts(prev => ({ ...prev, [branch.id]: data.forecast }));
      }
      await refreshComparison();
    } catch (err: any) {
      setError(err.message ?? 'Failed to create scenario fork');
    } finally {
      setLoading(false);
    }
  }, [companyId, backendUrl, refreshComparison]);

  // ----- updateFork -----
  const updateFork = useCallback(async (branchId: string, drivers: Record<string, any>) => {
    if (!companyId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${backendUrl}/fpa/scenarios/branch/${branchId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assumptions: drivers }),
      });
      if (!res.ok) throw new Error(`Failed to update fork: ${res.status}`);
      const data = await res.json();
      // Update branch in list
      setBranches(prev => prev.map(b => b.id === branchId ? { ...b, ...data.branch ?? data } : b));
      if (data.forecast) {
        setForecasts(prev => ({ ...prev, [branchId]: data.forecast }));
      }
      await refreshComparison();
    } catch (err: any) {
      setError(err.message ?? 'Failed to update scenario fork');
    } finally {
      setLoading(false);
    }
  }, [companyId, backendUrl, refreshComparison]);

  // ----- deleteFork -----
  const deleteFork = useCallback(async (branchId: string) => {
    if (!companyId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${backendUrl}/fpa/scenarios/branch/${branchId}`, {
        method: 'DELETE',
      });
      if (!res.ok) throw new Error(`Failed to delete fork: ${res.status}`);
      setBranches(prev => prev.filter(b => b.id !== branchId));
      setForecasts(prev => {
        const next = { ...prev };
        delete next[branchId];
        return next;
      });
      if (activeBranchId === branchId) setActiveBranchId(null);
      await refreshComparison();
    } catch (err: any) {
      setError(err.message ?? 'Failed to delete scenario fork');
    } finally {
      setLoading(false);
    }
  }, [companyId, backendUrl, activeBranchId, refreshComparison]);

  // ----- addBranchFromAgentResponse -----
  const addBranchFromAgentResponse = useCallback((result: any) => {
    const branch: ScenarioBranch | undefined = result.branch;
    if (!branch) return;
    setBranches(prev => {
      if (prev.find(b => b.id === branch.id)) return prev;
      return [...prev, branch];
    });
    if (result.forecast) {
      setForecasts(prev => ({ ...prev, [branch.id]: result.forecast }));
    }
    // Fire-and-forget comparison refresh
    refreshComparison();
  }, [refreshComparison]);

  // ----- setChartsFromComparison -----
  const setChartsFromComparison = useCallback((result: any) => {
    if (result.charts) {
      setCharts(result.charts.map((c: any) => ({ ...c, source: 'mcp' as const })));
    }
  }, []);

  return {
    companyId: companyId ?? '',
    branches,
    activeBranchId,
    forecasts,
    baseForecast,
    charts,
    loading,
    error,
    loadTree,
    createFork,
    updateFork,
    deleteFork,
    setActiveBranch: setActiveBranchId,
    refreshComparison,
    addBranchFromAgentResponse,
    setChartsFromComparison,
  };
}
