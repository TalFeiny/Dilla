'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
// import { Slider } from '@/components/ui/slider';
import { 
  LineChart, 
  Line, 
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Scatter,
  ScatterChart,
  ZAxis
} from 'recharts';
import {
  TrendingUp,
  Target,
  Zap,
  AlertTriangle,
  DollarSign,
  Percent,
  Calendar,
  BarChart3,
  Activity,
  Layers,
  Globe2,
  Brain
} from 'lucide-react';

interface SimulationParams {
  initialAUM: number;
  targetIRR: number;
  timeHorizon: number;
  concentration: number;
  publicAllocation: number;
  hedgeRatio: number;
}

interface PortfolioPosition {
  name: string;
  type: 'private' | 'public' | 'hedge';
  allocation: number;
  currentValue: number;
  irr: number;
  risk: number;
}

export default function PortfolioSimulator() {
  const [params, setParams] = useState<SimulationParams>({
    initialAUM: 300, // £300 starting
    targetIRR: 75,   // 75% target IRR
    timeHorizon: 5,  // 5 years
    concentration: 30, // Top position can be 30% of portfolio
    publicAllocation: 20, // 20% in public markets
    hedgeRatio: 10 // 10% hedging
  });

  const [isSimulating, setIsSimulating] = useState(false);
  const [selectedScenario, setSelectedScenario] = useState<'base' | 'bull' | 'bear'>('base');

  // Generate portfolio growth simulation
  const growthSimulation = useMemo(() => {
    const data = [];
    let value = params.initialAUM;
    
    for (let month = 0; month <= params.timeHorizon * 12; month++) {
      const monthlyReturn = selectedScenario === 'bull' ? 
        (params.targetIRR / 100 / 12) * 1.5 :
        selectedScenario === 'bear' ?
        (params.targetIRR / 100 / 12) * 0.3 :
        (params.targetIRR / 100 / 12);
      
      // Add volatility
      const volatility = (Math.random() - 0.5) * 0.1;
      value = value * (1 + monthlyReturn + volatility);
      
      data.push({
        month,
        year: month / 12,
        value: Math.round(value),
        scenario: selectedScenario,
        irr: ((value / params.initialAUM) ** (12 / (month || 1)) - 1) * 100
      });
    }
    
    return data;
  }, [params, selectedScenario]);

  // Portfolio allocation data
  const allocationData = [
    { name: 'Seed/Series A', value: 40, color: '#10b981' },
    { name: 'Series B+', value: 30, color: '#3b82f6' },
    { name: 'Public Equity', value: params.publicAllocation, color: '#8b5cf6' },
    { name: 'Hedges', value: params.hedgeRatio, color: '#ef4444' },
    { name: 'Cash', value: 20 - params.publicAllocation - params.hedgeRatio, color: '#6b7280' }
  ];

  // Risk/Return scatter data for different strategies
  const strategyComparison = [
    { strategy: 'Our Fund', risk: 35, return: params.targetIRR, size: 300 },
    { strategy: 'VC Index', risk: 30, return: 25, size: 200 },
    { strategy: 'S&P 500', risk: 15, return: 10, size: 150 },
    { strategy: 'Hedge Funds', risk: 20, return: 15, size: 180 },
    { strategy: 'Crypto', risk: 60, return: 100, size: 250 }
  ];

  // Kelly Criterion position sizing
  const kellyPositions = [
    { company: 'AI Infra Play', kelly: 25, current: 20, optimal: 28 },
    { company: 'Fintech Disruptor', kelly: 18, current: 15, optimal: 20 },
    { company: 'Biotech Moonshot', kelly: 8, current: 10, optimal: 8 },
    { company: 'SaaS Compounder', kelly: 15, current: 12, optimal: 17 },
    { company: 'Public Hedges', kelly: 10, current: 10, optimal: 10 }
  ];

  // Monte Carlo paths
  const monteCarloPaths = useMemo(() => {
    const paths = [];
    for (let sim = 0; sim < 100; sim++) {
      const path = [];
      let value = params.initialAUM;
      
      for (let month = 0; month <= params.timeHorizon * 12; month += 6) {
        const drift = params.targetIRR / 100 / 2;
        const volatility = (Math.random() - 0.5) * 0.4;
        value = value * (1 + drift + volatility);
        
        path.push({
          month,
          value: Math.round(value),
          percentile: sim < 10 ? 'p10' : sim < 50 ? 'p50' : 'p90'
        });
      }
      paths.push(path);
    }
    return paths;
  }, [params]);

  // Calculate key metrics
  const finalValue = growthSimulation[growthSimulation.length - 1]?.value || params.initialAUM;
  const totalReturn = ((finalValue / params.initialAUM - 1) * 100).toFixed(1);
  const cagr = ((Math.pow(finalValue / params.initialAUM, 1 / params.timeHorizon) - 1) * 100).toFixed(1);
  
  const runSimulation = () => {
    setIsSimulating(true);
    setTimeout(() => setIsSimulating(false), 2000);
  };

  return (
    <div className="w-full space-y-6">
      {/* Header with key metrics */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Starting AUM</p>
                <p className="text-2xl font-bold">£{params.initialAUM}</p>
              </div>
              <DollarSign className="h-8 w-8 text-green-600 opacity-20" />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Target Value</p>
                <p className="text-2xl font-bold">£{(finalValue / 1000).toFixed(1)}K</p>
              </div>
              <Target className="h-8 w-8 text-purple-600 opacity-20" />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Return</p>
                <p className="text-2xl font-bold text-green-600">{totalReturn}%</p>
              </div>
              <TrendingUp className="h-8 w-8 text-green-600 opacity-20" />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">CAGR</p>
                <p className="text-2xl font-bold">{cagr}%</p>
              </div>
              <Percent className="h-8 w-8 text-blue-600 opacity-20" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Simulation Controls */}
      <Card>
        <CardHeader>
          <CardTitle>Portfolio Simulation Parameters</CardTitle>
          <CardDescription>Adjust parameters to see how £{params.initialAUM} can grow</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-6">
            <div>
              <label className="text-sm font-medium">Target IRR: {params.targetIRR}%</label>
              <input
                type="range"
                value={params.targetIRR}
                onChange={(e) => setParams({...params, targetIRR: parseInt(e.target.value)})}
                min={20}
                max={150}
                step={5}
                className="mt-2 w-full"
              />
            </div>
            
            <div>
              <label className="text-sm font-medium">Time Horizon: {params.timeHorizon} years</label>
              <input
                type="range"
                value={params.timeHorizon}
                onChange={(e) => setParams({...params, timeHorizon: parseInt(e.target.value)})}
                min={1}
                max={10}
                step={1}
                className="mt-2 w-full"
              />
            </div>
            
            <div>
              <label className="text-sm font-medium">Max Concentration: {params.concentration}%</label>
              <input
                type="range"
                value={params.concentration}
                onChange={(e) => setParams({...params, concentration: parseInt(e.target.value)})}
                min={10}
                max={50}
                step={5}
                className="mt-2 w-full"
              />
            </div>
            
            <div>
              <label className="text-sm font-medium">Public Markets: {params.publicAllocation}%</label>
              <input
                type="range"
                value={params.publicAllocation}
                onChange={(e) => setParams({...params, publicAllocation: parseInt(e.target.value)})}
                min={0}
                max={40}
                step={5}
                className="mt-2 w-full"
              />
            </div>
          </div>
          
          <div className="flex items-center gap-4 pt-4">
            <Button onClick={runSimulation} disabled={isSimulating}>
              <Brain className="h-4 w-4 mr-2" />
              {isSimulating ? 'Simulating...' : 'Run Simulation'}
            </Button>
            
            <div className="flex gap-2">
              <Button
                variant={selectedScenario === 'bear' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setSelectedScenario('bear')}
              >
                Bear
              </Button>
              <Button
                variant={selectedScenario === 'base' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setSelectedScenario('base')}
              >
                Base
              </Button>
              <Button
                variant={selectedScenario === 'bull' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setSelectedScenario('bull')}
              >
                Bull
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Growth Projection Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Portfolio Growth Projection</CardTitle>
          <CardDescription>How £{params.initialAUM} grows to £{(finalValue / 1000).toFixed(1)}K</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={growthSimulation}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="year" label={{ value: 'Years', position: 'insideBottom', offset: -5 }} />
              <YAxis label={{ value: 'Portfolio Value (£)', angle: -90, position: 'insideLeft' }} />
              <Tooltip formatter={(value: any) => `£${value}`} />
              <Area 
                type="monotone" 
                dataKey="value" 
                stroke="#10b981" 
                fill="#10b981" 
                fillOpacity={0.3}
              />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 gap-6">
        {/* Portfolio Allocation */}
        <Card>
          <CardHeader>
            <CardTitle>Optimal Allocation</CardTitle>
            <CardDescription>Concentrated bets for maximum alpha</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={allocationData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={(entry) => `${entry.name}: ${entry.value}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {allocationData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Risk/Return Scatter */}
        <Card>
          <CardHeader>
            <CardTitle>Risk/Return Profile</CardTitle>
            <CardDescription>Our edge vs traditional strategies</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <ScatterChart>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="risk" name="Risk" unit="%" />
                <YAxis dataKey="return" name="Return" unit="%" />
                <ZAxis dataKey="size" range={[100, 400]} />
                <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                <Scatter name="Strategies" data={strategyComparison} fill="#8884d8">
                  {strategyComparison.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={index === 0 ? '#10b981' : '#94a3b8'} />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Kelly Criterion Position Sizing */}
      <Card>
        <CardHeader>
          <CardTitle>Kelly Criterion Position Sizing</CardTitle>
          <CardDescription>Mathematically optimal position sizes for maximum growth</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={kellyPositions}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="company" />
              <YAxis label={{ value: 'Allocation %', angle: -90, position: 'insideLeft' }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="current" fill="#94a3b8" name="Current" />
              <Bar dataKey="optimal" fill="#10b981" name="Optimal" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Key Insights */}
      <Card>
        <CardHeader>
          <CardTitle>Simulation Insights</CardTitle>
          <CardDescription>How to turn £{params.initialAUM} into £{(finalValue / 1000).toFixed(1)}K</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 bg-green-50 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="h-5 w-5 text-green-600" />
                <h4 className="font-semibold">Key Success Factors</h4>
              </div>
              <ul className="text-sm space-y-1 text-gray-700">
                <li>• Focus on 3-5 high-conviction positions</li>
                <li>• Target companies with 10x+ potential</li>
                <li>• Use public markets for liquidity and hedging</li>
                <li>• Exit winners at optimal times (3-5x)</li>
                <li>• Reinvest proceeds aggressively</li>
              </ul>
            </div>
            
            <div className="p-4 bg-yellow-50 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="h-5 w-5 text-yellow-600" />
                <h4 className="font-semibold">Risk Management</h4>
              </div>
              <ul className="text-sm space-y-1 text-gray-700">
                <li>• Max {params.concentration}% in single position</li>
                <li>• Maintain {params.hedgeRatio}% hedge ratio</li>
                <li>• Keep 10-20% dry powder for opportunities</li>
                <li>• Use stop losses on public positions</li>
                <li>• Diversify across vintages and sectors</li>
              </ul>
            </div>
          </div>
          
          <div className="mt-4 p-4 bg-blue-50 rounded-lg">
            <p className="text-sm font-medium text-blue-900">
              With {params.targetIRR}% IRR over {params.timeHorizon} years, £{params.initialAUM} becomes £{(finalValue / 1000).toFixed(1)}K.
              This requires hitting 2-3 major winners (10x+) and avoiding complete losses.
              The key is concentrated bets on asymmetric opportunities with limited downside.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}