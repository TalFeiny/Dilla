'use client';

import React, { useState, useMemo } from 'react';
import { ICellRendererParams } from 'ag-grid-community';
import { ChevronRight, ChevronDown, Building2, TrendingUp, DollarSign, Users, Calendar, MapPin, ExternalLink, PieChart } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { FullTreemap } from './TreemapRenderer';

interface EnhancedMasterDetailParams extends ICellRendererParams {
  onExpand?: (rowId: string) => void;
  fetchDetails?: (rowId: string) => Promise<any>;
}

export const EnhancedMasterDetailRenderer = React.memo(function EnhancedMasterDetailRenderer(params: EnhancedMasterDetailParams) {
  const { value, data, onExpand, fetchDetails } = params;
  const [isExpanded, setIsExpanded] = useState(false);
  const [details, setDetails] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const handleToggle = async () => {
    const newExpanded = !isExpanded;
    setIsExpanded(newExpanded);

    if (newExpanded && fetchDetails && data?.id) {
      setLoading(true);
      try {
        const fetchedDetails = await fetchDetails(data.id);
        setDetails(fetchedDetails);
      } catch (error) {
        console.error('Error fetching details:', error);
      } finally {
        setLoading(false);
      }
    }

    if (onExpand && data?.id) {
      onExpand(data.id);
    }
  };

  const company = data?._originalRow || data;
  const hasDetails = company?.companyId || company?.companyName;

  return (
    <div className="w-full">
      <div className="flex items-center gap-2 py-1">
        <Button
          variant="ghost"
          size="sm"
          className="h-6 w-6 p-0"
          onClick={handleToggle}
          disabled={!hasDetails}
        >
          {isExpanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </Button>
        <span className="flex-1 font-medium">{value || company?.companyName || '—'}</span>
      </div>

      {isExpanded && hasDetails && (
        <div className="mt-2 ml-8 border-l-2 border-primary/20 pl-4 pb-4">
          {loading ? (
            <div className="text-sm text-muted-foreground">Loading details...</div>
          ) : (
            <CompanyDetailExpanded
              company={company}
              details={details}
              matrixData={data}
            />
          )}
        </div>
      )}
    </div>
  );
});

function CompanyDetailExpanded({ company, details, matrixData }: { 
  company: any; 
  details?: any;
  matrixData?: any;
}) {
  const companyData = details || company;
  
  // Extract financial metrics
  const arr = companyData?.arr ?? companyData?.cells?.arr?.value ?? null;
  const valuation = companyData?.valuation ?? companyData?.cells?.valuation?.value ?? null;
  const growthRate = companyData?.growthRate ?? companyData?.cells?.growthRate?.value ?? null;
  const burnRate = companyData?.burnRate ?? companyData?.cells?.burnRate?.value ?? null;
  const runway = companyData?.runway ?? companyData?.cells?.runway?.value ?? null;
  const stage = companyData?.stage || companyData?.cells?.stage?.value || 'Unknown';
  const sector = companyData?.sector || companyData?.cells?.sector?.value || 'Unknown';
  const employees = companyData?.employees ?? companyData?.cells?.employees?.value ?? null;
  const founded = companyData?.foundedYear || companyData?.cells?.foundedYear?.value;
  const location = companyData?.location || companyData?.cells?.location?.value || 'Unknown';

  // Build hierarchical data for treemap
  const hierarchicalData = [
    {
      name: sector,
      value: arr,
      children: [
        {
          name: stage,
          value: arr,
          children: [
            {
              name: companyData?.companyName || 'Company',
              value: arr,
            }
          ]
        }
      ]
    }
  ];

  return (
    <Card className="mt-2 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Building2 className="h-4 w-4" />
          {companyData?.companyName || 'Company Details'}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="overview" className="w-full">
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="financials">Financials</TabsTrigger>
            <TabsTrigger value="cap-table">Cap Table</TabsTrigger>
            <TabsTrigger value="hierarchy">Hierarchy</TabsTrigger>
            <TabsTrigger value="details">Details</TabsTrigger>
          </TabsList>
          
          <TabsContent value="overview" className="mt-4 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-muted-foreground mb-1">Stage</div>
                <Badge variant="outline">{stage}</Badge>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">Sector</div>
                <Badge variant="outline">{sector}</Badge>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">Location</div>
                <div className="flex items-center gap-1 text-sm">
                  <MapPin className="h-3 w-3" />
                  {location}
                </div>
              </div>
              {founded && (
                <div>
                  <div className="text-xs text-muted-foreground mb-1">Founded</div>
                  <div className="flex items-center gap-1 text-sm">
                    <Calendar className="h-3 w-3" />
                    {founded}
                  </div>
                </div>
              )}
            </div>
            
            {companyData?.description && (
              <div>
                <div className="text-xs text-muted-foreground mb-1">Description</div>
                <p className="text-sm">{companyData.description}</p>
              </div>
            )}
          </TabsContent>
          
          <TabsContent value="financials" className="mt-4 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <MetricCard
                label="ARR"
                value={arr}
                format="currency"
                icon={<DollarSign className="h-4 w-4" />}
              />
              <MetricCard
                label="Valuation"
                value={valuation}
                format="currency"
                icon={<TrendingUp className="h-4 w-4" />}
              />
              <MetricCard
                label="Growth Rate"
                value={growthRate}
                format="percentage"
                icon={<TrendingUp className="h-4 w-4" />}
              />
              <MetricCard
                label="Burn Rate"
                value={burnRate}
                format="currency"
                icon={<DollarSign className="h-4 w-4" />}
              />
              <MetricCard
                label="Runway"
                value={runway}
                format="months"
                icon={<Calendar className="h-4 w-4" />}
              />
              <MetricCard
                label="Employees"
                value={employees}
                format="number"
                icon={<Users className="h-4 w-4" />}
              />
            </div>
          </TabsContent>
          
          <TabsContent value="cap-table" className="mt-4">
            <WhatIfInvestmentModeler
              companyId={companyData?.id || companyData?.company_id}
              companyName={companyData?.companyName || companyData?.name || 'Company'}
              currentValuation={valuation}
              stage={stage}
              founderOwnership={companyData?.founderOwnership ?? companyData?.cells?.founderOwnership?.value}
            />
          </TabsContent>

          <TabsContent value="hierarchy" className="mt-4">
            <div className="space-y-4">
              <div>
                <h4 className="text-sm font-medium mb-2">Portfolio Hierarchy</h4>
                <div className="border rounded p-4 bg-muted/50">
                  <FullTreemap
                    data={hierarchicalData}
                    width={600}
                    height={400}
                    onNodeClick={(node) => {
                      console.log('Clicked node:', node);
                    }}
                  />
                </div>
              </div>
              
              <div className="text-sm space-y-1">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded bg-primary"></div>
                  <span>Sector: {sector}</span>
                </div>
                <div className="flex items-center gap-2 ml-4">
                  <div className="w-3 h-3 rounded bg-primary/70"></div>
                  <span>Stage: {stage}</span>
                </div>
                <div className="flex items-center gap-2 ml-8">
                  <div className="w-3 h-3 rounded bg-primary/50"></div>
                  <span>Company: {companyData?.companyName}</span>
                </div>
              </div>
            </div>
          </TabsContent>
          
          <TabsContent value="details" className="mt-4">
            <div className="space-y-3 text-sm">
              {companyData?.website && (
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground min-w-[100px]">Website:</span>
                  <a 
                    href={companyData.website} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-primary hover:underline"
                  >
                    {companyData.website}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              )}
              
              {companyData?.investors && companyData.investors.length > 0 && (
                <div>
                  <span className="text-muted-foreground">Investors:</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {companyData.investors.map((investor: string, idx: number) => (
                      <Badge key={idx} variant="secondary" className="text-xs">
                        {investor}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              
              {companyData?.founders && companyData.founders.length > 0 && (
                <div>
                  <span className="text-muted-foreground">Founders:</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {companyData.founders.map((founder: any, idx: number) => (
                      <Badge key={idx} variant="outline" className="text-xs">
                        {founder.name || founder}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}

function WhatIfInvestmentModeler({
  companyId,
  companyName,
  currentValuation,
  stage,
  founderOwnership,
}: {
  companyId?: string;
  companyName: string;
  currentValuation?: number | null;
  stage: string;
  founderOwnership?: number | null;
}) {
  const [investmentAmount, setInvestmentAmount] = useState<string>('15000000');
  const [roundName, setRoundName] = useState<string>(stage || 'Series B');
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val);

  const formatPct = (val: number) => {
    if (val === null || val === undefined) return '—';
    // Handle both decimal (0.23) and percentage (23.0) formats
    const pct = val > 1 ? val : val * 100;
    return `${pct.toFixed(1)}%`;
  };

  const handleModel = async () => {
    setLoading(true);
    setError(null);
    try {
      const amount = parseFloat(investmentAmount);
      if (isNaN(amount) || amount <= 0) {
        setError('Enter a valid investment amount');
        return;
      }
      const res = await fetch(`/api/cell-actions/actions/cap_table.entry_impact/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action_id: 'cap_table.entry_impact',
          company_id: companyId,
          inputs: { our_investment: amount, round_name: roundName },
        }),
      });
      if (!res.ok) throw new Error(`Failed: ${res.status}`);
      const data = await res.json();
      setResult(data.result || data);
    } catch (e: any) {
      setError(e.message || 'Failed to model investment');
    } finally {
      setLoading(false);
    }
  };

  const topStakeholders = useMemo(() => {
    if (!result?.post_investment_cap_table) return [];
    return Object.entries(result.post_investment_cap_table)
      .map(([name, ownership]) => ({ name, ownership: Number(ownership) }))
      .sort((a, b) => b.ownership - a.ownership)
      .slice(0, 8);
  }, [result]);

  return (
    <div className="space-y-4">
      <div>
        <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
          <PieChart className="h-4 w-4" />
          Model Our Entry — {companyName}
        </h4>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <Label className="text-xs">Investment Amount ($)</Label>
            <Input
              type="number"
              value={investmentAmount}
              onChange={(e) => setInvestmentAmount(e.target.value)}
              placeholder="15000000"
              className="mt-1"
            />
          </div>
          <div>
            <Label className="text-xs">Round</Label>
            <Select value={roundName} onValueChange={setRoundName}>
              <SelectTrigger className="mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="Seed">Seed</SelectItem>
                <SelectItem value="Series A">Series A</SelectItem>
                <SelectItem value="Series B">Series B</SelectItem>
                <SelectItem value="Series C">Series C</SelectItem>
                <SelectItem value="Series D">Series D</SelectItem>
                <SelectItem value="Growth">Growth</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-end">
            <Button onClick={handleModel} disabled={loading} className="w-full">
              {loading ? 'Modeling...' : 'Model Entry'}
            </Button>
          </div>
        </div>
      </div>

      {error && (
        <div className="text-sm text-destructive bg-destructive/10 p-2 rounded">{error}</div>
      )}

      {result && (
        <div className="space-y-4">
          <Separator />
          <div className="grid grid-cols-4 gap-3">
            <div className="border rounded p-3">
              <div className="text-xs text-muted-foreground">Our Ownership</div>
              <div className="text-lg font-semibold text-primary">{formatPct(result.our_ownership)}</div>
            </div>
            <div className="border rounded p-3">
              <div className="text-xs text-muted-foreground">Post-Money</div>
              <div className="text-lg font-semibold">{formatCurrency(result.post_money_valuation)}</div>
            </div>
            <div className="border rounded p-3">
              <div className="text-xs text-muted-foreground">Dilution to Existing</div>
              <div className="text-lg font-semibold text-orange-600">{formatPct(result.dilution_to_existing)}</div>
            </div>
            <div className="border rounded p-3">
              <div className="text-xs text-muted-foreground">Founder After</div>
              <div className="text-lg font-semibold">{formatPct(result.founder_ownership_after)}</div>
            </div>
          </div>

          {topStakeholders.length > 0 && (
            <div>
              <h5 className="text-xs font-medium text-muted-foreground mb-2">Post-Investment Cap Table</h5>
              <div className="space-y-1">
                {topStakeholders.map(({ name, ownership }) => (
                  <div key={name} className="flex items-center gap-2">
                    <div className="flex-1 text-sm truncate">{name}</div>
                    <div className="w-32">
                      <div className="h-4 bg-muted rounded overflow-hidden">
                        <div
                          className={cn(
                            "h-full rounded",
                            name.includes('Our Fund') ? 'bg-primary' : 'bg-primary/30'
                          )}
                          style={{ width: `${Math.min(ownership > 1 ? ownership : ownership * 100, 100)}%` }}
                        />
                      </div>
                    </div>
                    <div className="w-14 text-right text-sm font-mono">{formatPct(ownership)}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {!result && founderOwnership != null && (
        <div className="text-sm text-muted-foreground">
          Current founder ownership: {formatPct(founderOwnership)}
          {currentValuation && ` · Valuation: ${formatCurrency(currentValuation)}`}
        </div>
      )}

      <Separator className="my-4" />
      <LiquidationWaterfallPanel companyId={companyId} companyName={companyName} />
    </div>
  );
}

function LiquidationWaterfallPanel({
  companyId,
  companyName,
}: {
  companyId?: string;
  companyName: string;
}) {
  const EXIT_VALUES = [50_000_000, 100_000_000, 250_000_000, 500_000_000, 1_000_000_000];
  const [exitValue, setExitValue] = useState<number>(250_000_000);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val);

  const formatShort = (val: number) => {
    if (val >= 1_000_000_000) return `$${(val / 1_000_000_000).toFixed(1)}B`;
    if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(0)}M`;
    return formatCurrency(val);
  };

  const [waterfallError, setWaterfallError] = useState<string | null>(null);

  const handleCalculate = async () => {
    setLoading(true);
    setWaterfallError(null);
    try {
      const res = await fetch(`/api/cell-actions/actions/waterfall/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action_id: 'waterfall',
          company_id: companyId,
          inputs: { exit_value: exitValue },
        }),
      });
      if (!res.ok) throw new Error(`Failed: ${res.status}`);
      const data = await res.json();
      setResult(data.result || data);
    } catch (e: any) {
      setWaterfallError(e.message || 'Calculation failed');
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const distributions = useMemo(() => {
    if (!result) return [];
    // Handle both dict and array formats
    const dist = result.distributions || result.waterfall || [];
    if (!dist || typeof dist !== 'object') return [];
    if (Array.isArray(dist)) return dist;
    return Object.entries(dist).map(([name, amount]) => ({ name, amount: Number(amount) }));
  }, [result]);

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium flex items-center gap-2">
        <DollarSign className="h-4 w-4" />
        Liquidation Waterfall — {companyName}
      </h4>
      <div className="flex items-center gap-2">
        <Label className="text-xs whitespace-nowrap">Exit Value:</Label>
        <div className="flex gap-1">
          {EXIT_VALUES.map((v) => (
            <Button
              key={v}
              size="sm"
              variant={exitValue === v ? 'default' : 'outline'}
              className="h-7 text-xs px-2"
              onClick={() => setExitValue(v)}
            >
              {formatShort(v)}
            </Button>
          ))}
        </div>
        <Button size="sm" onClick={handleCalculate} disabled={loading} className="h-7">
          {loading ? '...' : 'Calculate'}
        </Button>
      </div>
      {waterfallError && (
        <p className="text-xs text-destructive">{waterfallError}</p>
      )}

      {distributions.length > 0 && (
        <div className="space-y-1">
          {distributions.map((d: any, i: number) => {
            const name = d.name || d.investor_name || d.series || `Investor ${i + 1}`;
            const amount = Number(d.amount || d.proceeds || d.distribution || 0);
            const pct = exitValue > 0 ? (amount / exitValue) * 100 : 0;
            return (
              <div key={i} className="flex items-center gap-2">
                <div className="flex-1 text-sm truncate">{name}</div>
                <div className="w-40">
                  <div className="h-4 bg-muted rounded overflow-hidden">
                    <div
                      className="h-full rounded bg-green-500/60"
                      style={{ width: `${Math.min(pct, 100)}%` }}
                    />
                  </div>
                </div>
                <div className="w-20 text-right text-sm font-mono">{formatShort(amount)}</div>
                <div className="w-12 text-right text-xs text-muted-foreground">{pct.toFixed(1)}%</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function MetricCard({
  label,
  value,
  format,
  icon
}: {
  label: string;
  value: number;
  format: 'currency' | 'percentage' | 'number' | 'months';
  icon: React.ReactNode;
}) {
  const formattedValue = useMemo(() => {
    if (value === null || value === undefined) return '—';
    
    switch (format) {
      case 'currency':
        return new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: 'USD',
          maximumFractionDigits: 0,
        }).format(value);
      case 'percentage':
        return `${(value * 100).toFixed(1)}%`;
      case 'months':
        return `${value} months`;
      default:
        return value.toLocaleString();
    }
  }, [value, format]);

  return (
    <div className="border rounded p-3">
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <div className="text-lg font-semibold">{formattedValue}</div>
    </div>
  );
}
