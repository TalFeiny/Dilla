'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';

export default function TestAnalysisPage() {
  const [analysisData, setAnalysisData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');

  const fetchAnalysis = async () => {
    setLoading(true);
    setError('');
    
    try {
      const response = await fetch('/api/documents/11/analysis', {
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate'
        }
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      console.log('Analysis data received:', data);
      setAnalysisData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analysis');
    } finally {
      setLoading(false);
    }
  };

  const safeRender = (value: any): string => {
    if (value === null || value === undefined) return '';
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      return String(value);
    }
    if (Array.isArray(value)) {
      return value.length.toString();
    }
    if (typeof value === 'object') {
      return '[Object]';
    }
    return '';
  };

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">Analysis Test Page</h1>
      
      <Button onClick={fetchAnalysis} disabled={loading} className="mb-4">
        {loading ? 'Loading...' : 'Fetch Analysis'}
      </Button>
      
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
          <p className="text-red-800">Error: {error}</p>
        </div>
      )}
      
      {analysisData && (
        <div className="space-y-4">
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <h2 className="font-semibold text-green-800 mb-2">Analysis Loaded Successfully!</h2>
            <p className="text-green-600">Document ID: {safeRender(analysisData.id)}</p>
          </div>
          
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h3 className="font-semibold text-blue-800 mb-2">Safe Rendering Test</h3>
            <p>Document ID: {safeRender(analysisData.id)}</p>
            <p>Raw text length: {safeRender(analysisData.raw_text?.length)}</p>
            <p>Companies found: {safeRender(analysisData.comparables_analysis?.companies_found)}</p>
            <p>M&A transactions count: {safeRender(analysisData.comparables_analysis?.ma_transactions)}</p>
            <p>M&A deals count: {safeRender(analysisData.comparables_analysis?.ma_deals)}</p>
            <p>Red flags count: {safeRender(analysisData.issue_analysis?.red_flags)}</p>
          </div>
          
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
            <h3 className="font-semibold text-gray-800 mb-2">Raw Data (Full)</h3>
            <pre className="text-xs overflow-auto max-h-96">
              {JSON.stringify(analysisData, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
} 