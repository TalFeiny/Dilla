'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { 
  TrendingUp, 
  DollarSign, 
  BarChart3, 
  Brain, 
  FileText,
  PieChart,
  Target,
  Zap,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Download,
  RefreshCw,
  Calculator,
  Building2,
  Users,
  TrendingDown,
  MessageSquare
} from 'lucide-react';
import ActivityFeed from '@/components/agent/ActivityFeed';
import AgentChat from '@/components/agent/AgentChat';
import { formatCurrency, formatPercentage, formatMultiple, formatNumber } from '@/lib/format-utils';

interface InvestmentMemo {
  company: string;
  date: string;
  recommendation: 'STRONG_BUY' | 'BUY' | 'HOLD' | 'SELL' | 'PASS';
  irr: number;
  multiple: number;
  thesis: string;
  risks: string[];
  catalysts: string[];
  valuation: {
    current: number;
    intrinsic: number;
    hypeScore: number;
    valueScore: number;
  };
}

interface PortfolioConstruction {
  totalPositions: number;
  allocations: {
    sector: string;
    percentage: number;
    companies: number;
  }[];
  concentration: {
    top5: number;
    top10: number;
  };
  expectedReturns: {
    baseCase: number;
    bullCase: number;
    bearCase: number;
  };
}

export default function AgentCityPage() {
  const [activeTab, setActiveTab] = useState('memos');
  const [isGenerating, setIsGenerating] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(new Date());
  
  // Sample data - this would come from the agent's analysis
  const [investmentMemos, setInvestmentMemos] = useState<InvestmentMemo[]>([
    {
      company: 'TechCo AI',
      date: new Date().toISOString(),
      recommendation: 'STRONG_BUY',
      irr: 87,
      multiple: 5.2,
      thesis: 'Undervalued AI infrastructure play with 150% YoY growth. Trading at 8x ARR vs comps at 15x. Strong moat in GPU optimization.',
      risks: ['Competitive pressure from hyperscalers', 'High customer concentration'],
      catalysts: ['Q1 enterprise launch', 'Partnership with major cloud provider'],
      valuation: {
        current: 250000000,
        intrinsic: 450000000,
        hypeScore: 45,
        valueScore: 85,
      }
    },
    {
      company: 'FinFlow',
      date: new Date().toISOString(),
      recommendation: 'SELL',
      irr: 12,
      multiple: 1.8,
      thesis: 'Overhyped B2B payments play. Burning $5M/month with declining growth. Better opportunities elsewhere.',
      risks: ['Runway < 12 months', 'Regulatory headwinds', 'Commoditized product'],
      catalysts: ['Potential acqui-hire by incumbent'],
      valuation: {
        current: 500000000,
        intrinsic: 280000000,
        hypeScore: 90,
        valueScore: 35,
      }
    }
  ]);

  const portfolioConstruction: PortfolioConstruction = {
    totalPositions: 24,
    allocations: [
      { sector: 'AI/ML Infrastructure', percentage: 35, companies: 8 },
      { sector: 'B2B SaaS', percentage: 25, companies: 6 },
      { sector: 'Fintech', percentage: 20, companies: 5 },
      { sector: 'Healthcare Tech', percentage: 15, companies: 4 },
      { sector: 'Defense Tech', percentage: 5, companies: 1 },
    ],
    concentration: {
      top5: 42,
      top10: 68,
    },
    expectedReturns: {
      baseCase: 3.2,
      bullCase: 5.8,
      bearCase: 1.9,
    }
  };

  const generateMemo = async () => {
    setIsGenerating(true);
    try {
      const response = await fetch('/api/agent/claude', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: 'Generate an investment memo for the most promising opportunity in our pipeline. Include valuation analysis, IRR projections, and key risks.',
          history: []
        }),
      });
      
      const data = await response.json();
      console.log('Generated memo:', data);
      
      // Create a new memo from the response
      if (data.response) {
        const newMemo: InvestmentMemo = {
          company: 'AI-Generated Opportunity',
          date: new Date().toISOString().split('T')[0],
          recommendation: 'BUY',
          irr: 75,
          multiple: 10,
          thesis: data.response.substring(0, 200) + '...',
          risks: ['Market risk', 'Execution risk'],
          catalysts: ['Product launch', 'Market expansion'],
          valuation: {
            current: 10000000,
            intrinsic: 15000000,
            hypeScore: 60,
            valueScore: 80,
          }
        };
        setInvestmentMemos([newMemo, ...investmentMemos]);
      }
      
      setLastUpdate(new Date());
    } catch (error) {
      console.error('Error generating memo:', error);
      alert('Error generating memo. Check console for details.');
    } finally {
      setIsGenerating(false);
    }
  };

  const optimizePortfolio = async () => {
    setIsGenerating(true);
    try {
      const response = await fetch('/api/agent/claude', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: 'Analyze our current portfolio and recommend rebalancing for maximum risk-adjusted returns. Use Kelly Criterion for position sizing.',
          history: []
        }),
      });
      
      const data = await response.json();
      console.log('Portfolio optimization:', data);
      
      // Show the response in an alert for now (you can improve this later)
      if (data.response) {
        alert('Portfolio Optimization Result:\n\n' + data.response.substring(0, 500) + '...\n\n(Check console for full response)');
      }
      
      setLastUpdate(new Date());
    } catch (error) {
      console.error('Error optimizing portfolio:', error);
      alert('Error optimizing portfolio. Check console for details.');
    } finally {
      setIsGenerating(false);
    }
  };

  const getRecommendationColor = (rec: string) => {
    switch(rec) {
      case 'STRONG_BUY': return 'bg-green-600';
      case 'BUY': return 'bg-green-500';
      case 'HOLD': return 'bg-yellow-500';
      case 'SELL': return 'bg-red-500';
      case 'PASS': return 'bg-gray-500';
      default: return 'bg-gray-400';
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
              <Brain className="h-8 w-8 text-gray-600" />
              Agent City Command Center
            </h1>
            <p className="text-gray-600 mt-1">
              AI-Powered Investment Analysis & Portfolio Construction
            </p>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-sm text-gray-500">
              Last updated: {lastUpdate.toLocaleTimeString()}
            </div>
            <Button 
              onClick={() => setLastUpdate(new Date())}
              variant="outline"
              size="sm"
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>
        </div>
      </div>

      {/* Key Metrics Bar */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Portfolio IRR</p>
                <p className="text-2xl font-bold text-green-600">{formatPercentage(52.3)}</p>
              </div>
              <TrendingUp className="h-8 w-8 text-green-600 opacity-20" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Net TVPI</p>
                <p className="text-2xl font-bold">{formatMultiple(3.4)}</p>
              </div>
              <BarChart3 className="h-8 w-8 text-gray-600 opacity-20" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Alpha Opportunities</p>
                <p className="text-2xl font-bold text-gray-600">{formatNumber(7)}</p>
              </div>
              <Target className="h-8 w-8 text-gray-600 opacity-20" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Risk Score</p>
                <p className="text-2xl font-bold text-yellow-600">Medium</p>
              </div>
              <AlertTriangle className="h-8 w-8 text-yellow-600 opacity-20" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="memos" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Investment Memos
          </TabsTrigger>
          <TabsTrigger value="portfolio" className="flex items-center gap-2">
            <PieChart className="h-4 w-4" />
            Portfolio Construction
          </TabsTrigger>
          <TabsTrigger value="pipeline" className="flex items-center gap-2">
            <Target className="h-4 w-4" />
            Deal Pipeline
          </TabsTrigger>
          <TabsTrigger value="analysis" className="flex items-center gap-2">
            <Calculator className="h-4 w-4" />
            Live Analysis
          </TabsTrigger>
          <TabsTrigger value="chat" className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4" />
            AI Assistant
          </TabsTrigger>
        </TabsList>

        {/* Investment Memos Tab */}
        <TabsContent value="memos" className="mt-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">Latest Investment Memos</h2>
            <Button onClick={generateMemo} disabled={isGenerating}>
              {isGenerating ? (
                <>
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <FileText className="h-4 w-4 mr-2" />
                  Generate Memo
                </>
              )}
            </Button>
          </div>
          
          <div className="grid gap-4">
            {investmentMemos.map((memo, index) => (
              <Card key={index} className="overflow-hidden">
                <div className={`h-2 ${getRecommendationColor(memo.recommendation)}`} />
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-xl">{memo.company}</CardTitle>
                      <CardDescription>{new Date(memo.date).toLocaleDateString()}</CardDescription>
                    </div>
                    <div className="text-right">
                      <Badge className={`${getRecommendationColor(memo.recommendation)} text-white`}>
                        {memo.recommendation.replace('_', ' ')}
                      </Badge>
                      <div className="mt-2 space-y-1">
                        <p className="text-sm text-gray-600">Expected IRR</p>
                        <p className="text-2xl font-bold">{formatPercentage(memo.irr)}</p>
                      </div>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {/* Thesis */}
                    <div>
                      <h4 className="font-semibold mb-2">Investment Thesis</h4>
                      <p className="text-sm text-gray-700">{memo.thesis}</p>
                    </div>

                    {/* Valuation */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <h4 className="font-semibold mb-2">Valuation Analysis</h4>
                        <div className="space-y-1 text-sm">
                          <div className="flex justify-between">
                            <span className="text-gray-600">Current:</span>
                            <span className="font-medium">{formatCurrency(memo.valuation.current)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-600">Intrinsic:</span>
                            <span className="font-medium text-green-600">{formatCurrency(memo.valuation.intrinsic)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-600">Upside:</span>
                            <span className="font-bold text-green-600">
                              {formatPercentage((memo.valuation.intrinsic / memo.valuation.current - 1) * 100, 0)}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div>
                        <h4 className="font-semibold mb-2">Hype vs Value</h4>
                        <div className="space-y-2">
                          <div>
                            <div className="flex justify-between text-sm mb-1">
                              <span className="text-gray-600">Hype Score</span>
                              <span>{memo.valuation.hypeScore}/100</span>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-2">
                              <div 
                                className="bg-red-500 h-2 rounded-full"
                                style={{ width: `${memo.valuation.hypeScore}%` }}
                              />
                            </div>
                          </div>
                          <div>
                            <div className="flex justify-between text-sm mb-1">
                              <span className="text-gray-600">Value Score</span>
                              <span>{memo.valuation.valueScore}/100</span>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-2">
                              <div 
                                className="bg-green-500 h-2 rounded-full"
                                style={{ width: `${memo.valuation.valueScore}%` }}
                              />
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Risks & Catalysts */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <h4 className="font-semibold mb-2 flex items-center gap-1">
                          <AlertTriangle className="h-4 w-4 text-red-500" />
                          Key Risks
                        </h4>
                        <ul className="space-y-1">
                          {memo.risks.map((risk, i) => (
                            <li key={i} className="text-sm text-gray-700 flex items-start gap-1">
                              <span className="text-red-500 mt-1">•</span>
                              {risk}
                            </li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <h4 className="font-semibold mb-2 flex items-center gap-1">
                          <Zap className="h-4 w-4 text-green-500" />
                          Catalysts
                        </h4>
                        <ul className="space-y-1">
                          {memo.catalysts.map((catalyst, i) => (
                            <li key={i} className="text-sm text-gray-700 flex items-start gap-1">
                              <span className="text-green-500 mt-1">•</span>
                              {catalyst}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex justify-end gap-2 pt-4 border-t">
                      <Button variant="outline" size="sm">
                        <Download className="h-4 w-4 mr-2" />
                        Export PDF
                      </Button>
                      <Button variant="outline" size="sm">
                        View Full Analysis
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Portfolio Construction Tab */}
        <TabsContent value="portfolio" className="mt-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">Portfolio Construction</h2>
            <Button onClick={optimizePortfolio} disabled={isGenerating}>
              {isGenerating ? (
                <>
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  Optimizing...
                </>
              ) : (
                <>
                  <Calculator className="h-4 w-4 mr-2" />
                  Optimize Portfolio
                </>
              )}
            </Button>
          </div>

          <div className="grid grid-cols-2 gap-6">
            {/* Allocation Chart */}
            <Card>
              <CardHeader>
                <CardTitle>Sector Allocation</CardTitle>
                <CardDescription>Current portfolio composition by sector</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {portfolioConstruction.allocations.map((allocation, i) => (
                    <div key={i}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="font-medium">{allocation.sector}</span>
                        <span className="text-gray-600">
                          {allocation.percentage}% ({allocation.companies} companies)
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-3">
                        <div 
                          className="bg-gradient-to-r from-gray-600 to-gray-700 h-3 rounded-full"
                          style={{ width: `${allocation.percentage}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Concentration Risk */}
            <Card>
              <CardHeader>
                <CardTitle>Concentration Analysis</CardTitle>
                <CardDescription>Portfolio concentration metrics</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div>
                    <p className="text-sm text-gray-600 mb-2">Position Concentration</p>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-gray-50 p-3 rounded-lg">
                        <p className="text-sm text-gray-600">Top 5 Holdings</p>
                        <p className="text-2xl font-bold">{formatPercentage(portfolioConstruction.concentration.top5)}</p>
                      </div>
                      <div className="bg-gray-50 p-3 rounded-lg">
                        <p className="text-sm text-gray-600">Top 10 Holdings</p>
                        <p className="text-2xl font-bold">{formatPercentage(portfolioConstruction.concentration.top10)}</p>
                      </div>
                    </div>
                  </div>
                  
                  <div>
                    <p className="text-sm text-gray-600 mb-2">Expected Portfolio Returns</p>
                    <div className="space-y-2">
                      <div className="flex justify-between p-2 bg-green-50 rounded">
                        <span className="text-sm font-medium">Bull Case</span>
                        <span className="font-bold text-green-600">{formatMultiple(portfolioConstruction.expectedReturns.bullCase)}</span>
                      </div>
                      <div className="flex justify-between p-2 bg-gray-50 rounded">
                        <span className="text-sm font-medium">Base Case</span>
                        <span className="font-bold">{formatMultiple(portfolioConstruction.expectedReturns.baseCase)}</span>
                      </div>
                      <div className="flex justify-between p-2 bg-red-50 rounded">
                        <span className="text-sm font-medium">Bear Case</span>
                        <span className="font-bold text-red-600">{formatMultiple(portfolioConstruction.expectedReturns.bearCase)}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Recommendations */}
            <Card className="col-span-2">
              <CardHeader>
                <CardTitle>AI Recommendations</CardTitle>
                <CardDescription>Optimization suggestions from Agent City</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-4">
                  <div className="p-4 bg-green-50 rounded-lg border border-green-200">
                    <div className="flex items-center gap-2 mb-2">
                      <CheckCircle2 className="h-5 w-5 text-green-600" />
                      <h4 className="font-semibold">Add Position</h4>
                    </div>
                    <p className="text-sm text-gray-700">
                      AI Infrastructure sector underweight. Consider adding 2-3 positions for 15% allocation.
                    </p>
                    <p className="text-xs text-green-600 mt-2">Expected +8% IRR improvement</p>
                  </div>
                  
                  <div className="p-4 bg-yellow-50 rounded-lg border border-yellow-200">
                    <div className="flex items-center gap-2 mb-2">
                      <Clock className="h-5 w-5 text-yellow-600" />
                      <h4 className="font-semibold">Rebalance</h4>
                    </div>
                    <p className="text-sm text-gray-700">
                      Fintech overweight at 20%. Consider trimming 2 positions to reduce concentration risk.
                    </p>
                    <p className="text-xs text-yellow-600 mt-2">Risk reduction: -15% volatility</p>
                  </div>
                  
                  <div className="p-4 bg-red-50 rounded-lg border border-red-200">
                    <div className="flex items-center gap-2 mb-2">
                      <XCircle className="h-5 w-5 text-red-600" />
                      <h4 className="font-semibold">Exit Position</h4>
                    </div>
                    <p className="text-sm text-gray-700">
                      FinFlow showing signs of distress. Exit before further deterioration.
                    </p>
                    <p className="text-xs text-red-600 mt-2">Avoid -30% potential loss</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Deal Pipeline Tab */}
        <TabsContent value="pipeline" className="mt-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">Active Deal Pipeline</h2>
            <Badge variant="outline" className="text-lg px-3 py-1">
              12 Active Deals
            </Badge>
          </div>
          
          <div className="grid gap-4">
            <Card>
              <CardContent className="p-6">
                <div className="space-y-4">
                  {/* Pipeline stages */}
                  <div className="grid grid-cols-5 gap-4">
                    <div className="text-center">
                      <p className="text-3xl font-bold text-gray-400">{formatNumber(32)}</p>
                      <p className="text-sm text-gray-600">Sourced</p>
                    </div>
                    <div className="text-center">
                      <p className="text-3xl font-bold text-gray-600">{formatNumber(18)}</p>
                      <p className="text-sm text-gray-600">Screening</p>
                    </div>
                    <div className="text-center">
                      <p className="text-3xl font-bold text-gray-500">{formatNumber(8)}</p>
                      <p className="text-sm text-gray-600">Diligence</p>
                    </div>
                    <div className="text-center">
                      <p className="text-3xl font-bold text-gray-600">{formatNumber(3)}</p>
                      <p className="text-sm text-gray-600">Term Sheet</p>
                    </div>
                    <div className="text-center">
                      <p className="text-3xl font-bold text-green-600">{formatNumber(1)}</p>
                      <p className="text-sm text-gray-600">Closing</p>
                    </div>
                  </div>
                  
                  {/* Progress bar */}
                  <div className="w-full bg-gray-200 rounded-full h-3 flex overflow-hidden">
                    <div className="bg-gray-400" style={{ width: '20%' }} />
                    <div className="bg-gray-500" style={{ width: '20%' }} />
                    <div className="bg-gray-400" style={{ width: '25%' }} />
                    <div className="bg-gray-600" style={{ width: '25%' }} />
                    <div className="bg-green-600" style={{ width: '10%' }} />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Hot Deals */}
            <div className="grid grid-cols-2 gap-4">
              <Card className="border-l-4 border-green-500">
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle>NeuralStack</CardTitle>
                      <CardDescription>AI Infrastructure • Series B</CardDescription>
                    </div>
                    <Badge className="bg-green-100 text-green-700">HOT</Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-4 mb-3">
                    <div>
                      <p className="text-xs text-gray-600">Valuation</p>
                      <p className="font-semibold">{formatCurrency(180000000)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-600">Expected IRR</p>
                      <p className="font-semibold text-green-600">{formatPercentage(92)}</p>
                    </div>
                  </div>
                  <p className="text-sm text-gray-700">
                    GPU optimization platform with 200% QoQ growth. Strategic partnership with NVIDIA.
                  </p>
                  <div className="mt-3">
                    <p className="text-xs text-gray-600">Agent Confidence</p>
                    <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
                      <div className="bg-green-500 h-2 rounded-full" style={{ width: '85%' }} />
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card className="border-l-4 border-yellow-500">
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle>DataPipe</CardTitle>
                      <CardDescription>Data Infrastructure • Series A</CardDescription>
                    </div>
                    <Badge className="bg-yellow-100 text-yellow-700">REVIEW</Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-4 mb-3">
                    <div>
                      <p className="text-xs text-gray-600">Valuation</p>
                      <p className="font-semibold">{formatCurrency(45000000)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-600">Expected IRR</p>
                      <p className="font-semibold text-yellow-600">{formatPercentage(35)}</p>
                    </div>
                  </div>
                  <p className="text-sm text-gray-700">
                    Real-time ETL platform. Solid product but crowded market. Needs differentiation.
                  </p>
                  <div className="mt-3">
                    <p className="text-xs text-gray-600">Agent Confidence</p>
                    <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
                      <div className="bg-yellow-500 h-2 rounded-full" style={{ width: '60%' }} />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* Live Analysis Tab */}
        <TabsContent value="analysis" className="mt-6">
          <div className="grid grid-cols-2 gap-6">
            {/* Left Column - Alpha Opportunities & Risk Alerts */}
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Live Quantitative Analysis</CardTitle>
                  <CardDescription>Real-time calculations and predictions from Agent City</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-4">
                      <h3 className="font-semibold flex items-center gap-2">
                        <TrendingUp className="h-5 w-5 text-green-600" />
                        Alpha Opportunities
                      </h3>
                      <div className="space-y-2">
                        <div className="p-3 bg-green-50 rounded-lg">
                          <p className="font-medium text-sm">Undervalued: CloudSec</p>
                          <p className="text-xs text-gray-600">Trading at 4x ARR vs 12x sector median</p>
                          <p className="text-xs text-green-600 font-semibold mt-1">{formatPercentage(75)} upside potential</p>
                        </div>
                        <div className="p-3 bg-green-50 rounded-lg">
                          <p className="font-medium text-sm">Mispriced: DevTools Inc</p>
                          <p className="text-xs text-gray-600">150% YoY growth ignored by market</p>
                          <p className="text-xs text-green-600 font-semibold mt-1">{formatPercentage(110)} IRR potential</p>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-4">
                      <h3 className="font-semibold flex items-center gap-2">
                        <AlertTriangle className="h-5 w-5 text-red-600" />
                        Risk Alerts
                      </h3>
                      <div className="space-y-2">
                        <div className="p-3 bg-red-50 rounded-lg">
                          <p className="font-medium text-sm">Overhyped: AIChat Pro</p>
                          <p className="text-xs text-gray-600">Hype score 95/100, Value score 30/100</p>
                          <p className="text-xs text-red-600 font-semibold mt-1">Avoid - {formatPercentage(60)} downside risk</p>
                        </div>
                        <div className="p-3 bg-yellow-50 rounded-lg">
                          <p className="font-medium text-sm">Portfolio Risk: Fintech</p>
                          <p className="text-xs text-gray-600">Sector showing signs of correction</p>
                          <p className="text-xs text-yellow-600 font-semibold mt-1">Consider reducing exposure</p>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-6 space-y-4">
                    <h3 className="font-semibold flex items-center gap-2">
                      <Clock className="h-5 w-5 text-blue-600" />
                      Exit Timing Predictions
                    </h3>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="p-3 bg-blue-50 rounded-lg">
                        <p className="font-medium text-sm">TechCo AI</p>
                        <p className="text-xs text-gray-600">Optimal exit: Q2 2025</p>
                        <p className="text-xs text-blue-600 font-semibold mt-1">Expected {formatMultiple(4.2)} return</p>
                      </div>
                      <div className="p-3 bg-purple-50 rounded-lg">
                        <p className="font-medium text-sm">DataFlow</p>
                        <p className="text-xs text-gray-600">Hold for 18-24 months</p>
                        <p className="text-xs text-purple-600 font-semibold mt-1">Target {formatMultiple(3.5)} multiple</p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Right Column - Live Activity Feed */}
            <div>
              <ActivityFeed />
            </div>
          </div>
        </TabsContent>

        {/* AI Chat Tab */}
        <TabsContent value="chat" className="mt-6">
          <AgentChat 
            sessionId="agent-city"
            onMessageSent={(message) => console.log('Message sent:', message)}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}