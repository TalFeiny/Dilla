import { NextResponse } from 'next/server';

export async function GET() {
  return NextResponse.json({
    publishableKey: process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY || '',
    mode: 'subscription',
    features: {
      customerPortal: true,
      webhooks: true,
      multiCurrency: false,
    }
  });
}