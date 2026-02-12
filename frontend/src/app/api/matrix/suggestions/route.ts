import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';
import { applyCellUpdate } from '@/lib/matrix/apply-cell-server';

const MAX_POSITIVE = 1e12;
const MAX_VALUATION = 1e13;
const MAX_RUNWAY_MONTHS = 120;
const MAX_STRING_LENGTH = 200;

/** Validate positive number in [min, max]; return value or null if invalid */
function validPositive(
  value: unknown,
  min: number = 0,
  max: number = MAX_POSITIVE
): number | null {
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= min || value > max) {
    return null;
  }
  return value;
}

/** Validate gross margin (0–1 or 0–100); return 0–1 or null */
function validGrossMargin(value: unknown): number | null {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null;
  const n = value > 1 ? value / 100 : value;
  if (n < 0 || n > 1) return null;
  return n;
}

/** Validate growth % (0–maxPct); accept decimal (0.5 = 50%) or percentage (50) */
function validGrowthPct(value: unknown, maxPct: number = 500): number | null {
  if (value == null) return null;
  const n = typeof value === 'number' ? value : parseFloat(String(value));
  if (!Number.isFinite(n)) return null;
  const asPct = n <= 2 && n >= -0.5 ? n * 100 : n;
  if (asPct < -100 || asPct > maxPct) return null;
  return asPct;
}

/** Validate non-empty string with length limit */
function validString(value: unknown, maxLen: number = MAX_STRING_LENGTH): string | null {
  if (typeof value !== 'string') return null;
  const s = value.trim();
  return s.length > 0 && s.length <= maxLen ? s : null;
}

/** Current matrix row values per company (from companies table + extra_data) */
type MatrixRowValues = {
  arr: number | null;
  burnRate: number | null;
  runway: number | null;
  cashInBank: number | null;
  grossMargin: number | null;
  valuation: number | null;
  revenueGrowthMonthly: number | null;
  revenueGrowthAnnual: number | null;
  sector: string | null;
  latestUpdate: string | null;
  productUpdates: string | null;
  headcount: number | null;
  optionPool: number | null;
  tamUsd: number | null;
  samUsd: number | null;
  somUsd: number | null;
};

