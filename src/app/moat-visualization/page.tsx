'use client';

import React, { useState } from 'react';
import CompetitiveMoatCastle from '@/components/visualizations/CompetitiveMoatCastle';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export default function MoatVisualizationPage() {
  const [companyName, setCompanyName] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [moatData, setMoatData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = async () => {
    if (!companyName.trim()) {
      setError('Please enter a company name');
      return;
    }
    
    setIsAnalyzing(true);
    setError(null);
    
    try {
      // Call PWERM analysis API to get real data
      const response = await fetch('/api/moat-analysis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company_name: companyName })
      });
      
      if (!response.ok) {
        throw new Error('Failed to analyze company');
      }
      
      const data = await response.json();
      setMoatData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="container mx-auto py-8 px-4">
      <Card className="mb-8">
        <CardHeader>
          <CardTitle>Competitive Moat Analysis</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4 mb-6">
            <Input
              placeholder="Enter company name"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              className="flex-1"
            />
            <Button onClick={handleAnalyze} disabled={isAnalyzing}>
              {isAnalyzing ? 'Analyzing...' : 'Analyze Moats'}
            </Button>
          </div>
          
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}
          
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6">
            <p className="text-sm text-amber-800">
              <strong>Note:</strong> This visualization shows how companies build competitive moats (advantages that protect them from competition) 
              and face threats. The castle represents the company, the moat represents their competitive advantages, and the arrows show competitive threats.
            </p>
          </div>
        </CardContent>
      </Card>

      {moatData && <CompetitiveMoatCastle data={moatData} />}
    </div>
  );
}