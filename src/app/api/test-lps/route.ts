import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

export async function GET(request: NextRequest) {
  try {
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    // Try to get table information
    const { data: tables, error: tablesError } = await supabaseService
      .from('information_schema.tables')
      .select('table_name')
      .eq('table_schema', 'public')
      .like('table_name', '%lp%');

    // Also try a simple select to see what happens
    const { data: lpsData, error: lpsError, count } = await supabaseService
      .from('lps')
      .select('*', { count: 'exact' });

    // Try to get column information if table exists
    let columns = null;
    if (!lpsError) {
      const { data: cols } = await supabaseService
        .from('information_schema.columns')
        .select('column_name, data_type, is_nullable')
        .eq('table_schema', 'public')
        .eq('table_name', 'lps');
      columns = cols;
    }

    return NextResponse.json({
      tables: tables || [],
      tablesError: tablesError,
      lpsCount: count,
      lpsError: lpsError,
      columns: columns,
      lpsData: lpsData?.slice(0, 5) // First 5 records if any
    });

  } catch (error) {
    console.error('Test error:', error);
    return NextResponse.json({ 
      error: 'Failed to test LPs table',
      details: error instanceof Error ? error.message : error
    }, { status: 500 });
  }
}