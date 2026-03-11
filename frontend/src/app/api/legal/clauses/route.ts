/**
 * GET /api/legal/clauses?fundId=X&companyId=Y
 *
 * Reads from two sources and merges into one grid:
 *   1. document_clauses — accepted clauses (source of truth)
 *   2. pending_suggestions (column_id LIKE 'legal:%') — clauses awaiting review
 *
 * Each clause → one grid row with cells matching LEGAL_COLUMNS.
 * fundId is optional — when absent, returns all clauses for the user/org.
 */

import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

const CLAUSE_FIELDS = [
  'documentName', 'contractType', 'party', 'counterparty', 'status',
  'effectiveDate', 'expiryDate', 'totalValue', 'annualValue',
  'keyTerms', 'flags', 'obligations', 'nextDeadline', 'reasoning',
] as const;

type CellMap = Record<string, { value: unknown; source: string; metadata?: Record<string, unknown> }>;

function buildCells(values: Record<string, unknown>, cellMeta: Record<string, unknown>): CellMap {
  const cells: CellMap = {};
  for (const field of CLAUSE_FIELDS) {
    const val = values[field];
    if (val !== undefined && val !== null && val !== '') {
      cells[field] = { value: val, source: 'document', metadata: cellMeta };
    }
  }
  return cells;
}

export async function GET(request: NextRequest) {
  try {
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 503 });
    }

    const searchParams = request.nextUrl.searchParams;
    const fundId = searchParams.get('fundId');
    const companyId = searchParams.get('companyId');

    // ── 1. Accepted clauses from document_clauses ──
    let acceptedQuery = supabaseService
      .from('document_clauses')
      .select('*')
      .order('created_at', { ascending: true });
    if (fundId) acceptedQuery = acceptedQuery.eq('fund_id', fundId);
    if (companyId) acceptedQuery = acceptedQuery.eq('company_id', companyId);

    // ── 2. Pending clause suggestions ──
    let pendingQuery = supabaseService
      .from('pending_suggestions')
      .select('id, company_id, column_id, suggested_value, source_service, reasoning, metadata, created_at')
      .like('column_id', 'legal:%')
      .order('created_at', { ascending: true });
    if (fundId) pendingQuery = pendingQuery.eq('fund_id', fundId);
    if (companyId) pendingQuery = pendingQuery.eq('company_id', companyId);

    // ── 3. Rejected set (to filter pending) ──
    let rejectedQuery = supabaseService.from('rejected_suggestions').select('suggestion_id');
    if (fundId) rejectedQuery = rejectedQuery.eq('fund_id', fundId);

    const [acceptedResult, pendingResult, rejectedResult] = await Promise.all([
      acceptedQuery.then(r => r).catch(() => ({ data: null, error: { message: 'table missing' } })),
      pendingQuery,
      rejectedQuery,
    ]);

    const rejectedSet = new Set<string>(
      (rejectedResult.data ?? []).map((r: { suggestion_id: string }) => r.suggestion_id)
    );

    const rows: Array<Record<string, unknown>> = [];
    const seenClauseKeys = new Set<string>();

    // ── Map accepted clauses → grid rows ──
    const acceptedClauses = (acceptedResult.data ?? []) as Array<Record<string, unknown>>;
    for (const c of acceptedClauses) {
      const clauseKey = `${c.company_id}::${c.clause_id}::${c.document_id ?? 'none'}`;
      seenClauseKeys.add(clauseKey);

      const values: Record<string, unknown> = {
        documentName: c.document_name,
        contractType: c.clause_type ?? c.contract_type,
        party: c.party,
        counterparty: c.counterparty,
        status: c.status ?? 'active',
        effectiveDate: c.effective_date,
        expiryDate: c.expiry_date ?? c.obligation_deadline,
        totalValue: c.total_value,
        annualValue: c.annual_value,
        keyTerms: c.key_terms ?? c.title,
        flags: Array.isArray(c.flags) ? (c.flags as string[]).join(', ') : '',
        obligations: c.obligation_desc,
        nextDeadline: c.obligation_deadline,
        reasoning: c.reasoning,
      };

      rows.push({
        id: `legal:${c.clause_id ?? c.id}`,
        companyId: c.company_id,
        cells: buildCells(values, {
          confidence: c.confidence as number ?? 0.8,
          source_service: c.source_service,
          document_id: c.document_id,
          document_name: c.document_name,
          contract_type: c.clause_type ?? c.contract_type,
          flags: c.flags,
        }),
        isAccepted: true,
        confidence: c.confidence ?? 0.8,
        flags: c.flags ?? [],
        createdAt: c.created_at,
      });
    }

    // ── Map pending suggestions → grid rows (skip already-accepted or rejected) ──
    const pendingClauses = (pendingResult.data ?? []) as Array<Record<string, unknown>>;
    for (const row of pendingClauses) {
      const suggestionId = row.id as string;
      const columnId = row.column_id as string;
      const compId = row.company_id as string;

      // Skip rejected
      if (rejectedSet.has(suggestionId) || rejectedSet.has(`${compId}::${columnId}::service`)) continue;

      // Parse suggested_value
      let sv: Record<string, unknown> = {};
      const raw = row.suggested_value;
      if (typeof raw === 'string') {
        try { sv = JSON.parse(raw); } catch { sv = {}; }
      } else if (typeof raw === 'object' && raw !== null) {
        sv = raw as Record<string, unknown>;
      }

      const meta = (row.metadata ?? {}) as Record<string, unknown>;
      const clauseId = (sv.clauseId ?? columnId.replace('legal:', '')) as string;
      const docId = meta.document_id ? String(meta.document_id) : 'none';
      const clauseKey = `${compId}::${clauseId}::${docId}`;

      // Skip if already covered by accepted clauses
      if (seenClauseKeys.has(clauseKey)) continue;
      seenClauseKeys.add(clauseKey);

      rows.push({
        id: columnId,
        companyId: compId,
        cells: buildCells(sv, {
          confidence: meta.confidence as number ?? 0.8,
          source_service: row.source_service,
          document_id: meta.document_id,
          document_name: meta.document_name,
          contract_type: meta.clause_type ?? meta.contract_type,
          flags: meta.flags,
          suggestion_id: suggestionId,
        }),
        isAccepted: false,
        suggestionId,
        sourceService: row.source_service,
        confidence: meta.confidence as number ?? 0.8,
        flags: meta.flags as string[] ?? [],
        createdAt: row.created_at,
      });
    }

    return NextResponse.json({
      rows,
      metadata: {
        dataSource: 'legal',
        fundId: fundId ?? undefined,
        lastUpdated: new Date().toISOString(),
        totalClauses: rows.length,
        acceptedCount: rows.filter((r) => r.isAccepted).length,
        pendingCount: rows.filter((r) => !r.isAccepted).length,
      },
    });
  } catch (error) {
    console.error('Legal clauses route error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch legal clauses', details: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}
