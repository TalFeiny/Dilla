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
    
    console.log('DELETE /api/portfolio/[id] called with fundId:', fundId);
    
    if (!fundId || fundId.trim() === '') {
      return NextResponse.json({ 
        error: 'Fund ID is required' 
      }, { status: 400 });
    }
    
    if (!supabaseService) {
      console.error('Supabase service not initialized');
      const hasUrl = !!process.env.NEXT_PUBLIC_SUPABASE_URL;
      const hasKey = !!process.env.SUPABASE_SERVICE_ROLE_KEY;
      return NextResponse.json({ 
        error: 'Database connection not available',
        details: {
          hasUrl,
          hasKey,
          message: 'Missing required environment variables: NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY'
        }
      }, { status: 503 });
    }

    console.log('Unlinking companies from fund...');
    // Remove fund_id from all companies associated with this fund (set to null)
    const { data: companiesData, error: companiesError } = await supabaseService
      .from('companies')
      .update({ fund_id: null })
      .eq('fund_id', fundId)
      .select('id');

    if (companiesError) {
      console.error('Error removing companies from fund:', companiesError);
      return NextResponse.json({ 
        error: 'Failed to remove companies from fund',
        details: companiesError.message,
        code: companiesError.code
      }, { status: 500 });
    }

    console.log(`Unlinked ${companiesData?.length || 0} companies from fund`);

    // Then delete the fund itself
    console.log('Deleting fund...');
    const { data: fundData, error: fundError } = await supabaseService
      .from('funds')
      .delete()
      .eq('id', fundId)
      .select();

    if (fundError) {
      console.error('Error deleting fund:', fundError);
      return NextResponse.json({ 
        error: 'Failed to delete fund',
        details: fundError.message,
        code: fundError.code
      }, { status: 500 });
    }

    if (!fundData || fundData.length === 0) {
      console.warn('Fund not found or already deleted:', fundId);
      return NextResponse.json({ 
        error: 'Fund not found',
        message: 'The fund may have already been deleted'
      }, { status: 404 });
    }

    console.log('Fund deleted successfully:', fundId);
    return NextResponse.json({ 
      success: true,
      message: 'Portfolio deleted successfully',
      unlinkedCompanies: companiesData?.length || 0
    });
  } catch (error) {
    console.error('Error in DELETE /api/portfolio/[id]:', error);
    return NextResponse.json({ 
      error: 'Internal server error',
      details: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
} 