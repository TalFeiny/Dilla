"use client";

import React, { useState, useEffect } from 'react';
import { loadStripe } from '@stripe/stripe-js';
import { Check, X } from 'lucide-react';

// Initialize Stripe
const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY || '');

interface Plan {
  id: string;
  name: string;
  description: string;
  price: {
    monthly: number;
    yearly: number;
  };
  features: string[];
  limitations?: string[];
  recommended?: boolean;
  priceId: {
    monthly: string;
    yearly: string;
  };
}

const plans: Plan[] = [
  {
    id: 'free',
    name: 'Free',
    description: 'Perfect for trying out our platform',
    price: {
      monthly: 0,
      yearly: 0
    },
    features: [
      'Up to 5 company analyses per month',
      'Basic market research',
      'Limited API calls (100/month)',
      'Community support',
      'Basic data export (CSV)'
    ],
    limitations: [
      'No advanced analytics',
      'No custom reports',
      'Limited data retention (30 days)'
    ],
    priceId: {
      monthly: '',
      yearly: ''
    }
  },
  {
    id: 'starter',
    name: 'Starter',
    description: 'Great for small teams and growing startups',
    price: {
      monthly: 99,
      yearly: 990
    },
    features: [
      'Up to 50 company analyses per month',
      'Enhanced market research',
      'Standard API calls (1,000/month)',
      'Email support',
      'Export to CSV and Excel',
      'Basic analytics dashboard',
      '7-day free trial'
    ],
    priceId: {
      monthly: process.env.NEXT_PUBLIC_STRIPE_STARTER_MONTHLY || '',
      yearly: process.env.NEXT_PUBLIC_STRIPE_STARTER_YEARLY || ''
    }
  },
  {
    id: 'professional',
    name: 'Professional',
    description: 'For professional investors and VC firms',
    price: {
      monthly: 499,
      yearly: 4990
    },
    features: [
      'Up to 500 company analyses per month',
      'Deep market intelligence',
      'Enhanced API calls (10,000/month)',
      'Priority email & chat support',
      'Export to CSV, Excel, and PDF',
      'Advanced analytics & insights',
      'Custom report templates',
      'Team collaboration features',
      '14-day free trial'
    ],
    recommended: true,
    priceId: {
      monthly: process.env.NEXT_PUBLIC_STRIPE_PRO_MONTHLY || '',
      yearly: process.env.NEXT_PUBLIC_STRIPE_PRO_YEARLY || ''
    }
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    description: 'Custom solutions for large organizations',
    price: {
      monthly: -1,
      yearly: -1
    },
    features: [
      'Unlimited company analyses',
      'Premium market intelligence',
      'Unlimited API calls',
      'Dedicated account manager',
      '24/7 phone & email support',
      'All export formats + custom formats',
      'White-label options',
      'Custom integrations',
      'SLA guarantee',
      'On-premise deployment option'
    ],
    priceId: {
      monthly: '',
      yearly: ''
    }
  }
];

