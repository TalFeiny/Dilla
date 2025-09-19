'use client';

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Company, PWERMResult, PWERMPlaygroundConfig } from '@/types/company';

interface Scenario {
  id: number;
  name: string;
  valuation_range: string;
  outcome_type: string;
  probability: number;
  expected_value: number;
  description: string;
}

interface SimulationSummary {
  expected_return: number;
  expected_multiple: number;
  expected_irr: number;
  confidence_interval: [number, number];
  volatility: number;
  sharpe_ratio: number;
  success_probability: number;
  scenario_expected_value: number;
  percentiles: {
    p10: number;
    p25: number;
    p50: number;
    p75: number;
    p90: number;
  };
}

interface AIInsights {
  outcome_probabilities: {
    liquidation: number;
    acquihire: number;
    strategic_acquisition: number;
    ipo: number;
    mega_exit: number;
  };
  key_factors: string[];
  risk_factors: string[];
  opportunities: string[];
  expected_exit_time: number;
  confidence_level: string;
}

interface PWERMAnalysis {
  company_name: string;
  current_arr: number;
  growth_rate: number;
  sector: string;
  scenarios: Scenario[];
  summary: SimulationSummary;
  ai_insights?: AIInsights;
  charts: {
    return_distribution: string;
    top_scenarios: string;
    enterprise_value: string;
  };
  analysis_metadata: {
    total_scenarios: number;
    focus: string;
    ai_enhanced: boolean;
    timestamp: string;
  };
}

