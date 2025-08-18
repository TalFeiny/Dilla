import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);
const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { portfolioId, companies, graduationRates } = body;

    if (!portfolioId || !companies || companies.length === 0) {
      return NextResponse.json(
        { error: 'Portfolio ID and companies are required' },
        { status: 400 }
      );
    }

    // For now, we'll aggregate company-level results
    // Waterfall will be calculated at the company level first
    const totalInvestment = companies.reduce((sum: number, c: any) => sum + c.investmentAmount, 0);
    const totalValue = companies.reduce((sum: number, c: any) => sum + c.valuation, 0);
    
    // Aggregate company PWERM results
    const aggregatedResults = {
      expectedReturn: companies.reduce((sum: number, c: any) => sum + (c.pwermResults?.expectedReturn || 0), 0) / companies.length,
      riskScore: companies.reduce((sum: number, c: any) => sum + (c.pwermResults?.riskScore || 0), 0) / companies.length,
      confidence: companies.reduce((sum: number, c: any) => sum + (c.pwermResults?.confidence || 0), 0) / companies.length,
      fundIrr: companies.reduce((sum: number, c: any) => sum + (c.pwermResults?.irr || 0), 0) / companies.length,
      fundTvpi: totalValue / totalInvestment,
      totalInvestment,
      totalValue,
      companyCount: companies.length,
      companies: companies.map((company: any) => ({
        id: company.id,
        name: company.name,
        expectedReturn: company.pwermResults?.expectedReturn || 0,
        irr: company.pwermResults?.irr || 0,
        tvpi: company.pwermResults?.tvpi || 0,
        waterfall: company.pwermResults?.waterfall || null
      }))
    };

    return NextResponse.json({ 
      success: true, 
      pwermResults: aggregatedResults,
      message: 'Fund-level PWERM analysis completed (company-level waterfall applied)'
    });
  } catch (error) {
    console.error('Error in POST /api/portfolio/pwerm:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
} 