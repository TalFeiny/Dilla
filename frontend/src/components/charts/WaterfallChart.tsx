'use client';

import React, { useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
  LabelList
} from 'recharts';
import { cn } from '@/lib/utils';

interface WaterfallData {
  name: string;
  value?: number;
  increase?: number;
  decrease?: number;
  total?: number;
  isTotal?: boolean;
  isBridge?: boolean;
  color?: string;
}

interface WaterfallChartProps {
  data: WaterfallData[];
  title?: string;
  height?: number;
  showValues?: boolean;
  positiveColor?: string;
  negativeColor?: string;
  totalColor?: string;
  bridgeColor?: string;
  className?: string;
  formatValue?: (value: number) => string;
}

const defaultFormatValue = (value: number): string => {
  if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (Math.abs(value) >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  if (Math.abs(value) >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
  return `$${value.toLocaleString()}`;
};

export default function WaterfallChart({
  data,
  title,
  height = 400,
  showValues = true,
  positiveColor = '#10b981',
  negativeColor = '#ef4444',
  totalColor = '#3b82f6',
  bridgeColor = '#94a3b8',
  className,
  formatValue = defaultFormatValue
}: WaterfallChartProps) {
  // Process data for waterfall visualization
  const processedData = useMemo(() => {
    let runningTotal = 0;
    return data.map((item, index) => {
      let start = runningTotal;
      let end = runningTotal;
      let value = 0;
      let fill = bridgeColor;
      
      if (item.isTotal) {
        // Total bar starts from 0
        start = 0;
        end = runningTotal;
        value = runningTotal;
        fill = totalColor;
      } else if (item.isBridge) {
        // Bridge bars show intermediate totals
        start = 0;
        end = runningTotal;
        value = runningTotal;
        fill = bridgeColor;
      } else if (item.increase !== undefined) {
        // Positive change
        end = start + item.increase;
        value = item.increase;
        runningTotal = end;
        fill = positiveColor;
      } else if (item.decrease !== undefined) {
        // Negative change
        end = start - item.decrease;
        value = -item.decrease;
        runningTotal = end;
        fill = negativeColor;
      } else if (item.value !== undefined) {
        // Direct value (can be positive or negative)
        if (item.value >= 0) {
          end = start + item.value;
          value = item.value;
          fill = positiveColor;
        } else {
          end = start + item.value;
          value = item.value;
          fill = negativeColor;
        }
        runningTotal = end;
      }
      
      return {
        name: item.name,
        start,
        end,
        value,
        fill: item.color || fill,
        invisible: Math.min(start, end),
        visible: Math.abs(end - start),
        displayValue: value,
        isTotal: item.isTotal,
        isBridge: item.isBridge
      };
    });
  }, [data, positiveColor, negativeColor, totalColor, bridgeColor]);

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-white p-3 rounded-lg shadow-lg border border-gray-200">
          <p className="text-sm font-medium text-gray-900">{data.name}</p>
          <p className="text-sm" style={{ color: data.fill }}>
            {data.isTotal || data.isBridge ? 'Total: ' : 'Change: '}
            {formatValue(data.displayValue)}
          </p>
          {!data.isTotal && !data.isBridge && (
            <p className="text-sm text-gray-500">
              Running Total: {formatValue(data.end)}
            </p>
          )}
        </div>
      );
    }
    return null;
  };

  // Custom label
  const renderCustomLabel = (props: any) => {
    const { x, y, width, height, value, payload } = props;
    if (!showValues || !value) return null;
    
    const displayValue = formatValue(payload.displayValue);
    const yOffset = payload.displayValue >= 0 ? -5 : height + 15;
    
    return (
      <text
        x={x + width / 2}
        y={y + yOffset}
        fill={payload.fill}
        textAnchor="middle"
        fontSize={12}
        fontWeight="bold"
      >
        {displayValue}
      </text>
    );
  };

  return (
    <div className={cn("w-full", className)}>
      {title && (
        <h3 className="text-lg font-semibold text-gray-900 mb-4">{title}</h3>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={processedData} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis 
            dataKey="name" 
            stroke="#6b7280" 
            fontSize={12}
            angle={-45}
            textAnchor="end"
            height={80}
          />
          <YAxis 
            stroke="#6b7280" 
            fontSize={12}
            tickFormatter={formatValue}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={0} stroke="#94a3b8" />
          
          {/* Invisible bars to create the waterfall effect */}
          <Bar 
            dataKey="invisible" 
            stackId="stack" 
            fill="transparent"
            isAnimationActive={false}
          />
          
          {/* Visible bars */}
          <Bar 
            dataKey="visible" 
            stackId="stack"
            isAnimationActive={true}
          >
            <LabelList content={renderCustomLabel} position="top" />
            {processedData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// Exit waterfall specific for liquidation preferences
export function ExitWaterfall({ 
  exitValue,
  preferences,
  commonShares,
  title = "Exit Proceeds Waterfall"
}: {
  exitValue: number;
  preferences: Array<{
    name: string;
    amount: number;
    multiple: number;
    participating: boolean;
  }>;
  commonShares: number;
  title?: string;
}) {
  // Calculate waterfall distribution
  const waterfallData: WaterfallData[] = [];
  let remaining = exitValue;
  
  // Starting point
  waterfallData.push({
    name: "Exit Value",
    value: exitValue,
    isTotal: true
  });
  
  // Process each preference
  preferences.forEach(pref => {
    const prefAmount = pref.amount * pref.multiple;
    const distributed = Math.min(remaining, prefAmount);
    
    if (distributed > 0) {
      waterfallData.push({
        name: `${pref.name} (${pref.multiple}x)`,
        decrease: distributed,
        color: '#ef4444'
      });
      remaining -= distributed;
    }
  });
  
  // Common shareholders
  if (remaining > 0) {
    waterfallData.push({
      name: "Common Stock",
      decrease: remaining,
      color: '#10b981'
    });
  }
  
  // Final total (should be 0)
  waterfallData.push({
    name: "Remaining",
    isTotal: true
  });
  
  return <WaterfallChart data={waterfallData} title={title} />;
}