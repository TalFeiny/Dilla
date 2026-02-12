'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { ICellRendererParams } from 'ag-grid-community';
import { ChevronRight, ChevronDown, Building2, TrendingUp, DollarSign, Users, Calendar, MapPin, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
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
  const arr = companyData?.arr || companyData?.cells?.arr?.value || 0;
  const valuation = companyData?.valuation || companyData?.cells?.valuation?.value || 0;
  const growthRate = companyData?.growthRate || companyData?.cells?.growthRate?.value || 0;
  const burnRate = companyData?.burnRate || companyData?.cells?.burnRate?.value || 0;
  const runway = companyData?.runway || companyData?.cells?.runway?.value || 0;
  const stage = companyData?.stage || companyData?.cells?.stage?.value || 'Unknown';
  const sector = companyData?.sector || companyData?.cells?.sector?.value || 'Unknown';
  const employees = companyData?.employees || companyData?.cells?.employees?.value || 0;
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
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="financials">Financials</TabsTrigger>
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
