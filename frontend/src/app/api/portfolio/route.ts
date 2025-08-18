import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

export async function GET() {
  try {
    // Check if Supabase is properly configured
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
    
    if (!supabaseUrl || !serviceKey) {
      console.error('Missing Supabase credentials:', {
        hasUrl: !!supabaseUrl,
        hasServiceKey: !!serviceKey
      });
      // Return empty array instead of error for better UX
      return NextResponse.json([]);
    }
    
    if (!supabaseService) {
      console.error('Supabase service client not initialized');
      return NextResponse.json([]);
    }

    // Get only essential fields for portfolio companies to reduce payload
    let portfolioCompanies: any[] = [];
    
    const { data: pcData, error: pcError } = await supabaseService
      .from('companies')
      .select(`
        id,
        name,
        sector,
        fund_id,
        funnel_status,
        total_invested_usd,
        ownership_percentage,
        current_arr_usd,
        first_investment_date,
        exit_date,
        exit_value_usd,
        exit_multiple,
        created_at
      `)
      .not('fund_id', 'is', null)
      .order('created_at', { ascending: false })
      .limit(500); // Limit to prevent massive payloads

    if (pcError) {
      console.error('Error fetching portfolio companies:', pcError);
      // Continue with empty array instead of failing
      portfolioCompanies = [];
    } else {
      portfolioCompanies = pcData || [];
    }

    // Get all funds
    const { data: funds, error: fundsError } = await supabaseService
      .from('funds')
      .select('*')
      .order('created_at', { ascending: false });

    if (fundsError) {
      console.error('Error fetching funds:', fundsError);
      // Return empty array if no funds exist yet
      return NextResponse.json([]);
    }
    
    // If no funds exist, return empty array
    if (!funds || funds.length === 0) {
      console.log('No funds found in database');
      return NextResponse.json([]);
    }

    // Group companies by fund_id to create portfolio structure
    const portfolios = funds.map(fund => {
      const companies = portfolioCompanies.filter(company => company.fund_id === fund.id);
      
      // Calculate fund-level metrics
      const totalInvested = companies.reduce((sum, company) => sum + (company.total_invested_usd || 0), 0);
      const totalValuation = companies.reduce((sum, company) => {
        // Use current_arr as proxy for valuation
        const currentValue = (company.current_arr_usd || 0) * 10; // Simple multiple
        return sum + currentValue;
      }, 0);

      return {
        id: fund.id,
        name: fund.name,
        fundSize: fund.fund_size_usd,
        totalInvested,
        totalValuation,
        companies: companies.map(company => {
          // Calculate metrics server-side
          const investmentDate = company.first_investment_date ? new Date(company.first_investment_date) : null;
          const currentDate = new Date();
          const yearsSinceInvestment = investmentDate 
            ? (currentDate.getTime() - investmentDate.getTime()) / (1000 * 60 * 60 * 24 * 365.25)
            : 0;
          
          // Calculate individual IRR
          let individualIrr = 0;
          if (yearsSinceInvestment > 0 && company.total_invested_usd > 0) {
            const currentValue = (company.current_arr_usd || 0) * 10;
            individualIrr = Math.pow(currentValue / company.total_invested_usd, 1 / yearsSinceInvestment) - 1;
          }
          
          // Calculate individual multiple
          const individualMultiple = company.total_invested_usd > 0 
            ? ((company.current_arr_usd || 0) * 10) / company.total_invested_usd
            : 0;
          
          return {
            id: company.id,
            name: company.name,
            sector: company.sector,
            stage: company.funnel_status,
            investmentAmount: company.total_invested_usd || 0,
            ownershipPercentage: company.ownership_percentage || 0,
            currentArr: company.current_arr_usd || 0,
            valuation: (company.current_arr_usd || 0) * 10,
            investmentDate: company.first_investment_date,
            exitDate: company.exit_date,
            exitValue: company.exit_value_usd,
            exitMultiple: company.exit_multiple,
            fundId: company.fund_id,
            // Pre-calculated metrics
            individualIrr,
            individualMultiple,
            individualReturn: individualMultiple - 1
          };
        })
      };
    });

    return NextResponse.json(portfolios, {
      headers: {
        'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=30',
      },
    });
  } catch (error) {
    console.error('Error in portfolio API:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { name, fundSize, targetMultiple, vintageYear, fundType } = body;

    if (!name || !fundSize) {
      return NextResponse.json({ 
        error: 'Fund name and size are required' 
      }, { status: 400 });
    }

    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    // Create new fund
    const { data: fund, error: fundError } = await supabaseService
      .from('funds')
      .insert({
        name,
        fund_size_usd: fundSize,
        target_net_multiple_bps: targetMultiple || 30000,
        vintage_year: vintageYear,
        fund_type: fundType,
        status: 'fundraising'
      })
      .select()
      .single();

    if (fundError) {
      console.error('Error creating fund:', fundError);
      return NextResponse.json({ error: 'Failed to create fund' }, { status: 500 });
    }

    return NextResponse.json(fund);
  } catch (error) {
    console.error('Error in portfolio POST API:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
} 