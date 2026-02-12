'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { cn } from '@/lib/utils';
import {
  LineChart,
  BarChart3,
  PieChart,
  TrendingUp,
  TrendingDown,
  Activity,
  Target,
  Shield,
  AlertTriangle,
  CheckCircle,
  Info,
  Calculator,
  DollarSign,
  Percent,
  Calendar,
  Filter,
  Settings,
  Download,
  Upload,
  RefreshCw,
  Layers,
  Grid3x3,
  GitBranch,
  Zap,
  Eye,
  ChevronRight,
  ChevronDown,
  Plus,
  Minus,
  ArrowUpRight,
  ArrowDownRight,
  Scale,
  Briefcase,
  Building2,
  Globe,
  Map,
  Users,
  Clock,
  Award,
  FileText,
  Database,
  Sparkles,
  Brain,
  Shuffle,
  Lock,
  Unlock,
  BarChart,
  CandlestickChart,
  Sigma,
  Binary,
  Triangle
} from 'lucide-react';

// Portfolio Construction Types
interface Asset {
  id: string;
  name: string;
  ticker?: string;
  assetClass: 'equity' | 'fixed-income' | 'alternatives' | 'real-estate' | 'commodities' | 'cash' | 'crypto' | 'private-equity' | 'hedge-funds';
  sector?: string;
  geography?: string;
  currentWeight: number;
  targetWeight: number;
  minWeight?: number;
  maxWeight?: number;
  expectedReturn: number;
  volatility: number;
  sharpeRatio?: number;
  beta?: number;
  correlation?: Record<string, number>;
  currentValue: number;
  costBasis: number;
  unrealizedGain?: number;
  realizedGain?: number;
  dividendYield?: number;
  expenseRatio?: number;
  liquidityScore?: number; // 1-10
  riskScore?: number; // 1-10
  esgScore?: number; // 0-100
  vintage?: number; // for PE/VC
  commitment?: number; // for PE/VC
  called?: number; // for PE/VC
  distributed?: number; // for PE/VC
}

interface PortfolioMetrics {
  totalValue: number;
  expectedReturn: number;
  volatility: number;
  sharpeRatio: number;
  sortinoRatio?: number;
  maxDrawdown?: number;
  var95?: number; // Value at Risk 95%
  cvar95?: number; // Conditional VaR 95%
  beta: number;
  alpha?: number;
  trackingError?: number;
  informationRatio?: number;
  treynorRatio?: number;
  calmarRatio?: number;
  diversificationRatio?: number;
  effectiveNumberOfBets?: number;
}

interface OptimizationConstraints {
  targetReturn?: number;
  maxVolatility?: number;
  maxDrawdown?: number;
  minLiquidity?: number;
  maxConcentration?: number;
  sectorLimits?: Record<string, { min: number; max: number }>;
  geographyLimits?: Record<string, { min: number; max: number }>;
  assetClassLimits?: Record<string, { min: number; max: number }>;
  esgMinScore?: number;
  turnoverLimit?: number;
  tradingCosts?: number;
  taxRate?: number;
}

interface RiskFactor {
  name: string;
  exposure: number;
  contribution: number;
  sensitivity: number;
}

interface StressScenario {
  name: string;
  description: string;
  marketReturn: number;
  portfolioImpact: number;
  worstAssets: Array<{ asset: string; impact: number }>;
  bestAssets: Array<{ asset: string; impact: number }>;
}

interface RebalancingStrategy {
  type: 'calendar' | 'threshold' | 'tactical' | 'strategic';
  frequency?: 'daily' | 'weekly' | 'monthly' | 'quarterly' | 'annually';
  thresholds?: {
    absolute?: number;
    relative?: number;
  };
  costs: {
    fixed: number;
    variable: number;
    tax: number;
  };
}

interface BacktestResults {
  period: string;
  initialValue: number;
  finalValue: number;
  totalReturn: number;
  annualizedReturn: number;
  volatility: number;
  sharpeRatio: number;
  maxDrawdown: number;
  winRate: number;
  bestMonth: number;
  worstMonth: number;
  numberOfTrades: number;
  totalCosts: number;
}

