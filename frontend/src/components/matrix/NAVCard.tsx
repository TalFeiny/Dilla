'use client';

/**
 * NAV Card Component
 * 
 * Displays NAV (Net Asset Value) with sparkline visualization
 */

import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatCurrency } from '@/lib/utils/formatters';

interface NAVCardProps {
  value: number;
  sparkline?: number[];
  metadata?: {
    time_series?: any[];
  };
  companyId?: string;
  fundId?: string;
  onUpdate?: (value: number) => Promise<void>;
}

export function NAVCard({ value, sparkline, metadata, companyId, fundId, onUpdate }: NAVCardProps) {
  // Extract sparkline from time_series if sparkline is not provided
  const effectiveSparkline = sparkline || (() => {
    if (metadata?.time_series && Array.isArray(metadata.time_series)) {
      // Extract numeric values from time_series array
      return metadata.time_series.map((item) => {
        if (typeof item === 'number') return item;
        if (typeof item === 'object' && item !== null) {
          return item.revenue || item.value || item.nav || item.amount || 0;
        }
        return 0;
      }).filter((v) => typeof v === 'number' && !isNaN(v));
    }
    return undefined;
  })();
  const formatCurrencyDisplay = (val: number): string =>
    formatCurrency(val) === '-' ? '$0.00' : formatCurrency(val);

  const renderSparkline = () => {
    if (!effectiveSparkline || effectiveSparkline.length === 0) {
      return (
        <div className="h-8 w-full flex items-center justify-center text-xs text-muted-foreground">
          No data
        </div>
      );
    }

    const max = Math.max(...effectiveSparkline);
    const min = Math.min(...effectiveSparkline);
    const range = max - min || 1;
    const width = 100;
    const height = 30;
    const points = effectiveSparkline.map((val, idx) => {
      const x = (idx / (effectiveSparkline.length - 1 || 1)) * width;
      const y = height - ((val - min) / range) * height;
      return `${x},${y}`;
    }).join(' ');

    const isPositive = effectiveSparkline[effectiveSparkline.length - 1] > effectiveSparkline[0];
    const TrendIcon = isPositive ? TrendingUp : TrendingDown;

    return (
      <div className="flex items-center gap-2 w-full">
        <div className="flex-1 relative">
          <svg
            width="100%"
            height={height}
            viewBox={`0 0 ${width} ${height}`}
            className="overflow-visible"
          >
            <polyline
              points={points}
              fill="none"
              stroke={isPositive ? "rgb(34, 197, 94)" : "rgb(239, 68, 68)"}
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            {/* Current value dot */}
            <circle
              cx={width}
              cy={parseFloat(points.split(' ').pop()?.split(',')[1] || '0')}
              r="3"
              fill={isPositive ? "rgb(34, 197, 94)" : "rgb(239, 68, 68)"}
            />
          </svg>
        </div>
        <TrendIcon
          className={cn(
            "h-4 w-4",
            isPositive ? "text-green-500" : "text-red-500"
          )}
        />
      </div>
    );
  };

  return (
    <div className="w-full space-y-2">
      <div className="flex items-baseline justify-between">
        <span className="text-lg font-semibold">
          {formatCurrencyDisplay(value || 0)}
        </span>
      </div>
      {renderSparkline()}
    </div>
  );
}
