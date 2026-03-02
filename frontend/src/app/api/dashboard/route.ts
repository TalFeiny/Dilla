import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

export async function GET(request: NextRequest) {
  try {
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    // Fetch companies data
    const companiesResult = await supabaseService
      .from('companies')
      .select('*')
      .order('created_at', { ascending: false });

    if (companiesResult.error) {
      console.error('Companies fetch error:', companiesResult.error);
      return NextResponse.json({ error: 'Failed to fetch companies' }, { status: 500 });
    }

    const companies = companiesResult.data || [];

    // Try to fetch LPs data, but don't fail if it doesn't exist
    let lps = [];
    try {
      const lpsResult = await supabaseService
        .from('lps')
        .select('id')
        .order('created_at', { ascending: false });
      
      if (!lpsResult.error) {
        lps = lpsResult.data || [];
      }
    } catch (error) {
      console.log('LPs table not available, continuing without LP data');
    }

    // Calculate key metrics
    const totalArr = companies
      .filter(c => c.current_arr_usd)
      .reduce((sum, c) => sum + (c.current_arr_usd || 0), 0);
    
    const highGrowthCompanies = companies.filter(c => 
      c.revenue_growth_annual_pct && c.revenue_growth_annual_pct > 50
    ).length;
    
    const highThesisCompanies = companies.filter(c => 
      c.thesis_match_score && c.thesis_match_score > 70
    ).length;
    
    const pwermModels = companies.filter(c => c.has_pwerm_model).length;
    
    const companiesWithGrowth = companies.filter(c => c.revenue_growth_annual_pct);
    const avgGrowthRate = companiesWithGrowth.length > 0 
      ? companiesWithGrowth.reduce((sum, c) => sum + (c.revenue_growth_annual_pct || 0), 0) / companiesWithGrowth.length
      : 0;

    const dashboardData = {
      companies: companies.length,
      lps: lps.length,
      activeInvestments: companies.filter(c => c.status === 'active').length,
      totalDeals: companies.length + lps.length,
      totalArr: Math.round(totalArr / 1000000), // Convert to millions
      highGrowthCompanies,
      highThesisCompanies,
      pwermModels,
      avgGrowthRate: Math.round(avgGrowthRate),
    };

    // Add caching headers for better performance
    const response = NextResponse.json(dashboardData);
    response.headers.set('Cache-Control', 'public, max-age=30, stale-while-revalidate=60');
    
    return response;
  } catch (error) {
    console.error('Dashboard API error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
} 