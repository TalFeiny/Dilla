import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; companyId: string }> }
) {
  try {
    const { id: fundId, companyId } = await params;
    const body = await request.json();

    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    // Verify company belongs to this fund
    const { data: company, error: fetchError } = await supabaseService
      .from('companies')
      .select('id, fund_id, extracted_data')
      .eq('id', companyId)
      .single();

    if (fetchError || !company) {
      return NextResponse.json({ error: 'Company not found' }, { status: 404 });
    }

    if (company.fund_id !== fundId) {
      return NextResponse.json({ error: 'Company does not belong to this fund' }, { status: 403 });
    }

    // Get existing extracted_data or initialize
    const extractedData = company.extracted_data || {};
    const fundingRounds = extractedData.funding_rounds || [];
    const capTable = extractedData.cap_table || {};

    // Add new funding round
    const newRound = {
      round_name: body.round_name,
      date: body.date || new Date().toISOString().split('T')[0],
      amount_raised: body.amount_raised,
      pre_money_valuation: body.pre_money_valuation,
      post_money_valuation: (body.pre_money_valuation || 0) + (body.amount_raised || 0),
      investors: body.investors || [],
      liquidation_preference: body.liquidation_preference || 1.0,
      liquidation_type: body.liquidation_type || 'non_participating',
      participation_cap: body.participation_cap || null
    };

    // Calculate shares and ownership
    const existingShares = capTable.shares_outstanding || 1000000; // Default if not set
    const ownershipPct = (body.amount_raised || 0) / newRound.post_money_valuation;
    const newShares = Math.floor(existingShares * ownershipPct / (1 - ownershipPct));
    const sharePrice = newRound.post_money_valuation / (existingShares + newShares);

    // Update cap table
    const updatedCapTable = {
      ...capTable,
      shares_outstanding: existingShares + newShares,
      share_price: sharePrice,
      option_pool: capTable.option_pool || 0
    };

    // Add round to funding history
    const updatedFundingRounds = [...fundingRounds, newRound];

    // Update extracted_data
    const updatedExtractedData = {
      ...extractedData,
      funding_rounds: updatedFundingRounds,
      cap_table: updatedCapTable,
      funding_analysis: {
        ...(extractedData.funding_analysis || {}),
        latest_round: newRound,
        total_raised: (extractedData.funding_analysis?.total_raised || 0) + (body.amount_raised || 0)
      }
    };

    // Update company record
    const { data: updatedCompany, error: updateError } = await supabaseService
      .from('companies')
      .update({
        extracted_data: updatedExtractedData,
        updated_at: new Date().toISOString()
      })
      .eq('id', companyId)
      .select()
      .single();

    if (updateError) {
      console.error('Error updating company:', updateError);
      return NextResponse.json({ error: 'Failed to add funding round' }, { status: 500 });
    }

    return NextResponse.json({
      success: true,
      funding_round: newRound,
      cap_table: updatedCapTable,
      company: updatedCompany
    });
  } catch (error) {
    console.error('Error in POST /api/portfolio/[id]/companies/[companyId]/funding-rounds:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
