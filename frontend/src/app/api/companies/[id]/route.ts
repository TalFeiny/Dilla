import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: companyId } = await params;
    
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    // Get company data from Supabase
    const { data: company, error: companyError } = await supabaseService
      .from('companies')
      .select('*')
      .eq('id', companyId)
      .single();

    if (companyError) {
      console.error('Error fetching company:', companyError);
      return NextResponse.json({ error: 'Failed to fetch company' }, { status: 500 });
    }

    if (!company) {
      return NextResponse.json({ error: 'Company not found' }, { status: 404 });
    }

    return NextResponse.json(company);

  } catch (error) {
    console.error('Error in company fetch:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: companyId } = await params;
    const body = await request.json();
    
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    // Update company data in Supabase
    const { data: company, error: companyError } = await supabaseService
      .from('companies')
      .update(body)
      .eq('id', companyId)
      .select()
      .single();

    if (companyError) {
      console.error('Error updating company:', companyError);
      return NextResponse.json({ error: 'Failed to update company' }, { status: 500 });
    }

    return NextResponse.json(company);

  } catch (error) {
    console.error('Error in company update:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: companyId } = await params;
    
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    // Delete company from Supabase
    const { error: companyError } = await supabaseService
      .from('companies')
      .delete()
      .eq('id', companyId);

    if (companyError) {
      console.error('Error deleting company:', companyError);
      return NextResponse.json({ error: 'Failed to delete company' }, { status: 500 });
    }

    return NextResponse.json({ success: true, message: 'Company deleted successfully' });

  } catch (error) {
    console.error('Error in company deletion:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
