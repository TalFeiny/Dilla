'use client';

import React from 'react';
import { ICellRendererParams } from 'ag-grid-community';
import { CheckCircle2, AlertCircle, XCircle } from 'lucide-react';

interface ProgressBarRendererParams extends ICellRendererParams {
  maxValue?: number;
  showIcon?: boolean;
  thresholds?: {
    low?: number;
    high?: number;
  };
}

export const ProgressBarRenderer = React.memo(function ProgressBarRenderer(params: ProgressBarRendererParams) {
  const { value, maxValue = 100, showIcon = true, thresholds } = params;

  if (value === null || value === undefined || value === '') {
    return <span></span>;
  }

  const numValue = typeof value === 'number' ? value : parseFloat(String(value).replace(/[^0-9.-]/g, ''));

  if (isNaN(numValue)) {
    return <span>{String(value)}</span>;
  }

  const percentage = Math.max(0, Math.min(100, (numValue / maxValue) * 100));

  // Determine color based on thresholds
  let barColor = '#4CAF50'; // green
  let icon = <CheckCircle2 className="h-4 w-4 text-green-500" />;

  if (thresholds) {
    if (thresholds.low !== undefined && numValue < thresholds.low) {
      barColor = '#F44336'; // red
      icon = <XCircle className="h-4 w-4 text-red-500" />;
    } else if (thresholds.high !== undefined && numValue >= thresholds.high) {
      barColor = '#FF9800'; // orange
      icon = <AlertCircle className="h-4 w-4 text-orange-500" />;
    }
  }

  return (
    <div className="flex items-center gap-2 w-full h-full px-2">
      {showIcon && <div className="flex-shrink-0">{icon}</div>}
      <div className="flex-1 relative h-5 bg-gray-200 rounded overflow-hidden">
        <div
          className="h-full flex items-center justify-center text-xs font-medium text-white"
          style={{
            width: `${percentage}%`,
            backgroundColor: barColor,
          }}
        >
          {percentage >= 20 && `${Math.round(percentage)}%`}
        </div>
      </div>
      <span className="text-xs font-medium min-w-[50px] text-right">
        {numValue.toLocaleString()}
      </span>
    </div>
  );
});
