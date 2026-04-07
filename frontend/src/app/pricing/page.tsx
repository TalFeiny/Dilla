'use client';

import { useState } from 'react';
import { useAuth } from '@/components/providers/AuthProvider';
import { useRouter } from 'next/navigation';

const PRICE_ID = process.env.NEXT_PUBLIC_STRIPE_PRICE_ID || '';

export default function PricingPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubscribe = async () => {
    if (authLoading) return;

    if (!user) {
      router.push('/login');
      return;
    }

    if (!PRICE_ID) {
      setError('Stripe is not configured yet. Please contact support.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/stripe/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          price_id: PRICE_ID,
          success_url: `${window.location.origin}/subscription/success?session_id={CHECKOUT_SESSION_ID}`,
          cancel_url: `${window.location.origin}/pricing`,
          customer_email: user.email,
          metadata: { user_id: user.id },
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to create checkout session');
      }

      // Stripe Checkout session has a url field — redirect there
      const checkoutUrl = data.session?.url;
      if (checkoutUrl) {
        window.location.href = checkoutUrl;
      } else {
        throw new Error('No checkout URL returned');
      }
    } catch (err) {
      console.error('Checkout error:', err);
      setError(err instanceof Error ? err.message : 'Something went wrong');
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-black text-white flex items-center justify-center px-4">
      <div className="max-w-md w-full">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold mb-2">Dilla AI</h1>
          <p className="text-gray-400">Your strategic CFO agent</p>
        </div>

        <div className="border border-gray-800 rounded-2xl p-8 bg-gray-950">
          <div className="mb-6">
            <span className="text-sm font-medium text-gray-400 uppercase tracking-wide">Pro</span>
            <div className="mt-2 flex items-baseline gap-1">
              <span className="text-5xl font-bold">&pound;100</span>
              <span className="text-gray-400">/month</span>
            </div>
          </div>

          <ul className="space-y-3 mb-8 text-sm text-gray-300">
            <li className="flex items-start gap-2">
              <span className="text-green-400 mt-0.5">&#10003;</span>
              <span>Unlimited financial analysis</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-400 mt-0.5">&#10003;</span>
              <span>P&amp;L, balance sheet, cash flow intelligence</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-400 mt-0.5">&#10003;</span>
              <span>Cap table &amp; legal document parsing</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-400 mt-0.5">&#10003;</span>
              <span>Scenario modeling &amp; forecasting</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-400 mt-0.5">&#10003;</span>
              <span>Investor deck generation</span>
            </li>
          </ul>

          {error && (
            <div className="mb-4 p-3 rounded-lg bg-red-900/30 border border-red-800 text-red-300 text-sm">
              {error}
            </div>
          )}

          <button
            onClick={handleSubscribe}
            disabled={loading || authLoading}
            className="w-full py-3 px-4 rounded-lg bg-white text-black font-semibold hover:bg-gray-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Redirecting to checkout...' : 'Subscribe'}
          </button>

          {!user && !authLoading && (
            <p className="mt-3 text-center text-sm text-gray-500">
              You&apos;ll need to sign in first
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
