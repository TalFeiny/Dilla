import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: fundId } = await params;
    const body = await request.json();
    const { 
      name, 
      sector, 
      stage, 
      investmentAmount, 
      ownershipPercentage, 
      investmentDate,
      currentArr = 0,
      valuation = 0
    } = body;

    if (!name || !investmentAmount) {
      return NextResponse.json({ 
        error: 'Company name and investment amount are required' 
      }, { status: 400 });
    }

    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    // Create new company in the companies table
    const { data: company, error: companyError } = await supabaseService
      .from('companies')
      .insert({
        name,
        sector: sector || null,
        funnel_status: 'unaffiliated', // Use valid value
        total_invested_usd: investmentAmount,
        ownership_percentage: ownershipPercentage || null,
        first_investment_date: investmentDate || null,
        current_arr_usd: currentArr || null,
        fund_id: fundId,
        status: 'active'
      })
      .select()
      .single();

    if (companyError) {
      console.error('Error creating company:', companyError);
      return NextResponse.json({ error: 'Failed to create company' }, { status: 500 });
    }

    return NextResponse.json(company);
  } catch (error) {
    console.error('Error in POST /api/portfolio/[id]/companies:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: fundId } = await params;
    const { searchParams } = new URL(request.url);
    const companyId = searchParams.get('companyId');

    if (!companyId) {
      return NextResponse.json({ error: 'Company ID is required' }, { status: 400 });
    }

    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    // Delete portfolio company record
    const { error } = await supabaseService
      .from('companies')
      .delete()
      .eq('id', companyId)
      .eq('fund_id', fundId);

    if (error) {
      console.error('Error deleting portfolio company:', error);
      return NextResponse.json({ error: 'Failed to delete portfolio company' }, { status: 500 });
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error in DELETE /api/portfolio/[id]/companies:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
} 