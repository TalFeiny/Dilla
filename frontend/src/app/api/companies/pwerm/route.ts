import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const limit = parseInt(searchParams.get('limit') || '100');
    const offset = parseInt(searchParams.get('offset') || '0');

    // Get total count first
    const { count: totalCount, error: countError } = await supabaseService
      .from('companies')
      .select('*', { count: 'exact', head: true });

    if (countError) {
      console.error('Error counting companies:', countError);
      return NextResponse.json({ error: 'Failed to count companies' }, { status: 500 });
    }

    // Fetch companies that need PWERM analysis
    const { data: companies, error } = await supabaseService
      .from('companies')
      .select('*')
      .order('created_at', { ascending: false })
      .range(offset, offset + limit - 1);

    if (error) {
      console.error('Error fetching companies:', error);
      return NextResponse.json({ error: 'Failed to fetch companies' }, { status: 500 });
    }

    // Transform companies for PWERM analysis
    const pwermCompanies = companies?.map(company => ({
      id: company.id,
      name: company.name || `Company ${company.id}`, // Ensure name is never empty
      sector: company.sector || 'Technology',
      current_arr_usd: company.current_arr_usd || 1000000, // Default 1M ARR
      growth_rate: company.revenue_growth_annual_pct ? company.revenue_growth_annual_pct / 100 : 0.7, // Default 70%
      total_invested_usd: company.total_invested_usd || 0,
      ownership_percentage: company.ownership_percentage || 10,
      status: company.status,
      has_pwerm_model: company.has_pwerm_model || false,
      latest_pwerm_run_at: company.latest_pwerm_run_at,
      pwerm_ready: true
    })).filter(company => company.name && company.name.trim() !== '') || []; // Filter out empty names

    return NextResponse.json({
      companies: pwermCompanies,
      total: totalCount || 0,
      limit,
      offset
    });

  } catch (error) {
    console.error('GET /api/companies/pwerm error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const { companyId } = await request.json();

    if (!companyId) {
      return NextResponse.json({ error: 'Company ID is required' }, { status: 400 });
    }

    // Fetch company data
    const { data: company, error: fetchError } = await supabaseService
      .from('companies')
      .select('*')
      .eq('id', companyId)
      .single();

    if (fetchError || !company) {
      return NextResponse.json({ error: 'Company not found' }, { status: 404 });
    }

    // Prepare PWERM input
    const pwermInput = {
      company_name: company.name,
      current_arr_usd: company.current_arr_usd || 1000000,
      growth_rate: company.revenue_growth_annual_pct ? company.revenue_growth_annual_pct / 100 : 0.7,
      sector: company.sector || 'Technology',
      assumptions: {
        burn_rate_monthly_usd: company.burn_rate_monthly_usd,
        runway_months: company.runway_months
      }
    };

          // Call local PWERM analysis
      try {
        const response = await fetch('http://localhost:3001/api/pwerm/playground', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(pwermInput),
        });

        if (!response.ok) {
          throw new Error(`PWERM analysis responded with status ${response.status}`);
        }

        const pwermResults = await response.json();
        
        if (!pwermResults.success) {
          throw new Error(pwermResults.error || 'PWERM analysis failed');
        }

      // Update company with PWERM results (only existing columns)
      const updateData = {
        has_pwerm_model: true,
        latest_pwerm_run_at: new Date().toISOString(),
        pwerm_scenarios_count: pwermResults.summary?.total_scenarios || 499,
        thesis_match_score: pwermResults.summary?.success_probability ? pwermResults.summary.success_probability * 100 : 50
      };

      const { error: updateError } = await supabaseService
        .from('companies')
        .update(updateData)
        .eq('id', companyId);

      if (updateError) {
        console.error('Error updating company:', updateError);
        return NextResponse.json({ error: 'Failed to update company with PWERM results' }, { status: 500 });
      }

      return NextResponse.json({
        success: true,
        message: 'PWERM analysis completed successfully',
        company_id: companyId,
        results: pwermResults
      });

    } catch (processingError) {
      console.error('PWERM analysis error:', processingError);
      return NextResponse.json({ 
        error: 'PWERM analysis failed', 
        details: processingError instanceof Error ? processingError.message : 'Unknown error'
      }, { status: 500 });
    }

  } catch (error) {
    console.error('POST /api/companies/pwerm error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
} 