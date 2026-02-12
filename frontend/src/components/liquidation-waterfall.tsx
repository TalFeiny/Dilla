'use client';

import React, { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from 'recharts';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Info, TrendingUp, AlertTriangle } from 'lucide-react';

interface LiquidationWaterfallProps {
  waterfallData: {
    exit_values: number[];
    investor_returns: Record<string, number[]>;
  };
  preferenceStack: number;
  conversionThresholds: Array<{
    round: string;
    threshold: number;
    ownership: number;
  }>;
  insights: {
    preference_overhang: boolean;
    common_squeeze: boolean;
    misaligned_incentives: boolean;
    key_observations: string[];
  };
}

export const LiquidationWaterfall: React.FC<LiquidationWaterfallProps> = ({
  waterfallData,
  preferenceStack,
  conversionThresholds,
  insights
}) => {
  // Prepare chart data
  const chartData = useMemo(() => {
    return waterfallData.exit_values.map((exitValue, index) => {
      const dataPoint: any = {
        exitValue: exitValue / 1e6, // Convert to millions
        'Exit Value': exitValue / 1e6
      };
      
      // Add each investor's returns
      Object.entries(waterfallData.investor_returns).forEach(([investor, returns]) => {
        dataPoint[investor] = returns[index] / 1e6;
      });
      
      return dataPoint;
    });
  }, [waterfallData]);

  // Get all investor names for the chart
  const investors = Object.keys(waterfallData.investor_returns);
  
  // Colors for different investor types
  const getInvestorColor = (investor: string) => {
    if (investor.includes('Founder')) return '#10b981'; // Green for founders
    if (investor.includes('Employee')) return '#3b82f6'; // Blue for employees  
    if (investor.includes('Seed')) return '#f59e0b'; // Amber for seed
    if (investor.includes('Series A')) return '#8b5cf6'; // Purple for A
    if (investor.includes('Series B')) return '#ef4444'; // Red for B
    if (investor.includes('Series C')) return '#ec4899'; // Pink for C
    return '#6b7280'; // Gray default
  };

  return (
    <div className="space-y-6">
      {/* Key Insights */}
      {insights.key_observations.length > 0 && (
        <Alert>
          <Info className="h-4 w-4" />
          <AlertDescription>
            <ul className="space-y-1 mt-2">
              {insights.key_observations.map((observation, i) => (
                <li key={i} className="text-sm">{observation}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      {/* Warnings */}
      {(insights.preference_overhang || insights.common_squeeze) && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            {insights.preference_overhang && "High liquidation preference stack relative to likely exit values. "}
            {insights.common_squeeze && "Common shareholders face significant dilution in most scenarios."}
          </AlertDescription>
        </Alert>
      )}

      {/* Waterfall Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Liquidation Waterfall Analysis</CardTitle>
          <p className="text-sm text-muted-foreground">
            How proceeds are distributed at different exit values
          </p>
        </CardHeader>
        <CardContent>
          <div className="h-[400px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis 
                  dataKey="exitValue" 
                  label={{ value: 'Exit Value ($M)', position: 'insideBottom', offset: -5 }}
                />
                <YAxis 
                  label={{ value: 'Proceeds ($M)', angle: -90, position: 'insideLeft' }}
                />
                <Tooltip 
                  formatter={(value: number) => `$${value.toFixed(1)}M`}
                  labelFormatter={(label) => `Exit: $${label}M`}
                />
                <Legend />
                
                {/* Add reference lines for key thresholds */}
                <ReferenceLine 
                  x={preferenceStack / 1e6} 
                  stroke="#ef4444" 
                  strokeDasharray="5 5"
                  label="Preference Stack"
                />
                
                {conversionThresholds.map((threshold, i) => (
                  <ReferenceLine
                    key={i}
                    x={threshold.threshold / 1e6}
                    stroke="#8b5cf6"
                    strokeDasharray="3 3"
                    label={`${threshold.round} converts`}
                  />
                ))}
                
                {/* Stack areas for each investor */}
                {investors.map((investor, index) => (
                  <Area
                    key={investor}
                    type="monotone"
                    dataKey={investor}
                    stackId="1"
                    stroke={getInvestorColor(investor)}
                    fill={getInvestorColor(investor)}
                    fillOpacity={0.8}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Return Multiple Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Investor Return Multiples</CardTitle>
          <p className="text-sm text-muted-foreground">
            Return multiple (X) at different exit values
          </p>
        </CardHeader>
        <CardContent>
          <div className="h-[400px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis 
                  dataKey="exitValue" 
                  label={{ value: 'Exit Value ($M)', position: 'insideBottom', offset: -5 }}
                />
                <YAxis 
                  label={{ value: 'Return Multiple (X)', angle: -90, position: 'insideLeft' }}
                />
                <Tooltip 
                  formatter={(value: number) => `${value.toFixed(2)}x`}
                  labelFormatter={(label) => `Exit: $${label}M`}
                />
                <Legend />
                
                {/* Calculate and plot return multiples */}
                {investors.filter(inv => !inv.includes('Employee')).map((investor) => (
                  <Line
                    key={investor}
                    type="monotone"
                    dataKey={investor}
                    stroke={getInvestorColor(investor)}
                    strokeWidth={2}
                    dot={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Preference Stack</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              ${(preferenceStack / 1e6).toFixed(1)}M
            </div>
            <p className="text-xs text-muted-foreground">
              Total liquidation preferences
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">First Conversion</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              ${(conversionThresholds[0]?.threshold / 1e6 || 0).toFixed(1)}M
            </div>
            <p className="text-xs text-muted-foreground">
              {conversionThresholds[0]?.round || 'N/A'} converts to common
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Common Breakeven</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              ${((preferenceStack * 1.5) / 1e6).toFixed(1)}M
            </div>
            <p className="text-xs text-muted-foreground">
              Exit needed for meaningful common returns
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};