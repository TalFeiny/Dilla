// ---------------------------------------------------------------------------
// Dynamic Driver Chips — generated from backend driver registry
// ---------------------------------------------------------------------------

import type { ChipDef, ChipParamDef } from './types';
import { fetchDriverRegistry } from '@/lib/memo/api-helpers';

/** Shape returned by the backend driver registry */
interface DriverEntry {
  name: string;
  key: string;
  unit?: string;       // '%', '$', 'count', 'months', etc.
  default_value?: number;
  min?: number;
  max?: number;
  step?: number;
  category?: string;   // revenue, cost, growth, etc.
}

/** Convert a backend driver entry into a ChipDef */
function driverToChip(d: DriverEntry): ChipDef {
  const paramType = unitToParamType(d.unit);
  const param: ChipParamDef = {
    key: 'value',
    label: d.name,
    type: paramType,
    default: d.default_value ?? 0,
    min: d.min,
    max: d.max,
    step: d.step ?? (paramType === 'percent' ? 1 : undefined),
    chipDisplay: (v: number) => formatDriverValue(v, d.unit),
  };

  return {
    id: `driver_${d.key}`,
    label: d.name,
    domain: 'driver',
    icon: driverIcon(d.category),
    description: `Adjust ${d.name.toLowerCase()}`,
    tool: 'fpa_scenario_create',  // drivers compose into scenario forks
    params: [param],
    produces: ['driver_override'],
    outputRenderer: 'raw',
    costTier: 'free',
    timeoutMs: 5000,
  };
}

function unitToParamType(unit?: string): ChipParamDef['type'] {
  if (!unit) return 'number';
  const u = unit.toLowerCase();
  if (u === '%' || u === 'percent') return 'percent';
  if (u === '$' || u === 'usd' || u === 'currency') return 'currency';
  if (u === 'months' || u === 'mo') return 'months';
  if (u === 'days') return 'days';
  return 'number';
}

function formatDriverValue(v: number, unit?: string): string {
  if (!unit) return String(v);
  const u = unit.toLowerCase();
  if (u === '%' || u === 'percent') return `${v > 0 ? '+' : ''}${v}%`;
  if (u === '$' || u === 'usd' || u === 'currency') {
    if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
    if (Math.abs(v) >= 1_000) return `$${(v / 1_000).toFixed(0)}k`;
    return `$${v}`;
  }
  if (u === 'count') return `${v > 0 ? '+' : ''}${v}`;
  return `${v} ${unit}`;
}

function driverIcon(category?: string): string {
  if (!category) return 'Sliders';
  const c = category.toLowerCase();
  if (c.includes('revenue') || c.includes('growth')) return 'TrendingUp';
  if (c.includes('cost') || c.includes('burn')) return 'TrendingDown';
  if (c.includes('head') || c.includes('team') || c.includes('hire')) return 'Users';
  if (c.includes('churn') || c.includes('retention')) return 'UserMinus';
  if (c.includes('price') || c.includes('pricing')) return 'Tag';
  if (c.includes('cac') || c.includes('acquisition')) return 'Megaphone';
  return 'Sliders';
}

/** Cache to avoid re-fetching on every render */
let _cache: { companyId: string; chips: ChipDef[]; ts: number } | null = null;
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

/**
 * Fetch the driver registry for a company and return ChipDef[] for each driver.
 * Cached for 5 minutes per company.
 */
export async function loadDriverChips(companyId: string): Promise<ChipDef[]> {
  if (_cache && _cache.companyId === companyId && Date.now() - _cache.ts < CACHE_TTL) {
    return _cache.chips;
  }

  try {
    const registry = await fetchDriverRegistry(companyId);
    // Registry shape varies — handle array or object with .drivers
    const entries: DriverEntry[] = Array.isArray(registry)
      ? registry
      : registry?.drivers ?? registry?.items ?? [];

    const chips = entries.map(driverToChip);
    _cache = { companyId, chips, ts: Date.now() };
    return chips;
  } catch (err) {
    console.warn('[chips] Failed to load driver registry:', err);
    return _cache?.chips ?? [];
  }
}

/** Clear driver chip cache (e.g. on company switch) */
export function clearDriverChipCache() {
  _cache = null;
}
