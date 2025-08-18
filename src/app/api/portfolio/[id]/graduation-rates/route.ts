import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export async function PUT(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const body = await request.json();
    const {
      preferredReturn,
      catchUpPercentage,
      carriedInterest,
      managementFee,
      hurdleRate
    } = body;

    const { data: portfolio, error } = await supabase
      .from('portfolios')
      .update({
        graduation_rates: {
          preferredReturn,
          catchUpPercentage,
          carriedInterest,
          managementFee,
          hurdleRate
        },
        updated_at: new Date().toISOString()
      })
      .eq('id', params.id)
      .select()
      .single();

    if (error) {
      console.error('Error updating graduation rates:', error);
      return NextResponse.json({ error: 'Failed to update graduation rates' }, { status: 500 });
    }

    return NextResponse.json({ portfolio });
  } catch (error) {
    console.error('Error in PUT /api/portfolio/[id]/graduation-rates:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
} 