import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const limit = parseInt(searchParams.get('limit') || '10');
    
    // First get the total count of companies
    const { count } = await supabase
      .from('companies')
      .select('*', { count: 'exact', head: true });
    
    if (!count || count === 0) {
      return NextResponse.json([]);
    }
    
    // Generate random indices
    const randomIndices = new Set<number>();
    const actualLimit = Math.min(limit, count);
    
    while (randomIndices.size < actualLimit) {
      randomIndices.add(Math.floor(Math.random() * count));
    }
    
    // Fetch all companies and select random ones
    // Note: For large datasets, you might want to use a different approach
    const { data: allCompanies, error } = await supabase
      .from('companies')
      .select('id, name, sector, amount_raised, quarter_raised, current_arr_usd, total_invested_usd')
      .order('name');
    
    if (error) {
      console.error('Error fetching companies:', error);
      return NextResponse.json({ error: 'Failed to fetch companies' }, { status: 500 });
    }
    
    // Select random companies based on indices
    const selectedCompanies = Array.from(randomIndices).map(index => allCompanies![index]).filter(Boolean);
    
    return NextResponse.json(selectedCompanies);
  } catch (error) {
    console.error('Error in random companies API:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}