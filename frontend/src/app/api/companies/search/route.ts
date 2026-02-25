import { NextRequest, NextResponse } from 'next/server';
import { supabaseService as supabase } from '@/lib/supabase';

export async function GET(request: NextRequest) {
  try {
    if (!supabase) {
      console.error('Supabase client not initialized');
      return NextResponse.json(
        { error: 'Database not configured', companies: [], total: 0 },
        { status: 503 }
      );
    }

    const searchParams = request.nextUrl.searchParams;
    const query = searchParams.get('q') || '';
    const limit = parseInt(searchParams.get('limit') || '20');
    
    if (!query) {
      // Return all companies if no query
      const { data, error } = await supabase
        .from('companies')
        .select('id, name, sector, amount_raised, quarter_raised, current_arr_usd, total_invested_usd')
        .order('name')
        .limit(limit);

      if (error) {
        console.error('Error fetching companies:', error);
        console.error('Supabase error details:', {
          message: error.message,
          details: error.details,
          hint: error.hint,
          code: error.code
        });
        return NextResponse.json(
          { error: 'Failed to fetch companies', message: error.message, companies: [], total: 0 },
          { status: 500 }
        );
      }

      return NextResponse.json({ companies: data || [], total: data?.length || 0 });
    }

    // Search for companies matching the query
    const { data, error } = await supabase
      .from('companies')
      .select('id, name, sector, amount_raised, quarter_raised, current_arr_usd, total_invested_usd')
      .or(`name.ilike.%${query}%,sector.ilike.%${query}%`)
      .order('name')
      .limit(limit);

    if (error) {
      console.error('Error searching companies:', error);
      console.error('Supabase error details:', {
        message: error.message,
        details: error.details,
        hint: error.hint,
        code: error.code
      });
      return NextResponse.json(
        { error: 'Failed to search companies', message: error.message, companies: [], total: 0 },
        { status: 500 }
      );
    }

    return NextResponse.json({ 
      companies: data || [], 
      total: data?.length || 0,
      query: query
    });
  } catch (error) {
    console.error('Error in company search:', error);
    return NextResponse.json(
      { error: 'Internal server error', companies: [], total: 0 },
      { status: 500 }
    );
  }
}