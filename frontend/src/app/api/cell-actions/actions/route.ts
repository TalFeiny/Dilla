import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

/** Minimal fallback when backend cell_actions router returns 404 so UI still shows action list; execute may fail until backend loads. */
const FALLBACK_ACTIONS = [
  { action_id: 'valuation_engine.auto', name: 'Valuation', category: 'workflow', service_name: 'valuation_engine', execution_type: 'workflow', required_inputs: {}, output_type: 'object', mode_availability: ['portfolio', 'query', 'custom', 'lp'], column_compatibility: [] },
  { action_id: 'valuation_engine.pwerm', name: 'PWERM', category: 'workflow', service_name: 'valuation_engine', execution_type: 'workflow', required_inputs: {}, output_type: 'object', mode_availability: ['portfolio', 'query', 'custom', 'lp'], column_compatibility: [] },
  { action_id: 'cap_table.calculate', name: 'Cap Table', category: 'workflow', service_name: 'cap_table', execution_type: 'workflow', required_inputs: {}, output_type: 'object', mode_availability: ['portfolio', 'query', 'custom', 'lp'], column_compatibility: [] },
  { action_id: 'financial.irr', name: 'IRR', category: 'formula', service_name: 'financial', execution_type: 'formula', required_inputs: {}, output_type: 'number', mode_availability: ['portfolio', 'query', 'custom', 'lp'], column_compatibility: [] },
  { action_id: 'financial.moic', name: 'MOIC', category: 'formula', service_name: 'financial', execution_type: 'formula', required_inputs: {}, output_type: 'number', mode_availability: ['portfolio', 'query', 'custom', 'lp'], column_compatibility: [] },
];

/**
 * GET /api/cell-actions/actions
 * Proxy to backend cell-actions registry. On 404 (cell_actions router not loaded), return 200 with fallback list so frontend never sees 404.
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const mode = searchParams.get('mode') ?? 'portfolio';
    const category = searchParams.get('category') ?? undefined;
    const column_id = searchParams.get('column_id') ?? undefined;
    const column_type = searchParams.get('column_type') ?? undefined;

    const params = new URLSearchParams({ mode });
    if (category) params.append('category', category);
    if (column_id) params.append('column_id', column_id);
    if (column_type) params.append('column_type', column_type);

    const backendUrl = getBackendUrl();
    const res = await fetch(
      `${backendUrl}/api/cell-actions/actions?${params.toString()}`,
      { headers: { Accept: 'application/json' } }
    );

    if (res.status === 404) {
      return NextResponse.json({ actions: FALLBACK_ACTIONS, count: FALLBACK_ACTIONS.length });
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch actions' }));
      return NextResponse.json(
        { error: err.detail ?? 'Failed to fetch cell actions' },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Cell-actions proxy GET /actions:', error);
    return NextResponse.json(
      {
        error: 'Internal server error',
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
