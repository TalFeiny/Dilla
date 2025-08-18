import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

export async function GET() {
  try {
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
    
    if (!supabaseUrl || !supabaseServiceKey) {
      return NextResponse.json({ error: 'Database configuration error' }, { status: 500 });
    }
    
    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    // Use count queries instead of fetching all data
    const [
      { count: documentsCount },
      { count: companiesCount },
      { count: portfoliosCount },
      { count: lpsCount }
    ] = await Promise.all([
      supabase.from('processed_documents').select('*', { count: 'exact', head: true }),
      supabase.from('companies').select('*', { count: 'exact', head: true }),
      supabase.from('portfolio_companies').select('*', { count: 'exact', head: true }),
      supabase.from('limited_partners').select('*', { count: 'exact', head: true })
    ]);

    const stats = {
      documents: documentsCount || 0,
      companies: companiesCount || 0,
      portfolios: portfoliosCount || 0,
      lps: lpsCount || 0
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