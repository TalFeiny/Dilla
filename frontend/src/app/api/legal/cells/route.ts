/**
 * POST /api/legal/cells
 *
 * Persist a cell edit on a legal clause row.
 * Upserts into document_clauses keyed by (fund_id, clause_id, document_id).
 * company_id is nullable — legal docs don't belong to a company.
 */

import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

// Maps grid column IDs → document_clauses DB columns
const COLUMN_MAP: Record<string, string> = {
  documentName: 'document_name',
  contractType: 'clause_type',
  party: 'party',
  counterparty: 'counterparty',
  status: 'status',
  effectiveDate: 'effective_date',
  expiryDate: 'expiry_date',
  totalValue: 'total_value',
  annualValue: 'annual_value',
  keyTerms: 'title',
  flags: 'flags',
  obligations: 'obligation_desc',
  nextDeadline: 'obligation_deadline',
  reasoning: 'reasoning',
};

export async function POST(request: NextRequest) {
  try {
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase not configured' }, { status: 503 });
    }

    const body = await request.json();
    const { fund_id, clause_id, document_id, column_id, value } = body;

    if (!clause_id || !column_id) {
      return NextResponse.json({ error: 'clause_id and column_id are required' }, { status: 400 });
    }

    const dbColumn = COLUMN_MAP[column_id];
    if (!dbColumn) {
      return NextResponse.json({ error: `Unknown column: ${column_id}` }, { status: 400 });
    }

    // flags is stored as text[] in Postgres
    let dbValue = value;
    if (dbColumn === 'flags' && typeof value === 'string') {
      dbValue = value.split(',').map((f: string) => f.trim()).filter(Boolean);
    }

    // Upsert: update if clause exists, insert if new
    const { error } = await supabaseService
      .from('document_clauses')
      .upsert(
        {
          fund_id: fund_id || null,
          company_id: null,
          clause_id,
          document_id: document_id || null,
          [dbColumn]: dbValue,
          updated_at: new Date().toISOString(),
        },
        { onConflict: 'fund_id,company_id,clause_id,document_id' }
      );

    if (error) {
      console.error('[legal/cells] upsert error:', error);
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json({ success: true });
  } catch (err) {
    console.error('[legal/cells] error:', err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Unknown error' },
      { status: 500 }
    );
  }
}
