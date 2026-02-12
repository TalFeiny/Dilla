import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';
import { isDummyMatrixColumn } from '@/lib/matrix/column-helpers';

/**
 * DELETE /api/matrix/columns?fundId=...&columnId=... (or matrixId=...&columnId=...)
 * Delete any column from the matrix. Same idea as delete company (row) but for columns.
 * Persists to Supabase: removes the row from matrix_columns.
 */
export async function DELETE(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const columnId = searchParams.get('columnId');
    const fundId = searchParams.get('fundId');
    const matrixId = searchParams.get('matrixId');

    if (!columnId || (!fundId && !matrixId)) {
      return NextResponse.json(
        { error: 'columnId and (fundId or matrixId) are required' },
        { status: 400 }
      );
    }

    if (!supabaseService) {
      return NextResponse.json(
        { error: 'Supabase service not configured' },
        { status: 500 }
      );
    }

    let query = supabaseService
      .from('matrix_columns')
      .delete()
      .eq('column_id', columnId);

    if (fundId) {
      query = query.eq('fund_id', fundId);
    } else if (matrixId) {
      query = query.eq('matrix_id', matrixId);
    }

    const { error } = await query;

    if (error) {
      console.error('Error deleting matrix column:', error);
      return NextResponse.json(
        { error: 'Failed to delete column' },
        { status: 500 }
      );
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error in DELETE /api/matrix/columns:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

/**
 * GET /api/matrix/columns
 * Get columns for a matrix (by matrixId or fundId).
 * Removes dummy placeholder columns (temp-company remnants) from the DB and never returns them.
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const matrixId = searchParams.get('matrixId');
    const fundId = searchParams.get('fundId');

    if (!supabaseService) {
      console.error('[matrix/columns] Supabase service not initialized. Check NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.');
      return NextResponse.json(
        {
          error: 'Supabase service not configured',
          hint: 'Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env.local',
        },
        { status: 503 }
      );
    }

    if (!matrixId && !fundId) {
      return NextResponse.json(
        { error: 'matrixId or fundId is required' },
        { status: 400 }
      );
    }

    const buildQuery = () => {
      let q = supabaseService!
        .from('matrix_columns')
        .select('*')
        .order('created_at', { ascending: true });
      if (matrixId) q = q.eq('matrix_id', matrixId);
      else if (fundId) q = q.eq('fund_id', fundId);
      return q;
    };

    // Retry once on transient fetch failures (cold-start DNS/network timeouts)
    let data: any;
    let error: any;
    for (let attempt = 0; attempt < 2; attempt++) {
      const result = await buildQuery();
      data = result.data;
      error = result.error;
      if (!error) break;
      const isTransient = !error.code && /fetch failed/i.test(error.details || error.message || '');
      if (!isTransient || attempt === 1) break;
      console.warn('[matrix/columns] Transient fetch failure, retrying...');
      await new Promise(r => setTimeout(r, 500));
    }

    if (error) {
      console.error('[matrix/columns] Supabase error:', error.message, { code: error.code, details: error.details });
      const hint =
        error.code === '42P01'
          ? 'Run migrations: npx supabase db push or apply supabase/migrations manually'
          : error.code === '42501'
            ? 'Check RLS policies or service role key'
            : undefined;
      return NextResponse.json(
        {
          error: 'Failed to fetch columns',
          details: error.message,
          code: error.code,
          hint,
        },
        { status: 500 }
      );
    }

    const rows = (data || []) as { id: string; column_id: string; name: string }[];
    // Filter out dummy columns in response only; do NOT delete from DB on GET
    // (plan: stop deleting columns on GET - it can remove real columns if pattern is too broad)
    const columns = rows.filter(
      (row) => !isDummyMatrixColumn(row.column_id ?? '', row.name ?? '')
    );

    return NextResponse.json({ columns }, {
      headers: {
        // Cache for 60s on client, revalidate in background up to 5 min stale
        'Cache-Control': 'private, max-age=60, stale-while-revalidate=300',
      },
    });
  } catch (error) {
    console.error('Error in GET /api/matrix/columns:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

/**
 * POST /api/matrix/columns
 * Add a new column to the matrix
 * 
 * NOTE: Only persists columns for portfolio mode (fundId) or saved matrix views (matrixId).
 * Query/custom mode columns are ephemeral and not stored in the database.
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const {
      matrixId,
      columnId: bodyColumnId,
      name,
      type,
      service,
      formula,
      createdBy = 'human',
      fundId,
    } = body;

    if (!name || !type) {
      return NextResponse.json(
        { error: 'Missing required fields: name, type' },
        { status: 400 }
      );
    }

    // columnId is optional: allow workflows to pass a stable id, or generate one
    const columnId = (typeof bodyColumnId === 'string' && bodyColumnId.trim())
      ? bodyColumnId.trim()
      : `col-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    
    // Validate column name - reject 'poo' and empty names
    if (!name || name.trim() === '' || name.toLowerCase() === 'poo') {
      return NextResponse.json(
        { error: 'Invalid column name. Column name cannot be empty or "poo".' },
        { status: 400 }
      );
    }

    // Only persist for portfolio mode (fundId) or saved views (matrixId)
    // Query/custom mode columns are ephemeral
    if (!matrixId && !fundId) {
      return NextResponse.json(
        { error: 'Columns can only be persisted for portfolio mode (fundId) or saved matrix views (matrixId). Query/custom mode columns are ephemeral.' },
        { status: 400 }
      );
    }

    if (!supabaseService) {
      return NextResponse.json(
        { error: 'Supabase service not configured' },
        { status: 500 }
      );
    }

    // Check if column already exists
    let existingQuery = supabaseService
      .from('matrix_columns')
      .select('id')
      .eq('column_id', columnId);

    if (matrixId) {
      existingQuery = existingQuery.eq('matrix_id', matrixId);
    } else if (fundId) {
      existingQuery = existingQuery.eq('fund_id', fundId);
    }

    const { data: existing } = await existingQuery.maybeSingle();

    if (existing) {
      return NextResponse.json(
        { error: 'Column already exists' },
        { status: 409 }
      );
    }

    // Insert new column
    const { data, error } = await supabaseService
      .from('matrix_columns')
      .insert({
        matrix_id: matrixId || null,
        column_id: columnId,
        name,
        type,
        service_name: service?.name || null,
        service_type: service?.type || null,
        api_endpoint: service?.apiEndpoint || service?.api_endpoint || null,
        formula: formula || null,
        config: service?.config || null,
        created_by: createdBy,
        fund_id: fundId || null,
      })
      .select()
      .single();

    if (error) {
      console.error('Error creating matrix column:', error);
      console.error('Supabase error details:', JSON.stringify(error, null, 2));
      
      // Check for common issues
      let errorMessage = error.message || 'Failed to create column';
      if (error.code === '42P01') {
        errorMessage = 'Matrix columns table does not exist. Please run database migrations.';
      } else if (error.code === '42501') {
        errorMessage = 'Permission denied. Check RLS policies or service role key.';
      } else if (error.code === '23505') {
        errorMessage = 'A column with this ID already exists.';
      } else if (error.code === '23503') {
        errorMessage = `Foreign key constraint violation. Fund ID ${fundId} may not exist.`;
      } else if (error.code === '23514') {
        errorMessage = 'Check constraint violation. Either matrix_id or fund_id must be provided.';
      }
      
      return NextResponse.json(
        { 
          error: 'Failed to create column',
          details: errorMessage,
          code: error.code,
          hint: error.hint,
          fullError: process.env.NODE_ENV === 'development' ? JSON.stringify(error, null, 2) : undefined
        },
        { status: 500 }
      );
    }

    return NextResponse.json({ column: data });
  } catch (error) {
    console.error('Error in POST /api/matrix/columns:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

