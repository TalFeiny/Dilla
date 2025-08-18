import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

export async function GET(request: NextRequest) {
  try {
    // Create Supabase client directly in the route
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
    
    if (!supabaseUrl || !supabaseServiceKey) {
      console.error('Missing Supabase credentials', { 
        hasUrl: !!supabaseUrl, 
        hasKey: !!supabaseServiceKey 
      });
      return NextResponse.json({ error: 'Database configuration error' }, { status: 500 });
    }
    
    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    // Check if this is a lightweight request for dropdown
    const searchParams = request.nextUrl.searchParams;
    const isLightweight = searchParams.get('lightweight') === 'true';
    
    // Select only essential columns for lightweight mode
    const selectColumns = isLightweight 
      ? 'id, name, sector, current_arr_usd, total_invested_usd'
      : `
        id,
        name,
        sector,
        status,
        current_arr_usd,
        current_mrr_usd,
        revenue_growth_monthly_pct,
        revenue_growth_annual_pct,
        burn_rate_monthly_usd,
        runway_months,
        total_invested_usd,
        fund_id,
        amount_raised,
        thesis_match_score,
        has_pwerm_model,
        pwerm_scenarios_count,
        quarter_raised,
        location
      `.replace(/\s+/g, ' ').trim();

    // For lightweight mode, fetch all at once (faster for dropdown)
    if (isLightweight) {
      const { data, error } = await supabase
        .from('companies')
        .select(selectColumns)
        .order('current_arr_usd', { ascending: false, nullsFirst: false })
        .limit(2000);

      if (error) {
        console.error('Supabase error:', error);
        return NextResponse.json({ error: 'Failed to fetch companies' }, { status: 500 });
      }

      return NextResponse.json(data || [], {
        headers: {
          'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=60',
        },
      });
    }

    // Original pagination logic for full data
    const allCompanies = [];
    let offset = 0;
    const batchSize = 1000;
    let hasMore = true;

    while (hasMore) {
      const { data, error } = await supabase
        .from('companies')
        .select(selectColumns)
        .order('name', { ascending: true })
        .range(offset, offset + batchSize - 1);

      if (error) {
        console.error('Supabase error:', error);
        return NextResponse.json({ error: 'Failed to fetch companies' }, { status: 500 });
      }

      if (data && data.length > 0) {
        allCompanies.push(...data);
        offset += batchSize;
        hasMore = data.length === batchSize;
      } else {
        hasMore = false;
      }
    }

    // Add cache headers for better performance
    return NextResponse.json(allCompanies, {
      headers: {
        'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=30',
      },
    });
  } catch (error) {
    console.error('API error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}