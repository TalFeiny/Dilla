import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

/**
 * POST /api/matrix/charts/generate
 * Generate charts from matrix data. Proxies to backend.
 * Body: { fund_id?, matrix_data, chart_type?: "auto" | "sankey" | "waterfall" | "heatmap" | "path_to_100m" | "probability_cloud" | "cashflow" | "revenue_treemap" | "revenue_growth_treemap" | "product_velocity" | "dpi_sankey" }
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { fund_id, matrix_data, chart_type = 'auto' } = body;

    if (!matrix_data) {
      return NextResponse.json(
        { error: 'matrix_data is required' },
        { status: 400 }
      );
    }

    const backendUrl = getBackendUrl();
    const res = await fetch(`${backendUrl}/api/matrix/charts/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ fund_id, matrix_data, chart_type }),
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      return NextResponse.json(
        { error: data.detail || data.error || 'Chart generation failed' },
        { status: res.status }
      );
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error('Matrix charts generate error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    );
  }
}
