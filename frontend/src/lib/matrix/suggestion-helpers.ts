/**
 * Helpers for document-to-matrix suggestions: accept/reject API, payload building,
 * and options for persisting cell edits (sourceDocumentId) so suggestions flow is type-safe and consistent.
 */

/** UI payload when accepting a suggestion (rowId, columnId, suggestedValue, sourceDocumentId). */
export type SuggestionAcceptPayload = {
  rowId: string;
  columnId: string;
  suggestedValue: unknown;
  sourceDocumentId?: string | number;
};

/** Body shape for POST /api/matrix/suggestions when action === 'accept'. */
export type SuggestionApplyPayloadApi = {
  company_id: string;
  column_id: string;
  new_value: unknown;
  fund_id?: string;
  source_document_id?: string | number;
  data_source?: 'document' | 'service';
};

/** Options passed to onCellEdit when persisting a suggestion (portfolio expects sourceDocumentId). */
export type CellEditOptionsFromSuggestion = {
  sourceDocumentId?: string | number;
  data_source?: 'document';
  metadata?: { sourceDocumentId?: string | number };
};

/**
 * Build the API applyPayload from UI payload and fundId (for POST /api/matrix/suggestions accept).
 * Use companyIdOverride when the row's real company id differs from rowId (e.g. matrix row id vs company id).
 */
export function buildApplyPayloadFromSuggestion(
  payload: SuggestionAcceptPayload,
  fundId: string,
  companyIdOverride?: string,
  dataSource?: 'document' | 'service'
): SuggestionApplyPayloadApi {
  return {
    company_id: companyIdOverride ?? payload.rowId,
    column_id: payload.columnId,
    new_value: payload.suggestedValue,
    fund_id: fundId,
    source_document_id: payload.sourceDocumentId ?? undefined,
    data_source: dataSource ?? (payload.sourceDocumentId ? 'document' : undefined),
  };
}

/**
 * Build the 4th argument for onCellEdit when the edit comes from a suggestion,
 * so the portfolio (or other consumer) can persist source_document_id and data_source.
 */
export function buildCellEditOptionsFromSuggestion(
  sourceDocumentId?: string | number
): CellEditOptionsFromSuggestion | undefined {
  if (sourceDocumentId == null) return undefined;
  return {
    sourceDocumentId,
    data_source: 'document',
    metadata: { sourceDocumentId },
  };
}

/**
 * Add a service suggestion (valuation, PWERM, etc.) to pending_suggestions.
 * Result appears in the unified suggestions feed; user accepts/rejects via wrapper.
 */
export async function addServiceSuggestion(opts: {
  fundId: string;
  company_id: string;
  column_id: string;
  suggested_value: unknown;
  source_service: string;
  reasoning?: string;
  metadata?: Record<string, unknown>;
}): Promise<{ success: boolean; suggestionId?: string; error?: string }> {
  try {
    const res = await fetch('/api/matrix/suggestions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: 'add',
        fundId: opts.fundId,
        company_id: opts.company_id,
        column_id: opts.column_id,
        suggested_value: opts.suggested_value,
        source_service: opts.source_service,
        reasoning: opts.reasoning,
        metadata: opts.metadata,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      return { success: false, error: (data as { error?: string }).error ?? 'Failed to add suggestion' };
    }
    return { success: true, suggestionId: (data as { suggestionId?: string }).suggestionId };
  } catch (e) {
    return {
      success: false,
      error: e instanceof Error ? e.message : 'Unknown error',
    };
  }
}

/**
 * Reject a suggestion: POST /api/matrix/suggestions with action 'reject'.
 * Persists suggestion_id in rejected_suggestions for the fund so GET filters it out.
 * Pass companyId + columnId so the backend can also record the composite key
 * (companyId::columnId) — this survives dedup ID swaps on subsequent GETs.
 */
export async function rejectSuggestion(
  suggestionId: string,
  fundId: string,
  context?: { companyId?: string; columnId?: string }
): Promise<{ success: boolean; error?: string }> {
  try {
    const body: Record<string, unknown> = {
      suggestionId: String(suggestionId),
      action: 'reject',
      fundId,
    };
    if (context?.companyId && context?.columnId) {
      body.applyPayload = {
        company_id: context.companyId,
        column_id: context.columnId,
      };
    }
    const res = await fetch('/api/matrix/suggestions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      return { success: false, error: (data as { error?: string }).error ?? 'Failed to reject suggestion' };
    }
    return { success: true };
  } catch (e) {
    return {
      success: false,
      error: e instanceof Error ? e.message : 'Unknown error',
    };
  }
}

/**
 * Accept a suggestion via API: POST /api/matrix/suggestions with action 'accept'.
 * - Document: pass applyPayload; server applies via POST /api/matrix/cells.
 * - Service (UUID): pass fundId only; server looks up pending_suggestions and applies.
 */
export async function acceptSuggestionViaApi(
  suggestionId: string,
  applyPayloadOrFundId: SuggestionApplyPayloadApi | string,
  fundIdParam?: string
): Promise<{ success: boolean; applied?: boolean; error?: string }> {
  const idStr = String(suggestionId);
  const isService = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(idStr);
  const fundId = typeof applyPayloadOrFundId === 'string' ? applyPayloadOrFundId : (applyPayloadOrFundId.fund_id ?? fundIdParam);
  const body: Record<string, unknown> = {
    suggestionId: idStr,
    action: 'accept',
    fundId: fundId ?? undefined,
  };
  if (!isService && typeof applyPayloadOrFundId === 'object') {
    body.applyPayload = {
      company_id: applyPayloadOrFundId.company_id,
      column_id: applyPayloadOrFundId.column_id,
      new_value: applyPayloadOrFundId.new_value,
      fund_id: applyPayloadOrFundId.fund_id ?? null,
      source_document_id: applyPayloadOrFundId.source_document_id ?? null,
      data_source: applyPayloadOrFundId.data_source ?? undefined,
    };
  }
  try {
    const res = await fetch('/api/matrix/suggestions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      return { success: false, error: (data as { error?: string }).error ?? 'Failed to accept suggestion' };
    }
    return { success: true, applied: (data as { applied?: boolean }).applied };
  } catch (e) {
    return {
      success: false,
      error: e instanceof Error ? e.message : 'Unknown error',
    };
  }
}
