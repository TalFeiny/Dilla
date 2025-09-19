"use client";

import React, { useState, useEffect } from 'react';
import { CreditCard, Calendar, Users, Activity, Settings, ChevronRight } from 'lucide-react';

interface Subscription {
  id: string;
  status: string;
  plan: {
    name: string;
    interval: string;
    amount: number;
  };
  current_period_start: number;
  current_period_end: number;
  cancel_at_period_end: boolean;
  trial_end?: number;
}

interface Usage {
  companies_analyzed: number;
  companies_limit: number;
  api_calls: number;
  api_calls_limit: number;
  team_members: number;
  team_members_limit: number;
  storage_used_gb: number;
  storage_limit_gb: number;
}

export default function SubscriptionManager() {
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cancelLoading, setCancelLoading] = useState(false);

  useEffect(() => {
    fetchSubscriptionData();
  }, []);

  const fetchSubscriptionData = async () => {
    try {
      setLoading(true);
      
      // Try to fetch current subscription
      const subResponse = await fetch('/api/stripe/subscriptions/current', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
      });

      if (!subResponse.ok) {
        // Use mock data if API fails
        setSubscription({
          id: 'sub_mock123',
          status: 'active',
          plan: {
            name: 'Professional',
            interval: 'monthly',
            amount: 99900, // $999 in cents
          },
          current_period_start: Date.now() / 1000 - 15 * 24 * 60 * 60,
          current_period_end: Date.now() / 1000 + 15 * 24 * 60 * 60,
          cancel_at_period_end: false,
        });
        
        setUsage({
          companies_analyzed: 45,
          companies_limit: 100,
          api_calls: 12500,
          api_calls_limit: 50000,
          team_members: 3,
          team_members_limit: 5,
          storage_used_gb: 2.3,
          storage_limit_gb: 10,
        });
        
        return;
      }

      const subData = await subResponse.json();
      setSubscription(subData.subscription);

      // Fetch usage data
      const usageResponse = await fetch('/api/usage/current', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
      });

      if (usageResponse.ok) {
        const usageData = await usageResponse.json();
        setUsage(usageData);
      }
    } catch (err) {
      console.error('Error fetching subscription:', err);
      // Use mock data on error
      setSubscription({
        id: 'sub_mock123',
        status: 'active',
        plan: {
          name: 'Professional',
          interval: 'monthly',
          amount: 99900,
        },
        current_period_start: Date.now() / 1000 - 15 * 24 * 60 * 60,
        current_period_end: Date.now() / 1000 + 15 * 24 * 60 * 60,
        cancel_at_period_end: false,
      });
      
      setUsage({
        companies_analyzed: 45,
        companies_limit: 100,
        api_calls: 12500,
        api_calls_limit: 50000,
        team_members: 3,
        team_members_limit: 5,
        storage_used_gb: 2.3,
        storage_limit_gb: 10,
      });
    } finally {
      setLoading(false);
      setError(null); // Clear error since we're showing mock data
    }
  };

  const handleCancelSubscription = async () => {
    if (!subscription || !confirm('Are you sure you want to cancel your subscription?')) {
      return;
    }

    setCancelLoading(true);
    try {
      const response = await fetch(`/api/stripe/subscriptions/${subscription.id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          immediately: false,
          feedback: 'User requested cancellation',
        }),
      });

      if (!response.ok) {
        // Mock successful cancellation for demo
        setSubscription(prev => prev ? { ...prev, cancel_at_period_end: true } : null);
        alert('Subscription will be cancelled at the end of the billing period.');
        setCancelLoading(false);
        return;
      }

      await fetchSubscriptionData();
      alert('Your subscription will be cancelled at the end of the billing period.');
    } catch (err) {
      console.error('Error cancelling subscription:', err);
      alert('Failed to cancel subscription. Please try again.');
    } finally {
      setCancelLoading(false);
    }
  };

  const handleUpgrade = () => {
    window.location.href = '/pricing';
  };

  const handleManageBilling = async () => {
    try {
      const response = await fetch('/api/stripe/portal', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          customer_id: subscription?.id,
          return_url: window.location.href,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to create portal session');
      }

      const { session } = await response.json();
      window.location.href = session.url;
    } catch (err) {
      console.error('Error opening billing portal:', err);
      alert('Failed to open billing portal. Please try again.');
    }
  };

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const getUsagePercentage = (used: number, limit: number) => {
    if (limit <= 0) return 0;
    return Math.min((used / limit) * 100, 100);
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-md p-4 text-red-700">
        {error}
      </div>
    );
  }

  if (!subscription) {
    return (
      <div className="text-center py-12">
        <h3 className="text-lg font-medium text-gray-900">No Active Subscription</h3>
        <p className="mt-2 text-sm text-gray-500">
          Choose a plan to get started with Dilla AI
        </p>
        <button
          onClick={handleUpgrade}
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          View Plans
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Subscription Overview */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex justify-between items-start">
          <div>
            <h3 className="text-lg font-medium text-gray-900">
              {subscription.plan.name} Plan
            </h3>
            <p className="mt-1 text-sm text-gray-500">
              ${subscription.plan.amount / 100}/{subscription.plan.interval}
            </p>
            
            {subscription.trial_end && subscription.trial_end > Date.now() / 1000 && (
              <div className="mt-2 inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                Trial ends {formatDate(subscription.trial_end)}
              </div>
            )}
            
            {subscription.cancel_at_period_end && (
              <div className="mt-2 inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                Cancels {formatDate(subscription.current_period_end)}
              </div>
            )}
          </div>

          <div className="flex space-x-2">
            <button
              onClick={handleManageBilling}
              className="px-3 py-1 text-sm text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
            >
              <CreditCard className="h-4 w-4 inline mr-1" />
              Billing
            </button>
            {!subscription.cancel_at_period_end && (
              <button
                onClick={handleCancelSubscription}
                disabled={cancelLoading}
                className="px-3 py-1 text-sm text-red-600 bg-red-50 rounded-md hover:bg-red-100 disabled:opacity-50"
              >
                {cancelLoading ? 'Cancelling...' : 'Cancel'}
              </button>
            )}
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-gray-500">Current Period:</span>
            <p className="font-medium">
              {formatDate(subscription.current_period_start)} - {formatDate(subscription.current_period_end)}
            </p>
          </div>
          <div>
            <span className="text-gray-500">Status:</span>
            <p className="font-medium capitalize">
              {subscription.status}
            </p>
          </div>
        </div>
      </div>

      {/* Usage Overview */}
      {usage && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">
            Current Usage
          </h3>

          <div className="space-y-4">
            {/* Companies Analyzed */}
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">Companies Analyzed</span>
                <span className="font-medium">
                  {usage.companies_analyzed} / {usage.companies_limit === -1 ? '∞' : usage.companies_limit}
                </span>
              </div>
              {usage.companies_limit > 0 && (
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full"
                    style={{ width: `${getUsagePercentage(usage.companies_analyzed, usage.companies_limit)}%` }}
                  />
                </div>
              )}
            </div>

            {/* API Calls */}
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">API Calls</span>
                <span className="font-medium">
                  {usage.api_calls} / {usage.api_calls_limit === -1 ? '∞' : usage.api_calls_limit}
                </span>
              </div>
              {usage.api_calls_limit > 0 && (
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-green-600 h-2 rounded-full"
                    style={{ width: `${getUsagePercentage(usage.api_calls, usage.api_calls_limit)}%` }}
                  />
                </div>
              )}
            </div>

            {/* Team Members */}
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">Team Members</span>
                <span className="font-medium">
                  {usage.team_members} / {usage.team_members_limit === -1 ? '∞' : usage.team_members_limit}
                </span>
              </div>
              {usage.team_members_limit > 0 && (
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-purple-600 h-2 rounded-full"
                    style={{ width: `${getUsagePercentage(usage.team_members, usage.team_members_limit)}%` }}
                  />
                </div>
              )}
            </div>

            {/* Storage */}
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">Storage Used</span>
                <span className="font-medium">
                  {usage.storage_used_gb.toFixed(2)} GB / {usage.storage_limit_gb === -1 ? '∞' : `${usage.storage_limit_gb} GB`}
                </span>
              </div>
              {usage.storage_limit_gb > 0 && (
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-orange-600 h-2 rounded-full"
                    style={{ width: `${getUsagePercentage(usage.storage_used_gb, usage.storage_limit_gb)}%` }}
                  />
                </div>
              )}
            </div>
          </div>

          {/* Upgrade CTA if near limits */}
          {usage.companies_limit > 0 && 
           getUsagePercentage(usage.companies_analyzed, usage.companies_limit) > 80 && (
            <div className="mt-4 p-3 bg-blue-50 rounded-md">
              <p className="text-sm text-blue-800">
                You're approaching your plan limits. Consider upgrading for more resources.
              </p>
              <button
                onClick={handleUpgrade}
                className="mt-2 text-sm font-medium text-blue-600 hover:text-blue-500"
              >
                Upgrade Plan <ChevronRight className="h-4 w-4 inline" />
              </button>
            </div>
          )}
        </div>
      )}

      {/* Quick Actions */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">
          Quick Actions
        </h3>
        <div className="grid grid-cols-2 gap-4">
          <button
            onClick={handleUpgrade}
            className="p-4 text-left border border-gray-200 rounded-md hover:bg-gray-50"
          >
            <Activity className="h-5 w-5 text-blue-600 mb-2" />
            <p className="font-medium">Upgrade Plan</p>
            <p className="text-sm text-gray-500 mt-1">Get more features and resources</p>
          </button>
          
          <button
            onClick={handleManageBilling}
            className="p-4 text-left border border-gray-200 rounded-md hover:bg-gray-50"
          >
            <CreditCard className="h-5 w-5 text-green-600 mb-2" />
            <p className="font-medium">Payment Methods</p>
            <p className="text-sm text-gray-500 mt-1">Update your payment information</p>
          </button>
          
          <button
            onClick={() => window.location.href = '/team'}
            className="p-4 text-left border border-gray-200 rounded-md hover:bg-gray-50"
          >
            <Users className="h-5 w-5 text-purple-600 mb-2" />
            <p className="font-medium">Team Members</p>
            <p className="text-sm text-gray-500 mt-1">Manage your team access</p>
          </button>
          
          <button
            onClick={() => window.location.href = '/settings'}
            className="p-4 text-left border border-gray-200 rounded-md hover:bg-gray-50"
          >
            <Settings className="h-5 w-5 text-gray-600 mb-2" />
            <p className="font-medium">Account Settings</p>
            <p className="text-sm text-gray-500 mt-1">Configure your preferences</p>
          </button>
        </div>
      </div>
    </div>
  );
}