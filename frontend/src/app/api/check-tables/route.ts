import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

export async function GET(request: NextRequest) {
  try {
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    // Try different approaches to check for tables
    const results: any = {};

    // 1. Try to select from lps directly
    try {
      const { data, error, count } = await supabaseService
        .from('lps')
        .select('*', { count: 'exact', head: true });
      
      results.lps_select = {
        success: !error,
        count: count,
        error: error
      };
    } catch (e) {
      results.lps_select = { error: e };
    }

    // 2. Try to get one record
    try {
      const { data, error } = await supabaseService
        .from('lps')
        .select('*')
        .limit(1);
      
      results.lps_record = {
        success: !error,
        hasData: data && data.length > 0,
        record: data?.[0],
        error: error
      };
    } catch (e) {
      results.lps_record = { error: e };
    }

    // 3. Try to insert a test record
    try {
      const testRecord = {
        name: 'Test LP Check',
        type: 'individual',
        country: 'Test'
      };
      
      const { data, error } = await supabaseService
        .from('lps')
        .insert([testRecord])
        .select();
      
      results.lps_insert = {
        success: !error,
        inserted: data?.[0],
        error: error
      };
      
      // If successful, delete it
      if (data && data[0]) {
        await supabaseService
          .from('lps')
          .delete()
          .eq('id', data[0].id);
      }
    } catch (e) {
      results.lps_insert = { error: e };
    }

    // 4. Check other tables we know exist
    try {
      const { count: companiesCount } = await supabaseService
        .from('companies')
        .select('*', { count: 'exact', head: true });
      
      const { count: documentsCount } = await supabaseService
        .from('documents')
        .select('*', { count: 'exact', head: true });
      
      results.other_tables = {
        companies: companiesCount,
        documents: documentsCount
      };
    } catch (e) {
      results.other_tables = { error: e };
    }

    return NextResponse.json({
      results,
      summary: {
        lps_exists: results.lps_select?.success || results.lps_record?.success,
        can_insert: results.lps_insert?.success
      }
    });

  } catch (error) {
    console.error('Check tables error:', error);
    return NextResponse.json({ 
      error: 'Failed to check tables',
      details: error instanceof Error ? error.message : error
    }, { status: 500 });
  }
}