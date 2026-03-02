import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

/**
 * GET /api/health/db
 * Diagnostic endpoint to check database connectivity and table existence
 */
export async function GET(request: NextRequest) {
  const checks: Record<string, any> = {
    supabaseServiceInitialized: !!supabaseService,
    envVars: {
      hasUrl: !!process.env.NEXT_PUBLIC_SUPABASE_URL,
      hasServiceKey: !!process.env.SUPABASE_SERVICE_ROLE_KEY,
    },
    tables: {},
    errors: [],
  };

  if (!supabaseService) {
    return NextResponse.json({
      ...checks,
      error: 'Supabase service not initialized',
    }, { status: 503 });
  }

  // Check if tables exist
  const tablesToCheck = ['funds', 'companies', 'matrix_columns', 'matrix_edits'];
  
  for (const table of tablesToCheck) {
    try {
      // Try a simple SELECT query to check if table exists
      const { data, error } = await supabaseService
        .from(table)
        .select('*')
        .limit(1);
      
      if (error) {
        if (error.code === '42P01') {
          checks.tables[table] = { exists: false, error: 'Table does not exist' };
        } else if (error.code === '42501') {
          checks.tables[table] = { exists: true, error: 'Permission denied (RLS blocking?)' };
        } else {
          checks.tables[table] = { exists: true, error: error.message };
        }
        checks.errors.push({ table, error: error.message, code: error.code });
      } else {
        checks.tables[table] = { exists: true, rowCount: data?.length || 0 };
      }
    } catch (err) {
      checks.tables[table] = { exists: false, error: err instanceof Error ? err.message : String(err) };
      checks.errors.push({ table, error: err instanceof Error ? err.message : String(err) });
    }
  }

  // Try to create a test fund to check INSERT permissions
  try {
    const testFund = {
      name: `TEST_FUND_${Date.now()}`,
      fund_size_usd: 1000000,
      target_net_multiple_bps: 30000,
      vintage_year: new Date().getFullYear(),
      fund_type: 'venture',
      status: 'fundraising'
    };
    
    const { data, error } = await supabaseService
      .from('funds')
      .insert(testFund)
      .select()
      .single();
    
    if (error) {
      checks.insertTest = { success: false, error: error.message, code: error.code };
    } else {
      checks.insertTest = { success: true, testId: data.id };
      // Clean up test fund
      await supabaseService.from('funds').delete().eq('id', data.id);
    }
  } catch (err) {
    checks.insertTest = { success: false, error: err instanceof Error ? err.message : String(err) };
  }

  const hasErrors = checks.errors.length > 0 || !checks.insertTest?.success;
  
  return NextResponse.json(checks, {
    status: hasErrors ? 500 : 200,
  });
}
