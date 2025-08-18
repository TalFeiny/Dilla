'use client';

import React from 'react';
import CostCalculator from '@/components/agent/CostCalculator';
import { Brain, DollarSign, Calculator } from 'lucide-react';

export default function AgentCostsPage() {
  return (
    <div className="container mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <Calculator className="h-8 w-8 text-purple-600" />
          Claude 3.5 Cost Analysis
        </h1>
        <p className="text-gray-600 mt-2">
          Detailed cost breakdown for running Claude 3.5 Sonnet continuously or in 20-minute sprints
        </p>
      </div>

      <div className="mb-6 p-4 bg-blue-50 rounded-lg">
        <h2 className="font-semibold mb-2">Quick Answer: 20-Minute Runs</h2>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-sm text-gray-600">Claude 3.5 Haiku (Fast)</p>
            <p className="text-xl font-bold text-green-600">$0.05 per 20 min</p>
            <p className="text-xs text-gray-500">~20 queries @ 2K tokens</p>
          </div>
          <div>
            <p className="text-sm text-gray-600">Claude 3.5 Sonnet (Balanced)</p>
            <p className="text-xl font-bold text-purple-600">$0.63 per 20 min</p>
            <p className="text-xs text-gray-500">~20 queries @ 2K tokens</p>
          </div>
          <div>
            <p className="text-sm text-gray-600">Claude 3.5 Opus (Premium)</p>
            <p className="text-xl font-bold text-red-600">$3.15 per 20 min</p>
            <p className="text-xs text-gray-500">~20 queries @ 2K tokens</p>
          </div>
        </div>
      </div>

      <CostCalculator />
    </div>
  );
}