/** Format number for reasoning (compact) */
function fmtNum(n: number): string {
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n}`;
}

/** Map frontend columnId to value_explanations metric key */
function mapColumnToMetricKey(columnId: string): string {
  const map: Record<string, string> = {
    arr: 'arr',
    burnRate: 'burn_rate',
    runway: 'runway_months',
    runwayMonths: 'runway_months',
    cashInBank: 'cash_balance',
    grossMargin: 'gross_margin',
    growth_rate: 'growth_rate',
    revenueGrowthAnnual: 'growth_rate',
    revenueGrowthMonthly: 'growth_rate',
    headcount: 'headcount',
    optionPool: 'option_pool_bps',
    tamUsd: 'tam_usd',
    samUsd: 'sam_usd',
    somUsd: 'som_usd',
    valuation: 'valuation',
    sector: 'sector',
    latestUpdate: 'latest_update',
    productUpdates: 'product_updates',
  };
  return map[columnId] ?? columnId;
}

/** Build short, factual reasoning. When doc provides value_explanation, use only that (+ optional "was X"); no generic boilerplate. */
function buildReasoningAndConfidence(opts: {
  docName: string;
  columnId: string;
  suggestedValue: number | string;
  currentValue: number | string | null;
  businessUpdates: Record<string, unknown>;
  valueFromExplicitFinancials: boolean;
  redFlags?: string[];
  isExtrapolated?: boolean;
  valueExplanation?: string;
  changePercentage?: number;
}): { reasoning: string; confidence: number } {
  const { docName, columnId, suggestedValue, currentValue, businessUpdates, valueFromExplicitFinancials, redFlags = [], isExtrapolated = false, valueExplanation, changePercentage } = opts;
  const bu = businessUpdates as {
    challenges?: unknown[];
    risks?: unknown[];
    defensive_language?: unknown[];
    achievements?: unknown[];
    product_updates?: unknown[];
    latest_update?: string;
  };
  const challenges = Array.isArray(bu.challenges) ? bu.challenges.filter((c): c is string => typeof c === 'string') : [];
  const risks = Array.isArray(bu.risks) ? bu.risks.filter((r): r is string => typeof r === 'string') : [];
  const defensive = Array.isArray(bu.defensive_language) ? bu.defensive_language.filter((d): d is string => typeof d === 'string') : [];
  const achievements = Array.isArray(bu.achievements) ? bu.achievements.filter((a): a is string => typeof a === 'string') : [];
  const productUpdates = Array.isArray(bu.product_updates) ? bu.product_updates.filter((p): p is string => typeof p === 'string') : [];
  const hasCaution = challenges.length > 0 || risks.length > 0 || defensive.length > 0 || redFlags.length > 0;
  const hasPositive = achievements.length > 0 || productUpdates.length > 0;

  const isPctColumn = columnId === 'grossMargin' || columnId === 'revenueGrowthAnnual' || columnId === 'revenueGrowthMonthly';
  const fmtPct = (n: number) => (columnId === 'grossMargin' && n <= 1 ? (n * 100).toFixed(0) : n.toFixed(1)) + '%';
  const parts: string[] = [];
  if (valueExplanation != null && valueExplanation !== '') {
    // Prefer doc-sourced explanation when available
    const base = valueExplanation.trim();
    const suffix = currentValue !== null && currentValue !== undefined && currentValue !== '' ? ` (was ${typeof currentValue === 'number' ? (isPctColumn ? fmtPct(columnId === 'grossMargin' && currentValue <= 1 ? currentValue * 100 : currentValue) : fmtNum(currentValue)) : String(currentValue)}).` : '.';
    parts.push(base + suffix);
  } else if (currentValue !== null && currentValue !== undefined && currentValue !== '') {
    const curr = typeof currentValue === 'number' ? (isPctColumn ? fmtPct(columnId === 'grossMargin' && currentValue <= 1 ? currentValue * 100 : currentValue) : fmtNum(currentValue)) : String(currentValue);
    const sugg = typeof suggestedValue === 'number' ? (isPctColumn ? fmtPct(columnId === 'grossMargin' && suggestedValue <= 1 ? suggestedValue * 100 : suggestedValue) : fmtNum(suggestedValue)) : String(suggestedValue);
    const pctStr = changePercentage != null ? ` (${changePercentage > 0 ? '+' : ''}${(changePercentage * 100).toFixed(0)}%)` : '';
    parts.push(`Doc: ${sugg}${pctStr}. Matrix: ${curr}.`);
  } else {
    const sugg = typeof suggestedValue === 'number' ? (isPctColumn ? fmtPct(columnId === 'grossMargin' && suggestedValue <= 1 ? suggestedValue * 100 : suggestedValue) : fmtNum(suggestedValue)) : String(suggestedValue);
    parts.push(`From ${docName}: ${sugg}.`);
  }
  // Add context from extracted achievements/product updates and risks when no doc-sourced explanation
  if (valueExplanation == null || valueExplanation.trim() === '') {
    if (isExtrapolated) parts.push('Inferred from doc, not stated explicitly.');
    else if (hasPositive && hasCaution) parts.push('Achievements and product updates; challenges and risks noted.');
    else if (hasCaution) parts.push('Doc mentions risks or challenges.');
    else if (hasPositive) parts.push('Achievements/product updates in doc.');
  }

  const reasoning = parts.join(' ');
  const fromExplicit = valueFromExplicitFinancials ? 1 : 0;
  const fromCaution = hasCaution ? 1 : 0;
  const fromExtrapolated = isExtrapolated ? -0.1 : 0;
  const confidence = 0.5 + fromExplicit * 0.25 - fromCaution * 0.15 + fromExtrapolated;
  return { reasoning, confidence: Math.max(0.35, Math.min(0.95, confidence)) };
}

type MetricMapping = {
  columnId: string;
  rowKey: keyof MatrixRowValues;
  /** Dot-paths into extracted_data sections, tried in order. First non-null wins. */
  paths: string[];
  validator: (v: unknown) => number | string | null;
  label: string;
  idSuffix: string;
  /** Min relative difference to trigger suggestion (default 0.01 = 1%) */
  changeThreshold?: number;
  /** Extra check for "explicit" confidence boost */
  isExplicitCheck?: (sections: Record<string, Record<string, unknown>>) => boolean;
};

const METRIC_MAPPINGS: MetricMapping[] = [
  {
    columnId: 'arr', rowKey: 'arr', idSuffix: 'arr', label: 'ARR',
    paths: ['growthMetrics.current_arr', 'financialMetrics.arr', 'financialMetrics.revenue', 'extractedData.arr', 'extractedData.revenue'],
    validator: (v) => validPositive(v),
    changeThreshold: 0.01,
    isExplicitCheck: (s) => (s.financialMetrics?.arr ?? s.financialMetrics?.revenue ?? s.extractedData?.arr ?? s.extractedData?.revenue) != null,
  },
  {
    columnId: 'burnRate', rowKey: 'burnRate', idSuffix: 'burn', label: 'Burn Rate',
    paths: ['financialMetrics.burn_rate', 'financialMetrics.burn_rate_monthly', 'runwayAndCash.burn_rate', 'extractedData.burn_rate'],
    validator: (v) => validPositive(v),
    changeThreshold: 0.01,
  },
  {
    columnId: 'runway', rowKey: 'runway', idSuffix: 'runway', label: 'Runway',
    paths: ['financialMetrics.runway_months', 'runwayAndCash.runway_months', 'runwayAndCash.runway', 'extractedData.runway_months'],
    validator: (v) => validPositive(v, 0, MAX_RUNWAY_MONTHS),
    changeThreshold: 0, // use absolute: 1 month
  },
  {
    columnId: 'cashInBank', rowKey: 'cashInBank', idSuffix: 'cash', label: 'Cash',
    paths: ['financialMetrics.cash', 'financialMetrics.cash_balance', 'financialMetrics.cash_in_bank_usd', 'runwayAndCash.cash_in_bank', 'extractedData.cash_balance', 'extractedData.cash_in_bank_usd'],
    validator: (v) => validPositive(v),
    changeThreshold: 0.01,
  },
  {
    columnId: 'grossMargin', rowKey: 'grossMargin', idSuffix: 'margin', label: 'Gross Margin',
    paths: ['financialMetrics.gross_margin', 'financialMetrics.grossMargin', 'extractedData.gross_margin'],
    validator: (v) => validGrossMargin(v),
    changeThreshold: 0.01,
  },
  {
    columnId: 'revenueGrowthAnnual', rowKey: 'revenueGrowthAnnual', idSuffix: 'growth-annual', label: 'Annual Revenue Growth',
    paths: ['growthMetrics.revenue_growth_annual_pct', 'growthMetrics.yoy_growth', 'growthMetrics.growth_rate', 'financialMetrics.revenue_growth_annual_pct', 'financialMetrics.growth_rate', 'extractedData.growth_rate'],
    validator: (v) => validGrowthPct(v, 500),
    changeThreshold: 0.005,
  },
  {
    columnId: 'revenueGrowthMonthly', rowKey: 'revenueGrowthMonthly', idSuffix: 'growth-monthly', label: 'Monthly Revenue Growth',
    paths: ['growthMetrics.revenue_growth_monthly_pct', 'growthMetrics.monthly_growth', 'growthMetrics.mom_growth', 'financialMetrics.revenue_growth_monthly_pct'],
    validator: (v) => validGrowthPct(v, 100),
    changeThreshold: 0.005,
  },
  {
    columnId: 'valuation', rowKey: 'valuation', idSuffix: 'valuation', label: 'Valuation',
    paths: ['companyInfo.valuation', 'financialMetrics.valuation', 'extractedData.valuation', 'extractedData.valuation_pre_money'],
    validator: (v) => validPositive(v, 0, MAX_VALUATION),
    changeThreshold: 0.01,
  },
  {
    columnId: 'sector', rowKey: 'sector', idSuffix: 'sector', label: 'Sector',
    paths: ['companyInfo.sector', 'extractedData.sector', 'companyInfo.industry'],
    validator: (v) => validString(v),
  },
  {
    columnId: 'headcount', rowKey: 'headcount', idSuffix: 'headcount', label: 'Headcount',
    paths: ['operationalMetrics.headcount', 'extractedData.headcount'],
    validator: (v) => {
      const n = typeof v === 'number' ? v : parseFloat(String(v ?? ''));
      return Number.isFinite(n) && n > 0 ? n : null;
    },
    changeThreshold: 0,
  },
  {
    columnId: 'tamUsd', rowKey: 'tamUsd', idSuffix: 'tamUsd', label: 'TAM',
    paths: ['marketSize.tam_usd', 'marketSize.tam'],
    validator: (v) => validPositive(v),
    changeThreshold: 0.01,
  },
  {
    columnId: 'samUsd', rowKey: 'samUsd', idSuffix: 'samUsd', label: 'SAM',
    paths: ['marketSize.sam_usd', 'marketSize.sam'],
    validator: (v) => validPositive(v),
    changeThreshold: 0.01,
  },
  {
    columnId: 'somUsd', rowKey: 'somUsd', idSuffix: 'somUsd', label: 'SOM',
    paths: ['marketSize.som_usd', 'marketSize.som'],
    validator: (v) => validPositive(v),
    changeThreshold: 0.01,
  },
];

function resolveFirstValid(
  paths: string[],
  sections: Record<string, Record<string, unknown>>,
  validator: (v: unknown) => number | string | null
): number | string | null {
  for (const dotPath of paths) {
    const [section, key] = dotPath.split('.');
    const val = sections[section]?.[key];
    if (val == null) continue;
    const validated = validator(val);
    if (validated !== null) return validated;
  }
  return null;
}

function isChanged(
  current: number | string | null,
  suggested: number | string,
  threshold: number = 0.01
): boolean {
  if (current == null) return true;
  if (typeof current === 'string' || typeof suggested === 'string') {
    return String(current).trim().toLowerCase() !== String(suggested).trim().toLowerCase();
  }
  // For runway/headcount, use absolute threshold of 1
  if (threshold === 0) return Math.abs(current - suggested) >= 1;
  return Math.abs(current - suggested) > threshold * Math.max(1, Math.abs(current));
}

function sanityCheck(
  columnId: string,
  value: number | string,
  row: MatrixRowValues | undefined
): { pass: boolean; warning?: string } {
  if (typeof value !== 'number') return { pass: true };

  switch (columnId) {
    case 'burnRate':
      if (value < 5000) return { pass: false, warning: 'Burn < $5K/mo implausible for funded startup' };
      if (row?.arr && value > row.arr * 2) return { pass: false, warning: 'Burn > 2x ARR' };
      break;
    case 'arr':
      if (value < 1000) return { pass: false, warning: 'ARR < $1K not worth suggesting' };
      break;
    case 'headcount':
      if (value < 1 || value > 10000) return { pass: false, warning: 'Headcount out of range' };
      break;
    case 'runway':
      if (value < 1 || value > MAX_RUNWAY_MONTHS) return { pass: false, warning: 'Runway out of range' };
      break;
    case 'grossMargin':
      if (value < 0 || value > 1) return { pass: false, warning: 'Margin outside 0-100%' };
      break;
    case 'valuation':
      if (row?.arr && value < row.arr * 0.5) return { pass: false, warning: 'Valuation < 0.5x ARR' };
      break;
  }
  return { pass: true };
}

type InferredSuggestion = {
  columnId: string;
  value: number;
  reasoning: string;
  confidence: number;
};

function generateInferredSuggestions(
  sections: Record<string, Record<string, unknown>>,
  row: MatrixRowValues | undefined,
  docName: string,
): InferredSuggestion[] {
  const results: InferredSuggestion[] = [];
  const bu = sections.businessUpdates ?? {};
  const om = sections.operationalMetrics ?? {};

  // Rule 1: New hires → headcount + burn impact
  const newHires = Array.isArray(om.new_hires) ? om.new_hires : [];
  if (newHires.length > 0 && row) {
    const currentHeadcount = row.headcount ?? 0;
    if (currentHeadcount > 0) {
      results.push({
        columnId: 'headcount',
        value: currentHeadcount + newHires.length,
        reasoning: `${newHires.length} new hire(s) mentioned in ${docName}. Current: ${currentHeadcount} → ${currentHeadcount + newHires.length}. Inferred — verify.`,
        confidence: 0.45,
      });
    }
    const currentBurn = row.burnRate;
    if (currentBurn && currentBurn > 0) {
      const burnIncrease = newHires.length * 20000; // ~$20K/mo loaded cost per hire
      results.push({
        columnId: 'burnRate',
        value: currentBurn + burnIncrease,
        reasoning: `${newHires.length} new hire(s) × ~$20K/mo loaded cost. Burn: ${fmtNum(currentBurn)} → ${fmtNum(currentBurn + burnIncrease)}. Inferred — verify.`,
        confidence: 0.4,
      });
    }
  }

  // Rule 2: Customer loss language → ARR impact
  const buText = JSON.stringify(bu).toLowerCase();
  const customerLossMatch = buText.match(/lost?\s+(?:our\s+)?(?:largest|biggest|top)\s+customer/i)
    || buText.match(/(\d+)%\s+of\s+(?:arr|revenue)\s+(?:churn|lost|left)/i);
  if (customerLossMatch && row?.arr && row.arr > 0) {
    const pctMatch = buText.match(/(\d+)\s*%/);
    const lossPct = pctMatch ? parseInt(pctMatch[1]) / 100 : 0.3; // default 30% if "largest customer"
    const newArr = Math.round(row.arr * (1 - lossPct));
    results.push({
      columnId: 'arr',
      value: newArr,
      reasoning: `Customer loss mentioned in ${docName}. Estimated ${Math.round(lossPct * 100)}% ARR impact: ${fmtNum(row.arr)} → ${fmtNum(newArr)}. Inferred — verify.`,
      confidence: 0.35,
    });
  }

  // Rule 3: Fundraise detected → cash + runway
  const raiseMatch = buText.match(/raised?\s+\$?([\d.]+)\s*(m|million|k|thousand|b|billion)/i);
  if (raiseMatch && row) {
    const multiplier: Record<string, number> = { m: 1e6, million: 1e6, k: 1e3, thousand: 1e3, b: 1e9, billion: 1e9 };
    const raised = parseFloat(raiseMatch[1]) * (multiplier[raiseMatch[2].toLowerCase()] ?? 1);
    if (raised > 0 && row.cashInBank != null) {
      results.push({
        columnId: 'cashInBank',
        value: row.cashInBank + raised,
        reasoning: `Fundraise of ${fmtNum(raised)} detected in ${docName}. Cash: ${fmtNum(row.cashInBank)} → ${fmtNum(row.cashInBank + raised)}. Inferred — verify.`,
        confidence: 0.45,
      });
    }
    if (raised > 0 && row.burnRate && row.burnRate > 0) {
      const newCash = (row.cashInBank ?? 0) + raised;
      const newRunway = Math.round(newCash / row.burnRate);
      if (newRunway > 0 && newRunway <= MAX_RUNWAY_MONTHS) {
        results.push({
          columnId: 'runway',
          value: newRunway,
          reasoning: `Post-raise cash ${fmtNum(newCash)} ÷ burn ${fmtNum(row.burnRate)}/mo = ${newRunway} months. Inferred — verify.`,
          confidence: 0.4,
        });
      }
    }
  }

  // Rule 4: Cost reduction → burn rate
  const costReductionMatch = buText.match(/(?:cut|reduced?|lowered?)\s+(?:costs?|expenses?|burn|spending)\s+(?:by\s+)?(\d+)\s*%/i);
  if (costReductionMatch && row?.burnRate && row.burnRate > 0) {
    const reductionPct = parseInt(costReductionMatch[1]) / 100;
    const newBurn = Math.round(row.burnRate * (1 - reductionPct));
    results.push({
      columnId: 'burnRate',
      value: newBurn,
      reasoning: `${Math.round(reductionPct * 100)}% cost reduction mentioned in ${docName}. Burn: ${fmtNum(row.burnRate)} → ${fmtNum(newBurn)}. Inferred — verify.`,
      confidence: 0.4,
    });
  }

  return results;
}

/**
 * GET /api/matrix/suggestions
 * Suggestions = document-extracted values vs current matrix row values.
 *
 * REASONING & CITATION ENGINE:
 * - Each suggestion has reasoning (buildReasoningAndConfidence) and confidence.
 * - Reasoning: prefers value_explanations from extracted_data (doc-sourced); else "Doc: X. Matrix: Y." or "From {docName}: X."; adds context from business_updates (achievements, risks, challenges).
 * - Confidence: 0.35–0.95 from valueFromExplicitFinancials (+), risks/challenges (-), isExtrapolated (-).
 * - Citation: sourceDocumentId + sourceDocumentName identify the document; reasoning text is the human-readable citation. No separate citations[] array.
 * - Rejected suggestions are excluded using rejected_suggestions table (same fund_id).
 * - Accepted suggestions are excluded using accepted_suggestions table so they do not reappear after refresh.
 */
export async function GET(request: NextRequest) {
  try {
    if (!supabaseService) {
      return NextResponse.json(
        { error: 'Supabase service not configured' },
        { status: 503 }
      );
    }

    const searchParams = request.nextUrl.searchParams;
    const fundId = searchParams.get('fundId');
    const companyId = searchParams.get('companyId');

    if (!fundId) {
      return NextResponse.json(
        { error: 'Fund ID is required' },
        { status: 400 }
      );
    }

    // Fetch rejected and accepted suggestion IDs for this fund (tables may not exist before migrations)
    const [rejectedResult, acceptedResult] = await Promise.all([
      supabaseService.from('rejected_suggestions').select('suggestion_id').eq('fund_id', fundId),
      supabaseService.from('accepted_suggestions').select('suggestion_id').eq('fund_id', fundId),
    ]);
    const rejectedSet = rejectedResult.error
      ? new Set<string>()
      : new Set((rejectedResult.data ?? []).map((r: { suggestion_id: string }) => r.suggestion_id));
    const acceptedSet = acceptedResult.error
      ? new Set<string>()
      : new Set((acceptedResult.data ?? []).map((r: { suggestion_id: string }) => r.suggestion_id));

    let documentsQuery = supabaseService
      .from('processed_documents')
      .select('id, storage_path, processed_at, extracted_data, company_id')
      .eq('fund_id', fundId)
      .eq('status', 'completed')
      .order('processed_at', { ascending: false })
      .limit(50);
    if (companyId) documentsQuery = documentsQuery.eq('company_id', companyId);

    // Companies: use same tiered column list as GET /api/portfolio/[id]/companies so schema drift doesn't break the route
    const companyColumnsTiers = [
      ['id', 'current_arr_usd', 'burn_rate_monthly_usd', 'runway_months', 'cash_in_bank_usd', 'gross_margin', 'revenue_growth_monthly_pct', 'revenue_growth_annual_pct', 'sector', 'extra_data'],
      ['id', 'current_arr_usd', 'burn_rate_monthly_usd', 'runway_months', 'cash_in_bank_usd', 'gross_margin', 'sector', 'extra_data'],
    ];
    let companies: { id: string; [k: string]: unknown }[] | null = null;
    let companiesError: { code?: string } | null = null;
    for (const columnList of companyColumnsTiers) {
      const res = await supabaseService.from('companies').select(columnList.join(', ')).eq('fund_id', fundId);
      companies = res.data as unknown as typeof companies;
      companiesError = res.error;
      if (!companiesError) break;
      if (companiesError.code === '42703') continue;
      break;
    }

    if (companiesError || !companies) {
      return NextResponse.json({ error: 'Failed to fetch companies' }, { status: 500 });
    }

    // Documents: if table is missing fund_id/status (migration not run), return empty so route doesn't 500
    const [docsResult] = await Promise.all([
      Promise.resolve(documentsQuery).catch(() => ({ data: null as unknown as any[], error: { code: 'PGRST' } })),
    ]);
    const { data: documentsRaw, error: documentsError } = docsResult;
    const documents: { id: number; storage_path: string | null; extracted_data: unknown; company_id: string | null }[] =
      documentsError?.code === '42703' || documentsError?.code === '42P01' ? [] : (documentsRaw ?? []) ?? [];

    const companyRows = new Map<string, MatrixRowValues>();
    for (const c of companies) {
      const id = String(c.id);
      const extra = (c.extra_data && typeof c.extra_data === 'object') ? c.extra_data as Record<string, unknown> : {};
      const num = (k: string) => {
        const v = extra[k];
        if (typeof v === 'number' && Number.isFinite(v)) return v;
        const n = parseFloat(String(v ?? ''));
        return Number.isFinite(n) ? n : null;
      };
      const valuationFromExtra = num('valuation') ?? num('current_valuation_usd') ?? num('currentValuation');
      const revGrowthMonthly = c.revenue_growth_monthly_pct != null ? Number(c.revenue_growth_monthly_pct) : null;
      const revGrowthAnnual = c.revenue_growth_annual_pct != null ? Number(c.revenue_growth_annual_pct) : null;
      companyRows.set(id, {
        arr: c.current_arr_usd != null ? Number(c.current_arr_usd) : null,
        burnRate: c.burn_rate_monthly_usd != null ? Number(c.burn_rate_monthly_usd) : null,
        runway: c.runway_months != null ? Number(c.runway_months) : null,
        cashInBank: c.cash_in_bank_usd != null ? Number(c.cash_in_bank_usd) : null,
        grossMargin: c.gross_margin != null ? (Number(c.gross_margin) > 1 ? Number(c.gross_margin) / 100 : Number(c.gross_margin)) : null,
        valuation: valuationFromExtra,
        revenueGrowthMonthly: revGrowthMonthly,
        revenueGrowthAnnual: revGrowthAnnual,
        sector: typeof c.sector === 'string' ? c.sector : null,
        latestUpdate: typeof extra.latestUpdate === 'string' ? extra.latestUpdate : (typeof extra.latest_update === 'string' ? extra.latest_update : null),
        productUpdates: typeof extra.productUpdates === 'string' ? extra.productUpdates : (typeof extra.product_updates === 'string' ? extra.product_updates : null),
        headcount: num('headcount') ?? num('head_count') ?? null,
        optionPool: num('option_pool_bps') ?? num('optionPool') ?? null,
        tamUsd: num('tam_usd') ?? num('tamUsd') ?? null,
        samUsd: num('sam_usd') ?? num('samUsd') ?? null,
        somUsd: num('som_usd') ?? num('somUsd') ?? null,
      });
    }

    // Fetch pending_suggestions (service-originated: valuation, PWERM, etc.)
    let pendingQuery = supabaseService
      .from('pending_suggestions')
      .select('id, company_id, column_id, suggested_value, source_service, reasoning, metadata, created_at')
      .eq('fund_id', fundId);
    if (companyId) pendingQuery = pendingQuery.eq('company_id', companyId);
    const { data: pendingRows, error: pendingError } = await pendingQuery;
    if (pendingError) {
      // Table may not exist yet; ignore
      console.warn('[suggestions] pending_suggestions fetch failed:', pendingError.message);
    }

    const allSuggestions: Array<{
      id: string;
      cellId?: string;
      rowId: string;
      columnId: string;
      suggestedValue: number | string;
      currentValue: number | string | null;
      reasoning: string;
      confidence: number;
      sourceDocumentId?: number;
      sourceDocumentName: string;
      extractedMetric: string;
      changeType: 'new' | 'update' | 'increase' | 'decrease';
      changePercentage?: number;
      source?: 'document' | 'service';
      sourceService?: string;
      citationPage?: number;
      citationSection?: string;
    }> = [];

    /** column_id -> MatrixRowValues key for currentValue lookup */
    const columnToRowKey: Record<string, keyof MatrixRowValues> = {
      arr: 'arr', burnRate: 'burnRate', runway: 'runway', runwayMonths: 'runway',
      cashInBank: 'cashInBank', grossMargin: 'grossMargin', valuation: 'valuation',
      revenueGrowthAnnual: 'revenueGrowthAnnual', revenueGrowthMonthly: 'revenueGrowthMonthly',
      sector: 'sector', latestUpdate: 'latestUpdate', productUpdates: 'productUpdates',
      headcount: 'headcount', optionPool: 'optionPool', tamUsd: 'tamUsd', samUsd: 'samUsd', somUsd: 'somUsd',
      pwerm: 'valuation',
    };

    // Map pending_suggestions to unified suggestion shape
    for (const row of pendingRows ?? []) {
      const companyRow = companyRows.get(row.company_id);
      const key = columnToRowKey[row.column_id] ?? (row.column_id as keyof MatrixRowValues);
      const currentValue = companyRow && key ? (companyRow[key] as number | string | null) ?? null : null;
      const suggestedValue = row.suggested_value;
      const val = typeof suggestedValue === 'object' && suggestedValue !== null && 'value' in suggestedValue
        ? (suggestedValue as { value: unknown }).value
        : suggestedValue;
      allSuggestions.push({
        id: row.id,
        rowId: String(row.company_id),
        columnId: row.column_id,
        suggestedValue: val,
        currentValue,
        reasoning: row.reasoning ?? '',
        confidence: 0.7,
        source: 'service',
        sourceService: row.source_service,
        sourceDocumentName: row.source_service,
        extractedMetric: row.source_service,
        changeType: currentValue == null ? 'new' : 'update',
      });
    }

    const docName = (path: string) => path.split('/').pop()?.replace(/\.(pdf|docx|xlsx)$/i, '') || 'Unknown Document';

    /** Document-originated suggestions (from value_explanations, financial_metrics, etc.) */
    const suggestions: typeof allSuggestions = [];

    /** Insights from documents: red flags, implications, patterns - explainable, relatable to numbers */
    const insights: Array<{
      documentId: number;
      documentName: string;
      rowId: string;
      redFlags: string[];
      implications: string[];
      achievements: string[];
      challenges: string[];
      risks: string[];
    }> = [];

    let skippedNoCompany = 0;
    let skippedNoRow = 0;
    for (const doc of documents ?? []) {
      const rowId = doc.company_id ?? 'unknown';
      const row = companyRows.get(rowId);
      if (rowId === 'unknown') {
        skippedNoCompany++;
        if (skippedNoCompany === 1) {
          console.warn('[suggestions] Document(s) skipped: company_id is unknown (upload without company context)');
        }
        continue;
      }
      if (!row) {
        skippedNoRow++;
        if (skippedNoRow === 1) {
          console.warn('[suggestions] Document(s) skipped: no matching company row for company_id=', rowId);
        }
        continue;
      }
      const extractedData = (doc.extracted_data as Record<string, unknown>) || {};
      const financialMetrics = (extractedData.financial_metrics as Record<string, unknown>) || {};
      const growthMetrics = (extractedData.growth_metrics as Record<string, unknown>) || {};
      const companyInfo = (extractedData.company_info as Record<string, unknown>) || {};
      const businessUpdates = (extractedData.business_updates as Record<string, unknown>) || {};
      const runwayAndCash = (extractedData.runway_and_cash as Record<string, unknown>) || {};
      const operationalMetrics = (extractedData.operational_metrics as Record<string, unknown>) || {};
      const marketSize = (extractedData.market_size as Record<string, unknown>) || {};
      const name = docName(String(doc.storage_path ?? ''));
      const redFlagsArray = Array.isArray(extractedData.red_flags) ? (extractedData.red_flags as string[]).filter((x): x is string => typeof x === 'string') : [];
      const implications = Array.isArray(extractedData.implications) ? (extractedData.implications as string[]).filter((x): x is string => typeof x === 'string') : [];

      /** Doc-sourced reasoning: value_explanations from extraction (Cursor-for-CFO pattern) */
      const valueExplanations = extractedData.value_explanations != null && typeof extractedData.value_explanations === 'object'
        ? (extractedData.value_explanations as Record<string, string>)
        : {};
      const getValueExplanation = (columnId: string): { text: string; page?: number; section?: string } | undefined => {
        const expl = valueExplanations[columnId] ?? valueExplanations[mapColumnToMetricKey(columnId)];
        if (!expl) return undefined;
        if (typeof expl === 'string' && expl.trim()) return { text: expl };
        if (typeof expl === 'object' && expl !== null && 'text' in (expl as Record<string, unknown>)) {
          const obj = expl as Record<string, unknown>;
          return { text: String(obj.text), page: typeof obj.page === 'number' ? obj.page : undefined, section: typeof obj.section === 'string' ? obj.section : undefined };
        }
        return undefined;
      };

      // Build sections map for resolveFirstValid
      const sections: Record<string, Record<string, unknown>> = {
        financialMetrics,
        growthMetrics,
        companyInfo,
        businessUpdates,
        runwayAndCash,
        operationalMetrics,
        marketSize,
        extractedData,
      };

      // Data-driven metric extraction loop
      for (const mapping of METRIC_MAPPINGS) {
        const value = resolveFirstValid(mapping.paths, sections, mapping.validator);
        if (value === null) continue;

        const current = row?.[mapping.rowKey] ?? null;
        if (!isChanged(current, value, mapping.changeThreshold)) continue;

        const sanity = sanityCheck(mapping.columnId, value, row);
        if (!sanity.pass) continue;

        const isExplicit = mapping.isExplicitCheck?.(sections) ?? true;

        const changePercentage = typeof value === 'number' && typeof current === 'number' && current !== 0
          ? (value - current) / Math.abs(current)
          : undefined;

        const valExpl = getValueExplanation(mapping.columnId);
        const { reasoning, confidence } = buildReasoningAndConfidence({
          docName: name,
          columnId: mapping.columnId,
          suggestedValue: value,
          currentValue: current,
          businessUpdates,
          redFlags: redFlagsArray,
          valueFromExplicitFinancials: isExplicit,
          valueExplanation: valExpl?.text,
          changePercentage,
        });

        suggestions.push({
          id: `suggestion-${doc.id}-${mapping.idSuffix}`,
          cellId: `${rowId}-${mapping.columnId}`,
          rowId: String(rowId),
          columnId: mapping.columnId,
          suggestedValue: value,
          currentValue: current,
          reasoning,
          confidence,
          sourceDocumentId: doc.id,
          sourceDocumentName: name,
          extractedMetric: mapping.label,
          changeType: current == null ? 'new' : (typeof value === 'number' && typeof current === 'number' ? (value > current ? 'increase' : 'decrease') : 'update'),
          changePercentage,
          source: 'document',
          citationPage: valExpl?.page,
          citationSection: valExpl?.section,
        });
      }

      // Special case: Latest Update (builds from latest_update or first achievement — not a numeric metric)
      const latestUpdate = validString(
        (businessUpdates as { latest_update?: string }).latest_update
          ?? (Array.isArray((businessUpdates as { achievements?: unknown[] }).achievements)
            ? ((businessUpdates as { achievements: unknown[] }).achievements[0] as string)
            : null)
          ?? (companyInfo.achievements as string)
          ?? (extractedData.summary as string),
        2000
      );
      if (latestUpdate !== null) {
        const current = row?.latestUpdate ?? null;
        if (current == null || current.trim() !== latestUpdate.trim()) {
          const { reasoning, confidence } = buildReasoningAndConfidence({
            docName: name,
            columnId: 'latestUpdate',
            suggestedValue: latestUpdate,
            currentValue: current,
            businessUpdates,
            redFlags: redFlagsArray,
            valueFromExplicitFinancials: true,
            valueExplanation: getValueExplanation('latestUpdate')?.text,
          });
          suggestions.push({
            id: `suggestion-${doc.id}-latestUpdate`,
            rowId: String(rowId),
            columnId: 'latestUpdate',
            suggestedValue: latestUpdate,
            currentValue: current,
            reasoning,
            confidence,
            sourceDocumentId: doc.id,
            sourceDocumentName: name,
            extractedMetric: 'Latest Update',
            changeType: current == null ? 'new' : 'update',
            source: 'document',
          });
        }
      }

      // Special case: Product Updates (concatenates from product_updates or key_metrics)
      const productUpdatesRaw = (businessUpdates as { product_updates?: unknown[] }).product_updates ?? (extractedData.key_metrics as unknown[]);
      const productUpdatesStr = Array.isArray(productUpdatesRaw)
        ? productUpdatesRaw.map((u: unknown) => typeof u === 'string' ? u : String(u)).filter(Boolean).join('; ')
        : typeof productUpdatesRaw === 'string'
          ? productUpdatesRaw
          : null;
      const productUpdatesValid = validString(productUpdatesStr, 2000);
      if (productUpdatesValid !== null) {
        const current = row?.productUpdates ?? null;
        if (current == null || current.trim() !== productUpdatesValid.trim()) {
          const { reasoning, confidence } = buildReasoningAndConfidence({
            docName: name,
            columnId: 'productUpdates',
            suggestedValue: productUpdatesValid,
            currentValue: current,
            businessUpdates,
            redFlags: redFlagsArray,
            valueFromExplicitFinancials: true,
            valueExplanation: getValueExplanation('productUpdates')?.text,
          });
          suggestions.push({
            id: `suggestion-${doc.id}-productUpdates`,
            rowId: String(rowId),
            columnId: 'productUpdates',
            suggestedValue: productUpdatesValid,
            currentValue: current,
            reasoning,
            confidence,
            sourceDocumentId: doc.id,
            sourceDocumentName: name,
            extractedMetric: 'Product Updates',
            changeType: current == null ? 'new' : 'update',
            source: 'document',
          });
        }
      }

      // Special case: Option pool extrapolation (new_hires with senior → +200 bps per senior hire)
      const newHiresRaw = operationalMetrics.new_hires;
      const newHiresList = Array.isArray(newHiresRaw) ? newHiresRaw : (typeof newHiresRaw === 'string' && newHiresRaw ? [newHiresRaw] : []);
      const seniorHireKeywords = ['senior', 'product', 'engineering', 'eng', 'vp', 'director', 'lead'];
      const seniorHireCount = newHiresList.filter((h: unknown) => {
        const s = typeof h === 'string' ? h.toLowerCase() : (typeof h === 'object' && h && typeof (h as Record<string, unknown>).role === 'string' ? (h as Record<string, unknown>).role as string : '').toLowerCase();
        return seniorHireKeywords.some(kw => s.includes(kw));
      }).length;
      if (seniorHireCount > 0) {
        const BPS_PER_SENIOR_HIRE = 200;
        const suggestedBps = seniorHireCount * BPS_PER_SENIOR_HIRE;
        const current = row?.optionPool ?? null;
        const suggestedOptionPool = current != null ? Math.round(current + suggestedBps) : suggestedBps;
        if (current == null || Math.abs(suggestedOptionPool - (current as number)) >= BPS_PER_SENIOR_HIRE) {
          const { reasoning, confidence } = buildReasoningAndConfidence({
            docName: name,
            columnId: 'optionPool',
            suggestedValue: suggestedOptionPool,
            currentValue: current,
            businessUpdates,
            redFlags: redFlagsArray,
            valueFromExplicitFinancials: false,
            isExtrapolated: true,
            valueExplanation: getValueExplanation('optionPool')?.text,
          });
          suggestions.push({
            id: `suggestion-${doc.id}-optionPool`,
            rowId: String(rowId),
            columnId: 'optionPool',
            suggestedValue: suggestedOptionPool,
            currentValue: current,
            reasoning: getValueExplanation('optionPool')?.text ? reasoning : `Doc mentions [${newHiresList.slice(0, 3).map((h: unknown) => typeof h === 'string' ? h : (h as Record<string, unknown>)?.role ?? h).join(', ')}]. Senior product/eng hire typically expands option pool; suggest +${suggestedBps} bps (${seniorHireCount} hire(s) × 200 bps). ${reasoning}`,
            confidence,
            sourceDocumentId: doc.id,
            sourceDocumentName: name,
            extractedMetric: 'Option Pool (extrapolated)',
            changeType: current == null ? 'new' : 'update',
            source: 'document',
          });
        }
      }

      // Inference engine: generate suggestions from implicit signals in source text
      const inferred = generateInferredSuggestions(sections, row, name);
      for (const inf of inferred) {
        // Skip if an explicit suggestion for same column already exists
        const existingForCol = suggestions.find(s => s.rowId === String(rowId) && s.columnId === inf.columnId);
        if (existingForCol) continue;

        const sanity = sanityCheck(inf.columnId, inf.value, row);
        if (!sanity.pass) continue;

        suggestions.push({
          id: `suggestion-${doc.id}-inferred-${inf.columnId}`,
          cellId: `${rowId}-${inf.columnId}`,
          rowId: String(rowId),
          columnId: inf.columnId,
          suggestedValue: inf.value,
          currentValue: row?.[inf.columnId as keyof MatrixRowValues] ?? null,
          reasoning: inf.reasoning,
          confidence: inf.confidence,
          sourceDocumentId: doc.id,
          sourceDocumentName: name,
          extractedMetric: `${inf.columnId} (inferred)`,
          changeType: 'update',
          source: 'document',
        });
      }

      // Build insights for this document (explainable, relatable to suggestions)
      const achievements = Array.isArray(businessUpdates.achievements) ? (businessUpdates.achievements as unknown[]).filter((a): a is string => typeof a === 'string') : [];
      const challenges = Array.isArray(businessUpdates.challenges) ? (businessUpdates.challenges as unknown[]).filter((c): c is string => typeof c === 'string') : [];
      const risks = Array.isArray(businessUpdates.risks) ? (businessUpdates.risks as unknown[]).filter((r): r is string => typeof r === 'string') : [];
      if (redFlagsArray.length > 0 || implications.length > 0 || achievements.length > 0 || challenges.length > 0 || risks.length > 0) {
        insights.push({
          documentId: doc.id,
          documentName: name,
          rowId: String(rowId),
          redFlags: redFlagsArray,
          implications,
          achievements,
          challenges,
          risks,
        });
      }
    }

    if (skippedNoCompany > 0 || skippedNoRow > 0) {
      console.log('[suggestions] Skipped docs:', {
        fundId,
        totalDocs: documents.length,
        skippedNoCompany,
        skippedNoRow,
        hint: skippedNoCompany > 0 ? 'Upload from matrix cell or link document to company to get suggestions' : undefined,
      });
    }

    // Merge document + pending suggestions; exclude rejected and accepted
    const mergedSuggestions = [...allSuggestions, ...suggestions];
    const filteredSuggestions = mergedSuggestions.filter(
      (s) => !rejectedSet.has(s.id) && !acceptedSet.has(s.id)
    );

    if (skippedNoCompany > 0 || skippedNoRow > 0) {
      console.warn(
        `[suggestions] Skipped documents: ${skippedNoCompany} with company_id unknown, ${skippedNoRow} with no matching company row`
      );
    }

    return NextResponse.json({ suggestions: filteredSuggestions, insights });
  } catch (error) {
    console.error('Error generating suggestions:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

/** UUID format: service suggestions use pending_suggestions.id */
const isServiceSuggestionId = (id: string) => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id);

/**
 * POST /api/matrix/suggestions
 * - action 'add': insert service suggestion into pending_suggestions.
 * - action 'accept': apply value via POST /api/matrix/cells (document or service).
 * - action 'reject': persist in rejected_suggestions; if service, also delete from pending_suggestions.
 */
export async function POST(request: NextRequest) {
  try {
    if (!supabaseService) {
      return NextResponse.json(
        { error: 'Supabase service not configured' },
        { status: 503 }
      );
    }

    const body = await request.json();
    const {
      suggestionId,
      action,
      applyPayload,
      fundId: bodyFundId,
      company_id,
      column_id,
      suggested_value,
      source_service,
      reasoning,
      metadata,
    } = body as {
      suggestionId?: string;
      action?: string;
      fundId?: string;
      applyPayload?: { company_id: string; column_id: string; new_value: unknown; source_document_id?: string | number; fund_id?: string; data_source?: string };
      company_id?: string;
      column_id?: string;
      suggested_value?: unknown;
      source_service?: string;
      reasoning?: string;
      metadata?: Record<string, unknown>;
    };

    // action 'add' — insert service suggestion
    if (action === 'add') {
      const fundId = bodyFundId ?? body.fundId;
      if (!fundId || !company_id || !column_id || suggested_value === undefined || !source_service) {
        return NextResponse.json(
          { error: 'fundId, company_id, column_id, suggested_value, and source_service are required for action add' },
          { status: 400 }
        );
      }
      const { data: inserted, error: insertErr } = await supabaseService
        .from('pending_suggestions')
        .insert({
          fund_id: fundId,
          company_id,
          column_id,
          suggested_value: typeof suggested_value === 'object' && suggested_value !== null
            ? suggested_value
            : { value: suggested_value },
          source_service,
          reasoning: reasoning ?? null,
          metadata: metadata ?? null,
        })
        .select('id')
        .single();
      if (insertErr) {
        console.error('Error inserting pending suggestion:', insertErr);
        return NextResponse.json(
          { error: 'Failed to add suggestion' },
          { status: 500 }
        );
      }
      return NextResponse.json({ success: true, suggestionId: inserted.id });
    }

    if (!suggestionId || !action) {
      return NextResponse.json(
        { error: 'Suggestion ID and action are required' },
        { status: 400 }
      );
    }

    if (action === 'reject') {
      const fundId = bodyFundId ?? applyPayload?.fund_id;
      if (!fundId) {
        return NextResponse.json(
          { error: 'fundId is required when rejecting a suggestion' },
          { status: 400 }
        );
      }
      const { error: insertError } = await supabaseService
        .from('rejected_suggestions')
        .upsert(
          { fund_id: fundId, suggestion_id: String(suggestionId) },
          { onConflict: 'fund_id,suggestion_id' }
        );
      if (insertError) {
        console.error('[suggestions] Error persisting rejected suggestion:', { suggestionId, error: insertError.message });
        return NextResponse.json(
          { error: 'Failed to save rejected suggestion' },
          { status: 500 }
        );
      }
      if (isServiceSuggestionId(suggestionId)) {
        await supabaseService.from('pending_suggestions').delete().eq('id', suggestionId);
      }
      return NextResponse.json({
        success: true,
        message: `Suggestion ${suggestionId} rejected`,
        rejected: true,
      });
    }

    if (action === 'accept') {
      // Service suggestion (UUID): lookup pending_suggestions, apply in-process, delete
      if (isServiceSuggestionId(suggestionId)) {
        const fundId = bodyFundId ?? applyPayload?.fund_id;
        if (!fundId) {
          return NextResponse.json(
            { error: 'fundId is required when accepting a service suggestion' },
            { status: 400 }
          );
        }
        const { data: pendingRow, error: fetchErr } = await supabaseService
          .from('pending_suggestions')
          .select('company_id, column_id, suggested_value, source_service')
          .eq('id', suggestionId)
          .single();
        if (fetchErr || !pendingRow) {
          console.warn('[suggestions] pending_suggestions lookup failed', { suggestionId, error: fetchErr?.message, code: (fetchErr as { code?: string })?.code });
          return NextResponse.json(
            { error: 'Pending suggestion not found or already accepted' },
            { status: 404 }
          );
        }
        const newValue = typeof pendingRow.suggested_value === 'object' && pendingRow.suggested_value !== null && 'value' in pendingRow.suggested_value
          ? (pendingRow.suggested_value as { value: unknown }).value
          : pendingRow.suggested_value;
        const applyResult = await applyCellUpdate({
          company_id: pendingRow.company_id,
          column_id: pendingRow.column_id,
          new_value: newValue,
          fund_id: fundId,
          data_source: 'service',
          metadata: { source_service: pendingRow.source_service },
        });
        if (!applyResult.success) {
          const failResult = applyResult as { success: false; error: string; status: number };
          console.warn('[suggestions] applyCellUpdate failed (service accept)', { suggestionId, status: failResult.status, error: failResult.error });
          return NextResponse.json(
            { success: false, error: failResult.error },
            { status: failResult.status }
          );
        }
        await supabaseService.from('pending_suggestions').delete().eq('id', suggestionId);
        return NextResponse.json({
          success: true,
          message: `Suggestion ${suggestionId} accepted and applied`,
          applied: true,
        });
      }

      // Document suggestion: require applyPayload with company_id matching companies table
      const hasDocumentPayload = applyPayload?.company_id && applyPayload?.column_id !== undefined && applyPayload?.new_value !== undefined;
      if (!hasDocumentPayload) {
        console.warn('[suggestions] Document accept missing or incomplete applyPayload', { suggestionId, hasPayload: !!applyPayload });
        return NextResponse.json(
          { error: 'Document suggestions require applyPayload with company_id, column_id, and new_value' },
          { status: 400 }
        );
      }
      // Ensure applyPayload.company_id exists in companies table before applying
      const { data: companyRow, error: companyErr } = await supabaseService
        .from('companies')
        .select('id')
        .eq('id', applyPayload.company_id)
        .single();
      if (companyErr || !companyRow) {
        console.warn('[suggestions] Document accept: company_id not found in companies', { suggestionId, company_id: applyPayload.company_id, error: companyErr?.message });
        return NextResponse.json(
          { error: 'Company not found. The suggestion may refer to a company no longer in the matrix.' },
          { status: 404 }
        );
      }
      {
        const applyResult = await applyCellUpdate({
          company_id: applyPayload.company_id,
          column_id: applyPayload.column_id,
          new_value: applyPayload.new_value,
          fund_id: applyPayload.fund_id ?? null,
          source_document_id: applyPayload.source_document_id ?? null,
          data_source: applyPayload.data_source ?? 'document',
          metadata: applyPayload.source_document_id != null ? { sourceDocumentId: applyPayload.source_document_id } : undefined,
        });
        if (!applyResult.success) {
          const failResult = applyResult as { success: false; error: string; status: number };
          console.warn('[suggestions] applyCellUpdate failed (document accept)', { suggestionId, company_id: applyPayload.company_id, status: failResult.status, error: failResult.error });
          return NextResponse.json(
            { success: false, error: failResult.error },
            { status: failResult.status }
          );
        }
        const docFundId = applyPayload.fund_id ?? bodyFundId;
        if (docFundId && suggestionId) {
          const { error: acceptErr } = await supabaseService
            .from('accepted_suggestions')
            .upsert(
              { fund_id: docFundId, suggestion_id: String(suggestionId) },
              { onConflict: 'fund_id,suggestion_id' }
            );
          if (acceptErr) {
            console.error('Error persisting accepted suggestion:', acceptErr);
            return NextResponse.json(
              { error: acceptErr.message ?? 'Failed to save accepted suggestion' },
              { status: 500 }
            );
          }
        }
        return NextResponse.json({
          success: true,
          message: `Suggestion ${suggestionId} accepted and applied`,
          applied: true,
        });
      }
    }

    return NextResponse.json({
      success: true,
      message: `Suggestion ${suggestionId} ${action}ed`,
    });
  } catch (error) {
    console.error('[suggestions] POST error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
