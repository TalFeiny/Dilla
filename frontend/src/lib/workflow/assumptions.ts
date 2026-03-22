// ---------------------------------------------------------------------------
// Assumption-Driven Model Building — Types + Client-Side Curve Math
// ---------------------------------------------------------------------------

// ── Assumption shape — how the impact applies over time ─────────────────────

export type AssumptionShape = 'step' | 'ramp' | 'decay' | 'pulse';

export type MagnitudeUnit = 'percent' | 'absolute' | 'per_month';

export type AssumptionSource = 'user' | 'ai' | 'macro' | 'template';

// ── Core type: a single assumption on a driver node ─────────────────────────

export interface NodeAssumption {
  id: string;
  /** Natural language: "Closing $200k enterprise deal in Q3" */
  description: string;
  /** 0-1, user-adjustable probability */
  probability: number;
  /** Impact value (positive = upside, negative = downside) */
  magnitude: number;
  magnitudeUnit: MagnitudeUnit;
  /** When the impact starts — "2026-Q3", "2026-07", "month_3" */
  timing?: string;
  /** How many months the effect lasts */
  duration?: number;
  /** How the impact applies over time */
  shape: AssumptionShape;
  /** Where this assumption came from */
  source: AssumptionSource;
  /** Category for grouping */
  category?: 'growth' | 'risk' | 'cost' | 'funding' | 'market' | 'operational';
  /** AI analysis from BusinessEventAnalysisService / MacroEventAnalysisService */
  aiAnalysis?: {
    factors: { name: string; magnitude: number; confidence: string; order: number }[];
    driverAdjustments: { driverId: string; adjustmentPct: number; reasoning: string }[];
    reasoning?: string;
  };
}

// ── Company data snapshot — cached in workflow store ─────────────────────────

export interface CompanyDataSnapshot {
  companyId: string;
  /** { category: { period: amount } } — full history */
  timeSeries: Record<string, Record<string, number>>;
  /** { category: amount } — most recent period */
  latest: Record<string, number>;
  /** Sorted period strings e.g. ["2025-01", "2025-02", ...] */
  periods: string[];
  /** Derived analytics */
  analytics: {
    growth_rate?: number;
    burn_rate?: number;
    runway_months?: number;
    gross_margin?: number;
    net_burn?: number;
    headcount?: number;
    growth_trend?: string;
    recommended_method?: string;
    [key: string]: any;
  };
  /** Data quality info */
  metadata: {
    row_count: number;
    date_range?: { start: string; end: string };
    categories: string[];
  };
  /** When this snapshot was fetched */
  fetchedAt: number;
}

// ── Shape functions — apply timing and shape to get per-month impact ────────

function shapeStep(monthIndex: number, startMonth: number, _duration: number): number {
  return monthIndex >= startMonth ? 1.0 : 0.0;
}

function shapeRamp(monthIndex: number, startMonth: number, duration: number): number {
  if (monthIndex < startMonth) return 0;
  if (duration <= 0) return 1;
  const progress = (monthIndex - startMonth) / duration;
  return Math.min(progress, 1.0);
}

function shapeDecay(monthIndex: number, startMonth: number, duration: number): number {
  if (monthIndex < startMonth) return 0;
  if (duration <= 0) return 0;
  const elapsed = monthIndex - startMonth;
  return Math.max(1.0 - elapsed / duration, 0);
}

function shapePulse(monthIndex: number, startMonth: number, duration: number): number {
  if (monthIndex < startMonth) return 0;
  if (monthIndex >= startMonth + duration) return 0;
  return 1.0;
}

function getShapeFn(shape: AssumptionShape) {
  switch (shape) {
    case 'step': return shapeStep;
    case 'ramp': return shapeRamp;
    case 'decay': return shapeDecay;
    case 'pulse': return shapePulse;
  }
}

