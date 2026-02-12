'use client';

import React from 'react';
import { ICellRendererParams } from 'ag-grid-community';

interface DataBarRendererParams extends ICellRendererParams {
  minValue?: number;
  maxValue?: number;
  color?: string;
  showValue?: boolean;
}

export const DataBarRenderer = React.memo(function DataBarRenderer(params: DataBarRendererParams) {
  const { value, minValue, maxValue, color = '#4CAF50', showValue = true } = params;

  if (value === null || value === undefined || value === '') {
    return <span></span>;
  }

  const numValue = typeof value === 'number' ? value : parseFloat(String(value).replace(/[^0-9.-]/g, ''));

  if (isNaN(numValue)) {
    return <span>{String(value)}</span>;
  }

  // Calculate percentage
  const range = (maxValue || 100) - (minValue || 0);
  const percentage = range > 0
    ? Math.max(0, Math.min(100, ((numValue - (minValue || 0)) / range) * 100))
    : 0;

  return (
    <div className="flex items-center gap-2 w-full h-full px-2">
      <div className="flex-1 relative h-4 bg-gray-200 rounded overflow-hidden">
        <div
          className="h-full"
          style={{
            width: `${percentage}%`,
            backgroundColor: color,
          }}
        />
      </div>
      {showValue && (
        <span className="text-xs font-medium min-w-[60px] text-right">
          {typeof value === 'number'
            ? value.toLocaleString()
            : String(value)}
        </span>
      )}
    </div>
  );
});
