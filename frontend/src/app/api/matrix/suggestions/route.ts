import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';
import { applyCellUpdate } from '@/lib/matrix/apply-cell-server';
import { getColumnType, getColumnLabel } from '@/lib/matrix/cell-formatters';

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
  customerCount: number | null;
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

/**
 * Build reasoning with source attribution: "quote" → why → metric change.
 * When doc provides value_explanation (already in "quote → why → change" format), pass it through.
 * When absent, build attribution from best available signal in business_updates.
 */
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

  const isPctColumn = columnId === 'grossMargin' || columnId === 'revenueGrowthAnnual' || columnId === 'revenueGrowthMonthly';
  const fmtPct = (n: number) => (columnId === 'grossMargin' && n <= 1 ? (n * 100).toFixed(0) : n.toFixed(1)) + '%';
  const fmtVal = (v: number | string) => typeof v === 'number' ? (isPctColumn ? fmtPct(columnId === 'grossMargin' && v <= 1 ? v * 100 : v) : fmtNum(v)) : String(v);

  let reasoning: string;

  if (valueExplanation != null && valueExplanation !== '') {
    // LLM-sourced explanation already in "quote → why → change" format — pass through
    const base = valueExplanation.trim();
    if (currentValue !== null && currentValue !== undefined && currentValue !== '') {
      reasoning = `${base} (was ${fmtVal(currentValue)}).`;
    } else {
      reasoning = base.endsWith('.') ? base : `${base}.`;
    }
  } else {
    // Build attribution from best available signal
    const sugg = fmtVal(suggestedValue);
    const pctStr = changePercentage != null ? ` (${changePercentage > 0 ? '+' : ''}${(changePercentage * 100).toFixed(0)}%)` : '';

    // Pick the most relevant signal from business_updates as source attribution
    let signal: string | null = null;
    if (hasCaution && challenges.length > 0) signal = challenges[0];
    else if (hasCaution && risks.length > 0) signal = risks[0];
    else if (achievements.length > 0) signal = achievements[0];
    else if (productUpdates.length > 0) signal = productUpdates[0];
    else if (bu.latest_update && typeof bu.latest_update === 'string') signal = bu.latest_update;

    if (signal && currentValue !== null && currentValue !== undefined && currentValue !== '') {
      // Full attribution: "signal" → metric moves from X to Y
      const truncatedSignal = signal.length > 120 ? signal.slice(0, 117) + '...' : signal;
      reasoning = `"${truncatedSignal}" → ${columnId} ${sugg}${pctStr} (was ${fmtVal(currentValue)}).`;
    } else if (signal) {
      const truncatedSignal = signal.length > 120 ? signal.slice(0, 117) + '...' : signal;
      reasoning = `"${truncatedSignal}" → ${columnId} ${sugg}.`;
    } else if (currentValue !== null && currentValue !== undefined && currentValue !== '') {
      reasoning = `${docName}: ${sugg}${pctStr} (was ${fmtVal(currentValue)}).`;
    } else {
      reasoning = `${docName}: ${sugg}.`;
    }

    if (isExtrapolated) reasoning += ' Inferred, not stated explicitly.';
  }

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
  {
    columnId: 'customerCount', rowKey: 'customerCount', idSuffix: 'customerCount', label: 'Customer Count',
    paths: ['operationalMetrics.customer_count', 'financialMetrics.customer_count', 'extractedData.customer_count'],
    validator: (v) => {
      const n = typeof v === 'number' ? v : parseFloat(String(v ?? ''));
      return Number.isFinite(n) && n > 0 ? n : null;
    },
    changeThreshold: 0,
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
        reasoning: `"${newHires.length} new hire(s)" in ${docName} → headcount ${currentHeadcount} → ${currentHeadcount + newHires.length}. Inferred — verify.`,
        confidence: 0.45,
      });
    }
    const currentBurn = row.burnRate;
    if (currentBurn && currentBurn > 0) {
      const burnIncrease = newHires.length * 20000; // ~$20K/mo loaded cost per hire
      results.push({
        columnId: 'burnRate',
        value: currentBurn + burnIncrease,
        reasoning: `"${newHires.length} new hire(s)" → ~$20K/mo loaded each → burn ${fmtNum(currentBurn)} → ${fmtNum(currentBurn + burnIncrease)}. Inferred — verify.`,
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
      reasoning: `"customer loss" in ${docName} → ~${Math.round(lossPct * 100)}% ARR impact → ARR ${fmtNum(row.arr)} → ${fmtNum(newArr)}. Inferred — verify.`,
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
        reasoning: `"raised ${fmtNum(raised)}" in ${docName} → cash ${fmtNum(row.cashInBank)} → ${fmtNum(row.cashInBank + raised)}. Inferred — verify.`,
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
          reasoning: `"raised ${fmtNum(raised)}" → post-raise cash ${fmtNum(newCash)} ÷ burn ${fmtNum(row.burnRate)}/mo → runway ${newRunway}mo. Inferred — verify.`,
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
      reasoning: `"${Math.round(reductionPct * 100)}% cost reduction" in ${docName} → burn ${fmtNum(row.burnRate)} → ${fmtNum(newBurn)}. Inferred — verify.`,
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
    // Composite key sets for dedup-safe filtering.  When dedup keeps a higher-confidence
    // suggestion with a different ID, the raw acceptedSet/rejectedSet miss it.  These
    // sets track rowId::columnId::source so accepting a document suggestion does NOT
    // block a service suggestion for the same cell (and vice versa).
    // Legacy keys without source suffix (rowId::columnId) are treated as blocking both.
    const acceptedCompositeKeys = new Set<string>();
    const rejectedCompositeKeys = new Set<string>();
    for (const id of acceptedSet) {
      if (id.includes('::')) acceptedCompositeKeys.add(id);
    }
    for (const id of rejectedSet) {
      if (id.includes('::')) rejectedCompositeKeys.add(id);
    }

    // Include both 'completed' and 'pending' documents.  The backend inline-
    // processing path (document_query_service.py) can populate extracted_data on
    // pending docs before Celery marks them completed.  Without this, the demo
    // flow (upload → inline extract → still "pending" in DB) produces no
    // suggestions because the old .eq('status','completed') filter excluded them.
    // Pending docs without extracted_data are harmless — the metric extraction
    // loop simply finds nothing and skips them.
    let documentsQuery = supabaseService
      .from('processed_documents')
      .select('id, storage_path, processed_at, extracted_data, company_id')
      .eq('fund_id', fundId)
      .in('status', ['completed', 'pending'])
      .order('processed_at', { ascending: false })
      .limit(50);
    if (companyId) documentsQuery = documentsQuery.eq('company_id', companyId);

    // Companies: use same tiered column list as GET /api/portfolio/[id]/companies so schema drift doesn't break the route
    const companyColumnsTiers = [
      ['id', 'name', 'current_arr_usd', 'burn_rate_monthly_usd', 'runway_months', 'cash_in_bank_usd', 'gross_margin', 'revenue_growth_monthly_pct', 'revenue_growth_annual_pct', 'sector', 'extra_data'],
      ['id', 'name', 'current_arr_usd', 'burn_rate_monthly_usd', 'runway_months', 'cash_in_bank_usd', 'gross_margin', 'sector', 'extra_data'],
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
    const documentsAll: { id: number; storage_path: string | null; extracted_data: unknown; company_id: string | null }[] =
      documentsError?.code === '42703' || documentsError?.code === '42P01' ? [] : (documentsRaw ?? []) ?? [];

    // Deduplicate documents: when the same file is processed multiple times (inline + Celery),
    // keep only the most recent run per company_id + storage_path to avoid duplicate suggestions.
    const seenDocKeys = new Set<string>();
    const documents: typeof documentsAll = [];
    for (const doc of documentsAll) {
      const dedupKey = `${doc.company_id ?? 'none'}::${doc.storage_path ?? doc.id}`;
      if (seenDocKeys.has(dedupKey)) continue;
      seenDocKeys.add(dedupKey);
      documents.push(doc);
    }

    /** name→id lookup for documents uploaded without company context.
     *  Stores both the full name and the first token for partial matching.
     *  e.g. "Mercury Financial" → entries for "mercury financial" AND "mercury" */
    const companyNameToId = new Map<string, string>();
    for (const c of companies) {
      const cName = typeof c.name === 'string' ? c.name.trim().toLowerCase() : '';
      if (cName) {
        companyNameToId.set(cName, String(c.id));
        // Also index the first word (handles "Mercury Financial" → "mercury")
        const firstToken = cName.split(/\s+/)[0];
        if (firstToken && firstToken.length > 2 && !companyNameToId.has(firstToken)) {
          companyNameToId.set(firstToken, String(c.id));
        }
      }
    }

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
        customerCount: num('customer_count') ?? num('customerCount') ?? null,
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
      documentSummary?: string;
    }> = [];

    /** column_id -> MatrixRowValues key for currentValue lookup */
    const columnToRowKey: Record<string, keyof MatrixRowValues> = {
      arr: 'arr', burnRate: 'burnRate', runway: 'runway', runwayMonths: 'runway',
      cashInBank: 'cashInBank', grossMargin: 'grossMargin', valuation: 'valuation',
      revenueGrowthAnnual: 'revenueGrowthAnnual', revenueGrowthMonthly: 'revenueGrowthMonthly',
      sector: 'sector', latestUpdate: 'latestUpdate', productUpdates: 'productUpdates',
      headcount: 'headcount', optionPool: 'optionPool', tamUsd: 'tamUsd', samUsd: 'samUsd', somUsd: 'somUsd', customerCount: 'customerCount',
    };

    // Deduplicate pending_suggestions: keep latest per company_id + column_id
    const pendingDedup = new Map<string, (typeof pendingRows extends (infer T)[] | null ? T : never)>();
    for (const row of pendingRows ?? []) {
      const pk = `${row.company_id}::${row.column_id}`;
      const existing = pendingDedup.get(pk);
      if (!existing || new Date(row.created_at) > new Date(existing.created_at)) {
        pendingDedup.set(pk, row);
      }
    }
    const dedupedPending = [...pendingDedup.values()];

    // Map pending_suggestions to unified suggestion shape
    // Includes both cell-edit suggestions and action suggestions (_action_* column_id)
    for (const row of dedupedPending) {
      const isActionSuggestion = row.column_id?.startsWith('_action_');

      if (isActionSuggestion) {
        // Action suggestions (insights, warnings, action items) — parse from suggested_value JSON
        let actionData: Record<string, unknown> = {};
        try {
          actionData = typeof row.suggested_value === 'string'
            ? JSON.parse(row.suggested_value)
            : (row.suggested_value ?? {});
        } catch { actionData = {}; }

        allSuggestions.push({
          id: row.id,
          rowId: String(row.company_id),
          columnId: row.column_id,
          suggestedValue: (actionData.title as string) || row.reasoning || '',
          currentValue: null,
          reasoning: (actionData.description as string) || row.reasoning || '',
          confidence: (row.metadata as Record<string, unknown>)?.confidence as number ?? 0.65,
          source: 'service',
          sourceService: row.source_service,
          sourceDocumentName: row.source_service,
          extractedMetric: (actionData.type as string) || row.source_service,
          changeType: 'new',
        });
      } else {
        // Standard cell-edit suggestions
        const companyRow = companyRows.get(row.company_id);
        const key = columnToRowKey[row.column_id] ?? (row.column_id as keyof MatrixRowValues);
        const currentValue = companyRow && key ? (companyRow[key] as number | string | null) ?? null : null;
        let suggestedValue = row.suggested_value;
        // JSONB may return a JSON-encoded string — parse it
        if (typeof suggestedValue === 'string') {
          try {
            const parsed = JSON.parse(suggestedValue);
            suggestedValue = parsed;
          } catch { /* raw string, keep as-is */ }
        }
        // Extract primitive from wrapped objects (e.g. {"value": 123}, {"fair_value": 500000})
        let val = suggestedValue;
        let isDelta = false;
        if (typeof suggestedValue === 'object' && suggestedValue !== null && !Array.isArray(suggestedValue)) {
          const obj = suggestedValue as Record<string, unknown>;
          if ('delta' in obj && typeof obj.delta === 'number') {
            // Delta suggestion (from document impact estimates): apply to current matrix value
            isDelta = true;
            val = typeof currentValue === 'number' ? currentValue + obj.delta : null;
          } else {
            val = obj.value ?? obj.fair_value ?? obj.displayValue ?? obj.display_value ?? obj.amount;
            if (val === null || val === undefined) {
              const firstPrimitive = Object.values(obj).find(v => typeof v === 'string' || typeof v === 'number');
              val = firstPrimitive ?? JSON.stringify(suggestedValue);
            }
          }
        }
        // Skip delta suggestions that can't resolve (no current value to apply delta to)
        if (val === null || val === undefined) continue;
        allSuggestions.push({
          id: row.id,
          rowId: String(row.company_id),
          columnId: row.column_id,
          suggestedValue: val,
          currentValue,
          reasoning: row.reasoning ?? '',
          confidence: (row.metadata as Record<string, unknown>)?.confidence as number ?? 0.7,
          source: 'service',
          sourceService: row.source_service,
          sourceDocumentName: row.source_service,
          extractedMetric: row.source_service,
          changeType: currentValue == null ? 'new'
            : (isDelta && typeof val === 'number' && typeof currentValue === 'number'
              ? (val > currentValue ? 'increase' : 'decrease')
              : 'update'),
        });
      }
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

    // Build a set of (rowId::columnId) pairs already covered by pending_suggestions
    // so the document-extraction loop below doesn't produce duplicates.
    const pendingCoveredCells = new Set<string>();
    for (const s of allSuggestions) {
      if (s.source === 'service') {
        pendingCoveredCells.add(`${s.rowId}::${s.columnId}`);
      }
    }

    let skippedNoCompany = 0;
    let skippedNoRow = 0;
    for (const doc of documents ?? []) {
      let rowId = doc.company_id ?? 'unknown';

      // If no company_id, try to match by company name from extracted data or filename
      if (rowId === 'unknown') {
        const ext = (doc.extracted_data as Record<string, unknown>) ?? {};
        const info = (ext.company_info as Record<string, unknown>) ?? {};
        // Try multiple paths for company name in extracted data
        const docCompanyName = (
          info.name ?? info.company_name ?? info.company ??
          ext.company_name ?? ext.company ??
          (ext.summary_data as Record<string, unknown> | undefined)?.company_name ??
          ''
        ) as string;
        const docFileName = String(doc.storage_path ?? '');
        // Build candidate list: extracted name, extracted first-word, filename tokens
        const candidates: string[] = [];
        if (docCompanyName && typeof docCompanyName === 'string' && docCompanyName.trim()) {
          const fullName = docCompanyName.trim().toLowerCase();
          candidates.push(fullName);
          // Also try first word: "Mercury Financial Inc" -> "mercury"
          const firstWord = fullName.split(/\s+/)[0];
          if (firstWord && firstWord.length > 2 && firstWord !== fullName) {
            candidates.push(firstWord);
          }
        }
        // Try filename: "Mercury_Q3_Report.pdf" → "mercury"
        const fileBase = docFileName.split('/').pop()?.replace(/\.[^.]+$/, '')?.split(/[_\-\s]+/)?.[0];
        if (fileBase && fileBase.length > 2) candidates.push(fileBase.toLowerCase());

        for (const candidate of candidates) {
          if (candidate.length < 4) continue; // Skip short candidates to avoid false matches
          // Exact match
          const exactMatch = companyNameToId.get(candidate);
          if (exactMatch) { rowId = exactMatch; break; }
          // Substring match: "mercury" matches "mercury financial"
          // Only match if candidate is a substantial portion of the name (or vice versa)
          for (const [name, id] of companyNameToId) {
            if (name === candidate) { rowId = id; break; }
            if (name.length >= 4 && (name.startsWith(candidate) || candidate.startsWith(name))) {
              rowId = id; break;
            }
          }
          if (rowId !== 'unknown') break;
        }
        if (rowId !== 'unknown') {
          console.info(`[suggestions] Resolved document ${doc.id} to company ${rowId} via name matching (candidates: ${candidates.join(', ')})`);
        }
      }

      if (rowId === 'unknown') {
        skippedNoCompany++;
        if (skippedNoCompany <= 3) {
          const extD = (doc.extracted_data as Record<string, unknown>) ?? {};
          const infoD = (extD.company_info as Record<string, unknown>) ?? {};
          console.warn(`[suggestions] Document ${doc.id} skipped: no company match. extracted_name="${infoD.name ?? infoD.company_name ?? 'none'}", path="${doc.storage_path}"`);
        }
        continue;
      }
      const row = companyRows.get(rowId);
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

      // Build document summary from extracted sections for richer suggestion context
      const summaryParts: string[] = [];
      if (typeof extractedData.summary === 'string' && extractedData.summary.trim()) {
        summaryParts.push(extractedData.summary.trim());
      } else {
        // Synthesize from available fields
        if (typeof companyInfo.description === 'string') summaryParts.push(companyInfo.description);
        const bu = businessUpdates as Record<string, unknown>;
        const achArr = Array.isArray(bu.achievements) ? bu.achievements.filter((a): a is string => typeof a === 'string') : [];
        if (achArr.length > 0) summaryParts.push(`Key achievements: ${achArr.slice(0, 2).join('; ')}`);
        const riskArr = Array.isArray(bu.risks) ? bu.risks.filter((r): r is string => typeof r === 'string') : [];
        if (riskArr.length > 0) summaryParts.push(`Risks: ${riskArr.slice(0, 2).join('; ')}`);
      }
      const docSummary = summaryParts.length > 0 ? summaryParts.join('. ').slice(0, 500) : undefined;
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
        // Skip if this cell already has a pending_suggestion from the backend pipeline
        if (pendingCoveredCells.has(`${rowId}::${mapping.columnId}`)) continue;

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
          documentSummary: docSummary,
        });
      }

      // Special case: Latest Update (builds from latest_update or first achievement — NOT summary)
      // DO NOT fall back to extractedData.summary — that produces junk generic suggestions
      const latestUpdate = validString(
        (businessUpdates as { latest_update?: string }).latest_update
          ?? (Array.isArray((businessUpdates as { achievements?: unknown[] }).achievements)
              && (businessUpdates as { achievements: unknown[] }).achievements.length > 0
            ? ((businessUpdates as { achievements: unknown[] }).achievements[0] as string)
            : null),
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
            documentSummary: docSummary,
          });
        }
      }

      // Special case: Product Updates (concatenates from product_updates or key_metrics)
      const productUpdatesRaw = (businessUpdates as { product_updates?: unknown[] }).product_updates ?? (extractedData.key_metrics as unknown[]);
      const productUpdatesStr = Array.isArray(productUpdatesRaw)
        ? productUpdatesRaw.map((u: unknown) => {
            if (typeof u === 'string') return u;
            if (typeof u === 'object' && u !== null) { const o = u as Record<string, unknown>; return typeof o.text === 'string' ? o.text : typeof o.description === 'string' ? o.description : typeof o.update === 'string' ? o.update : typeof o.name === 'string' ? o.name : ''; }
            return '';
          }).filter(Boolean).join('; ')
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
            documentSummary: docSummary,
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
            reasoning: getValueExplanation('optionPool')?.text ? reasoning : `Doc mentions [${newHiresList.slice(0, 3).map((h: unknown) => { if (typeof h === 'string') return h; if (typeof h === 'object' && h !== null) { const o = h as Record<string, unknown>; return typeof o.role === 'string' ? o.role : typeof o.title === 'string' ? o.title : typeof o.name === 'string' ? o.name : 'hire'; } return 'hire'; }).join(', ')}]. Senior product/eng hire typically expands option pool; suggest +${suggestedBps} bps (${seniorHireCount} hire(s) × 200 bps). ${reasoning}`,
            confidence,
            sourceDocumentId: doc.id,
            sourceDocumentName: name,
            extractedMetric: 'Option Pool (extrapolated)',
            changeType: current == null ? 'new' : 'update',
            source: 'document',
            documentSummary: docSummary,
          });
        }
      }

      // === Impact Estimates: LLM-estimated material impact of qualitative signals ===
      // These are the transformation layer — qualitative prose → numeric suggestions
      // with document-level citation and reasoning from the LLM.
      const impactEstimates = (extractedData.impact_estimates as Record<string, unknown>) ?? {};
      const impactReasoning = (impactEstimates.impact_reasoning as Record<string, string>) ?? {};
      const IMPACT_TO_COLUMN: Record<string, { columnId: string; rowKey: keyof MatrixRowValues; label: string; isDelta: boolean }> = {
        estimated_arr_impact: { columnId: 'arr', rowKey: 'arr', label: 'ARR (impact)', isDelta: true },
        estimated_burn_impact: { columnId: 'burnRate', rowKey: 'burnRate', label: 'Burn Rate (impact)', isDelta: true },
        estimated_runway_impact: { columnId: 'runway', rowKey: 'runway', label: 'Runway (impact)', isDelta: true },
        estimated_headcount_impact: { columnId: 'headcount', rowKey: 'headcount', label: 'Headcount (impact)', isDelta: true },
        estimated_cash_impact: { columnId: 'cashInBank', rowKey: 'cashInBank', label: 'Cash (impact)', isDelta: true },
        estimated_valuation_impact: { columnId: 'valuation', rowKey: 'valuation', label: 'Valuation (impact)', isDelta: true },
        estimated_growth_rate_change: { columnId: 'revenueGrowthAnnual', rowKey: 'revenueGrowthAnnual', label: 'Growth Rate (impact)', isDelta: true },
      };
      for (const [impactKey, mapping] of Object.entries(IMPACT_TO_COLUMN)) {
        const delta = typeof impactEstimates[impactKey] === 'number' ? (impactEstimates[impactKey] as number) : null;
        if (delta == null || delta === 0) continue;
        // Skip if an explicit extraction already produced a suggestion for this column
        const existsExplicit = suggestions.find(s => s.rowId === String(rowId) && s.columnId === mapping.columnId);
        if (existsExplicit) continue;
        if (pendingCoveredCells.has(`${rowId}::${mapping.columnId}`)) continue;

        const current = row?.[mapping.rowKey] ?? null;
        // Apply delta to current value (impact estimates are deltas, not absolutes)
        const suggestedValue = typeof current === 'number' ? current + delta : null;
        if (suggestedValue == null) continue;

        const sanity = sanityCheck(mapping.columnId, suggestedValue, row);
        if (!sanity.pass) continue;

        // Use LLM's impact reasoning as document-level citation
        const impactReasonKey = impactKey.replace('estimated_', '').replace('_impact', '').replace('_change', '');
        const llmReasoning = impactReasoning[impactReasonKey] || impactReasoning[impactKey] || '';
        const deltaStr = delta > 0 ? `+${typeof delta === 'number' && Math.abs(delta) >= 1000 ? fmtNum(delta) : delta}` : `${typeof delta === 'number' && Math.abs(delta) >= 1000 ? fmtNum(delta) : delta}`;
        const reasoning = llmReasoning
          ? `${llmReasoning} (${deltaStr} from ${name}).`
          : `Estimated impact: ${deltaStr} based on qualitative signals in ${name}.`;

        suggestions.push({
          id: `suggestion-${doc.id}-impact-${mapping.columnId}`,
          cellId: `${rowId}-${mapping.columnId}`,
          rowId: String(rowId),
          columnId: mapping.columnId,
          suggestedValue,
          currentValue: current,
          reasoning,
          confidence: 0.5, // LLM-estimated impacts get moderate confidence
          sourceDocumentId: doc.id,
          sourceDocumentName: name,
          extractedMetric: mapping.label,
          changeType: typeof current === 'number' ? (suggestedValue > current ? 'increase' : 'decrease') : 'new',
          source: 'document',
          documentSummary: docSummary,
        });
      }

      // Inference engine: generate suggestions from implicit signals in source text
      // (fallback for when impact_estimates is missing — older extractions)
      const inferred = generateInferredSuggestions(sections, row, name);
      for (const inf of inferred) {
        // Skip if an explicit or impact-based suggestion for same column already exists
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
          documentSummary: docSummary,
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

    // --- Phase 7: Auto-enrich sparse companies with stage-based estimates ---
    const STAGE_BENCHMARKS: Record<string, Record<string, { value: number; confidence: number }>> = {
      'Pre-Seed': { arr: { value: 200_000, confidence: 0.35 }, burnRate: { value: 80_000, confidence: 0.3 }, headcount: { value: 5, confidence: 0.4 }, runway: { value: 18, confidence: 0.3 } },
      'Seed': { arr: { value: 1_000_000, confidence: 0.4 }, burnRate: { value: 200_000, confidence: 0.35 }, headcount: { value: 12, confidence: 0.4 }, runway: { value: 18, confidence: 0.35 }, grossMargin: { value: 0.65, confidence: 0.3 } },
      'Series A': { arr: { value: 5_000_000, confidence: 0.4 }, burnRate: { value: 500_000, confidence: 0.35 }, headcount: { value: 40, confidence: 0.4 }, runway: { value: 20, confidence: 0.35 }, grossMargin: { value: 0.7, confidence: 0.35 } },
      'Series B': { arr: { value: 15_000_000, confidence: 0.4 }, burnRate: { value: 1_200_000, confidence: 0.35 }, headcount: { value: 120, confidence: 0.4 }, runway: { value: 20, confidence: 0.35 }, grossMargin: { value: 0.72, confidence: 0.35 } },
      'Series C': { arr: { value: 50_000_000, confidence: 0.4 }, burnRate: { value: 3_000_000, confidence: 0.35 }, headcount: { value: 300, confidence: 0.4 }, runway: { value: 18, confidence: 0.35 }, grossMargin: { value: 0.75, confidence: 0.35 } },
    };

    for (const c of companies) {
      const id = String(c.id);
      const row = companyRows.get(id);
      if (!row) continue;
      const extra = (c.extra_data && typeof c.extra_data === 'object') ? c.extra_data as Record<string, unknown> : {};
      const stage = (extra.stage as string) || (extra.funnel_status as string) || (extra.funding_stage as string) || '';
      const normalizedStage = Object.keys(STAGE_BENCHMARKS).find(s => stage.toLowerCase().includes(s.toLowerCase()));
      if (!normalizedStage) continue;
      const benchmarks = STAGE_BENCHMARKS[normalizedStage];
      const emptyFields: string[] = [];
      if (row.arr == null) emptyFields.push('arr');
      if (row.burnRate == null) emptyFields.push('burnRate');
      if (row.headcount == null) emptyFields.push('headcount');
      if (row.runway == null) emptyFields.push('runway');
      if (row.grossMargin == null) emptyFields.push('grossMargin');
      if (emptyFields.length < 3) continue;
      const companyName = typeof c.name === 'string' ? c.name : 'Unknown';
      for (const field of emptyFields) {
        const benchmark = benchmarks[field as keyof typeof benchmarks];
        if (!benchmark) continue;
        const hasSuggestion = [...allSuggestions, ...suggestions].some(s => s.rowId === id && s.columnId === field);
        if (hasSuggestion) continue;
        const suggestionId = `auto-enrich-${id}-${field}`;
        if (rejectedSet.has(suggestionId) || acceptedSet.has(suggestionId)) continue;
        allSuggestions.push({
          id: suggestionId,
          rowId: id,
          columnId: field,
          suggestedValue: benchmark.value,
          currentValue: null,
          reasoning: `${normalizedStage} stage median for ${companyName}. Stage benchmark estimate — verify with actual data.`,
          confidence: benchmark.confidence,
          source: 'service',
          sourceService: 'auto_enrich.stage_benchmark',
          sourceDocumentName: 'Stage Benchmarks',
          extractedMetric: `${field} (stage estimate)`,
          changeType: 'new' as const,
        });
      }
    }

    // Merge document + pending suggestions; exclude rejected and accepted; dedup by rowId+columnId (keep highest confidence)
    const mergedRaw = [...allSuggestions, ...suggestions];

    // Before dedup: scan all raw suggestions and mark SOURCE-AWARE composite keys
    // (rowId::columnId::source) as accepted/rejected when ANY variant of the suggestion
    // ID was accepted/rejected.  This way accepting a doc suggestion for ARR does NOT
    // block a service suggestion for ARR on the same company.
    for (const s of mergedRaw) {
      const src = s.source ?? 'document';
      const sourceAwareKey = `${s.rowId}::${s.columnId}::${src}`;
      if (acceptedSet.has(s.id)) acceptedCompositeKeys.add(sourceAwareKey);
      if (rejectedSet.has(s.id)) rejectedCompositeKeys.add(sourceAwareKey);
    }

    // Dedup by rowId::columnId::source — keep highest confidence per cell per source type.
    // This means a doc suggestion and a service suggestion for the same cell both survive.
    const dedupMap = new Map<string, (typeof mergedRaw)[number]>();
    for (const s of mergedRaw) {
      const src = s.source ?? 'document';
      const key = `${s.rowId}::${s.columnId}::${src}`;
      const existing = dedupMap.get(key);
      if (!existing || s.confidence > existing.confidence) {
        dedupMap.set(key, s);
      }
    }

    // Value-aware dedup: if a doc and service suggestion target the same cell with
    // equivalent values, keep only the higher-confidence one regardless of source.
    const valueDedupMap = new Map<string, (typeof mergedRaw)[number]>();
    for (const s of dedupMap.values()) {
      const cellKey = `${s.rowId}::${s.columnId}`;
      const existing = valueDedupMap.get(cellKey);
      if (!existing) {
        valueDedupMap.set(cellKey, s);
        continue;
      }
      // Check if values are equivalent
      const valuesMatch = typeof s.suggestedValue === 'number' && typeof existing.suggestedValue === 'number'
        ? Math.abs(s.suggestedValue - existing.suggestedValue) <= 0.01 * Math.max(1, Math.abs(existing.suggestedValue))
        : String(s.suggestedValue).trim().toLowerCase() === String(existing.suggestedValue).trim().toLowerCase();
      if (valuesMatch) {
        // Same value — keep the higher-confidence one
        if (s.confidence > existing.confidence) {
          valueDedupMap.set(cellKey, s);
        }
      } else {
        // Different values — both survive, restore the source-keyed entry
        valueDedupMap.set(`${cellKey}::${s.source ?? 'document'}`, s);
        // Ensure existing also has a source-keyed entry
        const existingSourceKey = `${cellKey}::${existing.source ?? 'document'}`;
        if (!valueDedupMap.has(existingSourceKey)) {
          valueDedupMap.set(existingSourceKey, existing);
        }
      }
    }
    // Replace dedupMap with value-deduped results
    dedupMap.clear();
    for (const [k, v] of valueDedupMap) {
      dedupMap.set(k, v);
    }
    const filteredSuggestions = [...dedupMap.values()].filter((s) => {
      // Drop suggestions with null/empty values — these show as "N/A" in the UI
      if (s.suggestedValue === null || s.suggestedValue === undefined) return false;
      if (typeof s.suggestedValue === 'object' && s.suggestedValue !== null && !Array.isArray(s.suggestedValue)) {
        const obj = s.suggestedValue as Record<string, unknown>;
        const hasUsableValue = Object.values(obj).some(v => v !== null && v !== undefined && v !== '');
        if (!hasUsableValue) return false;
      }
      const src = s.source ?? 'document';
      const sourceAwareKey = `${s.rowId}::${s.columnId}::${src}`;
      // Legacy key (no source suffix) blocks both sources for backwards compat
      const legacyKey = `${s.rowId}::${s.columnId}`;
      if (rejectedSet.has(s.id) || rejectedCompositeKeys.has(sourceAwareKey) || rejectedCompositeKeys.has(legacyKey)) return false;
      if (acceptedSet.has(s.id) || acceptedCompositeKeys.has(sourceAwareKey) || acceptedCompositeKeys.has(legacyKey)) return false;
      return true;
    });

    // ── Suggestion ranking: composite score by impact, recency, corrections ──
    const highImpactColumns = new Set([
      'arr', 'valuation', 'grossMargin', 'revenueGrowthAnnual', 'burnRate', 'runway', 'totalRaised',
    ]);
    for (const s of filteredSuggestions) {
      let score = (s as any).confidence ?? 0.5;

      // Recency boost: suggestions from recent sources rank higher
      const createdAt = (s as any).createdAt || (s as any).created_at;
      if (createdAt) {
        const daysSince = (Date.now() - new Date(createdAt).getTime()) / 86_400_000;
        score += Math.max(0, 0.15 * (1 - daysSince / 30));
      }

      // Portfolio impact: financial fields matter more
      if (highImpactColumns.has(s.columnId)) score += 0.1;

      // Corrections: boost if flagged as a correction
      if ((s as any).isCorrection || (s as any).is_correction) score += 0.2;

      // Source trust: service suggestions (search-backed) slightly above document-inferred
      if (s.source === 'service') score += 0.05;

      (s as any)._score = score;
    }
    filteredSuggestions.sort((a, b) => ((b as any)._score ?? 0) - ((a as any)._score ?? 0));

    if (skippedNoCompany > 0 || skippedNoRow > 0) {
      console.warn(
        `[suggestions] Skipped documents: ${skippedNoCompany} with company_id unknown, ${skippedNoRow} with no matching company row`
      );
    }

    // Enrich each suggestion with column metadata so the frontend can
    // format values and auto-create columns without a separate lookup.
    const enriched = filteredSuggestions.map((s) => ({
      ...s,
      columnType: getColumnType(s.columnId),
      columnName: getColumnLabel(s.columnId),
    }));

    return NextResponse.json({ suggestions: enriched, insights });
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
        .upsert({
          fund_id: fundId,
          company_id,
          column_id,
          suggested_value: typeof suggested_value === 'object' && suggested_value !== null
            ? suggested_value
            : { value: suggested_value },
          source_service,
          reasoning: reasoning ?? null,
          metadata: metadata ?? null,
        }, { onConflict: 'fund_id,company_id,column_id' })
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
      // Build list of rejection records: raw ID + source-aware composite key.
      const rejectRows: { fund_id: string; suggestion_id: string }[] = [
        { fund_id: fundId, suggestion_id: String(suggestionId) },
      ];
      // If applyPayload carries company_id + column_id, record source-aware composite key.
      if (applyPayload?.company_id && applyPayload?.column_id) {
        const src = isServiceSuggestionId(suggestionId) ? 'service' : 'document';
        rejectRows.push({ fund_id: fundId, suggestion_id: `${applyPayload.company_id}::${applyPayload.column_id}::${src}` });
      }
      if (isServiceSuggestionId(suggestionId)) {
        // Look up the row first so we can record composite key and delete all duplicates
        const { data: pendingRow } = await supabaseService
          .from('pending_suggestions')
          .select('fund_id, company_id, column_id, source_service')
          .eq('id', suggestionId)
          .single();
        if (pendingRow) {
          rejectRows.push({ fund_id: fundId, suggestion_id: `${pendingRow.company_id}::${pendingRow.column_id}::service` });
          // Document-originated pending_suggestions (from emit_document_suggestions):
          // also block the document extraction path so it doesn't resurrect after reject
          if (typeof pendingRow.source_service === 'string' && pendingRow.source_service.startsWith('document:')) {
            rejectRows.push({ fund_id: fundId, suggestion_id: `${pendingRow.company_id}::${pendingRow.column_id}::document` });
          }
          await supabaseService.from('pending_suggestions')
            .delete()
            .eq('fund_id', pendingRow.fund_id)
            .eq('company_id', pendingRow.company_id)
            .eq('column_id', pendingRow.column_id);
        } else {
          // Row already gone, just delete by id as fallback
          await supabaseService.from('pending_suggestions').delete().eq('id', suggestionId);
        }
      }
      // Deduplicate rejectRows to avoid "ON CONFLICT DO UPDATE cannot affect row a second time"
      const uniqueRejectRows = [...new Map(rejectRows.map(r => [`${r.fund_id}::${r.suggestion_id}`, r])).values()];
      const { error: insertError } = await supabaseService
        .from('rejected_suggestions')
        .upsert(uniqueRejectRows, { onConflict: 'fund_id,suggestion_id' });
      if (insertError) {
        console.error('[suggestions] Error persisting rejected suggestion:', { suggestionId, error: insertError.message });
        return NextResponse.json(
          { error: 'Failed to save rejected suggestion' },
          { status: 500 }
        );
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
        // Validate company exists before applying
        const { data: svcCompanyRow, error: svcCompanyErr } = await supabaseService
          .from('companies')
          .select('id')
          .eq('id', pendingRow.company_id)
          .single();
        if (svcCompanyErr || !svcCompanyRow) {
          console.warn('[suggestions] Service accept: company_id not found', { suggestionId, company_id: pendingRow.company_id });
          // Clean up the orphaned pending suggestion
          await supabaseService.from('pending_suggestions').delete().eq('id', suggestionId);
          return NextResponse.json(
            { error: 'Company not found. The suggestion may refer to a company no longer in the matrix.' },
            { status: 404 }
          );
        }
        let rawSuggested = pendingRow.suggested_value;
        // JSONB may return a JSON-encoded string — parse it
        if (typeof rawSuggested === 'string') {
          try { rawSuggested = JSON.parse(rawSuggested); } catch { /* keep as-is */ }
        }
        const newValue = typeof rawSuggested === 'object' && rawSuggested !== null && 'value' in rawSuggested
          ? (rawSuggested as { value: unknown }).value
          : rawSuggested;
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
        // Persist to accepted_suggestions so the sparkle doesn't reappear.
        // Record the raw ID + source-aware composite key (companyId::columnId::service)
        // so that dedup ID swaps on next GET can't resurrect this suggestion.
        // For document-originated pending_suggestions, also block the document extraction
        // path so the same metric doesn't resurrect via processed_documents parsing.
        if (fundId) {
          const sourceAwareKey = `${pendingRow.company_id}::${pendingRow.column_id}::service`;
          const rows = [
            { fund_id: fundId, suggestion_id: String(suggestionId) },
            { fund_id: fundId, suggestion_id: sourceAwareKey },
          ];
          if (typeof pendingRow.source_service === 'string' && pendingRow.source_service.startsWith('document:')) {
            rows.push({ fund_id: fundId, suggestion_id: `${pendingRow.company_id}::${pendingRow.column_id}::document` });
          }
          const { error: acceptErr } = await supabaseService
            .from('accepted_suggestions')
            .upsert(rows, { onConflict: 'fund_id,suggestion_id' });
          if (acceptErr) {
            console.error('[suggestions] Error persisting accepted service suggestion:', acceptErr);
          }
        }
        // Delete ALL pending_suggestions for this company+column (not just this row),
        // because duplicate rows with different UUIDs would reappear on next GET.
        await supabaseService.from('pending_suggestions')
          .delete()
          .eq('fund_id', fundId)
          .eq('company_id', pendingRow.company_id)
          .eq('column_id', pendingRow.column_id);
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
        if (!docFundId) {
          // Cell was applied but we can't record acceptance — roll back is impractical, so return error
          return NextResponse.json(
            { error: 'fundId required to persist accepted suggestion' },
            { status: 400 }
          );
        }
        {
          // Record the raw ID + source-aware composite key (companyId::columnId::document)
          // so that dedup ID swaps on next GET can't resurrect this suggestion,
          // but service suggestions for the same cell are NOT blocked.
          const sourceAwareKey = `${applyPayload.company_id}::${applyPayload.column_id}::document`;
          const rows = [
            { fund_id: docFundId, suggestion_id: String(suggestionId) },
            { fund_id: docFundId, suggestion_id: sourceAwareKey },
          ];
          const { error: acceptErr } = await supabaseService
            .from('accepted_suggestions')
            .upsert(rows, { onConflict: 'fund_id,suggestion_id' });
          if (acceptErr) {
            console.error('[suggestions] FATAL: accepted_suggestions upsert failed:', acceptErr.message);
            return NextResponse.json(
              { error: 'Cell updated but failed to record acceptance — suggestion may reappear' },
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

    return NextResponse.json(
      { success: false, error: `Unknown action: ${action}` },
      { status: 400 }
    );
  } catch (error) {
    console.error('[suggestions] POST error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
