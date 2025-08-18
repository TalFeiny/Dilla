'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { 
  Building2, 
  TrendingUp, 
  DollarSign, 
  AlertCircle,
  Users,
  Scale,
  Target,
  Brain,
  ChartBar
} from 'lucide-react';

interface PWERMResultsDisplayProps {
  results: any;
}

export function PWERMResultsDisplay({ results }: PWERMResultsDisplayProps) {
  console.log('PWERMResultsDisplay received:', results);
  
  if (!results) {
    console.log('PWERMResultsDisplay: No results provided');
    return null;
  }

  const { summary, market_research, scenarios, company_data, exit_distribution_chart } = results;
  
  console.log('PWERMResultsDisplay data:', {
    hasSummary: !!summary,
    hasMarketResearch: !!market_research,
    hasScenarios: !!scenarios,
    scenariosCount: scenarios?.length
  });
  const exitComparables = market_research?.exit_comparables || [];
  const competitors = market_research?.direct_competitors || [];
  const competitiveIntel = market_research?.competitive_intelligence || {};
  const legalIssues = market_research?.legal_issues || {};
  const ipoLikelihood = market_research?.ipo_likelihood || {};
  const potentialAcquirers = market_research?.potential_acquirers || [];

  // Group comparables by sector
  const comparablesBySector = exitComparables.reduce((acc: any, comp: any) => {
    const sector = comp.sector || 'Unknown';
    if (!acc[sector]) acc[sector] = [];
    acc[sector].push(comp);
    return acc;
  }, {});

  // Calculate average multiples by sector
  const sectorAverages = Object.entries(comparablesBySector).map(([sector, comps]: [string, any]) => {
    const multiples = comps.map((c: any) => c.ev_revenue_multiple || c.revenue_multiple || 0).filter((m: number) => m > 0);
    const avgMultiple = multiples.length > 0 ? multiples.reduce((a: number, b: number) => a + b, 0) / multiples.length : 0;
    return {
      sector,
      avgMultiple,
      count: comps.length,
      range: multiples.length > 0 ? `${Math.min(...multiples).toFixed(1)}x - ${Math.max(...multiples).toFixed(1)}x` : 'N/A'
    };
  }).filter(s => s.count > 0); // Only show sectors with data

  return (
    <div className="space-y-6">
      {/* Executive Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5" />
            Executive Summary
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">Expected Exit Value</p>
              <p className="text-2xl font-bold">
                {summary?.expected_exit_value ? `$${(summary.expected_exit_value || 0).toFixed(1)}M` : 'N/A'}
              </p>
              {summary?.adjusted_expected_value && (
                <p className="text-sm text-green-600">
                  Adjusted: ${(summary?.adjusted_expected_value || 0).toFixed(1)}M
                </p>
              )}
            </div>
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">Median Exit Value</p>
              <p className="text-2xl font-bold">
                {summary?.median_exit_value ? `$${(summary.median_exit_value || 0).toFixed(1)}M` : 'N/A'}
              </p>
              <p className="text-xs text-muted-foreground">50th percentile</p>
            </div>
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">Success Probability</p>
              <p className="text-2xl font-bold">{summary?.success_probability ? `${(summary.success_probability * 100).toFixed(1)}%` : 'N/A'}</p>
              <Progress value={summary?.success_probability ? summary.success_probability * 100 : 0} className="h-2" />
            </div>
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">IPO Probability</p>
              <p className="text-2xl font-bold">{summary?.ipo_probability ? `${(summary.ipo_probability * 100).toFixed(1)}%` : 'N/A'}</p>
              <Badge variant={summary?.ipo_probability > 0.15 ? "default" : "secondary"}>
                {ipoLikelihood?.likelihood || 'Low'}
              </Badge>
            </div>
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">Outlier Score</p>
              <p className="text-2xl font-bold">{summary?.outlier_score ? `${summary.outlier_score.toFixed(0)}/100` : 'N/A'}</p>
              <Progress value={summary?.outlier_score || 0} className="h-2" />
            </div>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="comparables" className="w-full">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="comparables">Comparables</TabsTrigger>
          <TabsTrigger value="competition">Competition</TabsTrigger>
          <TabsTrigger value="exit-analysis">Exit Analysis</TabsTrigger>
          <TabsTrigger value="risks">Risks & Legal</TabsTrigger>
          <TabsTrigger value="scenarios">Scenarios</TabsTrigger>
        </TabsList>

        {/* Comparables Tab */}
        <TabsContent value="comparables">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ChartBar className="h-5 w-5" />
                Market Comparables Analysis
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {/* Sector Summary */}
                {sectorAverages.length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold mb-3">Revenue Multiples by Sector</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {sectorAverages.map((sector) => (
                      <Card key={sector.sector}>
                        <CardContent className="pt-4">
                          <div className="flex justify-between items-start">
                            <div>
                              <p className="font-medium">{sector.sector}</p>
                              <p className="text-2xl font-bold">{sector.avgMultiple ? `${sector.avgMultiple.toFixed(1)}x` : 'N/A'}</p>
                              <p className="text-sm text-muted-foreground">Range: {sector.range}</p>
                            </div>
                            <Badge variant="outline">{sector.count} deals</Badge>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                    </div>
                  </div>
                )}

                {/* Individual Comparables */}
                <div>
                  <h3 className="text-lg font-semibold mb-3">Recent Comparable Transactions</h3>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Target
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Acquirer
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Sector
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Revenue Multiple
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Source
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {exitComparables.slice(0, 10).map((comp: any, idx: number) => (
                          <tr key={idx}>
                            <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                              {comp.target}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                              {comp.acquirer}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                              <Badge variant="outline">{comp.sector}</Badge>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                              {comp.ev_revenue_multiple || comp.revenue_multiple || comp.arr_multiple ? 
                                `${((comp.ev_revenue_multiple || comp.revenue_multiple || comp.arr_multiple || 0)).toFixed(1)}x` : 
                                'N/A'}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                              <Badge variant={comp.confidence === 'high' ? 'default' : 'secondary'}>
                                {comp.source}
                              </Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Competition Tab */}
        <TabsContent value="competition">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5" />
                Competitive Intelligence
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {/* Market Position */}
                <Alert>
                  <AlertTitle>Market Position</AlertTitle>
                  <AlertDescription>
                    {competitiveIntel.market_position || 'Unknown'}
                  </AlertDescription>
                </Alert>

                {/* Direct Competitors */}
                <div>
                  <h3 className="text-lg font-semibold mb-3">Direct Competitors</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {(competitiveIntel.main_competitors || competitors || []).slice(0, 6).map((comp: any, idx: number) => (
                      <Card key={idx}>
                        <CardContent className="pt-4">
                          <p className="font-medium">{typeof comp === 'string' ? comp : comp.name}</p>
                          {typeof comp === 'object' && comp.market_share && (
                            <p className="text-sm text-muted-foreground">Market Share: {comp.market_share}</p>
                          )}
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>

                {/* Competitive Dynamics */}
                {Object.keys(competitiveIntel.competitive_dynamics || {}).length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold mb-3">Competitive Analysis</h3>
                    {Object.entries(competitiveIntel.competitive_dynamics || {}).map(([competitor, analysis]: [string, any]) => (
                      <Card key={competitor} className="mb-4">
                        <CardHeader>
                          <CardTitle className="text-base">{competitor}</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                              <p className="font-medium text-green-600 mb-2">Our Advantages</p>
                              <ul className="list-disc list-inside text-sm space-y-1">
                                {(analysis.our_advantages || []).map((adv: string, idx: number) => (
                                  <li key={idx}>{adv}</li>
                                ))}
                              </ul>
                            </div>
                            <div>
                              <p className="font-medium text-red-600 mb-2">Their Advantages</p>
                              <ul className="list-disc list-inside text-sm space-y-1">
                                {(analysis.advantages_over_us || []).map((adv: string, idx: number) => (
                                  <li key={idx}>{adv}</li>
                                ))}
                              </ul>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Exit Analysis Tab */}
        <TabsContent value="exit-analysis">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="h-5 w-5" />
                Exit Analysis
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {/* IPO Analysis */}
                <div>
                  <h3 className="text-lg font-semibold mb-3">IPO Likelihood</h3>
                  <Alert className={ipoLikelihood.likelihood === 'High' ? 'border-green-500' : ''}>
                    <AlertTitle>
                      Likelihood: {ipoLikelihood.likelihood || 'Low'}
                    </AlertTitle>
                    <AlertDescription>
                      Timeline: {ipoLikelihood.timeline || 'Unknown'}
                      {ipoLikelihood.reasons && (
                        <ul className="list-disc list-inside mt-2">
                          {ipoLikelihood.reasons.map((reason: string, idx: number) => (
                            <li key={idx}>{reason}</li>
                          ))}
                        </ul>
                      )}
                    </AlertDescription>
                  </Alert>
                </div>

                {/* Potential Acquirers */}
                <div>
                  <h3 className="text-lg font-semibold mb-3">Potential Acquirers</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {potentialAcquirers.map((acquirer: any, idx: number) => (
                      <Card key={idx}>
                        <CardContent className="pt-4">
                          <p className="font-medium">{acquirer.name}</p>
                          <div className="flex items-center gap-2 mt-2">
                            <Badge variant={
                              acquirer.strategic_fit === 'High' ? 'default' : 
                              acquirer.strategic_fit === 'Medium' ? 'secondary' : 'outline'
                            }>
                              {acquirer.strategic_fit} Fit
                            </Badge>
                            <Badge variant="outline">
                              {acquirer.likelihood} Likelihood
                            </Badge>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Risks Tab */}
        <TabsContent value="risks">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertCircle className="h-5 w-5" />
                Risk Assessment
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {/* Legal Issues */}
                <div>
                  <h3 className="text-lg font-semibold mb-3">Legal Issues</h3>
                  <Alert className={legalIssues.has_lawsuits ? 'border-red-500' : 'border-green-500'}>
                    <AlertCircle className="h-4 w-4" />
                    <AlertTitle>
                      {legalIssues.has_lawsuits ? 'Legal Issues Detected' : 'No Legal Issues Found'}
                    </AlertTitle>
                    <AlertDescription>
                      Risk Level: {legalIssues.risk_level || 'Low'}
                      {legalIssues.lawsuit_details && legalIssues.lawsuit_details.length > 0 && (
                        <ul className="list-disc list-inside mt-2">
                          {legalIssues.lawsuit_details.map((detail: any, idx: number) => (
                            <li key={idx} className="text-sm">
                              {detail.description}
                            </li>
                          ))}
                        </ul>
                      )}
                    </AlertDescription>
                  </Alert>
                </div>

                {/* Market Risks */}
                <div>
                  <h3 className="text-lg font-semibold mb-3">Market Dynamics</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Card>
                      <CardContent className="pt-4">
                        <p className="font-medium">TAM Growth</p>
                        <p className="text-2xl font-bold">
                          {((market_research?.market_dynamics?.tam_growth_rate || 0) * 100).toFixed(0)}%
                        </p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-4">
                        <p className="font-medium">Market Maturity</p>
                        <p className="text-lg">
                          {market_research?.market_dynamics?.maturity || 'Unknown'}
                        </p>
                      </CardContent>
                    </Card>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Scenarios Tab */}
        <TabsContent value="scenarios">
          <div className="space-y-6">
            {/* Exit Distribution Chart */}
            {exit_distribution_chart && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <ChartBar className="h-5 w-5" />
                    Exit Distribution Analysis
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <img 
                    src={`data:image/png;base64,${exit_distribution_chart}`} 
                    alt="Exit Distribution Chart" 
                    className="w-full max-w-4xl mx-auto"
                  />
                </CardContent>
              </Card>
            )}
            
            {/* Scenario Details Table */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <DollarSign className="h-5 w-5" />
                  Scenario Analysis (Top 10)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Type
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Exit Value
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Probability
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Revenue Multiple
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Description
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {(scenarios || []).slice(0, 10).map((scenario: any, idx: number) => (
                      <tr key={idx}>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                          <Badge variant={scenario.type === 'ipo' ? 'default' : 'secondary'}>
                            {scenario.type}
                          </Badge>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {scenario.exit_value ? `$${(scenario.exit_value || 0).toFixed(1)}M` : 'N/A'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {scenario.probability ? `${(scenario.probability * 100).toFixed(1)}%` : 'N/A'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {scenario.revenue_multiple ? `${(scenario.revenue_multiple || 0).toFixed(1)}x` : 'N/A'}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-500 max-w-xs truncate">
                          {scenario.description}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}