/** Parse timing string to a month index (0-based from forecast start) */
function parseTimingToMonth(timing?: string): number {
  if (!timing) return 0;
  // "month_3" → 3
  if (timing.startsWith('month_')) return parseInt(timing.replace('month_', ''), 10) || 0;
  // "2026-Q3" → approximate month offset from now
  if (timing.includes('-Q')) {
    const [year, q] = timing.split('-Q');
    const qMonth = (parseInt(q, 10) - 1) * 3;
    const now = new Date();
    const targetDate = new Date(parseInt(year, 10), qMonth);
    return Math.max(0, Math.round((targetDate.getTime() - now.getTime()) / (30 * 24 * 60 * 60 * 1000)));
  }
  // "2026-07" → month offset from now
  if (/^\d{4}-\d{2}$/.test(timing)) {
    const [year, month] = timing.split('-').map(Number);
    const now = new Date();
    const targetDate = new Date(year, month - 1);
    return Math.max(0, Math.round((targetDate.getTime() - now.getTime()) / (30 * 24 * 60 * 60 * 1000)));
  }
  return 0;
}

// ── Compose curve from baseline + weighted assumptions ──────────────────────

export interface CurvePoint {
  month: number;
  label: string;
  baseline: number;
  scenario: number;
  delta: number;
  /** Lower confidence bound */
  lo?: number;
  /** Upper confidence bound */
  hi?: number;
}

/**
 * Compose a forecast curve from a baseline trajectory + probability-weighted assumptions.
 *
 * @param baselineValue - The current actual / slider value
 * @param baselineGrowth - Monthly growth rate for the baseline trend (decimal, e.g. 0.015 for 1.5%/mo)
 * @param assumptions - Array of NodeAssumption
 * @param months - Number of forecast months (default 12)
 * @returns Array of CurvePoint for the chart
 */
export function composeAssumptionCurve(
  baselineValue: number,
  baselineGrowth: number,
  assumptions: NodeAssumption[],
  months: number = 12,
): CurvePoint[] {
  const points: CurvePoint[] = [];
  const now = new Date();

  for (let m = 0; m < months; m++) {
    // Baseline: compound growth from current value
    const baseline = baselineValue * Math.pow(1 + baselineGrowth, m);

    // Sum weighted assumption deltas
    let delta = 0;
    for (const a of assumptions) {
      const startMonth = parseTimingToMonth(a.timing);
      const shapeFn = getShapeFn(a.shape);
      const duration = a.duration || 6;

      const shapeVal = shapeFn(m, startMonth, duration);

      // Convert magnitude to absolute delta
      let absMagnitude: number;
      if (a.magnitudeUnit === 'percent') {
        absMagnitude = baseline * (a.magnitude / 100);
      } else if (a.magnitudeUnit === 'per_month') {
        absMagnitude = a.magnitude;
      } else {
        absMagnitude = a.magnitude;
      }

      delta += a.probability * absMagnitude * shapeVal;
    }

    const scenario = baseline + delta;

    // Month label
    const monthDate = new Date(now.getFullYear(), now.getMonth() + m);
    const label = monthDate.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });

    // Confidence band — width from probability uncertainty per assumption.
    // High-probability assumptions narrow the band; low-probability widen it.
    let uncertainty = 0;
    for (const a of assumptions) {
      const startMonth = parseTimingToMonth(a.timing);
      const shapeFn = getShapeFn(a.shape);
      const duration = a.duration || 6;
      const sv = shapeFn(m, startMonth, duration);
      let absMag: number;
      if (a.magnitudeUnit === 'percent') {
        absMag = baseline * (a.magnitude / 100);
      } else {
        absMag = a.magnitude;
      }
      // (1 - probability) = how uncertain this assumption is
      uncertainty += (1 - a.probability) * Math.abs(absMag) * sv;
    }
    const band = uncertainty;

    points.push({
      month: m,
      label,
      baseline,
      scenario,
      delta,
      lo: scenario - band,
      hi: scenario + band,
    });
  }

  return points;
}

