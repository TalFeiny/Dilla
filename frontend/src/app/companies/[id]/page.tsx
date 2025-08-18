'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, TrendingUp, TrendingDown, DollarSign, Users, Target } from 'lucide-react';

interface Company {
  id: string;
  name: string;
  sector: string;
  status: string;
  current_arr_usd: number;
  total_invested_usd: number;
  ownership_percentage: number;
  revenue_growth_annual_pct: number;
  funnel_status: string;
  fund_id: string;
  has_pwerm_model: boolean;
  latest_pwerm_run_at: string;
  pwerm_scenarios_count: number;
  latest_waterfall_run_at: string;
}

interface PWERMResults {
  scenarios: Record<string, any>;
  expected_return: number;
  risk_score: number;
  confidence: number;
  irr: number;
  tvpi: number;
}

interface WaterfallResults {
  gp_share: number;
  lp_share: number;
  carry_waterfall: any[];
  total_return: number;
}

export default function CompanyPage() {
  const params = useParams();
  const companyId = params.id as string;
  
  const [company, setCompany] = useState<Company | null>(null);
  const [loading, setLoading] = useState(true);
  const [pwermLoading, setPwermLoading] = useState(false);
  const [waterfallLoading, setWaterfallLoading] = useState(false);
  const [pwermResults, setPwermResults] = useState<PWERMResults | null>(null);
  const [waterfallResults, setWaterfallResults] = useState<WaterfallResults | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchCompany();
  }, [companyId]);

  const fetchCompany = async () => {
    try {
      const response = await fetch(`/api/companies/${companyId}`);
      if (!response.ok) {
        throw new Error('Failed to fetch company');
      }
      const data = await response.json();
      setCompany(data);
    } catch (err) {
      setError('Failed to load company data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const runPWERM = async () => {
    setPwermLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`/api/companies/${companyId}/pwerm`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'PWERM analysis failed');
      }

      const data = await response.json();
      
      // Extract results from the response
      if (data.results) {
        // Calculate derived metrics for display
        const results = data.results;
        
        // Convert scenarios array to object format for display
        const scenariosObj: Record<string, any> = {};
        if (Array.isArray(results.scenarios)) {
          // Group scenarios by type and aggregate probabilities
          const typeGroups: Record<string, { probability: number; count: number; avgValue: number }> = {};
          
          results.scenarios.forEach((scenario: any) => {
            if (!typeGroups[scenario.type]) {
              typeGroups[scenario.type] = { probability: 0, count: 0, avgValue: 0 };
            }
            typeGroups[scenario.type].probability += scenario.probability;
            typeGroups[scenario.type].count += 1;
            typeGroups[scenario.type].avgValue += scenario.exit_value;
          });
          
          // Convert to display format
          Object.entries(typeGroups).forEach(([type, data]) => {
            scenariosObj[type] = {
              probability: data.probability,
              avgValue: data.avgValue / data.count,
              count: data.count
            };
          });
        }
        
        setPwermResults({
          scenarios: scenariosObj,
          expected_return: results.summary?.success_probability || 0,
          risk_score: 1 - (results.summary?.success_probability || 0),
          confidence: results.summary?.success_probability || 0,
          irr: 0.15, // Default IRR, calculate from scenarios if needed
          tvpi: results.summary?.expected_exit_value ? 
            (results.summary.expected_exit_value / (company.total_invested_usd / 1000000)) : 1.5
        });
      }
      
      await fetchCompany(); // Refresh company data to get updated PWERM status
    } catch (err) {
      setError(err instanceof Error ? err.message : 'PWERM analysis failed');
    } finally {
      setPwermLoading(false);
    }
  };

  const runWaterfall = async () => {
    setWaterfallLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`/api/companies/${companyId}/waterfall`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Waterfall analysis failed');
      }

      const data = await response.json();
      setWaterfallResults(data.waterfall_results);
      await fetchCompany(); // Refresh company data to get updated waterfall status
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Waterfall analysis failed');
    } finally {
      setWaterfallLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto p-6">
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-8 w-8 animate-spin" />
        </div>
      </div>
    );
  }

  if (!company) {
    return (
      <div className="container mx-auto p-6">
        <Alert>
          <AlertDescription>Company not found</AlertDescription>
        </Alert>
      </div>
    );
  }

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'active':
        return 'bg-green-100 text-green-800';
      case 'exited':
        return 'bg-blue-100 text-blue-800';
      case 'distressed':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getSectorColor = (sector: string) => {
    const colors = [
      'bg-purple-100 text-purple-800',
      'bg-indigo-100 text-indigo-800',
      'bg-pink-100 text-pink-800',
      'bg-yellow-100 text-yellow-800',
      'bg-orange-100 text-orange-800',
    ];
    const index = sector?.length || 0;
    return colors[index % colors.length];
  };

  return (
    <div className="container mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">{company.name}</h1>
        <div className="flex gap-2 mb-4">
          <Badge className={getSectorColor(company.sector)}>
            {company.sector || 'Unknown Sector'}
          </Badge>
          <Badge className={getStatusColor(company.status)}>
            {company.status || 'Unknown Status'}
          </Badge>
          {company.has_pwerm_model && (
            <Badge className="bg-green-100 text-green-800">
              PWERM Model Available
            </Badge>
          )}
        </div>
      </div>

      {error && (
        <Alert className="mb-6">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">ARR</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              ${(company.current_arr_usd || 0).toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">
              Annual Recurring Revenue
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Investment</CardTitle>
            <Target className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              ${(company.total_invested_usd || 0).toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">
              Total Invested
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Ownership</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(company.ownership_percentage || 0).toFixed(1)}%
            </div>
            <p className="text-xs text-muted-foreground">
              Ownership Stake
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Growth</CardTitle>
            {company.revenue_growth_annual_pct > 0 ? (
              <TrendingUp className="h-4 w-4 text-green-600" />
            ) : (
              <TrendingDown className="h-4 w-4 text-red-600" />
            )}
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(company.revenue_growth_annual_pct || 0).toFixed(1)}%
            </div>
            <p className="text-xs text-muted-foreground">
              Annual Growth Rate
            </p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="analysis" className="space-y-4">
        <TabsList>
          <TabsTrigger value="analysis">Analysis</TabsTrigger>
          <TabsTrigger value="pwerm">PWERM Model</TabsTrigger>
          <TabsTrigger value="waterfall">Waterfall</TabsTrigger>
        </TabsList>

        <TabsContent value="analysis" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Financial Analysis</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between items-center">
                <span>Revenue Multiple</span>
                <span className="font-semibold">
                  {company.current_arr_usd > 0 
                    ? ((company.total_invested_usd || 0) / company.current_arr_usd).toFixed(2)
                    : 'N/A'
                  }
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span>Valuation</span>
                <span className="font-semibold">
                  ${((company.current_arr_usd || 0) * 10).toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span>Last PWERM Run</span>
                <span className="font-semibold">
                  {company.latest_pwerm_run_at 
                    ? new Date(company.latest_pwerm_run_at).toLocaleDateString()
                    : 'Never'
                  }
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span>PWERM Scenarios</span>
                <span className="font-semibold">
                  {company.pwerm_scenarios_count || 0}
                </span>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="pwerm" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>PWERM Analysis</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-4">
                <Button 
                  onClick={runPWERM} 
                  disabled={pwermLoading}
                  className="flex-1"
                >
                  {pwermLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Running PWERM...
                    </>
                  ) : (
                    'Run PWERM Analysis'
                  )}
                </Button>
              </div>

              {pwermResults && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="text-center">
                      <div className="text-2xl font-bold text-green-600">
                        {(pwermResults.expected_return * 100).toFixed(1)}%
                      </div>
                      <div className="text-sm text-muted-foreground">Expected Return</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-blue-600">
                        {(pwermResults.irr * 100).toFixed(1)}%
                      </div>
                      <div className="text-sm text-muted-foreground">IRR</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-purple-600">
                        {pwermResults.tvpi.toFixed(2)}
                      </div>
                      <div className="text-sm text-muted-foreground">TVPI</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-orange-600">
                        {(pwermResults.confidence * 100).toFixed(1)}%
                      </div>
                      <div className="text-sm text-muted-foreground">Confidence</div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <h4 className="font-semibold">Risk Score</h4>
                    <Progress value={pwermResults.risk_score * 100} className="w-full" />
                    <div className="text-sm text-muted-foreground">
                      Risk Level: {(pwermResults.risk_score * 100).toFixed(1)}%
                    </div>
                  </div>

                  {pwermResults.scenarios && (
                    <div>
                      <h4 className="font-semibold mb-2">Top Scenarios</h4>
                      <div className="space-y-2">
                        {Object.entries(pwermResults.scenarios)
                          .slice(0, 5)
                          .map(([scenario, data]: [string, any]) => (
                            <div key={scenario} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                              <span className="text-sm">{scenario}</span>
                              <span className="text-sm font-semibold">
                                {(data.probability * 100).toFixed(1)}%
                              </span>
                            </div>
                          ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="waterfall" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Waterfall Analysis</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-4">
                <Button 
                  onClick={runWaterfall} 
                  disabled={waterfallLoading}
                  className="flex-1"
                >
                  {waterfallLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Running Waterfall...
                    </>
                  ) : (
                    'Run Waterfall Analysis'
                  )}
                </Button>
              </div>

              {waterfallResults && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="text-center">
                      <div className="text-2xl font-bold text-green-600">
                        {(waterfallResults.gp_share * 100).toFixed(1)}%
                      </div>
                      <div className="text-sm text-muted-foreground">GP Share</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-blue-600">
                        {(waterfallResults.lp_share * 100).toFixed(1)}%
                      </div>
                      <div className="text-sm text-muted-foreground">LP Share</div>
                    </div>
                  </div>

                  <div className="text-center">
                    <div className="text-2xl font-bold text-purple-600">
                      {(waterfallResults.total_return * 100).toFixed(1)}%
                    </div>
                    <div className="text-sm text-muted-foreground">Total Return</div>
                  </div>

                  {waterfallResults.carry_waterfall && (
                    <div>
                      <h4 className="font-semibold mb-2">Carry Waterfall</h4>
                      <div className="space-y-2">
                        {waterfallResults.carry_waterfall.map((item: any, index: number) => (
                          <div key={index} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                            <span className="text-sm">{item.description}</span>
                            <span className="text-sm font-semibold">
                              ${item.amount.toLocaleString()}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
} 