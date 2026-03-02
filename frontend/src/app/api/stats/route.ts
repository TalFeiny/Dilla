import { NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

export async function GET() {
  try {
    if (!supabaseService) {
      return NextResponse.json({ error: 'Database configuration error' }, { status: 500 });
    }

    // Use count queries instead of fetching all data
    // Use actual schema: funds (not portfolio_companies), companies with fund_id
    const [
      { count: documentsCount },
      { count: companiesCount },
      { count: portfoliosCount }
    ] = await Promise.all([
      supabaseService.from('processed_documents').select('*', { count: 'exact', head: true }),
      supabaseService.from('companies').select('*', { count: 'exact', head: true }),
      supabaseService.from('funds').select('*', { count: 'exact', head: true })
    ]);

    // Limited partners table doesn't exist yet - return 0 until schema is added
    const lpsCount = 0;

    const stats = {
      documents: documentsCount || 0,
      companies: companiesCount || 0,
      portfolios: portfoliosCount || 0,
      lps: lpsCount
    };

    // Cache for 5 minutes
    return NextResponse.json(stats, {
      headers: {
        'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=60',
      },
    });
  } catch (error) {
    console.error('Stats API error:', error);
    return NextResponse.json({ 
      documents: 0,
      companies: 0,
      portfolios: 0,
      lps: 0
    }, { status: 200 }); // Return zeros instead of error
  }
}