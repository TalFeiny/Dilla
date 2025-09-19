'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { X, Check, Sparkles, Zap, Crown } from 'lucide-react';
import { signIn } from 'next-auth/react';

interface PaywallModalProps {
  isOpen: boolean;
  onClose: () => void;
  prompt?: string;
  result?: string | null;
}

export default function PaywallModal({ isOpen, onClose, prompt, result }: PaywallModalProps) {
  const [selectedPlan, setSelectedPlan] = useState<'starter' | 'professional'>('starter');
  const [billingPeriod, setBillingPeriod] = useState<'monthly' | 'yearly'>('monthly');
  const [seats, setSeats] = useState(1);
  const router = useRouter();

  if (!isOpen) return null;

  const plans = {
    starter: {
      name: 'Starter',
      monthly: 99,
      yearly: 990,
      features: [
        'Up to 50 analyses per month',
        'GPT-4o Mini & Claude Haiku',
        'Basic market research',
        'CSV & Excel export',
        'Email support',
        '3 team seats included',
      ],
      models: ['gpt-4o-mini', 'claude-3-haiku'],
      icon: <Zap className="w-6 h-6" />,
      color: 'blue',
    },
    professional: {
      name: 'Professional',
      monthly: 299,
      yearly: 2990,
      features: [
        'Up to 500 analyses per month',
        'GPT-4o & Claude 3.5 Sonnet',
        'Deep market intelligence',
        'All export formats',
        'Priority support',
        '5 team seats included',
        'Custom report templates',
      ],
      models: ['gpt-4o', 'claude-3.5-sonnet'],
      icon: <Crown className="w-6 h-6" />,
      color: 'indigo',
      recommended: true,
    },
  };

  const currentPlan = plansArray.from(ectedPlan);
  const price = billingPeriod === 'monthly' 
    ? currentPlan.monthly 
    : Math.floor(currentPlan.yearly / 12);
  
  const totalPrice = price * seats;

  const handleGoogleSignIn = async () => {
    // Store the selected plan and prompt in session storage
    sessionStorage.setItem('pending_plan', JSON.stringify({
      plan: selectedPlan,
      billingPeriod,
      seats,
      prompt,
      result,
    }));

    // Sign in with Google
    await signIn('google', {
      callbackUrl: '/checkout',
    });
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl max-w-4xl w-full max-h-Array.from(h) overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <h2 className="text-2xl font-bold text-gray-900">Choose Your Plan</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        <div className="p-6">
          {/* Success Message */}
          <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-6">
            <div className="flex items-center">
              <Sparkles className="w-5 h-5 text-green-600 mr-2" />
              <p className="text-green-800">
                Great! You've seen what our AI can do. Sign up now to continue analyzing companies.
              </p>
            </div>
          </div>

          {/* Billing Toggle */}
          <div className="flex justify-center mb-8">
            <div className="bg-gray-100 rounded-lg p-1 flex">
              <button
                onClick={() => setBillingPeriod('monthly')}
                className={`px-4 py-2 rounded-md font-medium transition-colors ${
                  billingPeriod === 'monthly'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600'
                }`}
              >
                Monthly
              </button>
              <button
                onClick={() => setBillingPeriod('yearly')}
                className={`px-4 py-2 rounded-md font-medium transition-colors ${
                  billingPeriod === 'yearly'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600'
                }`}
              >
                Yearly
                <span className="ml-1 text-xs text-green-600">Save 17%</span>
              </button>
            </div>
          </div>

          {/* Plans */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            {Object.entries(plans).map(([key, plan]) => (
              <div
                key={key}
                onClick={() => setSelectedPlan(key as 'starter' | 'professional')}
                className={`relative rounded-xl border-2 p-6 cursor-pointer transition-all ${
                  selectedPlan === key
                    ? `border-${plan.color}-500 bg-${plan.color}-50`
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                {plan.recommended && (
                  <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
                    <span className="bg-indigo-600 text-white text-xs font-semibold px-3 py-1 rounded-full">
                      RECOMMENDED
                    </span>
                  </div>
                )}

                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center">
                    <div className={`p-2 bg-${plan.color}-100 rounded-lg mr-3`}>
                      {plan.icon}
                    </div>
                    <h3 className="text-xl font-semibold text-gray-900">{plan.name}</h3>
                  </div>
                  {selectedPlan === key && (
                    <div className={`w-6 h-6 bg-${plan.color}-500 rounded-full flex items-center justify-center`}>
                      <Check className="w-4 h-4 text-white" />
                    </div>
                  )}
                </div>

                <div className="mb-4">
                  <span className="text-3xl font-bold text-gray-900">
                    ${billingPeriod === 'monthly' ? plan.monthly : Math.floor(plan.yearly / 12)}
                  </span>
                  <span className="text-gray-600 ml-1">
                    /seat/{billingPeriod === 'monthly' ? 'month' : 'month'}
                  </span>
                  {billingPeriod === 'yearly' && (
                    <div className="text-sm text-gray-500 mt-1">
                      ${plan.yearly} billed annually
                    </div>
                  )}
                </div>

                <div className="space-y-2">
                  {plan.features.map((feature, idx) => (
                    <div key={idx} className="flex items-start">
                      <Check className="w-4 h-4 text-green-500 mr-2 mt-0.5 flex-shrink-0" />
                      <span className="text-sm text-gray-700">{feature}</span>
                    </div>
                  ))}
                </div>

                <div className="mt-4 pt-4 border-t border-gray-200">
                  <p className="text-xs text-gray-600">
                    <strong>AI Models:</strong> {plan.models.join(', ')}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* Seat Selection */}
          <div className="bg-gray-50 rounded-xl p-6 mb-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h4 className="font-semibold text-gray-900">Number of Seats</h4>
                <p className="text-sm text-gray-600">
                  {currentPlan.name === 'Starter' ? '3 seats included' : '5 seats included'}
                </p>
              </div>
              <div className="flex items-center space-x-3">
                <button
                  onClick={() => setSeats(Math.max(1, seats - 1))}
                  className="w-8 h-8 rounded-lg border border-gray-300 flex items-center justify-center hover:bg-gray-100"
                >
                  -
                </button>
                <span className="w-12 text-center font-semibold">{seats}</span>
                <button
                  onClick={() => setSeats(seats + 1)}
                  className="w-8 h-8 rounded-lg border border-gray-300 flex items-center justify-center hover:bg-gray-100"
                >
                  +
                </button>
              </div>
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-600">Total:</p>
              <p className="text-2xl font-bold text-gray-900">
                ${totalPrice}
                <span className="text-sm font-normal text-gray-600">
                  /{billingPeriod === 'monthly' ? 'month' : 'month'}
                </span>
              </p>
            </div>
          </div>

          {/* Sign In Button */}
          <button
            onClick={handleGoogleSignIn}
            className="w-full py-4 bg-indigo-600 text-white rounded-xl font-semibold hover:bg-indigo-700 transition-colors flex items-center justify-center"
          >
            <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
              <path
                fill="currentColor"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="currentColor"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="currentColor"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="currentColor"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            Continue with Google
          </button>

          <p className="text-center text-sm text-gray-500 mt-4">
            No credit card required for sign up • Cancel anytime
          </p>
        </div>
      </div>
    </div>
  );
}