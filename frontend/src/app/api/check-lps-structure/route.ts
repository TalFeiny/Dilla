import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

export async function GET(request: NextRequest) {
  try {
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    // Try different table names that might exist
    const tableNames = ['lps', 'lp', 'limited_partners', 'investors', 'LPs', 'LP'];
    const results: any = {};

    for (const tableName of tableNames) {
      try {
        // Try to select with limit 0 to just check structure
        const { data, error } = await supabaseService
          .from(tableName)
          .select('*')
          .limit(1);
        
        if (!error) {
          results[tableName] = {
            exists: true,
            sampleData: data?.[0] || null,
            columns: data?.[0] ? Object.keys(data[0]) : []
          };
          
          // Also get count
          const { count } = await supabaseService
            .from(tableName)
            .select('*', { count: 'exact', head: true });
          
          results[tableName].count = count;
        } else {
          results[tableName] = {
            exists: false,
            error: error.message
          };
        }
      } catch (e) {
        results[tableName] = {
          exists: false,
          error: e
        };
      }
    }

    // Find which table actually exists
    const existingTable = Object.entries(results).find(([name, info]: [string, any]) => info.exists);

    return NextResponse.json({
      results,
      summary: {
        foundTable: existingTable ? existingTable[0] : null,
        tableStructure: existingTable ? (existingTable[1] as any).columns : null,
        recordCount: existingTable ? (existingTable[1] as any).count : 0
      }
    });

  } catch (error) {
    console.error('Check LPs structure error:', error);
    return NextResponse.json({ 
      error: 'Failed to check LPs structure',
      details: error instanceof Error ? error.message : error
    }, { status: 500 });
  }
}