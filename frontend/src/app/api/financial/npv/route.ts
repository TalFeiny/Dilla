import { NextRequest, NextResponse } from 'next/server';

/**
 * NPV = sum_t CF_t / (1 + r)^t
 */
function computeNPV(cashFlows: number[], discountRate: number): number {
  let sum = 0;
  for (let t = 0; t < cashFlows.length; t++) {
    sum += cashFlows[t] / Math.pow(1 + discountRate, t);
  }
  return sum;
}

/**
 * POST /api/financial/npv
 * Body: { cash_flows: number[], discount_rate?: number } (default discount_rate 0.1)
 * Returns: { npv, value }
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json().catch(() => ({}));
    const cashFlows = body.cash_flows ?? body.cashFlows ?? body.cashflows;
    const discountRate = typeof body.discount_rate === 'number'
      ? body.discount_rate
      : parseFloat(String(body.discount_rate ?? 0.1)) || 0.1;

    if (!Array.isArray(cashFlows) || cashFlows.length < 1) {
      return NextResponse.json(
        { error: 'cash_flows array with at least 1 value is required' },
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
    const npv = computeNPV(numeric, discountRate);
    return NextResponse.json({ npv, value: npv });
  } catch (error) {
    console.error('NPV API error:', error);
    return NextResponse.json(
      { error: 'Internal server error', details: error instanceof Error ? error.message : String(error) },
      { status: 500 }
    );
  }
}
