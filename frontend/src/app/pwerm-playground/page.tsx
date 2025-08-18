'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, TrendingUp, TrendingDown, Target, BarChart3, Calculator, DollarSign, PieChart } from 'lucide-react';

interface PWERMScenario {
  id: number;
  name: string;
  type: string;
  probability: number;
  exit_value: number;
  weighted_value: number;
  total_funding_raised: number;
  years_to_exit: number;
  path: string[];
  description: string;
  waterfall_analysis: any;
}

interface Incumbent {
  name: string;
  type: string;
  market_cap: number;
  description: string;
}

interface Competitor {
  name: string;
  stage: string;
  description: string;
}

interface Fragmentation {
  level: string;
  explanation: string;
}

interface MarketLandscape {
  submarket: string;
  incumbents: Incumbent[];
  competitors: Competitor[];
  fragmentation: Fragmentation;
  market_size: string;
  growth_rate: string;
  barriers_to_entry: string[];
}

interface Comparable {
  acquirer: string;
  target: string;
  deal_value: number;
  revenue_multiple: number;
  date: string;
}

interface Acquirer {
  name: string;
  type: string;
  market_cap: number;
  acquisition_history: string[];
}

interface PWERMResults {
  success: boolean;
  core_inputs: {
    company_name: string;
    current_arr_usd: number;
    growth_rate: number;
    sector: string;
  };
  market_research: {
    market_landscape: MarketLandscape;
    comparables: Comparable[];
    acquirers: Acquirer[];
    exit_comparables: any[];
    potential_acquirers: string[];
    graduation_rates?: any;
    competitors?: any[];
    market_conditions?: any;
    sector_analysis?: any;
  };
  scenarios: PWERMScenario[];
  summary: {
    expected_exit_value: number;
    median_exit_value: number;
    total_scenarios: number;
    success_probability: number;
    mega_exit_probability: number;
    p10_exit_value?: number;
    p25_exit_value?: number;
    p75_exit_value?: number;
    p90_exit_value?: number;
    expected_round_returns?: any;
    scenario_type_distribution?: any;
    liquidation_probability?: number;
    acquisition_probability?: number;
    ipo_probability?: number;
  };
  charts?: any;
  analysis_timestamp?: string;
}

