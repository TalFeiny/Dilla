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
      return NextResponse.json(
        { error: 'Supabase not configured', message: 'Missing required environment variables' },
        { status: 503 }
      );
    }
    
    if (!supabaseService) {
      console.error('Supabase service client not initialized');
      return NextResponse.json(
        { error: 'Supabase service not available', message: 'Service client failed to initialize' },
        { status: 503 }
      );
    }

    // Get only essential fields for portfolio companies to reduce payload
    let portfolioCompanies: any[] = [];
    
    // Explicitly select columns to avoid errors if new columns don't exist yet
    // Core columns that should always exist
    const coreColumns = [
      'id',
      'name',
      'sector',
      'funnel_status',
      'total_invested_usd',
      'ownership_percentage',
      'current_arr_usd',
      'first_investment_date',
      'exit_date',
      'exit_value_usd',
      'exit_multiple',
      'fund_id',
      'created_at',
      'updated_at'
    ];
    
    // Optional columns that may not exist if migration hasn't run
    const optionalColumns = [
      'cash_in_bank_usd',
      'investment_lead',
      'last_contacted_date',
      'burn_rate_monthly_usd',
      'runway_months',
      'gross_margin',
      'extra_data',
      'cash_updated_at',
      'burn_rate_updated_at',
      'runway_updated_at',
      'revenue_updated_at',
      'gross_margin_updated_at'
    ];
    
    // Try with all columns first, fall back to core columns if optional ones don't exist
    let selectColumns = [...coreColumns, ...optionalColumns].join(', ');
    let { data: pcData, error: pcError } = await supabaseService
      .from('companies')
      .select(selectColumns)
      .not('fund_id', 'is', null)
      .order('created_at', { ascending: false })
      .limit(500);

    // If error is about missing column, retry with only core columns
    if (pcError && pcError.code === '42703') {
      console.warn('Some optional columns missing, retrying with core columns only');
      selectColumns = coreColumns.join(', ');
      const retryResult = await supabaseService
        .from('companies')
        .select(selectColumns)
        .not('fund_id', 'is', null)
        .order('created_at', { ascending: false })
        .limit(500);
      
      pcData = retryResult.data;
      pcError = retryResult.error;
    }

    if (pcError) {
      console.error('Error fetching portfolio companies:', pcError);
      // Log detailed error for debugging
      console.error('Supabase error details:', {
        message: pcError.message,
        details: pcError.details,
        hint: pcError.hint,
        code: pcError.code
      });
      // Continue with empty array instead of failing - allow page to load with no companies
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
      console.error('Supabase error details:', {
        message: fundsError.message,
        details: fundsError.details,
        hint: fundsError.hint,
        code: fundsError.code
      });
      // Return error response instead of empty array
      return NextResponse.json(
        { error: 'Failed to fetch funds', message: fundsError.message },
        { status: 500 }
      );
    }
    
    // If no funds exist, return empty array (this is a valid state)
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
          
          const extra = company.extra_data && typeof company.extra_data === 'object' ? company.extra_data : {};
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
            // Portfolio report fields
            cashInBank: company.cash_in_bank_usd,
            investmentLead: company.investment_lead || null,
            lastContacted: company.last_contacted_date,
            burnRate: company.burn_rate_monthly_usd,
            runwayMonths: company.runway_months,
            grossMargin: company.gross_margin,
            // Update timestamps
            cashUpdatedAt: company.cash_updated_at,
            burnRateUpdatedAt: company.burn_rate_updated_at,
            runwayUpdatedAt: company.runway_updated_at,
            revenueUpdatedAt: company.revenue_updated_at,
            grossMarginUpdatedAt: company.gross_margin_updated_at,
            // Pre-calculated metrics
            individualIrr,
            individualMultiple,
            individualReturn: individualMultiple - 1,
            // extra_data: documents, optionPool, latestUpdate, productUpdates (for matrix)
            ...extra
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
    // Check Supabase connection first
    if (!supabaseService) {
      console.error('Supabase service not initialized');
      const hasUrl = !!process.env.NEXT_PUBLIC_SUPABASE_URL;
      const hasKey = !!process.env.SUPABASE_SERVICE_ROLE_KEY;
      return NextResponse.json({ 
        error: 'Database connection not available',
        details: {
          hasUrl,
          hasKey,
          message: 'Missing required environment variables: NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY',
          suggestion: 'Check your .env.local file and ensure SUPABASE_SERVICE_ROLE_KEY is set'
        }
      }, { status: 503 });
    }
    
    // Quick connectivity test
    try {
      const { error: testError } = await supabaseService.from('funds').select('id').limit(1);
      if (testError && testError.code === '42P01') {
        return NextResponse.json({
          error: 'Database table does not exist',
          details: 'The funds table does not exist. Please run database migrations.',
          suggestion: 'Run: npx supabase migration up or apply migrations manually'
        }, { status: 503 });
      }
    } catch (testErr) {
      console.warn('Connectivity test failed:', testErr);
    }

    const body = await request.json();
    const { name, fundSize, targetMultiple, vintageYear, fundType } = body;

    if (!name || name.trim() === '') {
      return NextResponse.json({ 
        error: 'Fund name is required' 
      }, { status: 400 });
    }

    // Validate fund size
    const parsedFundSize = typeof fundSize === 'string' ? parseFloat(fundSize) : fundSize;
    if (!parsedFundSize || isNaN(parsedFundSize) || parsedFundSize <= 0) {
      return NextResponse.json({ 
        error: 'Fund size must be a positive number' 
      }, { status: 400 });
    }

    // Create new fund
    const { data: fund, error: fundError } = await supabaseService
      .from('funds')
      .insert({
        name: name.trim(),
        fund_size_usd: parsedFundSize,
        target_net_multiple_bps: targetMultiple || 30000,
        vintage_year: vintageYear || new Date().getFullYear(),
        fund_type: fundType || 'venture',
        status: 'fundraising'
      })
      .select()
      .single();

    if (fundError) {
      console.error('Error creating fund:', fundError);
      console.error('Supabase error details:', JSON.stringify(fundError, null, 2));
      
      // Check for common issues
      let errorMessage = fundError.message || String(fundError);
      if (fundError.code === '42P01') {
        errorMessage = 'Funds table does not exist. Please run database migrations.';
      } else if (fundError.code === '42501') {
        errorMessage = 'Permission denied. Check RLS policies or service role key.';
      } else if (fundError.code === '23505') {
        errorMessage = 'A fund with this name already exists.';
      } else if (fundError.code === '23503') {
        errorMessage = 'Foreign key constraint violation. Check related tables.';
      }
      
      return NextResponse.json({ 
        error: 'Failed to create fund',
        details: errorMessage,
        code: fundError.code,
        hint: fundError.hint,
        fullError: process.env.NODE_ENV === 'development' ? JSON.stringify(fundError, null, 2) : undefined
      }, { status: 500 });
    }

    return NextResponse.json(fund);
  } catch (error) {
    console.error('Error in portfolio POST API:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
} 