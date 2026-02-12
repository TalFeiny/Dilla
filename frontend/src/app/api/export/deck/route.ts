/**
 * Deck Export API Route
 * Handles exporting decks to PPTX and PDF formats via backend service
 */

import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { deck, format = 'pptx' } = body;

    if (!deck) {
      return NextResponse.json(
        { error: 'Deck data is required' },
        { status: 400 }
      );
    }

    if (!['pptx', 'pdf'].includes(format)) {
      return NextResponse.json(
        { error: 'Format must be either "pptx" or "pdf"' },
        { status: 400 }
      );
    }

    // Log deck structure for debugging
    console.log('Export request - deck structure:', {
      title: deck.title,
      slideCount: deck.slides?.length,
      hasCharts: deck.slides?.some((s: any) => s.content?.chart_data),
      firstChartSlide: deck.slides?.find((s: any) => s.content?.chart_data)
    });

    // Forward to backend deck export service - fixed endpoint path
    const response = await fetch(`${BACKEND_URL}/api/export/deck`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        deck_data: deck,
        format: format,
        options: {
          include_notes: true,
          include_citations: true,
          include_charts: true
        }
      })
    });

    if (!response.ok) {
      const error = await response.text();
      console.error('Backend export error:', error);
      return NextResponse.json(
        { error: 'Export failed', details: error },
        { status: response.status }
      );
    }

    // Handle file response
    const contentType = response.headers.get('content-type');
    
    if (contentType?.includes('application/json')) {
      // JSON response with download URL
      const data = await response.json();
      return NextResponse.json(data);
    } else {
      // Direct file stream
      const buffer = await response.arrayBuffer();
      const filename = format === 'pptx' 
        ? `deck_${Date.now()}.pptx`
        : `deck_${Date.now()}.pdf`;
      
      return new NextResponse(buffer, {
        status: 200,
        headers: {
          'Content-Type': format === 'pptx' 
            ? 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
            : 'application/pdf',
          'Content-Disposition': `attachment; filename="${filename}"`,
          'Cache-Control': 'no-cache, no-store, must-revalidate',
        },
      });
    }
  } catch (error) {
    console.error('Export error:', error);
    return NextResponse.json(
      { error: 'Failed to export deck', details: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}