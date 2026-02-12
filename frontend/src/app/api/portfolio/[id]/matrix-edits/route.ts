import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

/**
 * GET /api/portfolio/[id]/matrix-edits
 * Fetch matrix_edits audit log for a fund (service runs, manual edits, etc.)
 * Used for citations, service logs, and auditing decisions.
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: fundId } = await params;
    const { searchParams } = new URL(request.url);
    const limit = Math.min(parseInt(searchParams.get('limit') || '100', 10), 500);
    const source = searchParams.get('source'); // 'service' | 'manual' | 'all'
    const companyId = searchParams.get('companyId');

    if (!fundId?.trim()) {
      return NextResponse.json({ error: 'Fund ID is required' }, { status: 400 });
    }

    if (!supabaseService) {
      return NextResponse.json(
        { error: 'Supabase service not configured' },
        { status: 500 }
      );
    }

    let query = supabaseService
      .from('matrix_edits')
      .select('id, company_id, column_id, old_value, new_value, edited_by, edited_at, data_source, fund_id, metadata')
      .eq('fund_id', fundId)
      .order('edited_at', { ascending: false })
      .limit(limit);

    if (source && source !== 'all') {
      query = query.eq('data_source', source);
    }
    if (companyId) {
      query = query.eq('company_id', companyId);
    }

    const { data: edits, error } = await query;

    if (error) {
      console.error('Error fetching matrix_edits:', {
        error,
        message: error.message,
        details: error.details,
        hint: error.hint,
        code: error.code,
        fundId,
      });
      
      // Handle specific error cases gracefully
      // 42P01 = table doesn't exist (migration not run)
      // 42501 = permission denied (RLS blocking)
      // 42P02 = column doesn't exist (schema mismatch)
      if (error.code === '42P01' || error.code === '42501' || error.code === '42P02') {
        // Return empty array instead of 500 - UI can still function
        console.warn(`matrix_edits query failed (${error.code}): ${error.message}. Returning empty edits.`);
        return NextResponse.json({ edits: [] });
      }
      
      // For other errors, still return 500 but with better diagnostics
      return NextResponse.json(
        { 
          error: 'Failed to fetch audit log', 
          details: error.message,
          code: error.code,
          hint: error.hint,
        },
        { status: 500 }
      );
    }

    // Optionally join company names for display
    // If companies fetch fails, fall back to empty companyNames - don't fail the whole request
    const companyIds = [...new Set((edits || []).map((e: any) => e.company_id).filter(Boolean))];
    let companyNames: Record<string, string> = {};
    if (companyIds.length > 0) {
      try {
        const { data: companies, error: companiesError } = await supabaseService
          .from('companies')
          .select('id, name')
          .in('id', companyIds);
        
        if (companiesError) {
          // Log but don't fail - we can still return edits without company names
          console.error('Error fetching company names for matrix-edits:', {
            error: companiesError,
            message: companiesError.message,
            details: companiesError.details,
            hint: companiesError.hint,
            code: companiesError.code,
            companyIds,
          });
          // Fall back to empty companyNames - edits will still be returned with companyId
        } else {
          (companies || []).forEach((c: any) => {
            companyNames[c.id] = c.name || c.id;
          });
        }
      } catch (err) {
        // Catch any unexpected errors in the companies fetch
        console.error('Unexpected error fetching company names:', err);
        // Continue with empty companyNames
      }
    }

    const items = (edits || []).map((e: any) => ({
      id: e.id,
      companyId: e.company_id,
      companyName: companyNames[e.company_id] || e.company_id,
      columnId: e.column_id,
      oldValue: e.old_value,
      newValue: e.new_value,
      editedBy: e.edited_by,
      editedAt: e.edited_at,
      dataSource: e.data_source,
      metadata: e.metadata || {},
    }));

    return NextResponse.json({ edits: items });
  } catch (err) {
    console.error('matrix-edits API error:', err);
    return NextResponse.json(
      { error: 'Internal server error', details: err instanceof Error ? err.message : String(err) },
      { status: 500 }
    );
  }
}
