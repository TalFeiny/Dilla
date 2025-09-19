'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { PortfolioCompany, PWERMBaseAssumptions, PWERMScenario, PWERMPlaygroundConfig } from '@/types/portfolio';

export default function PWERMPlaygroundPage() {
  const params = useParams();
  const portfolioId = params.id as string;
  
  const [portfolioCompany, setPortfolioCompany] = useState<PortfolioCompany | null>(null);
  const [loading, setLoading] = useState(true);
  const [runningAnalysis, setRunningAnalysis] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<any>(null);
  
  // Base assumptions state
  const [baseAssumptions, setBaseAssumptions] = useState<PWERMBaseAssumptions>({
    graduation_rate: 0.25,
    arr_growth_rate: 0.30,
    exit_multiple_range: [3, 8],
    dilution_per_round: 0.20,
    time_to_exit_years: 5,
    sector_multiplier: 1.0,
    market_conditions: 'neutral',
    ai_monitoring_enabled: true,
    custom_assumptions: {}
  });

  useEffect(() => {
    fetchPortfolioCompany();
  }, Array.from(tfolioId));

  const fetchPortfolioCompany = async () => {
    try {
      const response = await fetch(`/api/portfolio/${portfolioId}`);
      const data = await response.json();
      setPortfolioCompany(data);
    } catch (error) {
      console.error('Error fetching portfolio company:', error);
    } finally {
      setLoading(false);
    }
  };

  const runPWERMAnalysis = async () => {
    if (!portfolioCompany?.company) return;

    setRunningAnalysis(true);
    try {
      const config: PWERMPlaygroundConfig = {
        company_id: portfolioCompany.company.id,
        portfolio_company_id: portfolioCompany.id,
        base_assumptions: baseAssumptions,
        custom_scenarios: [],
        ai_monitoring_config: {
          enabled: baseAssumptions.ai_monitoring_enabled,
          monitoring_frequency: 'monthly',
          alert_thresholds: {
            arr_growth_rate: 0.15,
            burn_rate: 0.8,
            runway_months: 12
          }
        }
      };

      const response = await fetch('/api/portfolio/pwerm-playground', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });

      if (response.ok) {
        const result = await response.json();
        setAnalysisResult(result);
      } else {
        const error = await response.json();
        alert(error.error || 'Failed to run PWERM analysis');
      }
    } catch (error) {
      console.error('Error running PWERM analysis:', error);
      alert('Failed to run PWERM analysis');
    } finally {
      setRunningAnalysis(false);
    }
  };

  const updateBaseAssumption = (key: keyof PWERMBaseAssumptions, value: any) => {
    setBaseAssumptions(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
  };

  const formatPercentage = (value: number) => {
    return `${(value * 100).toFixed(1)}%`;
  };

  if (loading) {
    return (
      <div className="container mx-auto p-6">
        <div className="flex items-center justify-center h-64">
          <div className="text-lg">Loading PWERM playground...</div>
        </div>
      </div>
    );
  }

  if (!portfolioCompany) {
    return (
      <div className="container mx-auto p-6">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-600">Portfolio Company Not Found</h1>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">PWERM Playground</h1>
        <p className="text-gray-600">
          Configure assumptions and run PWERM analysis for {portfolioCompany.company?.name}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Configuration Panel */}
        <Card>
          <CardHeader>
            <CardTitle>Base Assumptions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="graduation-rate">Graduation Rate</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="graduation-rate"
                  type="number"
                  min="0"
                  max="1"
                  step="0.01"
                  value={baseAssumptions.graduation_rate}
                  onChange={(e) => updateBaseAssumption('graduation_rate', parseFloat(e.target.value))}
                />
                <span className="text-sm text-gray-500">
                  {formatPercentage(baseAssumptions.graduation_rate)}
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Probability of successful graduation to next stage
              </p>
            </div>

            <div>
              <Label htmlFor="arr-growth-rate">ARR Growth Rate</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="arr-growth-rate"
                  type="number"
                  min="0"
                  max="2"
                  step="0.01"
                  value={baseAssumptions.arr_growth_rate}
                  onChange={(e) => updateBaseAssumption('arr_growth_rate', parseFloat(e.target.value))}
                />
                <span className="text-sm text-gray-500">
                  {formatPercentage(baseAssumptions.arr_growth_rate)}
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Annual ARR growth rate
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="exit-multiple-min">Exit Multiple (Min)</Label>
                <Input
                  id="exit-multiple-min"
                  type="number"
                  min="1"
                  max="20"
                  step="0.1"
                  value={baseAssumptions.exit_multiple_range[0]}
                  onChange={(e) => updateBaseAssumption('exit_multiple_range', [
                    parseFloat(e.target.value),
                    baseAssumptions.exit_multiple_range[1]
                  ])}
                />
              </div>
              <div>
                <Label htmlFor="exit-multiple-max">Exit Multiple (Max)</Label>
                <Input
                  id="exit-multiple-max"
                  type="number"
                  min="1"
                  max="20"
                  step="0.1"
                  value={baseAssumptions.exit_multiple_range[1]}
                  onChange={(e) => updateBaseAssumption('exit_multiple_range', [
                    baseAssumptions.exit_multiple_range[0],
                    parseFloat(e.target.value)
                  ])}
                />
              </div>
            </div>

            <div>
              <Label htmlFor="dilution-per-round">Dilution per Round</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="dilution-per-round"
                  type="number"
                  min="0"
                  max="1"
                  step="0.01"
                  value={baseAssumptions.dilution_per_round}
                  onChange={(e) => updateBaseAssumption('dilution_per_round', parseFloat(e.target.value))}
                />
                <span className="text-sm text-gray-500">
                  {formatPercentage(baseAssumptions.dilution_per_round)}
                </span>
              </div>
            </div>

            <div>
              <Label htmlFor="time-to-exit">Time to Exit (Years)</Label>
              <Input
                id="time-to-exit"
                type="number"
                min="1"
                max="10"
                step="0.5"
                value={baseAssumptions.time_to_exit_years}
                onChange={(e) => updateBaseAssumption('time_to_exit_years', parseFloat(e.target.value))}
              />
            </div>

            <div>
              <Label htmlFor="sector-multiplier">Sector Multiplier</Label>
              <Input
                id="sector-multiplier"
                type="number"
                min="0.1"
                max="3"
                step="0.1"
                value={baseAssumptions.sector_multiplier}
                onChange={(e) => updateBaseAssumption('sector_multiplier', parseFloat(e.target.value))}
              />
            </div>

            <div>
              <Label htmlFor="market-conditions">Market Conditions</Label>
              <Select
                value={baseAssumptions.market_conditions}
                onValueChange={(value: 'bull' | 'bear' | 'neutral') => 
                  updateBaseAssumption('market_conditions', value)
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

            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="ai-monitoring"
                checked={baseAssumptions.ai_monitoring_enabled}
                onChange={(e) => updateBaseAssumption('ai_monitoring_enabled', e.target.checked)}
                className="rounded"
              />
              <Label htmlFor="ai-monitoring">Enable AI Monitoring</Label>
            </div>

            <Button 
              onClick={runPWERMAnalysis} 
              disabled={runningAnalysis}
              className="w-full"
            >
              {runningAnalysis ? 'Running Analysis...' : 'Run PWERM Analysis'}
            </Button>
          </CardContent>
        </Card>

        {/* Results Panel */}
        <Card>
          <CardHeader>
            <CardTitle>Analysis Results</CardTitle>
          </CardHeader>
          <CardContent>
            {analysisResult ? (
              <Tabs defaultValue="summary" className="w-full">
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger value="summary">Summary</TabsTrigger>
                  <TabsTrigger value="scenarios">Scenarios</TabsTrigger>
                  <TabsTrigger value="metrics">Metrics</TabsTrigger>
                </TabsList>

                <TabsContent value="summary" className="mt-4">
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="text-center p-4 bg-blue-50 rounded-lg">
                        <div className="text-2xl font-bold text-blue-600">
                          {formatCurrency(analysisResult.data.expected_return_usd)}
                        </div>
                        <div className="text-sm text-gray-600">Expected Return</div>
                      </div>
                      <div className="text-center p-4 bg-green-50 rounded-lg">
                        <div className="text-2xl font-bold text-green-600">
                          {analysisResult.data.expected_multiple.toFixed(1)}x
                        </div>
                        <div className="text-sm text-gray-600">Expected Multiple</div>
                      </div>
                    </div>
                    
                    <div className="text-center p-4 bg-purple-50 rounded-lg">
                      <div className="text-2xl font-bold text-purple-600">
                        {formatPercentage(analysisResult.data.expected_irr)}
                      </div>
                      <div className="text-sm text-gray-600">Expected IRR</div>
                    </div>

                    <div className="text-center p-4 bg-orange-50 rounded-lg">
                      <div className="text-2xl font-bold text-orange-600">
                        {analysisResult.data.risk_adjusted_return.toFixed(2)}
                      </div>
                      <div className="text-sm text-gray-600">Risk-Adjusted Return</div>
                    </div>

                    <div className="p-4 bg-gray-50 rounded-lg">
                      <div className="text-sm font-medium text-gray-700 mb-2">Confidence Interval (95%)</div>
                      <div className="text-lg">
                        {formatCurrency(analysisResult.data.confidence_interval_95[0])} - {formatCurrency(analysisResult.data.confidence_interval_95[1])}
                      </div>
                    </div>
                  </div>
                </TabsContent>

                <TabsContent value="scenarios" className="mt-4">
                  <div className="space-y-3">
                    {analysisResult.data.scenarios.map((scenario: PWERMScenario, index: number) => (
                      <div key={index} className="p-4 border rounded-lg">
                        <div className="flex justify-between items-start mb-2">
                          <h4 className="font-semibold">{scenario.scenario_name}</h4>
                          <Badge variant="secondary">
                            {formatPercentage(scenario.probability)}
                          </Badge>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-sm">
                          <div>Exit Value: {formatCurrency(scenario.exit_value_usd)}</div>
                          <div>Exit Multiple: {scenario.exit_multiple.toFixed(1)}x</div>
                          <div>Exit Year: {scenario.exit_year}</div>
                          <div>Exit Type: {scenario.exit_type}</div>
                        </div>
                        <p className="text-xs text-gray-600 mt-2">{scenario.description}</p>
                      </div>
                    ))}
                  </div>
                </TabsContent>

                <TabsContent value="metrics" className="mt-4">
                  <div className="space-y-3">
                    <div className="p-4 bg-gray-50 rounded-lg">
                      <h4 className="font-semibold mb-2">Investment Details</h4>
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        <div>Total Invested: {formatCurrency(portfolioCompany.total_invested_usd)}</div>
                        <div>Ownership: {portfolioCompany.ownership_percentage}%</div>
                        <div>Investment Date: {new Date(portfolioCompany.investment_date).toLocaleDateString()}</div>
                        <div>Current ARR: {portfolioCompany.company?.current_arr_usd ? formatCurrency(portfolioCompany.company.current_arr_usd) : 'N/A'}</div>
                      </div>
                    </div>

                    <div className="p-4 bg-gray-50 rounded-lg">
                      <h4 className="font-semibold mb-2">Analysis Metadata</h4>
                      <div className="text-sm">
                        <div>Sector: {analysisResult.data.analysis_metadata.sector || 'N/A'}</div>
                        <div>Analysis Type: {analysisResult.data.analysis_metadata.analysis_type}</div>
                        <div>Version: {analysisResult.data.analysis_metadata.version}</div>
                        <div>Scenarios: {analysisResult.data.scenario_count}</div>
                      </div>
                    </div>
                  </div>
                </TabsContent>
              </Tabs>
            ) : (
              <div className="text-center py-12 text-gray-500">
                <p>Run a PWERM analysis to see results here</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
} 