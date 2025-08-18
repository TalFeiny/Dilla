'use client';

import React, { useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell, PieChart, Pie } from 'recharts';
import { TrendingUp, TrendingDown, DollarSign, Briefcase, AlertTriangle, Target } from 'lucide-react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

interface PortfolioWaterfallProps {
  fundId?: string;
  portfolioData: {
    companies: Array<{
      id: string;
      name: string;
      initial_investment: number;
      current_valuation: number;
      realized_proceeds?: number;
      status: 'active' | 'exited' | 'written_off';
      investment_date: string;
      exit_date?: string;
      ownership_percentage: number;
      liquidation_preference?: number;
    }>;
    fundMetrics: {
      total_committed: number;
      total_deployed: number;
      total_realized: number;
      total_unrealized: number;
      dpi: number; // Distributions to Paid-In
      tvpi: number; // Total Value to Paid-In
      irr: number;
    };
  };
}

export const PortfolioWaterfall: React.FC<PortfolioWaterfallProps> = ({
  fundId,
  portfolioData
}) => {
  const [viewMode, setViewMode] = useState<'deployment' | 'value' | 'returns'>('deployment');
  
  // Calculate waterfall progression
  const waterfallData = useMemo(() => {
    const sortedCompanies = [...portfolioData.companies].sort(
      (a, b) => new Date(a.investment_date).getTime() - new Date(b.investment_date).getTime()
    );
    
    let cumulativeDeployed = 0;
    let cumulativeRealized = 0;
    let cumulativeValue = 0;
    
    return sortedCompanies.map(company => {
      cumulativeDeployed += company.initial_investment;
      
      if (company.status === 'exited' && company.realized_proceeds) {
        cumulativeRealized += company.realized_proceeds;
      }
      
      const currentValue = company.status === 'exited' 
        ? (company.realized_proceeds || 0)
        : company.current_valuation * (company.ownership_percentage / 100);
      
      cumulativeValue += currentValue;
      
      const multiple = company.initial_investment > 0 
        ? currentValue / company.initial_investment 
        : 0;
      
      return {
        name: company.name,
        investment: company.initial_investment,
        currentValue,
        multiple,
        status: company.status,
        cumulativeDeployed,
        cumulativeRealized,
        cumulativeValue,
        unrealizedGain: company.status === 'active' ? currentValue - company.initial_investment : 0,
        realizedGain: company.status === 'exited' ? (company.realized_proceeds || 0) - company.initial_investment : 0
      };
    });
  }, [portfolioData]);

  // Portfolio composition for pie chart
  const portfolioComposition = useMemo(() => {
    const composition = {
      active: 0,
      exited: 0,
      writtenOff: 0
    };
    
    portfolioData.companies.forEach(company => {
      const value = company.status === 'exited' 
        ? (company.realized_proceeds || 0)
        : company.current_valuation * (company.ownership_percentage / 100);
      
      if (company.status === 'active') composition.active += value;
      else if (company.status === 'exited') composition.exited += value;
      else if (company.status === 'written_off') composition.writtenOff += company.initial_investment;
    });
    
    return [
      { name: 'Active', value: composition.active, fill: '#3b82f6' },
      { name: 'Exited', value: composition.exited, fill: '#10b981' },
      { name: 'Written Off', value: composition.writtenOff, fill: '#ef4444' }
    ];
  }, [portfolioData]);

  // Returns distribution
  const returnsDistribution = useMemo(() => {
    return waterfallData.map(company => ({
      name: company.name,
      invested: -company.investment,
      realized: company.status === 'exited' ? company.realizedGain : 0,
      unrealized: company.status === 'active' ? company.unrealizedGain : 0,
      multiple: company.multiple
    }));
  }, [waterfallData]);

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-white p-3 border rounded-lg shadow-lg">
          <p className="font-semibold text-sm">{label}</p>
          {viewMode === 'deployment' && (
            <>
              <p className="text-xs">Investment: ${(data.investment / 1e6).toFixed(2)}M</p>
              <p className="text-xs">Cumulative: ${(data.cumulativeDeployed / 1e6).toFixed(2)}M</p>
            </>
          )}
          {viewMode === 'value' && (
            <>
              <p className="text-xs">Current Value: ${(data.currentValue / 1e6).toFixed(2)}M</p>
              <p className="text-xs">Multiple: {data.multiple.toFixed(2)}x</p>
              <p className="text-xs">Status: {data.status}</p>
            </>
          )}
          {viewMode === 'returns' && (
            <>
              <p className="text-xs text-red-600">Invested: ${(Math.abs(data.invested) / 1e6).toFixed(2)}M</p>
              {data.realized > 0 && (
                <p className="text-xs text-green-600">Realized: ${(data.realized / 1e6).toFixed(2)}M</p>
              )}
              {data.unrealized > 0 && (
                <p className="text-xs text-blue-600">Unrealized: ${(data.unrealized / 1e6).toFixed(2)}M</p>
              )}
              <p className="text-xs font-semibold">Multiple: {data.multiple.toFixed(2)}x</p>
            </>
          )}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-6">
      {/* Fund Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium flex items-center gap-1">
              <Briefcase className="h-3 w-3" />
              Committed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold">
              ${(portfolioData.fundMetrics.total_committed / 1e6).toFixed(0)}M
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium flex items-center gap-1">
              <DollarSign className="h-3 w-3" />
              Deployed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold">
              ${(portfolioData.fundMetrics.total_deployed / 1e6).toFixed(0)}M
            </div>
            <p className="text-xs text-muted-foreground">
              {((portfolioData.fundMetrics.total_deployed / portfolioData.fundMetrics.total_committed) * 100).toFixed(0)}%
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium flex items-center gap-1">
              <TrendingUp className="h-3 w-3 text-green-600" />
              Realized
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold text-green-600">
              ${(portfolioData.fundMetrics.total_realized / 1e6).toFixed(0)}M
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium flex items-center gap-1">
              <Target className="h-3 w-3 text-blue-600" />
              Unrealized
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold text-blue-600">
              ${(portfolioData.fundMetrics.total_unrealized / 1e6).toFixed(0)}M
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium">
              DPI
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold">
              {portfolioData.fundMetrics.dpi.toFixed(2)}x
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium">
              TVPI
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold">
              {portfolioData.fundMetrics.tvpi.toFixed(2)}x
            </div>
            <p className="text-xs text-muted-foreground">
              IRR: {portfolioData.fundMetrics.irr.toFixed(0)}%
            </p>
          </CardContent>
        </Card>
      </div>

      {/* View Mode Selector and Main Chart */}
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <div>
              <CardTitle>Portfolio Waterfall</CardTitle>
              <p className="text-sm text-muted-foreground mt-1">
                Track deployment and returns across portfolio companies
              </p>
            </div>
            <Select value={viewMode} onValueChange={(v: any) => setViewMode(v)}>
              <SelectTrigger className="w-[180px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="deployment">Capital Deployment</SelectItem>
                <SelectItem value="value">Current Value</SelectItem>
                <SelectItem value="returns">Returns Analysis</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          <div className="h-[400px]">
            <ResponsiveContainer width="100%" height="100%">
              {viewMode === 'deployment' && (
                <BarChart data={waterfallData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis 
                    dataKey="name" 
                    angle={-45}
                    textAnchor="end"
                    height={80}
                    interval={0}
                    tick={{ fontSize: 10 }}
                  />
                  <YAxis 
                    tickFormatter={(value) => `$${(value / 1e6).toFixed(0)}M`}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="investment" fill="#3b82f6" />
                </BarChart>
              )}
              
              {viewMode === 'value' && (
                <BarChart data={waterfallData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis 
                    dataKey="name" 
                    angle={-45}
                    textAnchor="end"
                    height={80}
                    interval={0}
                    tick={{ fontSize: 10 }}
                  />
                  <YAxis 
                    tickFormatter={(value) => `$${(value / 1e6).toFixed(0)}M`}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend />
                  <Bar dataKey="investment" fill="#94a3b8" name="Invested" />
                  <Bar dataKey="currentValue" name="Current Value">
                    {waterfallData.map((entry, index) => (
                      <Cell 
                        key={`cell-${index}`}
                        fill={
                          entry.status === 'exited' ? '#10b981' :
                          entry.status === 'written_off' ? '#ef4444' :
                          '#3b82f6'
                        }
                      />
                    ))}
                  </Bar>
                </BarChart>
              )}
              
              {viewMode === 'returns' && (
                <BarChart data={returnsDistribution}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis 
                    dataKey="name" 
                    angle={-45}
                    textAnchor="end"
                    height={80}
                    interval={0}
                    tick={{ fontSize: 10 }}
                  />
                  <YAxis 
                    tickFormatter={(value) => `$${(Math.abs(value) / 1e6).toFixed(0)}M`}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend />
                  <Bar dataKey="invested" fill="#ef4444" name="Invested" stackId="stack" />
                  <Bar dataKey="realized" fill="#10b981" name="Realized Gains" stackId="stack" />
                  <Bar dataKey="unrealized" fill="#3b82f6" name="Unrealized Gains" stackId="stack" />
                </BarChart>
              )}
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Portfolio Composition */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Portfolio Composition</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={portfolioComposition}
                    cx="50%"
                    cy="50%"
                    innerRadius={40}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {portfolioComposition.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip 
                    formatter={(value: number) => `$${(value / 1e6).toFixed(1)}M`}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="space-y-2 mt-4">
              {portfolioComposition.map(item => (
                <div key={item.name} className="flex justify-between items-center">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded" style={{ backgroundColor: item.fill }} />
                    <span className="text-sm">{item.name}</span>
                  </div>
                  <span className="text-sm font-semibold">
                    ${(item.value / 1e6).toFixed(1)}M
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Top Performers */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Top Performers</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {waterfallData
                .sort((a, b) => b.multiple - a.multiple)
                .slice(0, 5)
                .map(company => (
                  <div key={company.name} className="flex justify-between items-center">
                    <div>
                      <p className="text-sm font-medium">{company.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {company.status === 'exited' ? 'Exited' : 'Active'}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-bold">
                        {company.multiple.toFixed(1)}x
                      </p>
                      <p className="text-xs text-muted-foreground">
                        ${(company.currentValue / 1e6).toFixed(1)}M
                      </p>
                    </div>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};