export default function PortfolioConstructionModels() {
  const [activeView, setActiveView] = useState<'allocation' | 'optimization' | 'risk' | 'performance' | 'rebalancing' | 'backtest'>('allocation');
  const [assets, setAssets] = useState<Asset[]>([
    {
      id: '1',
      name: 'US Large Cap Equity',
      ticker: 'SPY',
      assetClass: 'equity',
      sector: 'Broad Market',
      geography: 'US',
      currentWeight: 0.30,
      targetWeight: 0.35,
      minWeight: 0.25,
      maxWeight: 0.40,
      expectedReturn: 0.10,
      volatility: 0.16,
      sharpeRatio: 0.625,
      beta: 1.0,
      currentValue: 3000000,
      costBasis: 2500000,
      unrealizedGain: 500000,
      dividendYield: 0.018,
      expenseRatio: 0.0009,
      liquidityScore: 10,
      riskScore: 6,
      esgScore: 75
    },
    {
      id: '2',
      name: 'International Developed Equity',
      ticker: 'EFA',
      assetClass: 'equity',
      sector: 'International',
      geography: 'Developed',
      currentWeight: 0.20,
      targetWeight: 0.20,
      minWeight: 0.15,
      maxWeight: 0.25,
      expectedReturn: 0.08,
      volatility: 0.18,
      sharpeRatio: 0.444,
      beta: 0.85,
      currentValue: 2000000,
      costBasis: 1800000,
      unrealizedGain: 200000,
      dividendYield: 0.025,
      expenseRatio: 0.0032,
      liquidityScore: 9,
      riskScore: 7,
      esgScore: 80
    },
    {
      id: '3',
      name: 'Investment Grade Bonds',
      ticker: 'AGG',
      assetClass: 'fixed-income',
      sector: 'Investment Grade',
      geography: 'US',
      currentWeight: 0.25,
      targetWeight: 0.20,
      minWeight: 0.15,
      maxWeight: 0.30,
      expectedReturn: 0.04,
      volatility: 0.04,
      sharpeRatio: 1.0,
      beta: 0.1,
      currentValue: 2500000,
      costBasis: 2450000,
      unrealizedGain: 50000,
      dividendYield: 0.035,
      expenseRatio: 0.0003,
      liquidityScore: 9,
      riskScore: 3,
      esgScore: 70
    },
    {
      id: '4',
      name: 'Real Estate',
      ticker: 'VNQ',
      assetClass: 'real-estate',
      sector: 'REITs',
      geography: 'US',
      currentWeight: 0.10,
      targetWeight: 0.10,
      minWeight: 0.05,
      maxWeight: 0.15,
      expectedReturn: 0.07,
      volatility: 0.19,
      sharpeRatio: 0.368,
      beta: 0.65,
      currentValue: 1000000,
      costBasis: 900000,
      unrealizedGain: 100000,
      dividendYield: 0.038,
      expenseRatio: 0.0012,
      liquidityScore: 8,
      riskScore: 7,
      esgScore: 65
    },
    {
      id: '5',
      name: 'Private Equity Fund',
      assetClass: 'private-equity',
      sector: 'Buyout',
      geography: 'Global',
      currentWeight: 0.10,
      targetWeight: 0.12,
      minWeight: 0.08,
      maxWeight: 0.15,
      expectedReturn: 0.15,
      volatility: 0.25,
      sharpeRatio: 0.6,
      beta: 1.2,
      currentValue: 1000000,
      costBasis: 800000,
      unrealizedGain: 200000,
      liquidityScore: 2,
      riskScore: 8,
      vintage: 2020,
      commitment: 1500000,
      called: 1000000,
      distributed: 200000
    },
    {
      id: '6',
      name: 'Commodities',
      ticker: 'DJP',
      assetClass: 'commodities',
      sector: 'Broad Basket',
      geography: 'Global',
      currentWeight: 0.05,
      targetWeight: 0.03,
      minWeight: 0.02,
      maxWeight: 0.08,
      expectedReturn: 0.05,
      volatility: 0.20,
      sharpeRatio: 0.25,
      beta: 0.3,
      currentValue: 500000,
      costBasis: 520000,
      unrealizedGain: -20000,
      expenseRatio: 0.0089,
      liquidityScore: 7,
      riskScore: 8,
      esgScore: 40
    }
  ]);

  const [portfolioMetrics, setPortfolioMetrics] = useState<PortfolioMetrics>({
    totalValue: 10000000,
    expectedReturn: 0.085,
    volatility: 0.12,
    sharpeRatio: 0.708,
    sortinoRatio: 0.95,
    maxDrawdown: -0.18,
    var95: -1200000,
    cvar95: -1500000,
    beta: 0.75,
    alpha: 0.02,
    trackingError: 0.04,
    informationRatio: 0.5,
    treynorRatio: 0.113,
    calmarRatio: 0.472,
    diversificationRatio: 1.8,
    effectiveNumberOfBets: 4.2
  });

  const [constraints, setConstraints] = useState<OptimizationConstraints>({
    targetReturn: 0.08,
    maxVolatility: 0.15,
    maxDrawdown: 0.20,
    minLiquidity: 7,
    maxConcentration: 0.40,
    esgMinScore: 60,
    turnoverLimit: 0.30,
    tradingCosts: 0.001,
    taxRate: 0.20
  });

  const [riskFactors, setRiskFactors] = useState<RiskFactor[]>([
    { name: 'Market Risk', exposure: 0.65, contribution: 0.52, sensitivity: 0.8 },
    { name: 'Interest Rate Risk', exposure: 0.25, contribution: 0.10, sensitivity: -0.3 },
    { name: 'Credit Risk', exposure: 0.20, contribution: 0.08, sensitivity: 0.4 },
    { name: 'Currency Risk', exposure: 0.20, contribution: 0.15, sensitivity: 0.5 },
    { name: 'Liquidity Risk', exposure: 0.15, contribution: 0.10, sensitivity: 0.6 },
    { name: 'Inflation Risk', exposure: 0.30, contribution: 0.05, sensitivity: 0.2 }
  ]);

  const [stressScenarios, setStressScenarios] = useState<StressScenario[]>([
    {
      name: '2008 Financial Crisis',
      description: 'Global financial meltdown',
      marketReturn: -0.37,
      portfolioImpact: -0.22,
      worstAssets: [
        { asset: 'US Large Cap Equity', impact: -0.37 },
        { asset: 'Real Estate', impact: -0.35 }
      ],
      bestAssets: [
        { asset: 'Investment Grade Bonds', impact: 0.05 },
        { asset: 'Cash', impact: 0.00 }
      ]
    },
    {
      name: 'COVID-19 Pandemic',
      description: 'March 2020 market crash',
      marketReturn: -0.34,
      portfolioImpact: -0.18,
      worstAssets: [
        { asset: 'Real Estate', impact: -0.40 },
        { asset: 'Commodities', impact: -0.35 }
      ],
      bestAssets: [
        { asset: 'Investment Grade Bonds', impact: 0.03 },
        { asset: 'US Large Cap Equity', impact: -0.20 }
      ]
    },
    {
      name: 'Rising Rates',
      description: '+200bps rate increase',
      marketReturn: -0.10,
      portfolioImpact: -0.08,
      worstAssets: [
        { asset: 'Investment Grade Bonds', impact: -0.08 },
        { asset: 'Real Estate', impact: -0.12 }
      ],
      bestAssets: [
        { asset: 'Cash', impact: 0.02 },
        { asset: 'Commodities', impact: 0.05 }
      ]
    }
  ]);

  const [rebalancingStrategy, setRebalancingStrategy] = useState<RebalancingStrategy>({
    type: 'threshold',
    thresholds: {
      absolute: 0.05,
      relative: 0.20
    },
    costs: {
      fixed: 10,
      variable: 0.001,
      tax: 0.15
    }
  });

  const [isOptimizing, setIsOptimizing] = useState(false);
  const [selectedAsset, setSelectedAsset] = useState<string | null>(null);

  // Calculate correlation matrix
  const correlationMatrix = useMemo(() => {
    const matrix: Record<string, Record<string, number>> = {};
    
    // Sample correlation matrix (in practice, calculate from historical data)
    const correlations = {
      'equity-equity': 0.85,
      'equity-fixed': -0.15,
      'equity-real': 0.65,
      'equity-comm': 0.40,
      'fixed-real': 0.20,
      'fixed-comm': -0.10,
      'real-comm': 0.30
    };
    
    assets.forEach(asset1 => {
      matrix[asset1.id] = {};
      assets.forEach(asset2 => {
        if (asset1.id === asset2.id) {
          matrix[asset1.id][asset2.id] = 1.0;
        } else {
          // Simplified correlation based on asset class
          const key = [asset1.assetClass, asset2.assetClass].sort().join('-');
          matrix[asset1.id][asset2.id] = correlations[key] || 0.3;
        }
      });
    });
    
    return matrix;
  }, [assets]);

  // Run portfolio optimization
  const runOptimization = useCallback(() => {
    setIsOptimizing(true);
    
    // Simulate optimization (in practice, use mean-variance optimization)
    setTimeout(() => {
      const optimizedAssets = assets.map(asset => {
        // Simple target weight adjustment based on Sharpe ratio
        const sharpeWeight = (asset.sharpeRatio || 0.5) / 2;
        const targetWeight = Math.min(
          asset.maxWeight || 1,
          Math.max(
            asset.minWeight || 0,
            sharpeWeight * (1 / assets.length)
          )
        );
        
        return {
          ...asset,
          targetWeight
        };
      });
      
      // Normalize weights
      const totalWeight = optimizedAssets.reduce((sum, a) => sum + a.targetWeight, 0);
      optimizedAssets.forEach(asset => {
        asset.targetWeight = asset.targetWeight / totalWeight;
      });
      
      setAssets(optimizedAssets);
      setIsOptimizing(false);
    }, 2000);
  }, [assets]);

  // Calculate efficient frontier
  const efficientFrontier = useMemo(() => {
    const points = [];
    for (let targetReturn = 0.02; targetReturn <= 0.15; targetReturn += 0.01) {
      // Simplified calculation
      const risk = targetReturn * 1.8; // Simplified risk calculation
      points.push({
        return: targetReturn,
        risk,
        sharpe: targetReturn / risk
      });
    }
    return points;
  }, []);

  // Render Asset Allocation View
  const renderAllocation = () => (
    <div className="space-y-6">
      {/* Portfolio Summary */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg p-6 text-white">
        <div className="grid grid-cols-5 gap-6">
          <div>
            <div className="text-sm text-blue-100">Total Value</div>
            <div className="text-2xl font-bold">${(portfolioMetrics.totalValue / 1000000).toFixed(1)}M</div>
          </div>
          <div>
            <div className="text-sm text-blue-100">Expected Return</div>
            <div className="text-2xl font-bold">{(portfolioMetrics.expectedReturn * 100).toFixed(1)}%</div>
          </div>
          <div>
            <div className="text-sm text-blue-100">Volatility</div>
            <div className="text-2xl font-bold">{(portfolioMetrics.volatility * 100).toFixed(1)}%</div>
          </div>
          <div>
            <div className="text-sm text-blue-100">Sharpe Ratio</div>
            <div className="text-2xl font-bold">{portfolioMetrics.sharpeRatio.toFixed(2)}</div>
          </div>
          <div>
            <div className="text-sm text-blue-100">Max Drawdown</div>
            <div className="text-2xl font-bold">{(portfolioMetrics.maxDrawdown * 100).toFixed(1)}%</div>
          </div>
        </div>
      </div>

      {/* Asset Allocation Table */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="p-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold">Asset Allocation</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-700">Asset</th>
                <th className="text-center px-4 py-3 text-sm font-medium text-gray-700">Class</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-gray-700">Current %</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-gray-700">Target %</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-gray-700">Drift</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-gray-700">Value</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-gray-700">P&L</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-gray-700">Return</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-gray-700">Risk</th>
                <th className="text-center px-4 py-3 text-sm font-medium text-gray-700">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {assets.map(asset => {
                const drift = asset.currentWeight - asset.targetWeight;
                const returnPct = ((asset.currentValue - asset.costBasis) / asset.costBasis) * 100;
                
                return (
                  <tr key={asset.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div>
                        <div className="font-medium text-sm">{asset.name}</div>
                        {asset.ticker && <div className="text-xs text-gray-500">{asset.ticker}</div>}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={cn(
                        "px-2 py-1 rounded text-xs font-medium",
                        asset.assetClass === 'equity' && "bg-blue-100 text-blue-700",
                        asset.assetClass === 'fixed-income' && "bg-green-100 text-green-700",
                        asset.assetClass === 'alternatives' && "bg-purple-100 text-purple-700",
                        asset.assetClass === 'real-estate' && "bg-orange-100 text-orange-700",
                        asset.assetClass === 'commodities' && "bg-yellow-100 text-yellow-700",
                        asset.assetClass === 'private-equity' && "bg-indigo-100 text-indigo-700"
                      )}>
                        {asset.assetClass}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-medium">
                      {(asset.currentWeight * 100).toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 text-right">
                      <input
                        type="number"
                        value={(asset.targetWeight * 100).toFixed(1)}
                        onChange={(e) => {
                          const newAssets = Array.from(assets);
                          const index = newAssets.findIndex(a => a.id === asset.id);
                          newAssets[index].targetWeight = Number(e.target.value) / 100;
                          setAssets(newAssets);
                        }}
                        className="w-16 px-2 py-1 text-sm border rounded text-right"
                        step="0.1"
                      />
                    </td>
                    <td className={cn(
                      "px-4 py-3 text-right font-medium",
                      Math.abs(drift) > 0.02 && "text-orange-600",
                      Math.abs(drift) > 0.05 && "text-red-600"
                    )}>
                      {drift > 0 ? '+' : ''}{(drift * 100).toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 text-right">
                      ${(asset.currentValue / 1000000).toFixed(2)}M
                    </td>
                    <td className={cn(
                      "px-4 py-3 text-right font-medium",
                      returnPct >= 0 ? "text-green-600" : "text-red-600"
                    )}>
                      {returnPct >= 0 ? '+' : ''}{returnPct.toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 text-right">
                      {(asset.expectedReturn * 100).toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 text-right">
                      {(asset.volatility * 100).toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 text-center">
                      {Math.abs(drift) > 0.02 && (
                        <span className={cn(
                          "px-2 py-1 rounded text-xs font-medium",
                          drift > 0 ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"
                        )}>
                          {drift > 0 ? 'Sell' : 'Buy'}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot className="bg-gray-50 border-t">
              <tr className="font-medium">
                <td colSpan={2} className="px-4 py-3">Total</td>
                <td className="px-4 py-3 text-right">
                  {(assets.reduce((sum, a) => sum + a.currentWeight, 0) * 100).toFixed(1)}%
                </td>
                <td className="px-4 py-3 text-right">
                  {(assets.reduce((sum, a) => sum + a.targetWeight, 0) * 100).toFixed(1)}%
                </td>
                <td className="px-4 py-3"></td>
                <td className="px-4 py-3 text-right">
                  ${(assets.reduce((sum, a) => sum + a.currentValue, 0) / 1000000).toFixed(2)}M
                </td>
                <td colSpan={4} className="px-4 py-3"></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      {/* Allocation Charts */}
      <div className="grid grid-cols-2 gap-6">
        {/* Current vs Target Allocation */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold mb-4">Current vs Target Allocation</h3>
          <div className="space-y-4">
            {assets.map(asset => (
              <div key={asset.id}>
                <div className="flex justify-between text-sm mb-1">
                  <span>{asset.name}</span>
                  <span className="text-gray-600">
                    {(asset.currentWeight * 100).toFixed(1)}% → {(asset.targetWeight * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="relative h-6 bg-gray-100 rounded overflow-hidden">
                  <div 
                    className="absolute left-0 top-0 h-full bg-blue-200"
                    style={{ width: `${asset.currentWeight * 100}%` }}
                  />
                  <div 
                    className="absolute left-0 top-0 h-3 bg-blue-600"
                    style={{ width: `${asset.targetWeight * 100}%` }}
                  />
                </div>
              </div>
            ))}
            <div className="flex items-center justify-center gap-4 pt-2 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-blue-200 rounded" />
                <span>Current</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-blue-600 rounded" />
                <span>Target</span>
              </div>
            </div>
          </div>
        </div>

        {/* Asset Class Distribution */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold mb-4">Asset Class Distribution</h3>
          <div className="space-y-3">
            {Object.entries(
              assets.reduce((acc, asset) => {
                const key = asset.assetClass;
                if (!acc[key]) acc[key] = { weight: 0, value: 0, count: 0 };
                acc[key].weight += asset.currentWeight;
                acc[key].value += asset.currentValue;
                acc[key].count += 1;
                return acc;
              }, {} as Record<string, { weight: number; value: number; count: number }>)
            ).map(([assetClass, data]) => (
              <div key={assetClass} className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={cn(
                    "w-3 h-3 rounded-full",
                    assetClass === 'equity' && "bg-blue-500",
                    assetClass === 'fixed-income' && "bg-green-500",
                    assetClass === 'real-estate' && "bg-orange-500",
                    assetClass === 'commodities' && "bg-yellow-500",
                    assetClass === 'private-equity' && "bg-indigo-500"
                  )} />
                  <span className="text-sm font-medium capitalize">{assetClass.replace('-', ' ')}</span>
                  <span className="text-xs text-gray-500">({data.count})</span>
                </div>
                <div className="text-right">
                  <div className="text-sm font-medium">{(data.weight * 100).toFixed(1)}%</div>
                  <div className="text-xs text-gray-500">${(data.value / 1000000).toFixed(1)}M</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  // Render Optimization View
  const renderOptimization = () => (
    <div className="space-y-6">
      {/* Optimization Controls */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold mb-4">Optimization Parameters</h3>
        <div className="grid grid-cols-3 gap-6">
          <div>
            <label className="text-sm font-medium text-gray-700">Target Return</label>
            <div className="mt-1 flex items-center gap-2">
              <input
                type="number"
                value={(constraints.targetReturn || 0) * 100}
                onChange={(e) => setConstraints(prev => ({ ...prev, targetReturn: Number(e.target.value) / 100 }))}
                className="flex-1 px-3 py-2 border border-gray-200 rounded-lg"
                step="0.1"
              />
              <span className="text-sm text-gray-600">%</span>
            </div>
          </div>
          
          <div>
            <label className="text-sm font-medium text-gray-700">Max Volatility</label>
            <div className="mt-1 flex items-center gap-2">
              <input
                type="number"
                value={(constraints.maxVolatility || 0) * 100}
                onChange={(e) => setConstraints(prev => ({ ...prev, maxVolatility: Number(e.target.value) / 100 }))}
                className="flex-1 px-3 py-2 border border-gray-200 rounded-lg"
                step="0.1"
              />
              <span className="text-sm text-gray-600">%</span>
            </div>
          </div>
          
          <div>
            <label className="text-sm font-medium text-gray-700">Max Concentration</label>
            <div className="mt-1 flex items-center gap-2">
              <input
                type="number"
                value={(constraints.maxConcentration || 0) * 100}
                onChange={(e) => setConstraints(prev => ({ ...prev, maxConcentration: Number(e.target.value) / 100 }))}
                className="flex-1 px-3 py-2 border border-gray-200 rounded-lg"
                step="1"
              />
              <span className="text-sm text-gray-600">%</span>
            </div>
          </div>
          
          <div>
            <label className="text-sm font-medium text-gray-700">Min ESG Score</label>
            <input
              type="number"
              value={constraints.esgMinScore || 0}
              onChange={(e) => setConstraints(prev => ({ ...prev, esgMinScore: Number(e.target.value) }))}
              className="w-full mt-1 px-3 py-2 border border-gray-200 rounded-lg"
            />
          </div>
          
          <div>
            <label className="text-sm font-medium text-gray-700">Turnover Limit</label>
            <div className="mt-1 flex items-center gap-2">
              <input
                type="number"
                value={(constraints.turnoverLimit || 0) * 100}
                onChange={(e) => setConstraints(prev => ({ ...prev, turnoverLimit: Number(e.target.value) / 100 }))}
                className="flex-1 px-3 py-2 border border-gray-200 rounded-lg"
                step="1"
              />
              <span className="text-sm text-gray-600">%</span>
            </div>
          </div>
          
          <div>
            <label className="text-sm font-medium text-gray-700">Trading Costs</label>
            <div className="mt-1 flex items-center gap-2">
              <input
                type="number"
                value={(constraints.tradingCosts || 0) * 100}
                onChange={(e) => setConstraints(prev => ({ ...prev, tradingCosts: Number(e.target.value) / 100 }))}
                className="flex-1 px-3 py-2 border border-gray-200 rounded-lg"
                step="0.01"
              />
              <span className="text-sm text-gray-600">%</span>
            </div>
          </div>
        </div>
        
        <div className="mt-6 flex justify-end">
          <button
            onClick={runOptimization}
            disabled={isOptimizing}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
          >
            {isOptimizing ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Optimizing...
              </>
            ) : (
              <>
                <Brain className="w-4 h-4" />
                Run Optimization
              </>
            )}
          </button>
        </div>
      </div>

      {/* Efficient Frontier */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold mb-4">Efficient Frontier</h3>
        <div className="relative h-64">
          {/* Simplified visualization - in practice use a charting library */}
          <div className="absolute inset-0 border-l-2 border-b-2 border-gray-300">
            <svg className="w-full h-full">
              {/* Efficient frontier curve */}
              <path
                d={`M ${efficientFrontier.map((point, i) => 
                  `${(point.risk * 500)},${ 256 - (point.return * 1500)}`
                ).join(' L ')}`}
                fill="none"
                stroke="rgb(59, 130, 246)"
                strokeWidth="2"
              />
              
              {/* Current portfolio position */}
              <circle
                cx={portfolioMetrics.volatility * 500}
                cy={256 - (portfolioMetrics.expectedReturn * 1500)}
                r="6"
                fill="rgb(239, 68, 68)"
              />
              
              {/* Individual assets */}
              {assets.map((asset, i) => (
                <circle
                  key={asset.id}
                  cx={asset.volatility * 500}
                  cy={256 - (asset.expectedReturn * 1500)}
                  r="4"
                  fill="rgb(156, 163, 175)"
                />
              ))}
            </svg>
          </div>
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 text-xs text-gray-600">Risk →</div>
          <div className="absolute top-1/2 left-0 -translate-y-1/2 -rotate-90 text-xs text-gray-600">Return →</div>
        </div>
        <div className="flex items-center justify-center gap-6 mt-4 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-blue-500 rounded-full" />
            <span>Efficient Frontier</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-red-500 rounded-full" />
            <span>Current Portfolio</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-gray-400 rounded-full" />
            <span>Individual Assets</span>
          </div>
        </div>
      </div>

      {/* Correlation Matrix */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold mb-4">Correlation Matrix</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr>
                <th className="p-2 text-left"></th>
                {assets.map(asset => (
                  <th key={asset.id} className="p-2 text-center font-medium">
                    {asset.ticker || asset.name.substring(0, 3).toUpperCase()}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {assets.map(asset1 => (
                <tr key={asset1.id}>
                  <td className="p-2 font-medium">
                    {asset1.ticker || asset1.name.substring(0, 3).toUpperCase()}
                  </td>
                  {assets.map(asset2 => {
                    const corr = correlationMatrix[asset1.id]?.[asset2.id] || 0;
                    return (
                      <td 
                        key={asset2.id} 
                        className={cn(
                          "p-2 text-center",
                          corr === 1 && "bg-blue-600 text-white",
                          corr > 0.7 && corr < 1 && "bg-blue-400 text-white",
                          corr > 0.3 && corr <= 0.7 && "bg-blue-200",
                          corr > -0.3 && corr <= 0.3 && "bg-gray-100",
                          corr > -0.7 && corr <= -0.3 && "bg-red-200",
                          corr <= -0.7 && "bg-red-400 text-white"
                        )}
                      >
                        {corr.toFixed(2)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );

  // Render Risk Analysis View
  const renderRiskAnalysis = () => (
    <div className="space-y-6">
      {/* Risk Metrics */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-600">VaR (95%)</span>
            <AlertTriangle className="w-4 h-4 text-orange-500" />
          </div>
          <div className="text-2xl font-bold text-red-600">
            -${Math.abs(portfolioMetrics.var95 || 0) / 1000000}M
          </div>
          <div className="text-xs text-gray-500 mt-1">1-day potential loss</div>
        </div>
        
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-600">CVaR (95%)</span>
            <AlertTriangle className="w-4 h-4 text-red-500" />
          </div>
          <div className="text-2xl font-bold text-red-600">
            -${Math.abs(portfolioMetrics.cvar95 || 0) / 1000000}M
          </div>
          <div className="text-xs text-gray-500 mt-1">Expected shortfall</div>
        </div>
        
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-600">Max Drawdown</span>
            <TrendingDown className="w-4 h-4 text-red-500" />
          </div>
          <div className="text-2xl font-bold text-red-600">
            {(portfolioMetrics.maxDrawdown * 100).toFixed(1)}%
          </div>
          <div className="text-xs text-gray-500 mt-1">Historical worst</div>
        </div>
        
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-600">Tracking Error</span>
            <Activity className="w-4 h-4 text-blue-500" />
          </div>
          <div className="text-2xl font-bold">
            {((portfolioMetrics.trackingError || 0) * 100).toFixed(1)}%
          </div>
          <div className="text-xs text-gray-500 mt-1">vs Benchmark</div>
        </div>
      </div>

      {/* Risk Factor Analysis */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold mb-4">Risk Factor Decomposition</h3>
        <div className="space-y-3">
          {riskFactors.map(factor => (
            <div key={factor.name}>
              <div className="flex justify-between items-center mb-1">
                <span className="text-sm font-medium">{factor.name}</span>
                <div className="flex items-center gap-4 text-sm">
                  <span>Exposure: {(factor.exposure * 100).toFixed(0)}%</span>
                  <span>Contribution: {(factor.contribution * 100).toFixed(0)}%</span>
                </div>
              </div>
              <div className="relative h-6 bg-gray-100 rounded overflow-hidden">
                <div 
                  className={cn(
                    "absolute left-0 top-0 h-full",
                    factor.sensitivity > 0 ? "bg-red-500" : "bg-green-500"
                  )}
                  style={{ width: `${Math.abs(factor.contribution) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Stress Testing */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold mb-4">Stress Test Scenarios</h3>
        <div className="space-y-4">
          {stressScenarios.map(scenario => (
            <div key={scenario.name} className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h4 className="font-medium">{scenario.name}</h4>
                  <p className="text-sm text-gray-600">{scenario.description}</p>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-red-600">
                    {(scenario.portfolioImpact * 100).toFixed(1)}%
                  </div>
                  <div className="text-xs text-gray-500">Portfolio Impact</div>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs font-medium text-gray-700 mb-2">Worst Performers</div>
                  <div className="space-y-1">
                    {scenario.worstAssets.map(asset => (
                      <div key={asset.asset} className="flex justify-between text-xs">
                        <span className="text-gray-600">{asset.asset}</span>
                        <span className="text-red-600 font-medium">
                          {(asset.impact * 100).toFixed(1)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="text-xs font-medium text-gray-700 mb-2">Best Performers</div>
                  <div className="space-y-1">
                    {scenario.bestAssets.map(asset => (
                      <div key={asset.asset} className="flex justify-between text-xs">
                        <span className="text-gray-600">{asset.asset}</span>
                        <span className={cn(
                          "font-medium",
                          asset.impact >= 0 ? "text-green-600" : "text-red-600"
                        )}>
                          {asset.impact >= 0 && '+'}{(asset.impact * 100).toFixed(1)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  // Render Performance View
  const renderPerformance = () => (
    <div className="space-y-6">
      {/* Performance Metrics Grid */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-600">Total Return</span>
            <TrendingUp className="w-4 h-4 text-green-500" />
          </div>
          <div className="text-2xl font-bold text-green-600">
            +{((portfolioMetrics.totalValue - 8500000) / 8500000 * 100).toFixed(1)}%
          </div>
          <div className="text-xs text-gray-500 mt-1">Since inception</div>
        </div>
        
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-600">Sharpe Ratio</span>
            <Award className="w-4 h-4 text-blue-500" />
          </div>
          <div className="text-2xl font-bold">
            {portfolioMetrics.sharpeRatio.toFixed(2)}
          </div>
          <div className="text-xs text-gray-500 mt-1">Risk-adjusted return</div>
        </div>
        
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-600">Alpha</span>
            <Sparkles className="w-4 h-4 text-purple-500" />
          </div>
          <div className="text-2xl font-bold text-purple-600">
            {((portfolioMetrics.alpha || 0) * 100).toFixed(1)}%
          </div>
          <div className="text-xs text-gray-500 mt-1">Excess return</div>
        </div>
        
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-600">Information Ratio</span>
            <Target className="w-4 h-4 text-indigo-500" />
          </div>
          <div className="text-2xl font-bold">
            {(portfolioMetrics.informationRatio || 0).toFixed(2)}
          </div>
          <div className="text-xs text-gray-500 mt-1">Active return / TE</div>
        </div>
      </div>

      {/* Attribution Analysis */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold mb-4">Performance Attribution</h3>
        <div className="space-y-4">
          <div>
            <div className="flex justify-between text-sm mb-2">
              <span className="font-medium">Asset Allocation Effect</span>
              <span className="text-green-600 font-medium">+2.3%</span>
            </div>
            <div className="h-2 bg-gray-100 rounded overflow-hidden">
              <div className="h-full bg-green-500" style={{ width: '60%' }} />
            </div>
          </div>
          
          <div>
            <div className="flex justify-between text-sm mb-2">
              <span className="font-medium">Security Selection Effect</span>
              <span className="text-green-600 font-medium">+1.8%</span>
            </div>
            <div className="h-2 bg-gray-100 rounded overflow-hidden">
              <div className="h-full bg-green-500" style={{ width: '45%' }} />
            </div>
          </div>
          
          <div>
            <div className="flex justify-between text-sm mb-2">
              <span className="font-medium">Currency Effect</span>
              <span className="text-red-600 font-medium">-0.5%</span>
            </div>
            <div className="h-2 bg-gray-100 rounded overflow-hidden">
              <div className="h-full bg-red-500" style={{ width: '12%' }} />
            </div>
          </div>
          
          <div>
            <div className="flex justify-between text-sm mb-2">
              <span className="font-medium">Trading Costs</span>
              <span className="text-red-600 font-medium">-0.3%</span>
            </div>
            <div className="h-2 bg-gray-100 rounded overflow-hidden">
              <div className="h-full bg-red-500" style={{ width: '8%' }} />
            </div>
          </div>
          
          <div className="pt-3 border-t">
            <div className="flex justify-between font-medium">
              <span>Total Active Return</span>
              <span className="text-green-600">+3.3%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Rolling Performance */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold mb-4">Rolling Performance</h3>
        <div className="grid grid-cols-5 gap-4">
          <div className="text-center">
            <div className="text-xs text-gray-600 mb-1">1 Month</div>
            <div className="text-lg font-bold text-green-600">+2.1%</div>
          </div>
          <div className="text-center">
            <div className="text-xs text-gray-600 mb-1">3 Months</div>
            <div className="text-lg font-bold text-green-600">+5.3%</div>
          </div>
          <div className="text-center">
            <div className="text-xs text-gray-600 mb-1">6 Months</div>
            <div className="text-lg font-bold text-green-600">+8.7%</div>
          </div>
          <div className="text-center">
            <div className="text-xs text-gray-600 mb-1">1 Year</div>
            <div className="text-lg font-bold text-green-600">+12.4%</div>
          </div>
          <div className="text-center">
            <div className="text-xs text-gray-600 mb-1">3 Years</div>
            <div className="text-lg font-bold text-green-600">+28.6%</div>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-gray-900">Portfolio Construction Models</h1>
            <div className="flex items-center gap-2">
              <button className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 flex items-center gap-2">
                <Download className="w-4 h-4" />
                Export Report
              </button>
              <button className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2">
                <Settings className="w-4 h-4" />
                Configure
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex gap-6">
            {[
              { id: 'allocation', label: 'Asset Allocation', icon: PieChart },
              { id: 'optimization', label: 'Optimization', icon: Brain },
              { id: 'risk', label: 'Risk Analysis', icon: Shield },
              { id: 'performance', label: 'Performance', icon: TrendingUp },
              { id: 'rebalancing', label: 'Rebalancing', icon: Scale },
              { id: 'backtest', label: 'Backtest', icon: Clock }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveView(tab.id as any)}
                className={cn(
                  "py-3 px-1 border-b-2 font-medium text-sm transition-colors flex items-center gap-2",
                  activeView === tab.id
                    ? "border-blue-600 text-blue-600"
                    : "border-transparent text-gray-500 hover:text-gray-700"
                )}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-6 py-6">
        {activeView === 'allocation' && renderAllocation()}
        {activeView === 'optimization' && renderOptimization()}
        {activeView === 'risk' && renderRiskAnalysis()}
        {activeView === 'performance' && renderPerformance()}
      </div>
    </div>
  );
}