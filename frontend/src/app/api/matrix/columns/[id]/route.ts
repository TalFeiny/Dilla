import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

/**
 * PUT /api/matrix/columns/{id}
 * Update a column configuration
 */
export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const body = await request.json();
    const { name, type, service, formula, config } = body;

    if (!supabaseService) {
      return NextResponse.json(
        { error: 'Supabase service not configured' },
        { status: 500 }
      );
    }

    const updateData: any = {
      updated_at: new Date().toISOString(),
    };

    if (name !== undefined) {
      // Validate column name - reject 'poo' and empty names
      if (!name || name.trim() === '' || name.toLowerCase() === 'poo') {
        return NextResponse.json(
          { error: 'Invalid column name. Column name cannot be empty or "poo".' },
          { status: 400 }
        );
      }
      updateData.name = name;
    }
    if (type !== undefined) updateData.type = type;
    if (service?.name !== undefined) updateData.service_name = service.name;
    if (service?.type !== undefined) updateData.service_type = service.type;
    if (service?.apiEndpoint !== undefined || service?.api_endpoint !== undefined) {
      updateData.api_endpoint = service.apiEndpoint || service.api_endpoint;
    }
    if (formula !== undefined) updateData.formula = formula;
    if (config !== undefined || service?.config !== undefined) {
      updateData.config = config || service.config;
    }

    const { data, error } = await supabaseService
      .from('matrix_columns')
      .update(updateData)
      .eq('id', id)
      .select()
      .single();

    if (error) {
      console.error('Error updating matrix column:', error);
      return NextResponse.json(
        { error: 'Failed to update column' },
        { status: 500 }
      );
    }

    return NextResponse.json({ column: data });
  } catch (error) {
    console.error('Error in PUT /api/matrix/columns/[id]:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

/**
 * DELETE /api/matrix/columns/{id}
 * Remove a column from the matrix
 */
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;

    if (!supabaseService) {
      return NextResponse.json(
        { error: 'Supabase service not configured' },
        { status: 500 }
      );
    }

    const { error } = await supabaseService
      .from('matrix_columns')
      .delete()
      .eq('id', id);

    if (error) {
      console.error('Error deleting matrix column:', error);
      return NextResponse.json(
        { error: 'Failed to delete column' },
        { status: 500 }
      );
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error in DELETE /api/matrix/columns/[id]:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
