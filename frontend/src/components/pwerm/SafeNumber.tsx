'use client';

import React from 'react';

interface SafeNumberProps {
  value: any;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  fallback?: string;
  format?: 'currency' | 'percentage' | 'multiple' | 'number';
}

export function SafeNumber({ 
  value, 
  decimals = 1, 
  prefix = '', 
  suffix = '', 
  fallback = 'N/A',
  format = 'number' 
}: SafeNumberProps) {
  try {
    // Debug log
    if (value === undefined || value === null) {
      console.warn('SafeNumber received undefined/null value:', { value, prefix, suffix, format });
      return <span>{fallback}</span>;
    }
    
    const numValue = typeof value === 'number' ? value : parseFloat(value);
    
    if (isNaN(numValue)) {
      console.warn('SafeNumber received non-numeric value:', { value, type: typeof value });
      return <span>{fallback}</span>;
    }
    
    let formatted: string;
    
    switch (format) {
      case 'currency':
        formatted = `$${(numValue / 1000).toFixed(decimals)}B`;
        break;
      case 'percentage':
        formatted = `${(numValue * 100).toFixed(decimals)}%`;
        break;
      case 'multiple':
        formatted = `${numValue.toFixed(decimals)}x`;
        break;
      default:
        formatted = numValue.toFixed(decimals);
    }
    
    return <span>{prefix}{formatted}{suffix}</span>;
  } catch (error) {
    console.error('SafeNumber error:', { value, error });
    return <span>{fallback}</span>;
  }
}