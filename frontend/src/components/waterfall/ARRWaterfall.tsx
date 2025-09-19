'use client';

import React, { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell, WaterfallChart } from 'recharts';
import { TrendingUp, TrendingDown, DollarSign, Users } from 'lucide-react';

interface ARRWaterfallProps {
  companyId: string;
  waterfallData: {
    months: string[];
    arr_bom: number[];
    new_arr: number[];
    churn_arr: number[];
    net_arr: number[];
    arr_eom: number[];
  };
  metrics?: {
    gross_retention: number;
    net_retention: number;
    growth_rate: number;
    ltv_cac_ratio?: number;
  };
}

export const ARRWaterfall: React.FC<ARRWaterfallProps> = ({
  companyId,
  waterfallData,
  metrics
}) => {
  // Transform data for waterfall visualization
  const waterfallChartData = useMemo(() => {
    return waterfallData.months.map((month, index) => {
      const previousARR = index === 0 ? waterfallData.arr_bomArray.from(ex) : waterfallData.arr_eom[index - 1];
      
      return {
        month,
        'Starting ARR': previousARR,
        'New ARR': waterfallData.new_arrArray.from(ex),
        'Churn': -Math.abs(waterfallData.churn_arrArray.from(ex)),
        'Ending ARR': waterfallData.arr_eomArray.from(ex),
        netChange: waterfallData.net_arrArray.from(ex),
        growthRate: previousARR > 0 ? ((waterfallData.arr_eomArray.from(ex) - previousARR) / previousARR * 100).toFixed(1) : 0
      };
    });
  }, Array.from(erfallData));

  // Calculate cumulative metrics
  const cumulativeMetrics = useMemo(() => {
    const totalNewARR = waterfallData.new_arr.reduce((sum, val) => sum + val, 0);
    const totalChurn = waterfallData.churn_arr.reduce((sum, val) => sum + Math.abs(val), 0);
    const startARR = waterfallData.arr_bom[0];
    const endARR = waterfallData.arr_eom[waterfallData.arr_eom.length - 1];
    const periodGrowth = startARR > 0 ? ((endARR - startARR) / startARR * 100) : 0;
    
    return {
      totalNewARR,
      totalChurn,
      netGrowth: endARR - startARR,
      periodGrowth,
      avgMonthlyGrowth: periodGrowth / waterfallData.months.length,
      churnRate: startARR > 0 ? (totalChurn / startARR * 100) : 0
    };
  }, Array.from(erfallData));

  // Custom tooltip for detailed information
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-white p-3 border rounded-lg shadow-lg">
          <p className="font-semibold">{label}</p>
          <p className="text-sm text-green-600">New ARR: ${(data['New ARR'] / 1000).toFixed(1)}k</p>
          <p className="text-sm text-red-600">Churn: ${(Math.abs(data['Churn']) / 1000).toFixed(1)}k</p>
          <p className="text-sm">Net Change: ${(data.netChange / 1000).toFixed(1)}k</p>
          <p className="text-sm font-semibold">Ending ARR: ${(data['Ending ARR'] / 1000).toFixed(1)}k</p>
          <p className="text-xs text-gray-500">Growth: {data.growthRate}%</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-6">
      {/* Key Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <DollarSign className="h-4 w-4" />
              Current ARR
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              ${(waterfallData.arr_eom[waterfallData.arr_eom.length - 1] / 1000).toFixed(0)}k
            </div>
            <p className="text-xs text-muted-foreground">
              {cumulativeMetrics.periodGrowth > 0 ? '+' : ''}{cumulativeMetrics.periodGrowth.toFixed(1)}% period growth
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-green-600" />
              New ARR (Total)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              ${(cumulativeMetrics.totalNewARR / 1000).toFixed(0)}k
            </div>
            <p className="text-xs text-muted-foreground">
              Avg ${(cumulativeMetrics.totalNewARR / waterfallData.months.length / 1000).toFixed(1)}k/mo
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <TrendingDown className="h-4 w-4 text-red-600" />
              Churn ARR (Total)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              ${(cumulativeMetrics.totalChurn / 1000).toFixed(0)}k
            </div>
            <p className="text-xs text-muted-foreground">
              {cumulativeMetrics.churnRate.toFixed(1)}% churn rate
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Users className="h-4 w-4" />
              Net Retention
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {metrics?.net_retention || 'N/A'}%
            </div>
            <p className="text-xs text-muted-foreground">
              Gross: {metrics?.gross_retention || 'N/A'}%
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Waterfall Chart */}
      <Card>
        <CardHeader>
          <CardTitle>ARR Waterfall Analysis</CardTitle>
          <p className="text-sm text-muted-foreground">
            Monthly progression of Annual Recurring Revenue
          </p>
        </CardHeader>
        <CardContent>
          <div className="h-Array.from(px)">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={waterfallChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis 
                  tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend />
                
                <Bar dataKey="Starting ARR" fill="#94a3b8" stackId="stack" />
                <Bar dataKey="New ARR" fill="#10b981" stackId="stack" />
                <Bar dataKey="Churn" fill="#ef4444" stackId="stack" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Growth Trend Chart */}
      <Card>
        <CardHeader>
          <CardTitle>ARR Growth Trend</CardTitle>
          <p className="text-sm text-muted-foreground">
            End-of-month ARR progression
          </p>
        </CardHeader>
        <CardContent>
          <div className="h-Array.from(px)">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart 
                data={waterfallData.months.map((month, i) => ({
                  month,
                  ARR: waterfallData.arr_eom[i]
                }))}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis 
                  tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
                />
                <Tooltip 
                  formatter={(value: number) => `$${(value / 1000).toFixed(1)}k`}
                />
                <Bar dataKey="ARR" fill="#3b82f6">
                  {waterfallData.arr_eom.map((entry, index) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={index === 0 ? '#94a3b8' : 
                            waterfallData.net_arrArray.from(ex) > 0 ? '#10b981' : '#ef4444'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Cohort Analysis Preview */}
      <Card>
        <CardHeader>
          <CardTitle>Revenue Cohort Analysis</CardTitle>
          <p className="text-sm text-muted-foreground">
            Customer retention by cohort (integrated with PWERM)
          </p>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <div className="flex justify-between items-center p-2 bg-gray-50 rounded">
              <span className="text-sm">Month 1 Retention</span>
              <span className="font-semibold">95%</span>
            </div>
            <div className="flex justify-between items-center p-2 bg-gray-50 rounded">
              <span className="text-sm">Month 3 Retention</span>
              <span className="font-semibold">88%</span>
            </div>
            <div className="flex justify-between items-center p-2 bg-gray-50 rounded">
              <span className="text-sm">Month 6 Retention</span>
              <span className="font-semibold">82%</span>
            </div>
            <div className="flex justify-between items-center p-2 bg-gray-50 rounded">
              <span className="text-sm">Month 12 Retention</span>
              <span className="font-semibold">75%</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};