export default function PricingPage() {
  const [billingInterval, setBillingInterval] = useState<'monthly' | 'yearly'>('monthly');
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubscribe = async (plan: Plan) => {
    if (plan.id === 'free') {
      // Handle free plan signup
      window.location.href = '/signup?plan=free';
      return;
    }

    if (plan.id === 'enterprise') {
      // Handle enterprise contact
      window.location.href = '/contact-sales';
      return;
    }

    setLoading(plan.id);
    setError(null);

    try {
      const priceId = plan.priceId[billingInterval];
      
      if (!priceId) {
        throw new Error('Price ID not configured');
      }

      // Create checkout session
      const response = await fetch('/api/stripe/checkout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          price_id: priceId,
          success_url: `${window.location.origin}/subscription/success?session_id={CHECKOUT_SESSION_ID}`,
          cancel_url: `${window.location.origin}/pricing`,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to create checkout session');
      }

      const { session } = await response.json();

      // Redirect to Stripe Checkout
      const stripe = await stripePromise;
      if (!stripe) {
        throw new Error('Stripe not loaded');
      }

      const { error } = await stripe.redirectToCheckout({
        sessionId: session.id,
      });

      if (error) {
        throw error;
      }
    } catch (err) {
      console.error('Subscription error:', err);
      setError(err instanceof Error ? err.message : 'Failed to start subscription');
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center">
          <h2 className="text-3xl font-extrabold text-gray-900 sm:text-4xl">
            Choose Your Plan
          </h2>
          <p className="mt-4 text-xl text-gray-600">
            Select the perfect plan for your investment research needs
          </p>
        </div>

        {/* Billing Toggle */}
        <div className="mt-8 flex justify-center">
          <div className="relative bg-gray-100 p-1 rounded-lg flex">
            <button
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                billingInterval === 'monthly'
                  ? 'bg-white text-gray-900 shadow'
                  : 'text-gray-500 hover:text-gray-900'
              }`}
              onClick={() => setBillingInterval('monthly')}
            >
              Monthly
            </button>
            <button
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                billingInterval === 'yearly'
                  ? 'bg-white text-gray-900 shadow'
                  : 'text-gray-500 hover:text-gray-900'
              }`}
              onClick={() => setBillingInterval('yearly')}
            >
              Yearly
              <span className="ml-2 text-green-600 text-xs">Save 17%</span>
            </button>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-md text-red-700 text-center">
            {error}
          </div>
        )}

        {/* Pricing Cards */}
        <div className="mt-12 grid gap-8 lg:grid-cols-4">
          {plans.map((plan) => (
            <div
              key={plan.id}
              className={`relative bg-white rounded-lg shadow-lg overflow-hidden ${
                plan.recommended ? 'ring-2 ring-blue-500' : ''
              }`}
            >
              {plan.recommended && (
                <div className="absolute top-0 right-0 bg-blue-500 text-white px-3 py-1 text-sm font-semibold rounded-bl">
                  Recommended
                </div>
              )}

              <div className="p-6">
                <h3 className="text-xl font-semibold text-gray-900">
                  {plan.name}
                </h3>
                <p className="mt-2 text-sm text-gray-500">
                  {plan.description}
                </p>

                <div className="mt-4">
                  {plan.price[billingInterval] === -1 ? (
                    <div className="text-3xl font-bold text-gray-900">
                      Custom
                    </div>
                  ) : (
                    <div className="flex items-baseline">
                      <span className="text-3xl font-bold text-gray-900">
                        ${plan.price[billingInterval]}
                      </span>
                      {plan.price[billingInterval] > 0 && (
                        <span className="ml-2 text-gray-500">
                          /{billingInterval === 'monthly' ? 'month' : 'year'}
                        </span>
                      )}
                    </div>
                  )}
                </div>

                <button
                  onClick={() => handleSubscribe(plan)}
                  disabled={loading === plan.id}
                  className={`mt-6 w-full py-3 px-4 rounded-md font-medium transition-colors ${
                    plan.recommended
                      ? 'bg-blue-600 text-white hover:bg-blue-700'
                      : 'bg-gray-900 text-white hover:bg-gray-800'
                  } disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  {loading === plan.id ? (
                    'Processing...'
                  ) : plan.id === 'free' ? (
                    'Start Free'
                  ) : plan.id === 'enterprise' ? (
                    'Contact Sales'
                  ) : (
                    'Start Trial'
                  )}
                </button>

                <div className="mt-6 space-y-3">
                  {plan.features.map((feature, index) => (
                    <div key={index} className="flex items-start">
                      <Check className="h-5 w-5 text-green-500 flex-shrink-0 mt-0.5" />
                      <span className="ml-2 text-sm text-gray-700">
                        {feature}
                      </span>
                    </div>
                  ))}
                  {plan.limitations?.map((limitation, index) => (
                    <div key={`limit-${index}`} className="flex items-start">
                      <X className="h-5 w-5 text-gray-400 flex-shrink-0 mt-0.5" />
                      <span className="ml-2 text-sm text-gray-500">
                        {limitation}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Additional Information */}
        <div className="mt-12 text-center">
          <p className="text-gray-600">
            All plans include a free trial. No credit card required to start.
          </p>
          <p className="mt-2 text-sm text-gray-500">
            Questions? <a href="/contact" className="text-blue-600 hover:text-blue-500">Contact our sales team</a>
          </p>
        </div>
      </div>
    </div>
  );
}