// ── Compute net exposure from assumptions ────────────────────────────────────

export interface ExposureSummary {
  /** Net monthly weighted impact */
  netMonthly: number;
  /** Total upside (positive assumptions) */
  upside: number;
  /** Total downside (negative assumptions) */
  downside: number;
  /** Number of assumptions */
  count: number;
  /** Weighted average probability */
  avgProbability: number;
}

export function computeExposure(assumptions: NodeAssumption[], baselineValue?: number): ExposureSummary {
  let upside = 0;
  let downside = 0;
  let totalProb = 0;

  for (const a of assumptions) {
    let absMag: number;
    if (a.magnitudeUnit === 'percent' && baselineValue) {
      absMag = baselineValue * (a.magnitude / 100);
    } else {
      absMag = a.magnitude;
    }

    const weighted = a.probability * absMag;
    if (weighted >= 0) {
      upside += weighted;
    } else {
      downside += weighted;
    }
    totalProb += a.probability;
  }

  return {
    netMonthly: upside + downside,
    upside,
    downside,
    count: assumptions.length,
    avgProbability: assumptions.length > 0 ? totalProb / assumptions.length : 0,
  };
}

// ── Smart assumption templates — one-click common scenarios ─────────────────

export interface AssumptionTemplate {
  label: string;
  description: string;
  category: NodeAssumption['category'];
  /** Which driver levels this template applies to */
  applicableLevels: string[];
  defaults: Omit<NodeAssumption, 'id' | 'source'>;
}

export const ASSUMPTION_TEMPLATES: AssumptionTemplate[] = [
  // ── Growth templates ──
  {
    label: 'New enterprise deal',
    description: 'Landing a new enterprise customer',
    category: 'growth',
    applicableLevels: ['revenue'],
    defaults: {
      description: 'Closing new enterprise deal',
      probability: 0.6,
      magnitude: 200000,
      magnitudeUnit: 'absolute',
      shape: 'step',
      duration: 12,
      category: 'growth',
    },
  },
  {
    label: 'Product launch',
    description: 'New product or feature driving revenue',
    category: 'growth',
    applicableLevels: ['revenue'],
    defaults: {
      description: 'New product launch driving additional revenue',
      probability: 0.5,
      magnitude: 15,
      magnitudeUnit: 'percent',
      shape: 'ramp',
      duration: 6,
      category: 'growth',
    },
  },
  {
    label: 'Pricing increase',
    description: 'Raising prices across existing customers',
    category: 'growth',
    applicableLevels: ['revenue'],
    defaults: {
      description: 'Implementing price increase across customer base',
      probability: 0.8,
      magnitude: 10,
      magnitudeUnit: 'percent',
      shape: 'step',
      duration: 12,
      category: 'growth',
    },
  },
  // ── Risk templates ──
  {
    label: 'Customer churn spike',
    description: 'Losing customers to competitor or pricing',
    category: 'risk',
    applicableLevels: ['revenue'],
    defaults: {
      description: 'Losing customers to price competition',
      probability: 0.3,
      magnitude: -50000,
      magnitudeUnit: 'per_month',
      shape: 'ramp',
      duration: 6,
      category: 'risk',
    },
  },
  {
    label: 'Key customer loss',
    description: 'Losing a major customer account',
    category: 'risk',
    applicableLevels: ['revenue'],
    defaults: {
      description: 'Risk of losing key enterprise customer',
      probability: 0.2,
      magnitude: -100000,
      magnitudeUnit: 'per_month',
      shape: 'step',
      category: 'risk',
    },
  },
  {
    label: 'Market downturn',
    description: 'Macro headwinds reducing growth',
    category: 'market',
    applicableLevels: ['revenue', 'capital'],
    defaults: {
      description: 'Macro economic downturn impacting demand',
      probability: 0.25,
      magnitude: -20,
      magnitudeUnit: 'percent',
      shape: 'ramp',
      duration: 9,
      category: 'market',
    },
  },
  // ── Cost templates ──
  {
    label: 'Hiring wave',
    description: 'Expanding team significantly',
    category: 'cost',
    applicableLevels: ['opex', 'workforce'],
    defaults: {
      description: 'Hiring 5 engineers + 3 sales reps',
      probability: 0.7,
      magnitude: 80000,
      magnitudeUnit: 'per_month',
      shape: 'ramp',
      duration: 3,
      category: 'cost',
    },
  },
  {
    label: 'Cost optimization',
    description: 'Reducing spend through efficiency',
    category: 'operational',
    applicableLevels: ['opex'],
    defaults: {
      description: 'Implementing cost optimization across ops',
      probability: 0.6,
      magnitude: -15,
      magnitudeUnit: 'percent',
      shape: 'ramp',
      duration: 4,
      category: 'operational',
    },
  },
  // ── Funding templates ──
  {
    label: 'Fundraise close',
    description: 'Closing a funding round',
    category: 'funding',
    applicableLevels: ['capital'],
    defaults: {
      description: 'Closing Series A at target valuation',
      probability: 0.5,
      magnitude: 5000000,
      magnitudeUnit: 'absolute',
      shape: 'step',
      category: 'funding',
    },
  },
  {
    label: 'Bridge round',
    description: 'Emergency or bridge financing',
    category: 'funding',
    applicableLevels: ['capital'],
    defaults: {
      description: 'Bridge note to extend runway',
      probability: 0.7,
      magnitude: 1000000,
      magnitudeUnit: 'absolute',
      shape: 'step',
      category: 'funding',
    },
  },
];

