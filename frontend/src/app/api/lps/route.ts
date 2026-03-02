import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

export async function GET(request: NextRequest) {
  try {
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    const { searchParams } = new URL(request.url);
    const limit = parseInt(searchParams.get('limit') || '500', 10);  // Increased default limit
    const offset = parseInt(searchParams.get('offset') || '0', 10);

    // Try to fetch from lps table, but return empty array if table doesn't exist
    try {
      // First, get the total count
      const { count } = await supabaseService
        .from('limited_partners')
        .select('*', { count: 'exact', head: true });
      
      console.log(`Total LPs in database: ${count}`);
      
      const { data, error } = await supabaseService
        .from('limited_partners')
        .select('*')
        .range(offset, offset + limit - 1)
        .order('created_at', { ascending: false });
      
      console.log(`Fetched ${data?.length || 0} LPs with limit=${limit}, offset=${offset}`);

      if (error) {
        console.error('Supabase LPs fetch error:', error);
        // Return error details for debugging
        return NextResponse.json({ 
          error: 'LPs table issue',
          details: error,
          message: error.message || 'Unknown error'
        }, { status: 500 });
      }

      return NextResponse.json(data || []);
    } catch (error) {
      console.error('Error fetching LPs:', error);
      return NextResponse.json([]);
    }
  } catch (error) {
    console.error('API error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    const body = await request.json();

    // Try to insert into lps table, but return error if table doesn't exist
    try {
      const { data, error } = await supabaseService
        .from('limited_partners')
        .insert([body])
        .select();

      if (error) {
        console.error('Supabase error:', error);
        return NextResponse.json({ error: 'Failed to create LP' }, { status: 500 });
      }

      return NextResponse.json(data?.[0] || {});
    } catch (error) {
      console.error('Error creating LP:', error);
      return NextResponse.json({ error: 'Failed to create LP' }, { status: 500 });
    }
  } catch (error) {
    console.error('API error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
} 