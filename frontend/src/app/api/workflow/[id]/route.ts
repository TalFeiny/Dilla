import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

/** GET — load a single workflow by ID */
export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const { data, error } = await supabaseService
      .from('workflows')
      .select('*')
      .eq('id', id)
      .single();

    if (error) {
      console.error('[workflow/get] Error:', error);
      return NextResponse.json({ error: error.message }, { status: 404 });
    }
    return NextResponse.json(data);
  } catch (err) {
    console.error('[workflow/get] Exception:', err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Unknown error' },
      { status: 500 }
    );
  }
}

/** DELETE — remove a workflow */
export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const { error } = await supabaseService
      .from('workflows')
      .delete()
      .eq('id', id);

    if (error) {
      console.error('[workflow/delete] Error:', error);
      return NextResponse.json({ error: error.message }, { status: 500 });
    }
    return NextResponse.json({ deleted: true });
  } catch (err) {
    console.error('[workflow/delete] Exception:', err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Unknown error' },
      { status: 500 }
    );
  }
}
