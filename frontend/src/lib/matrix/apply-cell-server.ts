/**
 * Server-only: apply a matrix cell update (companies + matrix_edits).
 * Used by POST /api/matrix/cells and by accept flow in /api/matrix/suggestions
 * so we never rely on server-to-self HTTP.
 */

import { supabaseService } from '@/lib/supabase';
import { parseCurrencyInput } from '@/lib/matrix/cell-formatters';

export type ApplyCellInput = {
  company_id: string;
  column_id: string;
  new_value: unknown;
  old_value?: unknown;
  fund_id?: string | null;
  user_id?: string | null;
  data_source?: string;
  metadata?: Record<string, unknown>;
  source_document_id?: string | number | null;
};

export type ApplyCellResult =
  | { success: true; company: unknown }
  | { success: false; error: string; status: number; code?: string };

const fieldMap: Record<string, string> = {
  company: 'name',
  companyName: 'name',
  name: 'name',
  website: 'website',
  sector: 'sector',
  category: 'category',
  businessModel: 'business_model',
  revenueModel: 'revenue_model',
  kpiFramework: 'kpi_framework',
  stage: 'funnel_status',
  funnelStatus: 'funnel_status',
  arr: 'current_arr_usd',
  currentArr: 'current_arr_usd',
  mrr: 'current_mrr_usd',
  currentMrr: 'current_mrr_usd',
  revenueGrowthMonthly: 'revenue_growth_monthly_pct',
  revenueGrowthAnnual: 'revenue_growth_annual_pct',
  burnRate: 'burn_rate_monthly_usd',
  runway: 'runway_months',
  runwayMonths: 'runway_months',
  grossMargin: 'gross_margin',
  cashInBank: 'cash_in_bank_usd',
  cash: 'cash_in_bank_usd',
  invested: 'total_invested_usd',
  totalInvested: 'total_invested_usd',
  investmentAmount: 'total_invested_usd',
  ownership: 'ownership_percentage',
  ownershipPercentage: 'ownership_percentage',
  firstInvestmentDate: 'first_investment_date',
  investmentDate: 'first_investment_date',
  date_announced: 'first_investment_date',
  dateAnnounced: 'first_investment_date',
  latestInvestmentDate: 'latest_investment_date',
  valuation: 'current_valuation_usd',
  currentValuation: 'current_valuation_usd',
  exitDate: 'exit_date',
  exitType: 'exit_type',
  exitValue: 'exit_value_usd',
  exitMultiple: 'exit_multiple',
  customerSegmentEnterprise: 'customer_segment_enterprise_pct',
  customerSegmentMidmarket: 'customer_segment_midmarket_pct',
  customerSegmentSme: 'customer_segment_sme_pct',
  investmentLead: 'investment_lead',
  lastContactedDate: 'last_contacted_date',
  aiFirst: 'ai_first',
  hasPwermModel: 'has_pwerm_model',
  fund: 'fund_id',
  fundId: 'fund_id',
  fund_id: 'fund_id',
};

const EXTRA_DATA_KEYS: Record<string, string> = {
  optionPool: 'option_pool_bps',
  option_pool: 'option_pool_bps',
  latestUpdate: 'latest_update',
  latest_update: 'latest_update',
  latestUpdateDate: 'latest_update_date',
  latest_update_date: 'latest_update_date',
  productUpdates: 'product_updates',
  product_updates: 'product_updates',
  documents: 'documents',
  headcount: 'headcount',
  tam: 'tam_usd',
  tamUsd: 'tam_usd',
  tam_usd: 'tam_usd',
  sam: 'sam_usd',
  samUsd: 'sam_usd',
  sam_usd: 'sam_usd',
  som: 'som_usd',
  somUsd: 'som_usd',
  som_usd: 'som_usd',
};