export default function PWERMPlayground() {
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<PWERMResults | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [companies, setCompanies] = useState<any[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<string>('manual');
  const [loadingCompanies, setLoadingCompanies] = useState(true);
  const [progress, setProgress] = useState<string[]>([]);

  // Input parameters
  const [companyName, setCompanyName] = useState('Test Company');
  const [currentARR, setCurrentARR] = useState(1000000);
  const [growthRate, setGrowthRate] = useState(50);
  const [selectedSector, setSelectedSector] = useState('Technology');

  const sectors = [
    'AI', 'Adtech', 'B2B Fintech', 'B2C Fintech', 'B2C', 'Capital Markets',
    'Climate Deep', 'Climate Software', 'Crypto', 'Cyber', 'Deep', 'Dev Tool',
    'E-com', 'Edtech', 'Fintech', 'HR', 'Health', 'Insurtech', 'Marketplace',
    'Renewables', 'SaaS', 'Supply-Chain', 'Technology', 'Travel'
  ];

  // Load companies on component mount
  useEffect(() => {
    const loadCompanies = async () => {
      try {
        setLoadingCompanies(true);
        console.log('Loading companies...');
        const response = await fetch('/api/companies/pwerm?limit=1000');
        console.log('Response status:', response.status);
        
        if (response.ok) {
          const data = await response.json();
          console.log('Loaded companies:', data.companies?.length || 0);
          console.log('Total companies in DB:', data.total || 0);
          console.log('Companies data:', data.companies);
          setCompanies(data.companies || []);
          console.log('Companies state set, length:', data.companies?.length || 0);
        } else {
          console.error('Failed to load companies:', response.status);
          const errorText = await response.text();
          console.error('Error response:', errorText);
        }
      } catch (error) {
        console.error('Failed to load companies:', error);
      } finally {
        setLoadingCompanies(false);
      }
    };
    
    loadCompanies();
  }, []);

  // Update form when company is selected
  useEffect(() => {
    if (selectedCompany && selectedCompany !== 'manual') {
      const company = companies.find(c => c.id === selectedCompany);
      if (company) {
        setCompanyName(company.name);
        setCurrentARR(company.current_arr_usd || 1000000);
        setGrowthRate(company.growth_rate || 50);
      }
    }
  }, [selectedCompany, companies]);

  // Debug companies state changes
  useEffect(() => {
    console.log('Companies state changed, length:', companies.length);
    console.log('First few companies:', companies.slice(0, 3));
  }, [companies]);

  const runPWERMAnalysis = async () => {
    setLoading(true);
    setError(null);
    setProgress([]);
    
    try {
      const response = await fetch('/api/pwerm/playground', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          company_name: companyName,
          current_arr_usd: currentARR / 1000000, // Convert to millions
          growth_rate: growthRate / 100, // Convert percentage to decimal
          sector: selectedSector
        }),
      });

      const data = await response.json();
      
      console.log('Raw API response:', data);
      console.log('Response type:', typeof data);
      console.log('Response keys:', Object.keys(data));
      
      if (data.error) {
        setError(data.error);
        setProgress(data.progress || []);
        return;
      }

      console.log('PWERM Analysis Response:', data);
      console.log('Full response structure:', JSON.stringify(data, null, 2));
      
      // Debug: Check what fields are actually available
      console.log('Available fields in data:', Object.keys(data));
      console.log('Market research fields:', data.market_research ? Object.keys(data.market_research) : 'No market_research');
      console.log('Summary fields:', data.summary ? Object.keys(data.summary) : 'No summary');
      console.log('Scenarios count:', data.scenarios ? data.scenarios.length : 'No scenarios');
      
      // Debug scenarios specifically
      if (data.scenarios) {
        console.log('First scenario:', data.scenarios[0]);
        console.log('Scenarios structure:', data.scenarios.slice(0, 3));
      }
      
      // Debug market research specifically
      if (data.market_research) {
        console.log('Market research structure:', data.market_research);
        if (data.market_research.acquirers) {
          console.log('Acquirers:', data.market_research.acquirers);
        }
        if (data.market_research.openai_analysis) {
          console.log('OpenAI analysis fields:', Object.keys(data.market_research.openai_analysis));
          if (data.market_research.openai_analysis.acquirer_analysis) {
            console.log('Acquirer analysis:', data.market_research.openai_analysis.acquirer_analysis);
          }
        }
      }
      
      console.log('Setting results with data:', data);
      setResults(data);
      console.log('Results state after setting:', results);
      setProgress(data.progress || []);
    } catch (err) {
      setError('Failed to run PWERM analysis');
      console.error('PWERM analysis error:', err);
    } finally {
      setLoading(false);
    }
  };

  const getSectorColor = (sector: string) => {
    const colors: { [key: string]: string } = {
      'AI': 'bg-blue-100 text-blue-800',
      'SaaS': 'bg-green-100 text-green-800',
      'Fintech': 'bg-purple-100 text-purple-800',
      'Health': 'bg-red-100 text-red-800',
      'Technology': 'bg-gray-100 text-gray-800'
    };
    return colors[sector] || 'bg-gray-100 text-gray-800';
  };

  const getRiskColor = (risk: number) => {
    if (risk > 0.7) return 'text-green-600';
    if (risk > 0.4) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getReturnColor = (return_value: number) => {
    if (return_value > 10) return 'text-green-600'; // > $10M
    if (return_value > 1) return 'text-yellow-600'; // > $1M
    return 'text-red-600'; // < $1M
  };

  const formatCurrency = (value: number | undefined | null) => {
    if (value === undefined || value === null || isNaN(value)) {
      return 'N/A';
    }
    if (value >= 1000) {
      return `$${(value / 1000).toFixed(1)}B`;
    }
    return `$${value.toFixed(1)}M`;
  };

  const formatPercentage = (value: number | undefined | null) => {
    if (value === undefined || value === null || isNaN(value)) {
      return 'N/A';
    }
    return `${(value * 100).toFixed(1)}%`;
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">PWERM Analysis Playground</h1>
          <p className="text-gray-600">Probability-Weighted Expected Return Model</p>
        </div>
        <div className="flex items-center space-x-2">
          <Calculator className="h-6 w-6 text-blue-600" />
          <span className="text-sm text-gray-500">Enhanced Analysis</span>
        </div>
      </div>

      {/* Input Form */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="h-5 w-5" />
            Analysis Parameters
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Company Selection */}
            <div className="space-y-2">
              <Label htmlFor="company-select">Company</Label>
              <Select value={selectedCompany} onValueChange={setSelectedCompany}>
                <SelectTrigger>
                  <SelectValue placeholder={loadingCompanies ? "Loading companies..." : `Select a company or enter name (${companies.length} available)`} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="manual">Enter manually</SelectItem>
                  {loadingCompanies ? (
                    <SelectItem value="loading" disabled>Loading companies...</SelectItem>
                  ) : companies.length === 0 ? (
                    <SelectItem value="none" disabled>No companies available</SelectItem>
                  ) : (
                    companies
                      .filter(company => company.name && company.name.trim() !== '')
                      .map((company) => (
                        <SelectItem key={company.id} value={company.id}>
                          {company.name}
                        </SelectItem>
                      ))
                  )}
                </SelectContent>
              </Select>
              {selectedCompany === 'manual' && (
                <Input
                  placeholder="Enter company name"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                />
              )}
            </div>

            {/* ARR Input */}
            <div className="space-y-2">
              <Label htmlFor="arr">Current ARR (USD)</Label>
              <Input
                id="arr"
                type="number"
                value={currentARR}
                onChange={(e) => setCurrentARR(Number(e.target.value))}
                placeholder="e.g., 1000000"
              />
              <p className="text-sm text-gray-500">
                ${currentARR ? (currentARR / 1000000).toFixed(1) : '0.0'}M
              </p>
            </div>

            {/* Growth Rate Input */}
            <div className="space-y-2">
              <Label htmlFor="growth">Growth Rate (%)</Label>
              <Input
                id="growth"
                type="number"
                value={growthRate}
                onChange={(e) => setGrowthRate(Number(e.target.value))}
                placeholder="e.g., 50"
              />
              <p className="text-sm text-gray-500">
                {growthRate}% annually
              </p>
            </div>

            {/* Sector Selection */}
            <div className="space-y-2">
              <Label htmlFor="sector">Sector</Label>
              <Select value={selectedSector} onValueChange={setSelectedSector}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a sector" />
                </SelectTrigger>
                <SelectContent>
                  {sectors.map((sector) => (
                    <SelectItem key={sector} value={sector}>
                      {sector}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <Button 
            onClick={runPWERMAnalysis} 
            disabled={loading || !companyName}
            className="w-full"
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Running Analysis...
              </>
            ) : (
              <>
                <Calculator className="mr-2 h-4 w-4" />
                Run PWERM Analysis
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Error Display */}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Results Display */}
      {results && (
        <div className="space-y-6">

          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Expected Exit Value</CardTitle>
                <DollarSign className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className={`text-2xl font-bold ${getReturnColor((results.summary?.expected_exit_value || 0) / 1000)}`}>
                  {results.summary?.expected_exit_value !== undefined ? formatCurrency(results.summary.expected_exit_value / 1000) : 'N/A'}
                </div>
                <p className="text-xs text-muted-foreground">
                  Probability-weighted average
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Scenarios</CardTitle>
                <PieChart className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-blue-600">
                  {results.summary?.total_scenarios || 'N/A'}
                </div>
                <p className="text-xs text-muted-foreground">
                  Monte Carlo simulations
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Success Probability</CardTitle>
                <TrendingUp className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className={`text-2xl font-bold ${getRiskColor(results.summary?.success_probability || 0)}`}>
                  {results.summary?.success_probability !== undefined ? formatPercentage(results.summary.success_probability) : 'N/A'}
                </div>
                <p className="text-xs text-muted-foreground">
                  Exit &gt; $10M scenarios
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Median Exit Value</CardTitle>
                <BarChart3 className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-blue-600">
                  {results.summary?.median_exit_value !== undefined ? formatCurrency(results.summary.median_exit_value / 1000) : 'N/A'}
                </div>
                <p className="text-xs text-muted-foreground">
                  50th percentile outcome
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Detailed Results Tabs */}
          <Tabs defaultValue="scenarios" className="space-y-4">
            <TabsList>
              <TabsTrigger value="scenarios">Scenarios ({results.summary?.total_scenarios || 0})</TabsTrigger>
              <TabsTrigger value="market">Market Landscape</TabsTrigger>
              <TabsTrigger value="competitors">Competitors & Incumbents</TabsTrigger>
              <TabsTrigger value="comparables">Comparables & Acquisitions</TabsTrigger>
              <TabsTrigger value="acquirers">Potential Acquirers</TabsTrigger>
            </TabsList>

            <TabsContent value="scenarios" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Top 20 Most Likely Scenarios</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {(results.scenarios || []).slice(0, 20).map((scenario, index) => (
                      <div key={scenario.id || index} className="border rounded-lg p-4">
                        <div className="flex justify-between items-start">
                          <div className="flex-1">
                            <h4 className="font-semibold">{scenario.name || `Scenario ${scenario.id || index + 1}`}</h4>
                            <p className="text-sm text-gray-600">{scenario.description || scenario.type || 'No description available'}</p>
                            <div className="flex gap-2 mt-2">
                              <Badge variant="outline">{scenario.type || 'unknown'}</Badge>
                              <Badge variant="secondary">
                                {formatPercentage(scenario.probability)} probability
                              </Badge>
                              {scenario.time_to_exit && (
                                <Badge variant="outline">
                                  {scenario.time_to_exit.toFixed(1)} years
                                </Badge>
                              )}
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="font-semibold">
                              ${(scenario.exit_value / 1000).toFixed(1)}M
                            </div>
                            <div className="text-sm text-gray-600">
                              Stage: {scenario.graduation_stage || 'N/A'}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="waterfall" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Waterfall Analysis Summary</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="text-center">
                      <div className="text-2xl font-bold">
                        {formatPercentage(results.summary?.expected_exit_value ? (results.summary.expected_exit_value / results.core_inputs?.current_arr_usd || 1) - 1 : 0)}
                      </div>
                      <div className="text-sm text-gray-600">Average ROI</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold">
                        {formatPercentage(results.summary?.success_probability || 0)}
                      </div>
                      <div className="text-sm text-gray-600">Average IRR</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold">
                        {results.scenarios?.length || 0}
                      </div>
                      <div className="text-sm text-gray-600">Scenarios Analyzed</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="market" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Market Landscape Analysis</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-6">
                    {results.market_research?.market_landscape ? (
                      <>
                        {/* Submarket */}
                        <div className="bg-blue-50 rounded-lg p-4">
                          <h4 className="font-semibold text-blue-900 mb-2">Submarket</h4>
                          <p className="text-blue-700 text-sm">
                            {results.market_research.market_landscape.submarket || 'N/A'}
                          </p>
                        </div>

                        {/* Market Size & Growth */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="bg-green-50 rounded-lg p-4">
                            <h4 className="font-semibold text-green-900 mb-2">Market Size</h4>
                            <p className="text-green-700 text-sm">
                              {results.market_research.market_landscape.market_size || 'N/A'}
                            </p>
                          </div>
                          <div className="bg-purple-50 rounded-lg p-4">
                            <h4 className="font-semibold text-purple-900 mb-2">Growth Rate</h4>
                            <p className="text-purple-700 text-sm">
                              {results.market_research.market_landscape.growth_rate || 'N/A'}
                            </p>
                          </div>
                        </div>

                        {/* Market Fragmentation */}
                        <div className="bg-yellow-50 rounded-lg p-4">
                          <h4 className="font-semibold text-yellow-900 mb-2">
                            Market Fragmentation: {results.market_research.market_landscape.fragmentation?.level || 'N/A'}
                          </h4>
                          <p className="text-yellow-700 text-sm">
                            {results.market_research.market_landscape.fragmentation?.explanation || 'No explanation available'}
                          </p>
                        </div>

                        {/* Barriers to Entry */}
                        <div>
                          <h4 className="font-semibold mb-3">Barriers to Entry:</h4>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                            {(results.market_research.market_landscape.barriers_to_entry || []).map((barrier, index) => (
                              <div key={index} className="flex items-center space-x-2 p-2 bg-red-50 rounded">
                                <div className="w-2 h-2 bg-red-500 rounded-full"></div>
                                <span className="text-sm">{barrier}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </>
                    ) : (
                      <div className="bg-gray-50 rounded-lg p-4">
                        <h4 className="font-semibold text-gray-900 mb-2">Market Landscape Not Available</h4>
                        <p className="text-gray-700 text-sm">
                          Market landscape analysis is not available for this analysis.
                        </p>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="competitors" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Competitors & Incumbents Analysis</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-6">
                    {results.market_research?.market_landscape ? (
                      <>
                        {/* Incumbents */}
                        <div>
                          <h4 className="font-semibold mb-3">Market Incumbents:</h4>
                          <div className="space-y-3">
                            {(results.market_research.market_landscape.incumbents || []).map((incumbent, index) => (
                              <div key={index} className="border rounded-lg p-4 bg-blue-50">
                                <div className="flex justify-between items-start">
                                  <div className="flex-1">
                                    <h5 className="font-semibold text-blue-900">{incumbent.name}</h5>
                                    <p className="text-sm text-blue-700 mb-2">{incumbent.description}</p>
                                    <div className="flex gap-2">
                                      <Badge variant="outline">{incumbent.type}</Badge>
                                      <Badge variant="secondary">
                                        Market Cap: ${(incumbent.market_cap / 1000).toFixed(1)}B
                                      </Badge>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* Competitors */}
                        <div>
                          <h4 className="font-semibold mb-3">Direct Competitors:</h4>
                          <div className="space-y-3">
                            {(results.market_research.market_landscape.competitors || []).map((competitor, index) => (
                              <div key={index} className="border rounded-lg p-4 bg-green-50">
                                <div className="flex justify-between items-start">
                                  <div className="flex-1">
                                    <h5 className="font-semibold text-green-900">{competitor.name}</h5>
                                    <p className="text-sm text-green-700 mb-2">{competitor.description}</p>
                                    <Badge variant="outline">{competitor.stage}</Badge>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </>
                    ) : (
                      <div className="bg-gray-50 rounded-lg p-4">
                        <h4 className="font-semibold text-gray-900 mb-2">Competitor Analysis Not Available</h4>
                        <p className="text-gray-700 text-sm">
                          Competitive landscape analysis is not available for this analysis.
                        </p>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="comparables" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Comparables & Acquisition Analysis</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-6">
                    {/* Comparable Deals */}
                    <div>
                      <h4 className="font-semibold mb-3">Recent Comparable Deals:</h4>
                      <div className="space-y-3">
                        {(results.market_research?.comparables || []).map((deal, index) => {
                          // Handle both object and string formats for acquirer/target
                          const acquirerName = typeof deal.acquirer === 'object' ? deal.acquirer.name : deal.acquirer;
                          const targetName = typeof deal.target === 'object' ? deal.target.name : deal.target;
                          
                          return (
                            <div key={index} className="border rounded-lg p-4 bg-purple-50">
                              <div className="flex justify-between items-start">
                                <div className="flex-1">
                                  <h5 className="font-semibold text-purple-900">
                                    {acquirerName || 'Unknown Acquirer'} → {targetName || 'Unknown Target'}
                                  </h5>
                                  {deal.date && (
                                    <p className="text-sm text-purple-700 mb-2">
                                      Deal Date: {deal.date}
                                    </p>
                                  )}
                                  <div className="flex gap-2 flex-wrap">
                                    {deal.deal_value && (
                                      <Badge variant="outline">
                                        Deal Value: ${deal.deal_value}M
                                      </Badge>
                                    )}
                                    {deal.revenue_multiple && (
                                      <Badge variant="secondary">
                                        Revenue Multiple: {deal.revenue_multiple}x
                                      </Badge>
                                    )}
                                    {deal.likelihood && (
                                      <Badge variant="outline">
                                        Likelihood: {deal.likelihood}
                                      </Badge>
                                    )}
                                    {deal.strategic_fit && (
                                      <Badge variant="secondary">
                                        Strategic Fit: {deal.strategic_fit}
                                      </Badge>
                                    )}
                                    {deal.typical_multiple && (
                                      <Badge variant="outline">
                                        Typical Multiple: {deal.typical_multiple}
                                      </Badge>
                                    )}
                                  </div>
                                  {deal.recent_similar_deals && deal.recent_similar_deals.length > 0 && (
                                    <div className="mt-2">
                                      <p className="text-xs text-purple-600 font-medium">Recent Similar Deals:</p>
                                      <ul className="text-xs text-purple-700 mt-1">
                                        {deal.recent_similar_deals.map((similarDeal, i) => (
                                          <li key={i}>• {similarDeal}</li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Exit Comparables */}
                    {results.market_research?.exit_comparables && Array.isArray(results.market_research.exit_comparables) && results.market_research.exit_comparables.length > 0 && (
                      <div>
                        <h4 className="font-semibold mb-3">Exit Comparables:</h4>
                        <div className="space-y-3">
                          {results.market_research.exit_comparables.map((exit: any, index: number) => (
                            <div key={index} className="border rounded-lg p-4 bg-green-50">
                              <div className="flex justify-between items-start">
                                <div className="flex-1">
                                  {exit.company && (
                                    <h5 className="font-semibold text-green-900">
                                      {typeof exit.company === 'object' ? exit.company.name : exit.company}
                                    </h5>
                                  )}
                                  <div className="flex gap-2 flex-wrap mt-2">
                                    {exit.exit_value && (
                                      <Badge variant="outline">
                                        Exit Value: ${exit.exit_value}M
                                      </Badge>
                                    )}
                                    {exit.exit_type && (
                                      <Badge variant="secondary">
                                        Type: {exit.exit_type}
                                      </Badge>
                                    )}
                                    {exit.year && (
                                      <Badge variant="outline">
                                        Year: {exit.year}
                                      </Badge>
                                    )}
                                    {exit.multiple && (
                                      <Badge variant="secondary">
                                        Multiple: {exit.multiple}x
                                      </Badge>
                                    )}
                                  </div>
                                  {exit.details && (
                                    <p className="text-sm text-green-700 mt-2">{exit.details}</p>
                                  )}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Potential Acquirers List */}
                    <div>
                      <h4 className="font-semibold mb-3">Identified Potential Acquirers:</h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {(results.market_research?.potential_acquirers || []).map((acquirer, index) => {
                          const acquirerName = typeof acquirer === 'object' ? (acquirer.name || 'Unknown') : acquirer;
                          return (
                            <div key={index} className="flex items-center space-x-3 p-3 bg-blue-50 rounded">
                              <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
                              <span className="font-medium text-blue-900">{acquirerName}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="acquirers" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Detailed Acquirer Analysis</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-6">
                    {/* Acquirer Companies */}
                    <div>
                      <h4 className="font-semibold mb-3">Potential Acquiring Companies:</h4>
                      <div className="space-y-3">
                        {(results.market_research?.acquirers || []).map((acquirer, index) => (
                          <div key={index} className="border rounded-lg p-4 bg-orange-50">
                            <div className="flex justify-between items-start">
                              <div className="flex-1">
                                <h5 className="font-semibold text-orange-900">{acquirer.name}</h5>
                                <div className="flex gap-2 mt-2 mb-3">
                                  <Badge variant="outline">{acquirer.type}</Badge>
                                  <Badge variant="secondary">
                                    Market Cap: ${(acquirer.market_cap / 1000).toFixed(1)}B
                                  </Badge>
                                </div>
                                {acquirer.acquisition_history && acquirer.acquisition_history.length > 0 && (
                                  <div>
                                    <h6 className="font-medium text-orange-800 mb-1">Acquisition History:</h6>
                                    <div className="space-y-1">
                                      {acquirer.acquisition_history.map((acquisition, histIndex) => (
                                        <div key={histIndex} className="flex items-center space-x-2">
                                          <div className="w-2 h-2 bg-orange-500 rounded-full"></div>
                                          <span className="text-sm text-orange-700">{acquisition}</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Summary Stats */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="text-center p-3 bg-blue-50 rounded">
                        <div className="text-lg font-bold text-blue-600">
                          {results.market_research?.acquirers?.length || 0}
                        </div>
                        <div className="text-xs text-gray-600">Identified Acquirers</div>
                      </div>
                      <div className="text-center p-3 bg-green-50 rounded">
                        <div className="text-lg font-bold text-green-600">
                          {results.market_research?.potential_acquirers?.length || 0}
                        </div>
                        <div className="text-xs text-gray-600">Potential Matches</div>
                      </div>
                      <div className="text-center p-3 bg-purple-50 rounded">
                        <div className="text-lg font-bold text-purple-600">
                          {formatPercentage(results.summary?.mega_exit_probability || 0)}
                        </div>
                        <div className="text-xs text-gray-600">Mega Exit Probability</div>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  );
} 