export default function PWERMPlaygroundPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<PWERMAnalysis | null>(null);
  const [error, setError] = useState<string>('');
  const [activeTab, setActiveTab] = useState('overview');
  const [showCharts, setShowCharts] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Enhanced assumptions with more realistic defaults
  const [assumptions, setAssumptions] = useState({
    // Base assumptions
    graduation_rate: 0.25,
    arr_growth_rate: 0.30,
    exit_multiple_range: [3, 8] as [number, number],
    dilution_per_round: 0.20,
    time_to_exit_years: 5,
    sector_multiplier: 1.0,
    market_conditions: 'neutral' as 'bull' | 'neutral' | 'bear',
    
    // Investment assumptions
    investment_amount: 500000,
    ownership_percentage: 0.15,
    fund_size: 50000000,
    
    // Simulation parameters
    simulation_runs: 10000,
    confidence_level: 0.95,
    
    // Distribution customization
    liquidation_probability: 0.15,
    acquihire_probability: 0.15,
    strategic_probability: 0.25,
    ipo_probability: 0.15,
    mega_exit_probability: 0.10,
    other_probability: 0.20
  });

  useEffect(() => {
    setMounted(true);
    fetchCompanies();
  }, []);

  const fetchCompanies = async () => {
    try {
      const response = await fetch('/api/companies?limit=1000');
      const data = await response.json();
      setCompanies(data);
    } catch (error) {
      console.error('Error fetching companies:', error);
      setError('Failed to fetch companies');
    }
  };

  const runPWERMAnalysis = async () => {
    console.log('runPWERMAnalysis called');
    if (!selectedCompany) {
      console.log('No company selected');
      setError('Please select a company');
      return;
    }

    console.log('Starting analysis for company:', selectedCompany);
    setLoading(true);
    setError('');

    try {
      const company = companies.find(c => c.id === selectedCompany);
      if (!company) {
        throw new Error('Company not found');
      }

      const config = {
        company_name: company.name,
        current_arr_usd: company.current_arr_usd || 5000000,
        growth_rate: company.revenue_growth_annual_pct || 0.30,
        sector: company.sector || 'Technology',
        assumptions: assumptions
      };

      const response = await fetch(`/api/pwerm/playground`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(config),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'PWERM analysis failed');
      }

      const result = await response.json();
      console.log('API Response:', result);
      
      if (!result.success) {
        throw new Error(result.error || 'API request failed');
      }
      
      // Transform the result into our enhanced format
      const enhancedAnalysis = transformPWERMResult(result, company);
      console.log('Transformed Analysis:', enhancedAnalysis);
      setAnalysis(enhancedAnalysis);
    } catch (error) {
      console.error('PWERM analysis error:', error);
      setError(error instanceof Error ? error.message : 'Analysis failed');
    } finally {
      console.log('Analysis completed, setting loading to false');
      setLoading(false);
    }
  };

  const transformPWERMResult = (result: any, company: Company): PWERMAnalysis => {
    const simulationResults = result.simulation_results;
    
    // Transform the summary to match our interface
    const summary: any = simulationResults.summary || {};
    const transformedSummary: SimulationSummary = {
      expected_return: summary.expected_return || 0,
      expected_multiple: summary.expected_multiple || 0,
      expected_irr: summary.expected_irr || 0,
      confidence_interval: [0, 0] as [number, number], // Not provided by API
      volatility: 0, // Not provided by API
      sharpe_ratio: 0, // Not provided by API
      success_probability: summary.success_probability || 0,
      scenario_expected_value: 0, // Not provided by API
      percentiles: summary.percentiles || { p10: 0, p25: 0, p50: 0, p75: 0, p90: 0 }
    };
    
    return {
      company_name: company.name,
      current_arr: company.current_arr_usd || 0,
      growth_rate: company.revenue_growth_annual_pct || 0,
      sector: company.sector || 'Technology',
      scenarios: simulationResults.scenarios || [],
      summary: transformedSummary,
      ai_insights: result.ai_insights || undefined,
      charts: result.charts || {},
      analysis_metadata: simulationResults.metadata || {
        total_scenarios: 499,
        focus: 'outlier_scenarios',
        ai_enhanced: false,
        timestamp: ''
      }
    };
  };

  const formatCurrency = (value: number) => {
    // Convert to millions for display
    const valueInMillions = value / 1000000;
    if (valueInMillions >= 1000) {
      return `$${(valueInMillions / 1000).toFixed(1)}B`;
    } else if (valueInMillions >= 1) {
      return `$${valueInMillions.toFixed(1)}M`;
    } else {
      return `$${(valueInMillions * 1000).toFixed(0)}K`;
    }
  };

  const formatPercentage = (value: number) => {
    return `${(value * 100).toFixed(1)}%`;
  };

  const getOutcomeTypeColor = (outcomeType: string) => {
    const colors = {
      liquidation: 'bg-red-100 text-red-800',
      distressed: 'bg-orange-100 text-orange-800',
      acquihire: 'bg-yellow-100 text-yellow-800',
      strategic: 'bg-blue-100 text-blue-800',
      ipo: 'bg-green-100 text-green-800',
      mega_exit: 'bg-purple-100 text-purple-800'
    };
    return colors[outcomeType as keyof typeof colors] || 'bg-gray-100 text-gray-800';
  };

  const handleDistributionChange = (outcomeType: string, newProbability: number) => {
    setAssumptions(prev => ({
      ...prev,
      [`${outcomeType}_probability`]: newProbability
    }));
  };

  if (!mounted) {
    return (
      <div className="container mx-auto p-6 space-y-6">
        <div className="flex justify-center items-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Loading PWERM Playground...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">PWERM Analysis & Valuation</h1>
          <p className="text-gray-600 mt-2">Probability-Weighted Expected Return Model with real-time simulation and Tavily integration</p>
        </div>
        <Button onClick={runPWERMAnalysis} disabled={loading || !selectedCompany} size="lg">
          {loading ? 'Running Simulation...' : 'Run PWERM Analysis'}
        </Button>
      </div>

      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <p className="text-red-600">{error}</p>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Configuration Panel */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Company Selection */}
            <div className="space-y-2">
              <Label htmlFor="company">Select Company</Label>
              <Select value={selectedCompany} onValueChange={setSelectedCompany}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose a company" />
                </SelectTrigger>
                <SelectContent>
                  {companies.map((company) => (
                    <SelectItem key={company.id} value={company.id}>
                      {company.name} - {company.sector}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Tabs defaultValue="base" className="w-full">
              <TabsList className="grid w-full grid-cols-5">
                <TabsTrigger value="base">Base</TabsTrigger>
                <TabsTrigger value="investment">Investment</TabsTrigger>
                <TabsTrigger value="simulation">Simulation</TabsTrigger>
                <TabsTrigger value="distribution">Distribution</TabsTrigger>
                <TabsTrigger value="ai-insights">AI Insights</TabsTrigger>
              </TabsList>

              {/* Base Assumptions */}
              <TabsContent value="base" className="space-y-4">
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="arr_growth_rate">ARR Growth Rate</Label>
                    <Input
                      id="arr_growth_rate"
                      type="number"
                      step="0.01"
                      value={assumptions.arr_growth_rate}
                      onChange={(e) => setAssumptions(prev => ({
                        ...prev,
                        arr_growth_rate: parseFloat(e.target.value)
                      }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="graduation_rate">Graduation Rate</Label>
                    <Input
                      id="graduation_rate"
                      type="number"
                      step="0.01"
                      value={assumptions.graduation_rate}
                      onChange={(e) => setAssumptions(prev => ({
                        ...prev,
                        graduation_rate: parseFloat(e.target.value)
                      }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="time_to_exit">Time to Exit (Years)</Label>
                    <Input
                      id="time_to_exit"
                      type="number"
                      value={assumptions.time_to_exit_years}
                      onChange={(e) => setAssumptions(prev => ({
                        ...prev,
                        time_to_exit_years: parseInt(e.target.value)
                      }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="market_conditions">Market Conditions</Label>
                    <Select
                      value={assumptions.market_conditions}
                      onValueChange={(value: 'bull' | 'neutral' | 'bear') => 
                        setAssumptions(prev => ({ ...prev, market_conditions: value }))
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="bull">Bull Market</SelectItem>
                        <SelectItem value="neutral">Neutral</SelectItem>
                        <SelectItem value="bear">Bear Market</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </TabsContent>

              {/* Investment Assumptions */}
              <TabsContent value="investment" className="space-y-4">
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="investment_amount">Investment Amount</Label>
                    <Input
                      id="investment_amount"
                      type="number"
                      value={assumptions.investment_amount}
                      onChange={(e) => setAssumptions(prev => ({
                        ...prev,
                        investment_amount: parseInt(e.target.value)
                      }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="ownership_percentage">Ownership %</Label>
                    <Input
                      id="ownership_percentage"
                      type="number"
                      step="0.01"
                      value={assumptions.ownership_percentage}
                      onChange={(e) => setAssumptions(prev => ({
                        ...prev,
                        ownership_percentage: parseFloat(e.target.value)
                      }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="dilution_per_round">Dilution per Round</Label>
                    <Input
                      id="dilution_per_round"
                      type="number"
                      step="0.01"
                      value={assumptions.dilution_per_round}
                      onChange={(e) => setAssumptions(prev => ({
                        ...prev,
                        dilution_per_round: parseFloat(e.target.value)
                      }))}
                    />
                  </div>
                </div>
              </TabsContent>

              {/* Simulation Parameters */}
              <TabsContent value="simulation" className="space-y-4">
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="simulation_runs">Simulation Runs</Label>
                    <Input
                      id="simulation_runs"
                      type="number"
                      value={assumptions.simulation_runs}
                      onChange={(e) => setAssumptions(prev => ({
                        ...prev,
                        simulation_runs: parseInt(e.target.value)
                      }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="confidence_level">Confidence Level</Label>
                    <Input
                      id="confidence_level"
                      type="number"
                      step="0.01"
                      value={assumptions.confidence_level}
                      onChange={(e) => setAssumptions(prev => ({
                        ...prev,
                        confidence_level: parseFloat(e.target.value)
                      }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="exit_multiple_min">Exit Multiple (Min)</Label>
                    <Input
                      id="exit_multiple_min"
                      type="number"
                      step="0.1"
                      value={assumptions.exit_multiple_range[0]}
                      onChange={(e) => setAssumptions(prev => ({
                        ...prev,
                        exit_multiple_range: [parseFloat(e.target.value), prev.exit_multiple_range[1]]
                      }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="exit_multiple_max">Exit Multiple (Max)</Label>
                    <Input
                      id="exit_multiple_max"
                      type="number"
                      step="0.1"
                      value={assumptions.exit_multiple_range[1]}
                      onChange={(e) => setAssumptions(prev => ({
                        ...prev,
                        exit_multiple_range: [prev.exit_multiple_range[0], parseFloat(e.target.value)]
                      }))}
                    />
                  </div>
                </div>
              </TabsContent>

              {/* Distribution Customization */}
              <TabsContent value="distribution" className="space-y-4">
                <div className="space-y-4">
                  <p className="text-sm text-gray-600">Customize scenario probability distribution:</p>
                  
                  <div className="space-y-3">
                    <div className="space-y-2">
                      <Label htmlFor="liquidation_prob">Liquidation Probability</Label>
                      <div className="flex items-center space-x-2">
                        <Input
                          id="liquidation_prob"
                          type="number"
                          step="0.01"
                          value={assumptions.liquidation_probability}
                          onChange={(e) => handleDistributionChange('liquidation', parseFloat(e.target.value))}
                        />
                        <span className="text-sm text-gray-500">%</span>
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <Label htmlFor="acquihire_prob">Acquihire Probability</Label>
                      <div className="flex items-center space-x-2">
                        <Input
                          id="acquihire_prob"
                          type="number"
                          step="0.01"
                          value={assumptions.acquihire_probability}
                          onChange={(e) => handleDistributionChange('acquihire', parseFloat(e.target.value))}
                        />
                        <span className="text-sm text-gray-500">%</span>
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <Label htmlFor="strategic_prob">Strategic Acquisition Probability</Label>
                      <div className="flex items-center space-x-2">
                        <Input
                          id="strategic_prob"
                          type="number"
                          step="0.01"
                          value={assumptions.strategic_probability}
                          onChange={(e) => handleDistributionChange('strategic', parseFloat(e.target.value))}
                        />
                        <span className="text-sm text-gray-500">%</span>
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <Label htmlFor="ipo_prob">IPO Probability</Label>
                      <div className="flex items-center space-x-2">
                        <Input
                          id="ipo_prob"
                          type="number"
                          step="0.01"
                          value={assumptions.ipo_probability}
                          onChange={(e) => handleDistributionChange('ipo', parseFloat(e.target.value))}
                        />
                        <span className="text-sm text-gray-500">%</span>
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <Label htmlFor="mega_exit_prob">Mega Exit Probability</Label>
                      <div className="flex items-center space-x-2">
                        <Input
                          id="mega_exit_prob"
                          type="number"
                          step="0.01"
                          value={assumptions.mega_exit_probability}
                          onChange={(e) => handleDistributionChange('mega_exit', parseFloat(e.target.value))}
                        />
                        <span className="text-sm text-gray-500">%</span>
                      </div>
                    </div>
                  </div>
                  
                  <div className="bg-blue-50 p-3 rounded-lg">
                    <p className="text-sm text-blue-800">
                      Total: {(
                        assumptions.liquidation_probability + 
                        assumptions.acquihire_probability + 
                        assumptions.strategic_probability + 
                        assumptions.ipo_probability + 
                        assumptions.mega_exit_probability + 
                        assumptions.other_probability
                      ).toFixed(1)}%
                    </p>
                  </div>
                </div>
              </TabsContent>

              {/* AI Insights */}
              <TabsContent value="ai-insights" className="space-y-4">
                <div className="space-y-4">
                  <div className="bg-blue-50 p-4 rounded-lg">
                    <h3 className="text-lg font-semibold text-blue-900 mb-2">🤖 AI-Powered Analysis</h3>
                    <p className="text-sm text-blue-800">
                      Our AI analyzes real market data and company characteristics to provide 
                      dynamic probability adjustments for more accurate PWERM modeling.
                    </p>
                  </div>
                  
                  {analysis?.ai_insights ? (
                    <div className="space-y-4">
                      {/* AI Outcome Probabilities */}
                      <div className="space-y-3">
                        <h4 className="font-semibold">AI-Adjusted Outcome Probabilities</h4>
                        <div className="grid grid-cols-2 gap-3">
                          <div className="bg-green-50 p-3 rounded-lg">
                            <div className="text-sm text-green-700">Liquidation</div>
                            <div className="text-lg font-semibold text-green-900">
                              {formatPercentage(analysis.ai_insights.outcome_probabilities.liquidation)}
                            </div>
                          </div>
                          <div className="bg-yellow-50 p-3 rounded-lg">
                            <div className="text-sm text-yellow-700">Acquihire</div>
                            <div className="text-lg font-semibold text-yellow-900">
                              {formatPercentage(analysis.ai_insights.outcome_probabilities.acquihire)}
                            </div>
                          </div>
                          <div className="bg-blue-50 p-3 rounded-lg">
                            <div className="text-sm text-blue-700">Strategic Acquisition</div>
                            <div className="text-lg font-semibold text-blue-900">
                              {formatPercentage(analysis.ai_insights.outcome_probabilities.strategic_acquisition)}
                            </div>
                          </div>
                          <div className="bg-green-50 p-3 rounded-lg">
                            <div className="text-sm text-green-700">IPO</div>
                            <div className="text-lg font-semibold text-green-900">
                              {formatPercentage(analysis.ai_insights.outcome_probabilities.ipo)}
                            </div>
                          </div>
                          <div className="bg-purple-50 p-3 rounded-lg col-span-2">
                            <div className="text-sm text-purple-700">Mega Exit</div>
                            <div className="text-lg font-semibold text-purple-900">
                              {formatPercentage(analysis.ai_insights.outcome_probabilities.mega_exit)}
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Key Factors */}
                      <div className="space-y-2">
                        <h4 className="font-semibold">Key Factors</h4>
                        <div className="space-y-1">
                          {analysis.ai_insights.key_factors.map((factor, index) => (
                            <div key={index} className="flex items-center space-x-2">
                              <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                              <span className="text-sm">{factor}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Risk Factors */}
                      <div className="space-y-2">
                        <h4 className="font-semibold text-red-700">Risk Factors</h4>
                        <div className="space-y-1">
                          {analysis.ai_insights.risk_factors.map((risk, index) => (
                            <div key={index} className="flex items-center space-x-2">
                              <div className="w-2 h-2 bg-red-500 rounded-full"></div>
                              <span className="text-sm text-red-700">{risk}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Opportunities */}
                      <div className="space-y-2">
                        <h4 className="font-semibold text-green-700">Opportunities</h4>
                        <div className="space-y-1">
                          {analysis.ai_insights.opportunities.map((opportunity, index) => (
                            <div key={index} className="flex items-center space-x-2">
                              <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                              <span className="text-sm text-green-700">{opportunity}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* AI Confidence */}
                      <div className="bg-gray-50 p-3 rounded-lg">
                        <div className="flex justify-between items-center">
                          <span className="text-sm text-gray-600">AI Confidence Level:</span>
                          <Badge className={`${
                            analysis.ai_insights.confidence_level === 'high' ? 'bg-green-100 text-green-800' :
                            analysis.ai_insights.confidence_level === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                            'bg-red-100 text-red-800'
                          }`}>
                            {analysis.ai_insights.confidence_level.toUpperCase()}
                          </Badge>
                        </div>
                        <div className="mt-2">
                          <span className="text-sm text-gray-600">Expected Exit Time:</span>
                          <span className="ml-2 font-medium">{analysis.ai_insights.expected_exit_time} years</span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="text-center py-8 text-gray-500">
                      <div className="text-4xl mb-2">🤖</div>
                      <p>Run a PWERM analysis to see AI-powered insights</p>
                    </div>
                  )}
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        {/* Results Panel */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>PWERM Analysis Results</CardTitle>
            {analysis && (
              <div className="flex items-center space-x-4">
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => setShowCharts(!showCharts)}
                >
                  {showCharts ? 'Hide Charts' : 'Show Charts'}
                </Button>
                <Badge className="bg-green-100 text-green-800">
                  {analysis.analysis_metadata.total_scenarios} scenarios
                </Badge>
                {analysis.analysis_metadata.ai_enhanced && (
                  <Badge className="bg-blue-100 text-blue-800">
                    🤖 AI Enhanced
                  </Badge>
                )}
              </div>
            )}
          </CardHeader>
          <CardContent>
            {analysis ? (
              <div className="space-y-6">
                {/* Company Summary */}
                <div className="bg-gray-50 p-4 rounded-lg">
                  <h3 className="text-lg font-semibold mb-2">{analysis.company_name}</h3>
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <span className="text-gray-600">Current ARR:</span>
                      <div className="font-medium">{formatCurrency(analysis.current_arr)}</div>
                    </div>
                    <div>
                      <span className="text-gray-600">Growth Rate:</span>
                      <div className="font-medium">{formatPercentage(analysis.growth_rate)}</div>
                    </div>
                    <div>
                      <span className="text-gray-600">Sector:</span>
                      <div className="font-medium">{analysis.sector}</div>
                    </div>
                  </div>
                </div>

                {/* Charts */}
                {showCharts && analysis.charts && (
                  <div className="space-y-4">
                    <h3 className="text-lg font-semibold">Simulation Charts</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {analysis.charts.return_distribution && (
                        <div className="border rounded-lg p-4">
                          <h4 className="font-medium mb-2">Return Distribution</h4>
                          <img 
                            src={analysis.charts.return_distribution} 
                            alt="Return Distribution"
                            className="w-full h-auto"
                          />
                        </div>
                      )}
                      {analysis.charts.top_scenarios && (
                        <div className="border rounded-lg p-4">
                          <h4 className="font-medium mb-2">Top Scenarios</h4>
                          <img 
                            src={analysis.charts.top_scenarios} 
                            alt="Top Scenarios"
                            className="w-full h-auto"
                          />
                        </div>
                      )}
                      {analysis.charts.enterprise_value && (
                        <div className="border rounded-lg p-4 md:col-span-2">
                          <h4 className="font-medium mb-2">Enterprise Value Distribution</h4>
                          <img 
                            src={analysis.charts.enterprise_value} 
                            alt="Enterprise Value Distribution"
                            className="w-full h-auto"
                          />
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Key Metrics */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center p-4 bg-blue-50 rounded-lg">
                    <div className="text-2xl font-bold text-blue-600">
                      {formatCurrency(analysis.summary.expected_return)}
                    </div>
                    <div className="text-sm text-gray-600">Expected Return</div>
                  </div>
                  <div className="text-center p-4 bg-green-50 rounded-lg">
                    <div className="text-2xl font-bold text-green-600">
                      {analysis.summary.expected_multiple.toFixed(1)}x
                    </div>
                    <div className="text-sm text-gray-600">Expected Multiple</div>
                  </div>
                  <div className="text-center p-4 bg-purple-50 rounded-lg">
                    <div className="text-2xl font-bold text-purple-600">
                      {formatPercentage(analysis.summary.expected_irr)}
                    </div>
                    <div className="text-sm text-gray-600">Expected IRR</div>
                  </div>
                  <div className="text-center p-4 bg-orange-50 rounded-lg">
                    <div className="text-2xl font-bold text-orange-600">
                      {formatPercentage(analysis.summary.success_probability)}
                    </div>
                    <div className="text-sm text-gray-600">Success Probability</div>
                  </div>
                </div>

                {/* Risk Metrics */}
                <div className="bg-white border rounded-lg p-4">
                  <h3 className="text-lg font-semibold mb-4">Risk & Performance Metrics</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <span className="text-sm text-gray-600">Volatility:</span>
                      <div className="font-medium">{formatCurrency(analysis.summary.volatility)}</div>
                    </div>
                    <div>
                      <span className="text-sm text-gray-600">Sharpe Ratio:</span>
                      <div className="font-medium">{analysis.summary.sharpe_ratio.toFixed(2)}</div>
                    </div>
                    <div>
                      <span className="text-sm text-gray-600">95% CI Lower:</span>
                      <div className="font-medium">{formatCurrency(analysis.summary.confidence_interval[0])}</div>
                    </div>
                    <div>
                      <span className="text-sm text-gray-600">95% CI Upper:</span>
                      <div className="font-medium">{formatCurrency(analysis.summary.confidence_interval[1])}</div>
                    </div>
                  </div>
                </div>

                {/* Percentiles */}
                <div className="bg-white border rounded-lg p-4">
                  <h3 className="text-lg font-semibold mb-4">Return Percentiles</h3>
                  <div className="grid grid-cols-5 gap-4">
                    <div className="text-center">
                      <div className="text-sm text-gray-600">P10</div>
                      <div className="font-medium">{formatCurrency(analysis.summary.percentiles.p10)}</div>
                    </div>
                    <div className="text-center">
                      <div className="text-sm text-gray-600">P25</div>
                      <div className="font-medium">{formatCurrency(analysis.summary.percentiles.p25)}</div>
                    </div>
                    <div className="text-center">
                      <div className="text-sm text-gray-600">P50 (Median)</div>
                      <div className="font-medium">{formatCurrency(analysis.summary.percentiles.p50)}</div>
                    </div>
                    <div className="text-center">
                      <div className="text-sm text-gray-600">P75</div>
                      <div className="font-medium">{formatCurrency(analysis.summary.percentiles.p75)}</div>
                    </div>
                    <div className="text-center">
                      <div className="text-sm text-gray-600">P90</div>
                      <div className="font-medium">{formatCurrency(analysis.summary.percentiles.p90)}</div>
                    </div>
                  </div>
                </div>

                {/* Scenario Distribution */}
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold">Scenario Distribution</h3>
                  <div className="space-y-3">
                    {analysis.scenarios
                      .sort((a, b) => b.probability - a.probability)
                      .slice(0, 10)
                      .map((scenario, index) => (
                        <div key={scenario.id} className="border rounded-lg p-4">
                          <div className="flex justify-between items-start mb-2">
                            <div className="flex items-center space-x-2">
                              <span className="text-sm font-medium text-gray-500">#{index + 1}</span>
                              <h4 className="font-medium">{scenario.name}</h4>
                              <Badge className={getOutcomeTypeColor(scenario.outcome_type)}>
                                {scenario.outcome_type}
                              </Badge>
                            </div>
                            <span className="text-sm text-gray-500">
                              {formatPercentage(scenario.probability)} probability
                            </span>
                          </div>
                          <div className="grid grid-cols-2 gap-4 text-sm mb-2">
                            <div>
                              <span className="text-gray-600">Valuation:</span>
                              <div className="font-medium">{scenario.valuation_range}</div>
                            </div>
                            <div>
                              <span className="text-gray-600">Expected Value:</span>
                              <div className="font-medium">{formatCurrency(scenario.expected_value)}</div>
                            </div>
                          </div>
                          <p className="text-sm text-gray-600">{scenario.description}</p>
                          <div className="mt-2">
                            <Progress value={scenario.probability * 100} className="h-2" />
                          </div>
                        </div>
                      ))}
                  </div>
                </div>

                {/* Simulation Metadata */}
                <div className="bg-gray-50 p-4 rounded-lg">
                  <h4 className="font-medium mb-2">Simulation Details</h4>
                  <div className="text-sm text-gray-600">
                    <p>Total Scenarios: {analysis.analysis_metadata.total_scenarios.toLocaleString()}</p>
                    <p>Focus: {analysis.analysis_metadata.focus}</p>
                    {analysis.analysis_metadata.ai_enhanced && (
                      <p>🤖 AI Enhanced Analysis</p>
                    )}
                    {analysis.analysis_metadata.timestamp && (
                      <p>Timestamp: {analysis.analysis_metadata.timestamp}</p>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center text-gray-500 py-8">
                Select a company and run PWERM analysis to see comprehensive simulation results
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
} 