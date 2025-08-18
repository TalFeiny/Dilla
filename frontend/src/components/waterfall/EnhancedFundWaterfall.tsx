'use client';

import React, { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Legend
} from 'recharts';
import { currencyFormatter } from '@/lib/currency-formatter';
import { chartStylingSystem } from '@/lib/chart-styling-system';

interface EnhancedFundWaterfallProps {
  data: any[];
  currency?: string;
  title?: string;
}

export const EnhancedFundWaterfall: React.FC<EnhancedFundWaterfallProps> = ({
  data,
  currency = 'USD',
  title = 'Fund Performance Waterfall'
}) => {
  const chartConfig = chartStylingSystem.getChartConfig();
  const theme = chartStylingSystem.getTheme();

  // Custom gradient definitions matching the reference style
  const gradients = useMemo(() => (
    <defs>
      {/* Smooth blue gradient like in the reference */}
      <linearGradient id="blueGradient" x1="0" y1="0" x2="0" y2="1">
        <stop offset="5%" stopColor="#60a5fa" stopOpacity={0.9}/>
        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.1}/>
      </linearGradient>
      
      {/* Teal gradient */}
      <linearGradient id="tealGradient" x1="0" y1="0" x2="0" y2="1">
        <stop offset="5%" stopColor="#5eead4" stopOpacity={0.9}/>
        <stop offset="95%" stopColor="#14b8a6" stopOpacity={0.1}/>
      </linearGradient>
      
      {/* Purple gradient */}
      <linearGradient id="purpleGradient" x1="0" y1="0" x2="0" y2="1">
        <stop offset="5%" stopColor="#c084fc" stopOpacity={0.9}/>
        <stop offset="95%" stopColor="#9333ea" stopOpacity={0.1}/>
      </linearGradient>
      
      {/* Green gradient */}
      <linearGradient id="greenGradient" x1="0" y1="0" x2="0" y2="1">
        <stop offset="5%" stopColor="#86efac" stopOpacity={0.9}/>
        <stop offset="95%" stopColor="#22c55e" stopOpacity={0.1}/>
      </linearGradient>
      
      {/* Orange gradient */}
      <linearGradient id="orangeGradient" x1="0" y1="0" x2="0" y2="1">
        <stop offset="5%" stopColor="#fdba74" stopOpacity={0.9}/>
        <stop offset="95%" stopColor="#fb923c" stopOpacity={0.1}/>
      </linearGradient>
    </defs>
  ), []);

  // Custom tooltip with proper formatting
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white/95 backdrop-blur-sm p-4 rounded-lg shadow-xl border border-gray-200">
          <p className="font-semibold text-gray-900 mb-2">{label}</p>
          <div className="space-y-1">
            {payload.map((entry: any, index: number) => (
              <div key={index} className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-2">
                  <div 
                    className="w-3 h-3 rounded-full" 
                    style={{ backgroundColor: entry.color }}
                  />
                  <span className="text-sm text-gray-600">{entry.name}:</span>
                </div>
                <span className="font-medium text-gray-900">
                  {currencyFormatter.formatNumber(entry.value, { 
                    currency, 
                    compact: true 
                  })}
                </span>
              </div>
            ))}
          </div>
          {payload[0]?.payload?.total && (
            <div className="mt-2 pt-2 border-t border-gray-200">
              <div className="flex justify-between">
                <span className="text-sm font-medium text-gray-600">Total:</span>
                <span className="font-semibold text-gray-900">
                  {currencyFormatter.formatNumber(payload[0].payload.total, { 
                    currency, 
                    compact: true 
                  })}
                </span>
              </div>
            </div>
          )}
        </div>
      );
    }
    return null;
  };

  return (
    <Card className="border-0 shadow-lg">
      <CardHeader className="pb-2">
        <CardTitle className="text-xl font-semibold text-gray-900">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-6">
        <div style={{ width: '100%', height: 400 }}>
          <ResponsiveContainer>
            <AreaChart
              data={data}
              margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
            >
              {gradients}
              
              <CartesianGrid 
                strokeDasharray="0" 
                stroke="#f3f4f6"
                vertical={false}
              />
              
              <XAxis 
                dataKey="period"
                axisLine={false}
                tickLine={false}
                tick={{ 
                  fill: '#6b7280', 
                  fontSize: 12,
                  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
                }}
                dy={10}
              />
              
              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ 
                  fill: '#6b7280', 
                  fontSize: 12,
                  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
                }}
                tickFormatter={(value) => currencyFormatter.formatCompact(value, currency)}
                dx={-10}
              />
              
              <Tooltip 
                content={<CustomTooltip />}
                cursor={{ fill: 'transparent' }}
              />
              
              <Legend 
                wrapperStyle={{
                  paddingTop: '20px',
                  fontSize: '12px'
                }}
                iconType="rect"
                iconSize={12}
              />
              
              {/* Stacked areas with smooth curves and gradients */}
              <Area
                type="monotone"
                dataKey="deployed"
                stackId="1"
                stroke="#3b82f6"
                strokeWidth={2}
                fill="url(#blueGradient)"
                name="Deployed Capital"
              />
              
              <Area
                type="monotone"
                dataKey="realized"
                stackId="1"
                stroke="#14b8a6"
                strokeWidth={2}
                fill="url(#tealGradient)"
                name="Realized Returns"
              />
              
              <Area
                type="monotone"
                dataKey="unrealized"
                stackId="1"
                stroke="#9333ea"
                strokeWidth={2}
                fill="url(#purpleGradient)"
                name="Unrealized Gains"
              />
              
              <Area
                type="monotone"
                dataKey="distributions"
                stackId="1"
                stroke="#22c55e"
                strokeWidth={2}
                fill="url(#greenGradient)"
                name="Distributions"
              />
              
              {data[0]?.management && (
                <Area
                  type="monotone"
                  dataKey="management"
                  stackId="1"
                  stroke="#fb923c"
                  strokeWidth={2}
                  fill="url(#orangeGradient)"
                  name="Management Fees"
                />
              )}
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Key Metrics Bar */}
        <div className="mt-6 p-4 bg-gray-50 rounded-lg">
          <div className="grid grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider">Total Deployed</p>
              <p className="text-lg font-semibold text-gray-900">
                {currencyFormatter.formatNumber(
                  data[data.length - 1]?.deployed || 0,
                  { currency, compact: true }
                )}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider">Total Realized</p>
              <p className="text-lg font-semibold text-green-600">
                {currencyFormatter.formatNumber(
                  data[data.length - 1]?.realized || 0,
                  { currency, compact: true }
                )}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider">Unrealized Value</p>
              <p className="text-lg font-semibold text-purple-600">
                {currencyFormatter.formatNumber(
                  data[data.length - 1]?.unrealized || 0,
                  { currency, compact: true }
                )}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider">Total Value</p>
              <p className="text-lg font-semibold text-blue-600">
                {currencyFormatter.formatNumber(
                  data[data.length - 1]?.total || 0,
                  { currency, compact: true }
                )}
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};