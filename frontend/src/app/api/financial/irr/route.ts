import { NextRequest, NextResponse } from 'next/server';

/**
 * Compute IRR (Internal Rate of Return) via Newton-Raphson.
 * NPV(r) = sum_t CF_t / (1+r)^t; we solve NPV(r) = 0 for r.
 */
function computeIRR(cashFlows: number[], maxIterations = 100, tolerance = 1e-7): number | null {
  if (!cashFlows.length || cashFlows.length < 2) return null;
  const cf = [...cashFlows];

  function npv(rate: number): number {
    let sum = 0;
    for (let t = 0; t < cf.length; t++) {
      sum += cf[t] / Math.pow(1 + rate, t);
    }
    return sum;
  }

  function npvDerivative(rate: number): number {
    let sum = 0;
    for (let t = 0; t < cf.length; t++) {
      sum -= (t * cf[t]) / Math.pow(1 + rate, t + 1);
    }
    return sum;
  }

  let r = 0.1;
  for (let i = 0; i < maxIterations; i++) {
    const n = npv(r);
    if (Math.abs(n) < tolerance) return r;
    const d = npvDerivative(r);
    if (Math.abs(d) < 1e-15) break;
    r = r - n / d;
    if (r <= -1) r = -0.99;
    if (r > 10) return null;
  }
  return Math.abs(npv(r)) < 0.01 ? r : null;
}

/**
 * POST /api/financial/irr
 * Body: { cash_flows: number[] }
 * Returns: { irr, value } (value is same as irr for compatibility)
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json().catch(() => ({}));
    const cashFlows = body.cash_flows ?? body.cashFlows ?? body.cashflows;
    if (!Array.isArray(cashFlows) || cashFlows.length < 2) {
      return NextResponse.json(
        { error: 'cash_flows array with at least 2 values is required' },
        { status: 400 }
      );
    }
    const numeric = cashFlows.map((c: unknown) => (typeof c === 'number' ? c : parseFloat(String(c))));
    if (numeric.some((n: number) => isNaN(n))) {
      return NextResponse.json(
        { error: 'All cash_flows must be numbers' },
        { status: 400 }
      );
    }
    const irr = computeIRR(numeric);
    if (irr === null) {
      return NextResponse.json(
        { error: 'IRR could not be computed for these cash flows' },
        { status: 422 }
      );
    }
    return NextResponse.json({ irr, value: irr });
  } catch (error) {
    console.error('IRR API error:', error);
    return NextResponse.json(
      { error: 'Internal server error', details: error instanceof Error ? error.message : String(error) },
      { status: 500 }
    );
  }
}
