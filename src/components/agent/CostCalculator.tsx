'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
// import { Slider } from '@/components/ui/slider';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Calculator,
  DollarSign,
  Clock,
  Zap,
  Brain,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  Activity
} from 'lucide-react';

/**
 * CLAUDE 3.5 PRICING BREAKDOWN
 * 
 * Claude 3.5 Sonnet (Most Capable):
 * - Input: $3 per million tokens
 * - Output: $15 per million tokens
 * 
 * Claude 3.5 Haiku (Faster, Cheaper):
 * - Input: $0.25 per million tokens
 * - Output: $1.25 per million tokens
 * 
 * Claude 3.5 Opus (Premium):
 * - Input: $15 per million tokens
 * - Output: $75 per million tokens
 */

interface UsageScenario {
  name: string;
  queriesPerHour: number;
  avgInputTokens: number;
  avgOutputTokens: number;
  description: string;
}

export default function CostCalculator() {
  const [hoursPerDay, setHoursPerDay] = useState(24);
  const [queriesPerMinute, setQueriesPerMinute] = useState(1);
  const [avgInputTokens, setAvgInputTokens] = useState(2000);
  const [avgOutputTokens, setAvgOutputTokens] = useState(1500);
  const [model, setModel] = useState<'sonnet' | 'haiku' | 'opus'>('sonnet');

  // Pricing per million tokens
  const pricing = {
    sonnet: { input: 3, output: 15 },
    haiku: { input: 0.25, output: 1.25 },
    opus: { input: 15, output: 75 }
  };

  // Usage scenarios
  const scenarios: UsageScenario[] = [
    {
      name: 'Light Analysis',
      queriesPerHour: 10,
      avgInputTokens: 1000,
      avgOutputTokens: 800,
      description: 'Basic queries, simple analysis'
    },
    {
      name: 'Active Trading',
      queriesPerHour: 60,
      avgInputTokens: 2000,
      avgOutputTokens: 1500,
      description: 'Real-time market analysis'
    },
    {
      name: 'Deep Research',
      queriesPerHour: 20,
      avgInputTokens: 5000,
      avgOutputTokens: 3000,
      description: 'Comprehensive company analysis'
    },
    {
      name: 'Continuous Learning',
      queriesPerHour: 120,
      avgInputTokens: 1500,
      avgOutputTokens: 1000,
      description: 'Self-learning with feedback loops'
    },
    {
      name: 'Max Throughput',
      queriesPerHour: 600,
      avgInputTokens: 2000,
      avgOutputTokens: 1500,
      description: 'Maximum API usage'
    }
  ];

  // Calculate costs
  const calculateCost = () => {
    const queriesPerHour = queriesPerMinute * 60;
    const totalQueries = queriesPerHour * hoursPerDay;
    
    const totalInputTokens = totalQueries * avgInputTokens;
    const totalOutputTokens = totalQueries * avgOutputTokens;
    
    const inputCost = (totalInputTokens / 1000000) * pricing[model].input;
    const outputCost = (totalOutputTokens / 1000000) * pricing[model].output;
    const totalCost = inputCost + outputCost;
    
    return {
      totalQueries,
      totalInputTokens,
      totalOutputTokens,
      inputCost,
      outputCost,
      totalCost,
      costPerQuery: totalCost / totalQueries,
      costPerHour: totalCost / hoursPerDay
    };
  };

  const costs = calculateCost();

  // Calculate monthly costs
  const dailyCost = costs.totalCost;
  const weeklyCost = dailyCost * 7;
  const monthlyCost = dailyCost * 30;
  const yearlyCost = dailyCost * 365;

  // ROI calculation
  const potentialAlpha = monthlyCost * 10; // Assume 10x return on good analysis
  const breakEvenQueries = Math.ceil(300 / costs.costPerQuery); // Break even on £300 AUM

  return (
    <div className="w-full space-y-6">
      {/* Header Alert */}
      <Alert>
        <Brain className="h-4 w-4" />
        <AlertDescription>
          <strong>Running Claude 3.5 All Night Cost Analysis</strong><br />
          Continuous operation for {hoursPerDay} hours at {queriesPerMinute} queries/minute
        </AlertDescription>
      </Alert>

      {/* Model Selection */}
      <Card>
        <CardHeader>
          <CardTitle>Model Selection</CardTitle>
          <CardDescription>Choose your Claude 3.5 model based on needs and budget</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4">
            <button
              onClick={() => setModel('haiku')}
              className={`p-4 border rounded-lg ${model === 'haiku' ? 'border-blue-500 bg-blue-50' : ''}`}
            >
              <h4 className="font-semibold">Claude 3.5 Haiku</h4>
              <p className="text-sm text-gray-600">Fast & Cheap</p>
              <p className="text-xs mt-2">$0.25/$1.25 per M tokens</p>
              <Badge className="mt-2 bg-green-100 text-green-700">Best Value</Badge>
            </button>
            
            <button
              onClick={() => setModel('sonnet')}
              className={`p-4 border rounded-lg ${model === 'sonnet' ? 'border-purple-500 bg-purple-50' : ''}`}
            >
              <h4 className="font-semibold">Claude 3.5 Sonnet</h4>
              <p className="text-sm text-gray-600">Balanced</p>
              <p className="text-xs mt-2">$3/$15 per M tokens</p>
              <Badge className="mt-2 bg-purple-100 text-purple-700">Recommended</Badge>
            </button>
            
            <button
              onClick={() => setModel('opus')}
              className={`p-4 border rounded-lg ${model === 'opus' ? 'border-red-500 bg-red-50' : ''}`}
            >
              <h4 className="font-semibold">Claude 3.5 Opus</h4>
              <p className="text-sm text-gray-600">Most Capable</p>
              <p className="text-xs mt-2">$15/$75 per M tokens</p>
              <Badge className="mt-2 bg-red-100 text-red-700">Premium</Badge>
            </button>
          </div>
        </CardContent>
      </Card>

      {/* Usage Configuration */}
      <Card>
        <CardHeader>
          <CardTitle>Usage Configuration</CardTitle>
          <CardDescription>Set your expected usage patterns</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <label className="text-sm font-medium">Hours per day: {hoursPerDay}</label>
            <input
              type="range"
              value={hoursPerDay}
              onChange={(e) => setHoursPerDay(parseInt(e.target.value))}
              min={1}
              max={24}
              step={1}
              className="mt-2 w-full"
            />
          </div>
          
          <div>
            <label className="text-sm font-medium">Queries per minute: {queriesPerMinute}</label>
            <input
              type="range"
              value={queriesPerMinute}
              onChange={(e) => setQueriesPerMinute(parseFloat(e.target.value))}
              min={0.1}
              max={10}
              step={0.1}
              className="mt-2 w-full"
            />
          </div>
          
          <div>
            <label className="text-sm font-medium">Avg input tokens: {avgInputTokens}</label>
            <input
              type="range"
              value={avgInputTokens}
              onChange={(e) => setAvgInputTokens(parseInt(e.target.value))}
              min={100}
              max={10000}
              step={100}
              className="mt-2 w-full"
            />
          </div>
          
          <div>
            <label className="text-sm font-medium">Avg output tokens: {avgOutputTokens}</label>
            <input
              type="range"
              value={avgOutputTokens}
              onChange={(e) => setAvgOutputTokens(parseInt(e.target.value))}
              min={100}
              max={5000}
              step={100}
              className="mt-2 w-full"
            />
          </div>
        </CardContent>
      </Card>

      {/* Cost Breakdown */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <DollarSign className="h-5 w-5" />
            Cost Breakdown for {hoursPerDay} Hours
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-600">Total Queries:</span>
                <span className="font-semibold">{costs.totalQueries.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Input Tokens:</span>
                <span className="font-semibold">{(costs.totalInputTokens / 1000000).toFixed(2)}M</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Output Tokens:</span>
                <span className="font-semibold">{(costs.totalOutputTokens / 1000000).toFixed(2)}M</span>
              </div>
            </div>
            
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-600">Input Cost:</span>
                <span className="font-semibold">${costs.inputCost.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Output Cost:</span>
                <span className="font-semibold">${costs.outputCost.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-lg">
                <span className="font-semibold">Total Cost:</span>
                <span className="font-bold text-purple-600">${costs.totalCost.toFixed(2)}</span>
              </div>
            </div>
          </div>
          
          <div className="mt-6 p-4 bg-gray-50 rounded-lg">
            <div className="grid grid-cols-4 gap-4 text-center">
              <div>
                <p className="text-sm text-gray-600">Per Hour</p>
                <p className="text-xl font-bold">${costs.costPerHour.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Per Query</p>
                <p className="text-xl font-bold">${costs.costPerQuery.toFixed(4)}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Per Week</p>
                <p className="text-xl font-bold">${weeklyCost.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Per Month</p>
                <p className="text-xl font-bold text-red-600">${monthlyCost.toFixed(2)}</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 20-Minute Run Analysis */}
      <Card className="border-green-200 bg-green-50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5" />
            20-Minute Sprint Analysis (Optimized)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {(() => {
              const twentyMinQueries = queriesPerMinute * 20;
              const twentyMinInputTokens = twentyMinQueries * avgInputTokens;
              const twentyMinOutputTokens = twentyMinQueries * avgOutputTokens;
              const twentyMinCost = (twentyMinInputTokens * pricing[model].input + 
                                    twentyMinOutputTokens * pricing[model].output) / 1000000;
              const runsPerDay = Math.floor(24 * 60 / 20); // 72 possible 20-min runs per day
              const optimalRunsPerDay = 6; // Every 4 hours
              
              return (
                <>
                  <Alert className="border-green-200">
                    <CheckCircle className="h-4 w-4" />
                    <AlertDescription>
                      <strong>20-Minute Sprint Strategy:</strong><br />
                      • Cost per 20-min run: <strong className="text-green-600">${twentyMinCost.toFixed(2)}</strong><br />
                      • Queries per run: {twentyMinQueries.toFixed(0)}<br />
                      • Perfect for focused analysis sessions<br />
                      • {twentyMinCost < 1 ? '✅ Very affordable - run multiple times daily' : 
                         twentyMinCost < 5 ? '✅ Cost-effective for regular use' : 
                         '⚠️ Consider using Haiku model for sprints'}
                    </AlertDescription>
                  </Alert>

                  <div className="grid grid-cols-3 gap-4">
                    <div className="p-3 bg-white rounded-lg">
                      <h5 className="font-semibold text-sm">Single Sprint</h5>
                      <p className="text-2xl font-bold text-green-600">${twentyMinCost.toFixed(2)}</p>
                      <p className="text-xs text-gray-600">{twentyMinQueries.toFixed(0)} queries</p>
                    </div>
                    
                    <div className="p-3 bg-white rounded-lg">
                      <h5 className="font-semibold text-sm">Daily (6 sprints)</h5>
                      <p className="text-2xl font-bold">${(twentyMinCost * optimalRunsPerDay).toFixed(2)}</p>
                      <p className="text-xs text-gray-600">Every 4 hours</p>
                    </div>
                    
                    <div className="p-3 bg-white rounded-lg">
                      <h5 className="font-semibold text-sm">Monthly</h5>
                      <p className="text-2xl font-bold">${(twentyMinCost * optimalRunsPerDay * 30).toFixed(2)}</p>
                      <p className="text-xs text-gray-600">180 sprints</p>
                    </div>
                  </div>

                  <div className="p-3 bg-blue-50 rounded-lg">
                    <h5 className="font-semibold mb-2">Optimal 20-Minute Sprint Schedule:</h5>
                    <div className="grid grid-cols-3 gap-2 text-sm">
                      <div>• 6:00 AM - Pre-market</div>
                      <div>• 10:00 AM - Market open</div>
                      <div>• 2:00 PM - Midday</div>
                      <div>• 6:00 PM - After hours</div>
                      <div>• 10:00 PM - Asia open</div>
                      <div>• 2:00 AM - Overnight</div>
                    </div>
                    <p className="text-xs text-gray-600 mt-2">
                      Total daily cost: ${(twentyMinCost * 6).toFixed(2)} for comprehensive coverage
                    </p>
                  </div>
                </>
              );
            })()}
          </div>
        </CardContent>
      </Card>

      {/* All Night Specific Analysis */}
      <Card className="border-purple-200 bg-purple-50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Running All Night (24 Hours) Analysis
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <Alert className={dailyCost < 10 ? 'border-green-200' : dailyCost < 50 ? 'border-yellow-200' : 'border-red-200'}>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                <strong>24-Hour Continuous Operation:</strong><br />
                • Model: Claude 3.5 {model.charAt(0).toUpperCase() + model.slice(1)}<br />
                • Total Cost: <strong>${dailyCost.toFixed(2)}/night</strong><br />
                • Queries Processed: {costs.totalQueries.toLocaleString()}<br />
                • Cost per hour: ${costs.costPerHour.toFixed(2)}<br />
                • {dailyCost < 10 ? '✅ Affordable for daily use' : 
                   dailyCost < 50 ? '⚠️ Moderate cost - use strategically' : 
                   '🚨 High cost - optimize usage'}
              </AlertDescription>
            </Alert>

            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 bg-white rounded-lg">
                <h4 className="font-semibold mb-2">Monthly Impact</h4>
                <p className="text-sm text-gray-600">Running every night for 30 days:</p>
                <p className="text-2xl font-bold text-red-600 mt-1">${monthlyCost.toFixed(2)}</p>
                <p className="text-xs text-gray-500 mt-1">
                  {monthlyCost > 1000 ? 'Consider optimization strategies' : 'Manageable for serious trading'}
                </p>
              </div>
              
              <div className="p-4 bg-white rounded-lg">
                <h4 className="font-semibold mb-2">Break-Even Analysis</h4>
                <p className="text-sm text-gray-600">With £300 starting AUM:</p>
                <p className="text-2xl font-bold text-green-600 mt-1">{breakEvenQueries} queries</p>
                <p className="text-xs text-gray-500 mt-1">
                  Queries needed to find one 10x opportunity
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Scenario Comparison */}
      <Card>
        <CardHeader>
          <CardTitle>Usage Scenario Comparison</CardTitle>
          <CardDescription>Common usage patterns and their costs</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {scenarios.map(scenario => {
              const scenarioCost = (scenario.queriesPerHour * 24 * 
                ((scenario.avgInputTokens * pricing[model].input + 
                  scenario.avgOutputTokens * pricing[model].output) / 1000000));
              
              return (
                <div key={scenario.name} className="flex items-center justify-between p-3 border rounded-lg">
                  <div>
                    <p className="font-medium">{scenario.name}</p>
                    <p className="text-sm text-gray-600">{scenario.description}</p>
                    <p className="text-xs text-gray-500">
                      {scenario.queriesPerHour}/hour • {scenario.avgInputTokens}/{scenario.avgOutputTokens} tokens
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-bold">${scenarioCost.toFixed(2)}</p>
                    <p className="text-sm text-gray-600">per 24h</p>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Cost Optimization Tips */}
      <Card>
        <CardHeader>
          <CardTitle>Cost Optimization Strategies</CardTitle>
          <CardDescription>How to reduce costs while maintaining performance</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-3">
              <div className="flex items-start gap-2">
                <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
                <div>
                  <p className="font-medium">Use Haiku for Simple Tasks</p>
                  <p className="text-sm text-gray-600">12x cheaper than Sonnet for basic queries</p>
                </div>
              </div>
              <div className="flex items-start gap-2">
                <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
                <div>
                  <p className="font-medium">Cache Common Responses</p>
                  <p className="text-sm text-gray-600">Save 30-50% on repeated queries</p>
                </div>
              </div>
              <div className="flex items-start gap-2">
                <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
                <div>
                  <p className="font-medium">Batch Similar Queries</p>
                  <p className="text-sm text-gray-600">Process multiple in one API call</p>
                </div>
              </div>
            </div>
            
            <div className="space-y-3">
              <div className="flex items-start gap-2">
                <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
                <div>
                  <p className="font-medium">Compress Context</p>
                  <p className="text-sm text-gray-600">Reduce input tokens by 40%</p>
                </div>
              </div>
              <div className="flex items-start gap-2">
                <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
                <div>
                  <p className="font-medium">Smart Scheduling</p>
                  <p className="text-sm text-gray-600">Run intensive tasks during off-peak</p>
                </div>
              </div>
              <div className="flex items-start gap-2">
                <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
                <div>
                  <p className="font-medium">Set Budget Limits</p>
                  <p className="text-sm text-gray-600">Auto-pause at daily threshold</p>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ROI Analysis */}
      <Card className="border-green-200 bg-green-50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            ROI Justification
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <p className="text-sm">
              With ${monthlyCost.toFixed(2)}/month in AI costs:
            </p>
            <ul className="space-y-2">
              <li className="flex items-start gap-2">
                <span className="text-green-600">•</span>
                <span className="text-sm">Find 1 undervalued position = 10x potential return</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-green-600">•</span>
                <span className="text-sm">Avoid 1 bad investment = Save entire fund</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-green-600">•</span>
                <span className="text-sm">24/7 market monitoring = Never miss opportunities</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-green-600">•</span>
                <span className="text-sm">Process {costs.totalQueries.toLocaleString()} analyses = Superhuman coverage</span>
              </li>
            </ul>
            <div className="p-3 bg-white rounded-lg mt-4">
              <p className="text-sm font-medium">Break-even requirement:</p>
              <p className="text-lg font-bold text-green-600">
                Just ${(monthlyCost * 12).toFixed(0)} in alpha per year
              </p>
              <p className="text-xs text-gray-600">
                Less than 0.1% return on a typical $1M portfolio
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}