export async function applyCellUpdate(input: ApplyCellInput): Promise<ApplyCellResult> {
  const {
    company_id,
    column_id,
    new_value,
    old_value,
    fund_id,
    user_id,
    data_source,
    metadata,
    source_document_id: inputSourceDocId,
  } = input;

  const sourceDocumentId =
    inputSourceDocId ??
    (metadata && metadata.sourceDocumentId != null ? metadata.sourceDocumentId : null);

  if (!company_id || !column_id || new_value === undefined) {
    return { success: false, error: 'Missing required fields: company_id, column_id, new_value', status: 400 };
  }

  if (!supabaseService) {
    return { success: false, error: 'Supabase service not configured', status: 500 };
  }

  const { data: companyExists, error: companyFetchErr } = await supabaseService
    .from('companies')
    .select('id')
    .eq('id', company_id)
    .single();
  if (companyFetchErr || !companyExists) {
    console.warn('[apply-cell] Company not found', { company_id, error: companyFetchErr?.message });
    return { success: false, error: 'Company not found', status: 404, code: 'COMPANY_NOT_FOUND' };
  }

  const extraDataKey = EXTRA_DATA_KEYS[column_id];
  if (extraDataKey) {
    const raw: unknown =
      new_value != null && typeof new_value === 'object' && !Array.isArray(new_value)
        ? (new_value as Record<string, unknown>).value ??
          (new_value as Record<string, unknown>).displayValue ??
          (new_value as Record<string, unknown>).display_value ??
          ''
        : new_value;
    let value: string | number | unknown[] | null = null;
    if (extraDataKey === 'documents') {
      const docs = metadata?.documents;
      if (Array.isArray(docs)) value = docs;
      else if (Array.isArray(new_value)) value = new_value;
      else value = null;
    } else if (extraDataKey === 'option_pool_bps') {
      const n = typeof raw === 'number' ? raw : parseFloat(String(raw ?? ''));
      value = Number.isFinite(n) ? Math.round(n) : null;
    } else if (['headcount', 'tam_usd', 'sam_usd', 'som_usd'].includes(extraDataKey)) {
      const n = typeof raw === 'number' ? raw : parseFloat(String(raw ?? '').replace(/[$,]/g, ''));
      value = Number.isFinite(n) ? n : null;
    } else {
      value = raw != null ? String(raw).trim() : null;
      if (value === '') value = null;
    }
    const { data: company, error: fetchErr } = await supabaseService
      .from('companies')
      .select('extra_data')
      .eq('id', company_id)
      .single();
    if (fetchErr || !company) {
      return { success: false, error: 'Failed to load company', status: 500 };
    }
    const extra: Record<string, string | number | unknown[]> =
      company.extra_data && typeof company.extra_data === 'object' ? { ...company.extra_data } : {};
    if (value === null) delete extra[extraDataKey];
    else extra[extraDataKey] = value as string | number | unknown[];
    const { data: updatedCompany, error: updateError } = await supabaseService
      .from('companies')
      .update({ extra_data: extra, updated_at: new Date().toISOString() })
      .eq('id', company_id)
      .select()
      .single();
    if (updateError) {
      return { success: false, error: 'Failed to update company', status: 500 };
    }
    try {
      await supabaseService.from('matrix_edits').insert({
        company_id,
        column_id,
        old_value: old_value !== undefined ? old_value : null,
        new_value: value,
        edited_by: user_id || 'system',
        edited_at: new Date().toISOString(),
        data_source: data_source === 'service' ? 'service' : data_source || 'manual',
        fund_id: fund_id || null,
        ...(sourceDocumentId != null ? { source_document_id: sourceDocumentId } : {}),
        ...(metadata && typeof metadata === 'object' ? { metadata } : {}),
      });
    } catch (_) {}
    return { success: true, company: updatedCompany };
  }

  const dbField = fieldMap[column_id] || column_id;
  const COLUMN_TO_DOCUMENT_ID_FIELD: Record<string, string> = {
    arr: 'revenue_document_id',
    currentArr: 'revenue_document_id',
    burnRate: 'burn_rate_document_id',
    runway: 'runway_document_id',
    runwayMonths: 'runway_document_id',
    cashInBank: 'cash_document_id',
    cash: 'cash_document_id',
    grossMargin: 'gross_margin_document_id',
  };
  const documentIdField = COLUMN_TO_DOCUMENT_ID_FIELD[column_id];

  const raw: unknown =
    new_value != null && typeof new_value === 'object' && !Array.isArray(new_value)
      ? (new_value as Record<string, unknown>).value ??
        (new_value as Record<string, unknown>).displayValue ??
        (new_value as Record<string, unknown>).display_value ??
        ''
      : new_value;

  const currencyFields = [
    'arr', 'currentArr', 'mrr', 'currentMrr', 'burnRate', 'cashInBank', 'cash',
    'invested', 'totalInvested', 'investmentAmount', 'valuation', 'currentValuation', 'exitValue',
  ];
  const numberFields = [
    'runway', 'runwayMonths', 'ownership', 'ownershipPercentage', 'exitMultiple',
    'revenueGrowthMonthly', 'revenueGrowthAnnual', 'customerSegmentEnterprise',
    'customerSegmentMidmarket', 'customerSegmentSme',
  ];
  const percentageFields = ['grossMargin', 'ownership', 'ownershipPercentage'];
  const booleanFields = ['aiFirst', 'hasPwermModel'];
  const dateFields = [
    'firstInvestmentDate', 'investmentDate', 'date_announced', 'dateAnnounced',
    'latestInvestmentDate', 'exitDate', 'lastContactedDate',
  ];
  const stringFields = [
    'company', 'companyName', 'name', 'website', 'sector', 'category', 'businessModel',
    'revenueModel', 'kpiFramework', 'stage', 'funnelStatus', 'investmentLead', 'lastContactedDate',
  ];

  let dbValue: string | number | boolean | null;
  if (currencyFields.includes(column_id)) {
    dbValue = parseCurrencyInput(
      raw === null || raw === undefined ? undefined : typeof raw === 'string' || typeof raw === 'number' ? raw : String(raw)
    );
  } else if (numberFields.includes(column_id)) {
    dbValue = typeof raw === 'string' ? parseFloat(raw) || 0 : parseFloat(raw as string) || 0;
  } else if (percentageFields.includes(column_id)) {
    let n = typeof raw === 'number' ? raw : parseFloat(raw as string);
    if (Number.isNaN(n)) n = 0;
    if (n > 1 && column_id === 'grossMargin') n = n / 100;
    dbValue = n;
  } else if (booleanFields.includes(column_id)) {
    dbValue = typeof raw === 'boolean' ? raw : raw === 'true' || raw === true || raw === 1;
  } else if (dateFields.includes(column_id)) {
    dbValue = raw != null ? String(raw) : null;
  } else if (column_id === 'runwayMonths' || column_id === 'runway') {
    dbValue = typeof raw === 'number' ? Math.floor(raw) : parseInt(String(raw), 10) || 0;
  } else if (dbField === 'fund_id') {
    const s = raw != null ? String(raw).trim() : '';
    const uuidMatch = s.match(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);
    dbValue = uuidMatch ? s : null;
  } else if (stringFields.includes(column_id) || dbField === column_id) {
    dbValue = raw != null ? String(raw).trim() : null;
    if (dbValue === '') dbValue = null;
    if (dbField === 'name' && dbValue != null && dbValue !== '') {
      const strVal = String(dbValue);
      const looksLikeId =
        /^company[a-z0-9]+$/i.test(strVal) ||
        /^[a-f0-9-]{36}$/i.test(strVal) ||
        /^[0-9a-f]{8}-[0-9a-f]{4}/i.test(strVal);
      if (looksLikeId) {
        return { success: false, error: 'Company name cannot be an ID', status: 400 };
      }
    }
  } else {
    dbValue =
      raw != null && typeof raw !== 'object' ? (raw as string | number) : raw != null ? String(raw) : null;
  }

  const updatePayload: Record<string, unknown> = {
    [dbField]: dbValue,
    updated_at: new Date().toISOString(),
  };
  if (documentIdField && sourceDocumentId != null) {
    updatePayload[documentIdField] =
      typeof sourceDocumentId === 'number'
        ? sourceDocumentId
        : typeof sourceDocumentId === 'string' && /^\d+$/.test(sourceDocumentId)
          ? parseInt(sourceDocumentId, 10)
          : sourceDocumentId;
  }

  const { data: updatedCompany, error: updateError } = await supabaseService
    .from('companies')
    .update(updatePayload)
    .eq('id', company_id)
    .select()
    .single();

  if (updateError) {
    const errCode = (updateError as { code?: string }).code ?? '';
    const isNoRow = errCode === 'PGRST116';
    const isColumnMissing = errCode === 'PGRST204' || errCode === '42703';
    console.warn('[apply-cell] Update failed', {
      company_id,
      column_id,
      dbField,
      code: errCode,
      message: (updateError as { message?: string }).message,
    });
    if (isNoRow) {
      return { success: false, error: 'Company not found', status: 404, code: 'COMPANY_NOT_FOUND' };
    }
    // Column doesn't exist in main table — fall back to extra_data
    if (isColumnMissing) {
      console.info('[apply-cell] Column missing in DB, falling back to extra_data', { dbField, column_id });
      const { data: company, error: fetchErr } = await supabaseService
        .from('companies')
        .select('extra_data')
        .eq('id', company_id)
        .single();
      if (fetchErr || !company) {
        return { success: false, error: 'Failed to load company for extra_data fallback', status: 500 };
      }
      const extra: Record<string, unknown> =
        company.extra_data && typeof company.extra_data === 'object' ? { ...company.extra_data } : {};
      extra[column_id] = dbValue;
      const { data: updatedViaExtra, error: extraUpdateErr } = await supabaseService
        .from('companies')
        .update({ extra_data: extra, updated_at: new Date().toISOString() })
        .eq('id', company_id)
        .select()
        .single();
      if (extraUpdateErr) {
        return { success: false, error: 'Failed to update company via extra_data', status: 500 };
      }
      try {
        await supabaseService.from('matrix_edits').insert({
          company_id,
          column_id,
          old_value: old_value !== undefined ? String(old_value) : null,
          new_value: dbValue != null ? String(dbValue) : null,
          edited_by: user_id || 'system',
          edited_at: new Date().toISOString(),
          data_source: data_source === 'service' ? 'service' : data_source || 'manual',
          fund_id: fund_id || null,
          ...(sourceDocumentId != null ? { source_document_id: sourceDocumentId } : {}),
          ...(metadata && typeof metadata === 'object' ? { metadata } : {}),
        });
      } catch (_) {}
      return { success: true, company: updatedViaExtra };
    }
    return { success: false, error: 'Failed to update company', status: 500 };
  }

  const editDataSource = data_source === 'service' ? 'service' : data_source || 'manual';
  const editMetadata = metadata && typeof metadata === 'object' ? metadata : null;
  try {
    await supabaseService.from('matrix_edits').insert({
      company_id,
      column_id,
      old_value: old_value !== undefined ? String(old_value) : null,
      new_value: dbValue != null ? String(dbValue) : null,
      edited_by: user_id || 'system',
      edited_at: new Date().toISOString(),
      data_source: editDataSource,
      fund_id: fund_id || null,
      ...(sourceDocumentId != null ? { source_document_id: sourceDocumentId } : {}),
      ...(editMetadata ? { metadata: editMetadata } : {}),
    });
  } catch (_) {}

  return { success: true, company: updatedCompany };
}
