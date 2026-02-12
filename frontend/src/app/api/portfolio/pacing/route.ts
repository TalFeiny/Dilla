import { NextResponse } from 'next/server';
import supabase from '@/lib/supabase';

export async function GET() {
  try {
    // Fetch portfolio companies with investment data
    const { data: companies, error } = await supabase
      .from('companies')
      .select('*')
      .order('first_investment_date', { ascending: true });

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    // Calculate summary statistics
    const totalCompanies = companies?.length || 0;
    const totalInvested = companies?.reduce((sum, company) => 
      sum + (company.total_invested_usd || 0), 0
    ) || 0;
    const avgOwnership = totalCompanies > 0 
      ? companies?.reduce((sum, company) => sum + (company.ownership_percentage || 0), 0) / totalCompanies
      : 0;

    return NextResponse.json({
      companies: companies || [],
      summary: {
        totalCompanies,
        totalInvested,
        avgOwnership: Math.round(avgOwnership * 100) / 100,
      }
    });
  } catch (error) {
    console.error('Error fetching portfolio pacing data:', error);
    return NextResponse.json(
      { error: 'Internal server error' }, 
      { status: 500 }
    );
  }
} 