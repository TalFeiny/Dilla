import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: fundId } = await params;
    
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    // Get fund details
    const { data: fund, error: fundError } = await supabaseService
      .from('funds')
      .select('*')
      .eq('id', fundId)
      .single();
    
    if (fundError) {
      if (fundError.code === 'PGRST116') {
        return NextResponse.json({ error: 'Fund not found' }, { status: 404 });
      }
      console.error('Error fetching fund:', fundError);
      return NextResponse.json({ error: 'Failed to fetch fund' }, { status: 500 });
    }
    
    return NextResponse.json(fund);
  } catch (error) {
    console.error('Error in portfolio GET by ID:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: fundId } = await params;
    const body = await request.json();
    
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }
    
    // Update fund details
    const { data: fund, error: fundError } = await supabaseService
      .from('funds')
      .update(body)
      .eq('id', fundId)
      .select()
      .single();
    
    if (fundError) {
      console.error('Error updating fund:', fundError);
      return NextResponse.json({ error: 'Failed to update fund' }, { status: 500 });
    }
    
    return NextResponse.json(fund);
  } catch (error) {
    console.error('Error in PUT /api/portfolio/[id]:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: fundId } = await params;
    
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    // Remove fund_id from all companies associated with this fund (set to null)
    const { error: companiesError } = await supabaseService
      .from('companies')
      .update({ fund_id: null })
      .eq('fund_id', fundId);

    if (companiesError) {
      console.error('Error removing companies from fund:', companiesError);
      return NextResponse.json({ error: 'Failed to remove companies from fund' }, { status: 500 });
    }

    // Then delete the fund itself
    const { error: fundError } = await supabaseService
      .from('funds')
      .delete()
      .eq('id', fundId);

    if (fundError) {
      console.error('Error deleting fund:', fundError);
      return NextResponse.json({ error: 'Failed to delete fund' }, { status: 500 });
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error in DELETE /api/portfolio/[id]:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
} 