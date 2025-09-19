"use client";

import SubscriptionManager from '@/components/subscription/SubscriptionManager';

export default function SubscriptionPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">Subscription Management</h1>
        <SubscriptionManager />
      </div>
    </div>
  );
}