// ── Formatting helpers ──────────────────────────────────────────────────────

export function formatMagnitude(value: number, unit: MagnitudeUnit): string {
  const abs = Math.abs(value);
  const sign = value >= 0 ? '+' : '-';

  if (unit === 'percent') {
    return `${sign}${abs.toFixed(1)}%`;
  }

  if (abs >= 1_000_000) {
    return `${sign}$${(abs / 1_000_000).toFixed(1)}M`;
  }
  if (abs >= 1_000) {
    return `${sign}$${(abs / 1_000).toFixed(0)}k`;
  }
  return `${sign}$${abs.toFixed(0)}`;
}

export function formatExposure(value: number): string {
  const abs = Math.abs(value);
  const sign = value >= 0 ? '+' : '-';

  if (abs >= 1_000_000) {
    return `${sign}$${(abs / 1_000_000).toFixed(1)}M/mo`;
  }
  if (abs >= 1_000) {
    return `${sign}$${(abs / 1_000).toFixed(0)}k/mo`;
  }
  return `${sign}$${abs.toFixed(0)}/mo`;
}

/** Category color map */
export const CATEGORY_COLORS: Record<string, string> = {
  growth: '#10b981',
  risk: '#ef4444',
  cost: '#f59e0b',
  funding: '#3b82f6',
  market: '#8b5cf6',
  operational: '#6b7280',
};

/** Shape labels for display */
export const SHAPE_LABELS: Record<AssumptionShape, string> = {
  step: 'Immediate',
  ramp: 'Gradual ramp',
  decay: 'Fading',
  pulse: 'Temporary',
};

/** Compact dollar formatter ($1.2M, $450k, $32) */
export function formatCompact(v: number): string {
  const abs = Math.abs(v);
  const sign = v < 0 ? '-' : '';
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(0)}k`;
  return `${sign}$${abs.toFixed(0)}`;
}

/** Shape descriptions for tooltips */
export const SHAPE_DESCRIPTIONS: Record<AssumptionShape, string> = {
  step: 'Full impact from the start date onward',
  ramp: 'Gradually increases to full impact over the duration',
  decay: 'Full impact at start, fading to zero over the duration',
  pulse: 'Full impact for the duration, then stops',
};
