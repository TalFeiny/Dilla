'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Brain, TrendingUp, DollarSign, AlertCircle, Building2, Calendar, Target, Zap, Award, Users } from 'lucide-react';
import { SafeNumber } from './SafeNumber';
import { DebugWrapper } from './DebugWrapper';
import { Progress } from '@/components/ui/progress';
import { LiquidationWaterfall } from '@/components/liquidation-waterfall';
import { OutcomeDistribution } from './OutcomeDistribution';

interface PWERMResultsDisplayV2Props {
  results: any;
}

export function PWERMResultsDisplayV2({ results }: PWERMResultsDisplayV2Props) {
  console.log('PWERMResultsDisplayV2 received:', results);
  console.log('Results type:', typeof results);
  console.log('Results keys:', results ? Object.keys(results) : 'null');
  
  if (!results) {
    return (
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>No Results</AlertTitle>
        <AlertDescription>No analysis results to display.</AlertDescription>
      </Alert>
    );
  }

  const { 
    summary, 
    market_research, 
    market_landscape,
    scenarios, 
    company_data,
    categorization,
    outlier_analysis 
  } = results;
  
  // Build citation map (Perplexity-style)
  const citations = new Map<string, { index: number; url?: string }>();
  let citationIndex = 1;
  
  const getCitation = (source: string | { title: string; url?: string }): string => {
    if (!source) return '';
    const key = typeof source === 'string' ? source : source.title;
    if (!key) return '';
    
    if (!citations.has(key)) {
      citations.set(key, {
        index: citationIndex++,
        url: typeof source === 'object' ? source.url : undefined
      });
    }
    const citation = citations.get(key);
    return citation ? `[${citation.index}]` : '';
  };
  
  // Calculate key metrics
  const expectedValue = summary?.expected_exit_value || 0;
  const medianValue = summary?.median_exit_value || 0;
  const successProb = summary?.success_probability || 0;
  const megaExitProb = summary?.mega_exit_probability || 0;
  
  // Debug logging
  console.log('PWERM Metrics Debug:', {
    expectedValue,
    medianValue,
    successProb,
    megaExitProb,
    expectedValueFormatted: `$${expectedValue.toFixed(1)}M`,
    medianValueFormatted: `$${medianValue.toFixed(1)}M`,
    exitComparablesCount: market_research?.exit_comparables?.length,
    firstExitComp: market_research?.exit_comparables?.[0],
    hasMarketResearch: !!market_research,
    marketResearchKeys: market_research ? Object.keys(market_research) : []
  });
  
  // Get funding history from company data
  const fundingHistory: any = company_data?.funding_history || market_research?.company_funding || {};
  const totalRaised = fundingHistory?.total_raised || company_data?.funding || 0;
  const lastValuation = fundingHistory?.last_valuation || 0;
  const latestRound: any = fundingHistory?.latest_round || {};
  
  // Get outlier score
  const outlierScore = outlier_analysis?.overall_outlier_score || 0;
  const outlierProbability = outlier_analysis?.outlier_probability || 0;
  
  return (
    <div className="space-y-6">
      {/* Main Valuation Card - THE KEY OUTPUT */}
      <Card className="border-2 border-primary">
        <CardHeader className="bg-primary/5">
          <CardTitle className="flex items-center justify-between">
            <span className="flex items-center gap-2">
              <DollarSign className="h-6 w-6" />
              PWERM Valuation Analysis
            </span>
            <Badge variant="outline" className="text-lg">
              {company_data?.name || 'Company'}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Expected Exit Value - PRIMARY METRIC */}
            <div className="text-center p-4 bg-green-50 dark:bg-green-950 rounded-lg">
              <p className="text-sm text-muted-foreground mb-2">Expected Exit Value</p>
              <p className="text-4xl font-bold text-green-600 dark:text-green-400">
                {`$${expectedValue.toFixed(1)}M`}
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                Probability-weighted average
              </p>
            </div>
            
            {/* Median Exit Value */}
            <div className="text-center p-4 bg-blue-50 dark:bg-blue-950 rounded-lg">
              <p className="text-sm text-muted-foreground mb-2">Median Exit Value</p>
              <p className="text-4xl font-bold text-blue-600 dark:text-blue-400">
                {`$${medianValue.toFixed(1)}M`}
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                50th percentile outcome
              </p>
            </div>
            
            {/* Success Probability */}
            <div className="text-center p-4 bg-gray-50 dark:bg-gray-950 rounded-lg">
              <p className="text-sm text-muted-foreground mb-2">Success Probability</p>
              <p className="text-4xl font-bold text-gray-600 dark:text-gray-400">
                {`${(successProb * 100).toFixed(1)}%`}
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                Probability of 3x+ return
              </p>
            </div>
          </div>
          
          {/* Graduation Rates Assessment */}
          {outlierScore > 0 && (
            <div className="mt-6 p-4 bg-amber-50 dark:bg-amber-950 rounded-lg">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold flex items-center gap-2">
                  <Award className="h-5 w-5" />
                  Company Quality Assessment
                </h3>
                <Badge variant={outlierScore > 70 ? "default" : outlierScore > 40 ? "secondary" : "outline"}>
                  Outlier Score: {outlierScore}/100
                </Badge>
              </div>
              <Progress value={outlierScore} className="h-3 mb-2" />
              <p className="text-sm text-muted-foreground">
                {outlierScore > 70 
                  ? "Exceptional company - using premium graduation rates (70%+ Series C to exit)"
                  : outlierScore > 40
                  ? "Strong company - using standard graduation rates (40% Series C to exit)"
                  : "Average company - using conservative graduation rates (20% Series C to exit)"}
              </p>
              {outlier_analysis?.outlier_reasoning && (
                <p className="text-sm mt-2">{outlier_analysis.outlier_reasoning}</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Company & Funding Info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Company Overview */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="h-5 w-5" />
              Company Overview
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div>
                <p className="text-sm text-muted-foreground">Sector Classification</p>
                <p className="font-medium">{categorization?.sector || company_data?.sector || 'Unknown'}</p>
                {categorization?.subsector && (
                  <p className="text-sm text-muted-foreground">{categorization.subsector}</p>
                )}
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Current ARR</p>
                <p className="font-medium">{`$${(company_data?.revenue || 0).toFixed(1)}M`}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Growth Rate</p>
                <p className="font-medium">{((company_data?.growth_rate || 0) * 100).toFixed(0)}% annually</p>
              </div>
              {market_landscape?.submarket && (
                <div>
                  <p className="text-sm text-muted-foreground">Submarket</p>
                  <p className="font-medium">
                    {typeof market_landscape.submarket === 'string' 
                      ? market_landscape.submarket 
                      : market_landscape.submarket?.name || 'N/A'}
                  </p>
                  {typeof market_landscape.submarket === 'object' && market_landscape.submarket?.description && (
                    <p className="text-xs text-muted-foreground mt-1">{market_landscape.submarket.description}</p>
                  )}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Funding History */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="h-5 w-5" />
              Funding History
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div>
                <p className="text-sm text-muted-foreground">Total Raised</p>
                <p className="font-medium">
                  {totalRaised > 0 ? `$${totalRaised.toFixed(1)}M` : 'Not disclosed'}
                </p>
              </div>
              {lastValuation > 0 && (
                <div>
                  <p className="text-sm text-muted-foreground">Last Valuation</p>
                  <p className="font-medium">{`$${lastValuation.toFixed(1)}M`}</p>
                </div>
              )}
              {latestRound?.stage && (
                <div>
                  <p className="text-sm text-muted-foreground">Latest Round</p>
                  <p className="font-medium">{latestRound.stage}</p>
                  {latestRound.amount && (
                    <p className="text-sm text-muted-foreground">
                      {`$${latestRound.amount.toFixed(1)}M`}
                    </p>
                  )}
                </div>
              )}
              {fundingHistory?.investors && fundingHistory.investors.length > 0 && (
                <div>
                  <p className="text-sm text-muted-foreground">Key Investors</p>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {fundingHistory.investors.slice(0, 5).map((investor: string, idx: number) => (
                      <Badge key={idx} variant="outline" className="text-xs">
                        {investor}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Outcome Distribution Chart */}
      {scenarios && scenarios.length > 0 && (
        <OutcomeDistribution 
          scenarios={scenarios}
          expectedValue={expectedValue}
        />
      )}

      <Tabs defaultValue="market" className="w-full">
        <TabsList className={`grid w-full ${fundingHistory?.rounds?.length > 0 ? 'grid-cols-5' : 'grid-cols-4'}`}>
          <TabsTrigger value="market">Market Analysis</TabsTrigger>
          <TabsTrigger value="scenarios">Exit Scenarios</TabsTrigger>
          <TabsTrigger value="comparables">Comparables</TabsTrigger>
          <TabsTrigger value="acquirers">Potential Acquirers</TabsTrigger>
          {fundingHistory?.rounds?.length > 0 && (
            <TabsTrigger value="waterfall">Waterfall</TabsTrigger>
          )}
        </TabsList>

        {/* Market Analysis Tab */}
        <TabsContent value="market">
          <Card>
            <CardHeader>
              <CardTitle>Market Intelligence</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {/* Competitors */}
                {market_landscape?.competitors && market_landscape.competitors.length > 0 && (
                  <div>
                    <h3 className="font-semibold mb-2">Direct Competitors
                      <Badge variant="outline" className="ml-2 text-xs font-normal">
                        Source: Market Research
                      </Badge>
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {market_landscape.competitors.slice(0, 10).map((comp: any, idx: number) => (
                        <div key={idx} className="flex items-center justify-between p-2 border rounded">
                          <span className="font-medium">
                            {comp.name}
                            {comp.source && (
                              <sup className="text-xs text-blue-600 ml-1">{getCitation(comp.source || 'Market Research')}</sup>
                            )}
                          </span>
                          {comp.stage && <Badge variant="outline">{comp.stage}</Badge>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Incumbents */}
                {market_landscape?.incumbents && market_landscape.incumbents.length > 0 && (
                  <div>
                    <h3 className="font-semibold mb-2">Market Incumbents
                      <Badge variant="outline" className="ml-2 text-xs font-normal">
                        Source: Industry Analysis
                      </Badge>
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {market_landscape.incumbents.slice(0, 6).map((inc: any, idx: number) => (
                        <div key={idx} className="flex items-center justify-between p-2 border rounded">
                          <span className="font-medium">{inc.name}</span>
                          {inc.type && <Badge variant="secondary">{inc.type}</Badge>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Market Dynamics */}
                {market_landscape?.fragmentation && (
                  <div>
                    <h3 className="font-semibold mb-2">Market Dynamics</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-sm text-muted-foreground">Market Fragmentation</p>
                        <Badge variant={
                          market_landscape.fragmentation.level === 'high' ? 'default' : 
                          market_landscape.fragmentation.level === 'medium' ? 'secondary' : 'outline'
                        }>
                          {market_landscape.fragmentation.level}
                        </Badge>
                      </div>
                      {market_landscape.market_size && (
                        <div>
                          <p className="text-sm text-muted-foreground">TAM (Total Addressable Market)</p>
                          <p className="font-medium text-lg">{market_landscape.market_size}</p>
                        </div>
                      )}
                      {market_landscape.sam && (
                        <div>
                          <p className="text-sm text-muted-foreground">SAM (Serviceable Addressable)</p>
                          <p className="font-medium">{market_landscape.sam}</p>
                        </div>
                      )}
                      {market_landscape.som && (
                        <div>
                          <p className="text-sm text-muted-foreground">SOM (Obtainable Market)</p>
                          <p className="font-medium">{market_landscape.som}</p>
                        </div>
                      )}
                      {market_landscape.growth_rate && (
                        <div>
                          <p className="text-sm text-muted-foreground">Market Growth</p>
                          <p className="font-medium">{market_landscape.growth_rate}</p>
                        </div>
                      )}
                      {market_landscape.submarket && (
                        <div className="col-span-2">
                          <p className="text-sm text-muted-foreground">Specific Submarket</p>
                          <p className="font-medium text-gray-600 dark:text-gray-400">
                            {typeof market_landscape.submarket === 'string' 
                              ? market_landscape.submarket 
                              : market_landscape.submarket?.name || 'N/A'}
                          </p>
                          {typeof market_landscape.submarket === 'object' && (
                            <>
                              {market_landscape.submarket?.description && (
                                <p className="text-sm text-muted-foreground mt-1">{market_landscape.submarket.description}</p>
                              )}
                              {market_landscape.submarket?.estimated_size && (
                                <p className="text-sm mt-1">
                                  <span className="text-muted-foreground">Size:</span> {market_landscape.submarket.estimated_size}
                                </p>
                              )}
                              {market_landscape.submarket?.key_differentiator && (
                                <p className="text-sm mt-1">
                                  <span className="text-muted-foreground">Key Differentiator:</span> {market_landscape.submarket.key_differentiator}
                                </p>
                              )}
                            </>
                          )}
                        </div>
                      )}
                    </div>
                    {market_landscape.fragmentation.explanation && (
                      <p className="text-sm text-muted-foreground mt-2">
                        {market_landscape.fragmentation.explanation}
                      </p>
                    )}
                  </div>
                )}

                {/* Barriers to Entry / Moat Analysis */}
                {market_landscape?.barriers_to_entry && market_landscape.barriers_to_entry.length > 0 && (
                  <div>
                    <h3 className="font-semibold mb-2">Competitive Moat & Barriers to Entry</h3>
                    <div className="space-y-2">
                      {market_landscape.barriers_to_entry.map((barrier: string, idx: number) => (
                        <div key={idx} className="flex items-start gap-2">
                          <div className="w-2 h-2 rounded-full bg-gray-500 mt-1.5 flex-shrink-0" />
                          <p className="text-sm">{barrier}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Scenarios Tab */}
        <TabsContent value="scenarios">
          <Card>
            <CardHeader>
              <CardTitle>Exit Scenario Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              {scenarios && scenarios.length > 0 ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="text-center p-3 border rounded">
                      <p className="text-sm text-muted-foreground">IPO</p>
                      <p className="text-xl font-bold">
                        {(scenarios.filter((s: any) => s.type === 'ipo').length / scenarios.length * 100).toFixed(1)}%
                      </p>
                    </div>
                    <div className="text-center p-3 border rounded">
                      <p className="text-sm text-muted-foreground">Strategic Acquisition</p>
                      <p className="text-xl font-bold">
                        {(scenarios.filter((s: any) => s.type === 'strategic_acquisition').length / scenarios.length * 100).toFixed(1)}%
                      </p>
                    </div>
                    <div className="text-center p-3 border rounded">
                      <p className="text-sm text-muted-foreground">Mega Exit</p>
                      <p className="text-xl font-bold">
                        {(scenarios.filter((s: any) => s.type === 'mega_exit').length / scenarios.length * 100).toFixed(1)}%
                      </p>
                    </div>
                    <div className="text-center p-3 border rounded">
                      <p className="text-sm text-muted-foreground">Liquidation</p>
                      <p className="text-xl font-bold">
                        {(scenarios.filter((s: any) => s.type === 'liquidation').length / scenarios.length * 100).toFixed(1)}%
                      </p>
                    </div>
                  </div>
                  
                  <div>
                    <h3 className="font-semibold mb-2">Top Exit Scenarios</h3>
                    <div className="space-y-2">
                      {scenarios
                        .sort((a: any, b: any) => b.exit_value - a.exit_value)
                        .slice(0, 5)
                        .map((scenario: any, idx: number) => (
                        <div key={idx} className="flex items-center justify-between p-2 border rounded">
                          <div>
                            <Badge variant={
                              scenario.type === 'ipo' ? 'default' :
                              scenario.type === 'mega_exit' ? 'secondary' :
                              scenario.type === 'strategic_acquisition' ? 'outline' : 'destructive'
                            }>
                              {scenario.type.replace('_', ' ')}
                            </Badge>
                            <span className="ml-2 text-sm">{scenario.description}</span>
                          </div>
                          <span className="font-bold">
                            {`$${(scenario.exit_value / 1000000).toFixed(1)}M`}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-muted-foreground">No scenario data available.</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Comparables Tab */}
        <TabsContent value="comparables">
          <div className="space-y-6">
            {/* Public Comparables */}
            <Card>
              <CardHeader>
                <CardTitle>Public Market Comparables</CardTitle>
                <CardDescription>
                  Similar public companies for valuation benchmarking
                  <Badge variant="outline" className="ml-2 text-xs">
                    Source: Public Market Data
                  </Badge>
                </CardDescription>
              </CardHeader>
              <CardContent>
                {market_research?.public_comparables && market_research.public_comparables.length > 0 ? (
                  <div className="space-y-3">
                    {market_research.public_comparables.slice(0, 8).map((comp: any, idx: number) => (
                      <div key={idx} className="p-4 border rounded-lg bg-gradient-to-r from-gray-50 to-gray-100 dark:from-gray-950/20 dark:to-gray-900/20">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="font-semibold text-lg">
                              {comp.company || comp.name}
                              {comp.source && (
                                <sup className="text-xs text-blue-600 ml-1">{getCitation(comp.source)}</sup>
                              )}
                            </p>
                            {comp.ticker && (
                              <p className="text-sm text-muted-foreground font-mono">
                                {comp.ticker}
                              </p>
                            )}
                            {comp.rationale && (
                              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                                {comp.rationale}
                              </p>
                            )}
                          </div>
                          <div className="text-right">
                            {comp.market_cap && (
                              <p className="font-bold text-lg">{comp.market_cap}</p>
                            )}
                            {comp.ev_revenue_multiple && (
                              <p className="text-sm font-semibold text-gray-600 dark:text-gray-400">
                                {comp.ev_revenue_multiple.toFixed(1)}x EV/Rev
                              </p>
                            )}
                            {comp.revenue_growth && (
                              <p className="text-sm text-muted-foreground">
                                {comp.revenue_growth}% growth
                              </p>
                            )}
                            {comp.relevance_score && (
                              <Badge className="mt-1" variant={comp.relevance_score > 0.7 ? "default" : "secondary"}>
                                {(comp.relevance_score * 100).toFixed(0)}% match
                              </Badge>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                    {market_research.median_ev_multiple && (
                      <div className="mt-4 p-3 bg-gray-100 dark:bg-gray-900/30 rounded-lg">
                        <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">
                          Median Public Multiple: {market_research.median_ev_multiple.toFixed(1)}x EV/Revenue
                        </p>
                        <p className="text-xs text-gray-600 dark:text-gray-300 mt-1">
                          Source: PublicSaaS Index / SVB Benchmarks
                        </p>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-muted-foreground">No public comparables data available.</p>
                )}
              </CardContent>
            </Card>

            {/* Exit Comparables */}
            <Card>
              <CardHeader>
                <CardTitle>Recent M&A Transactions</CardTitle>
                <CardDescription>
                  Comparable private company exits in the sector
                  <Badge variant="outline" className="ml-2 text-xs">
                    Source: {market_research?.exit_comparables?.[0]?.source || 'Market Research'}
                  </Badge>
                </CardDescription>
              </CardHeader>
              <CardContent>
                {(market_research?.exit_comparables && market_research.exit_comparables.length > 0) || 
                 (results?.ma_transactions && results.ma_transactions.length > 0) ? (
                <div className="space-y-2">
                  {(market_research?.exit_comparables || results?.ma_transactions || []).slice(0, 10).map((comp: any, idx: number) => (
                    <div key={idx} className="p-3 border rounded-lg">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium">{comp.company || comp.company_name || comp.target || 'Unknown'}</p>
                          {comp.acquirer && (
                            <p className="text-sm text-muted-foreground">
                              Acquired by {comp.acquirer}
                            </p>
                          )}
                        </div>
                        <div className="text-right">
                          {comp.deal_value && (
                            <p className="font-bold">
                              {typeof comp.deal_value === 'number' 
                                ? `$${comp.deal_value.toFixed(1)}M`
                                : comp.deal_value
                              }
                            </p>
                          )}
                          {(comp.ev_revenue_multiple || comp.revenue_multiple) && (
                            <p className="text-sm text-muted-foreground">
                              {typeof (comp.ev_revenue_multiple || comp.revenue_multiple) === 'number'
                                ? `${(comp.ev_revenue_multiple || comp.revenue_multiple).toFixed(1)}x revenue`
                                : `${comp.ev_revenue_multiple || comp.revenue_multiple}x revenue`
                              }
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted-foreground">No comparable transactions found.</p>
              )}
            </CardContent>
          </Card>
          </div>
        </TabsContent>

        {/* Potential Acquirers Tab */}
        <TabsContent value="acquirers">
          <Card>
            <CardHeader>
              <CardTitle>Potential Strategic Acquirers</CardTitle>
              <CardDescription>
                Based on market analysis and M&A activity
                <Badge variant="outline" className="ml-2 text-xs">
                  Source: Strategic Analysis
                </Badge>
              </CardDescription>
            </CardHeader>
            <CardContent>
              {market_research?.potential_acquirers && market_research.potential_acquirers.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {market_research.potential_acquirers.slice(0, 10).map((acq: any, idx: number) => (
                    <div key={idx} className="p-3 border rounded-lg">
                      <p className="font-medium">{acq.name}</p>
                      {acq.market_cap && (
                        <p className="text-sm text-muted-foreground">
                          Market Cap: {acq.market_cap}
                        </p>
                      )}
                      {acq.recent_acquisitions && acq.recent_acquisitions.length > 0 && (
                        <p className="text-xs text-muted-foreground mt-1">
                          Recent: {acq.recent_acquisitions[0]}
                        </p>
                      )}
                      {acq.source && (
                        <p className="text-xs text-muted-foreground mt-1">
                          <span className="font-medium">Source:</span> {acq.source}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : market_research?.data_driven_acquirers && market_research.data_driven_acquirers.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {market_research.data_driven_acquirers.slice(0, 10).map((acq: any, idx: number) => (
                    <div key={idx} className="p-3 border rounded-lg">
                      <p className="font-medium">{acq.name}</p>
                      {acq.deals_count > 0 && (
                        <p className="text-sm text-muted-foreground">
                          {acq.deals_count} recent acquisitions
                        </p>
                      )}
                      {acq.avg_acquisition_multiple && (
                        <p className="text-xs text-muted-foreground">
                          Avg multiple: {acq.avg_acquisition_multiple.toFixed(1)}x
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted-foreground">No potential acquirers identified.</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Citation Sources - Perplexity Style */}
      {citations.size > 0 && (
        <Card className="mt-6 bg-gray-50 dark:bg-gray-900">
          <CardHeader>
            <CardTitle className="text-sm font-medium">Sources</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              {Array.from(citations.entries())
                .sort((a, b) => a[1].index - b[1].index)
                .map(([source, citation]) => (
                  <div key={citation.index} className="flex items-start gap-2 text-xs">
                    <span className="text-blue-600 font-medium min-w-Array.from(x)">[{citation.index}]</span>
                    {citation.url ? (
                      <a
                        href={citation.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 underline cursor-pointer"
                      >
                        {source}
                      </a>
                    ) : (
                      <span className="text-gray-600 dark:text-gray-400">{source}</span>
                    )}
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Sources Section */}
      {results.sources && results.sources.length > 0 && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5" />
              Data Sources & References
            </CardTitle>
            <CardDescription>
              Analysis based on {results.sources.length} sources
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {results.sources
                .sort((a: any, b: any) => (b.relevance_score || 0) - (a.relevance_score || 0))
                .map((source: any, idx: number) => (
                <div key={idx} className="flex items-start gap-3 p-3 border rounded-lg hover:bg-accent/50 transition-colors">
                  <span className="text-sm font-medium text-muted-foreground min-w-Array.from(x)">
                    {idx + 1}.
                  </span>
                  <div className="flex-1">
                    <a 
                      href={source.url} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
                    >
                      {source.title}
                    </a>
                    {source.relevance_score > 0 && (
                      <span className="ml-2 text-xs text-muted-foreground">
                        (relevance: {(source.relevance_score * 100).toFixed(0)}%)
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}