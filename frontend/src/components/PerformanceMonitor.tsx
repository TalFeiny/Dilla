'use client';

import { useEffect, useState } from 'react';

interface PerformanceMetrics {
  pageLoadTime: number;
  apiResponseTime: number;
  memoryUsage?: number;
}

export default function PerformanceMonitor() {
  const [metrics, setMetrics] = useState<PerformanceMetrics>({
    pageLoadTime: 0,
    apiResponseTime: 0,
  });

  useEffect(() => {
    // Measure page load time
    if (typeof window !== 'undefined') {
      const loadTime = performance.now();
      setMetrics(prev => ({ ...prev, pageLoadTime: loadTime }));

      // Measure memory usage if available
      if ('memory' in performance) {
        const memory = (performance as any).memory;
        setMetrics(prev => ({ 
          ...prev, 
          memoryUsage: memory.usedJSHeapSize / 1024 / 1024 // Convert to MB
        }));
      }
    }
  }, []);

  const measureApiCall = async (url: string) => {
    const start = performance.now();
    try {
      await fetch(url);
      const end = performance.now();
      setMetrics(prev => ({ ...prev, apiResponseTime: end - start }));
    } catch (error) {
      console.error('API measurement error:', error);
    }
  };

  // Only show in development
  if (process.env.NODE_ENV !== 'development') {
    return null;
  }

  return (
    <div className="fixed bottom-4 right-4 bg-black bg-opacity-75 text-white p-3 rounded-lg text-xs font-mono z-50">
      <div className="mb-1">
        <span className="text-gray-300">Page Load: </span>
        <span className={metrics.pageLoadTime > 1000 ? 'text-red-400' : 'text-green-400'}>
          {metrics.pageLoadTime.toFixed(0)}ms
        </span>
      </div>
      {metrics.apiResponseTime > 0 && (
        <div className="mb-1">
          <span className="text-gray-300">API: </span>
          <span className={metrics.apiResponseTime > 1000 ? 'text-red-400' : 'text-green-400'}>
            {metrics.apiResponseTime.toFixed(0)}ms
          </span>
        </div>
      )}
      {metrics.memoryUsage && (
        <div>
          <span className="text-gray-300">Memory: </span>
          <span className={metrics.memoryUsage > 100 ? 'text-red-400' : 'text-green-400'}>
            {metrics.memoryUsage.toFixed(1)}MB
          </span>
        </div>
      )}
    </div>
  );
} 