'use client';

import React, { useState, useCallback } from 'react';
import { Button } from '../../components/ui/button';

export default function TestAnalysisStep() {
  const [isOpen, setIsOpen] = useState(false);
  const [step, setStep] = useState(1);
  const [analysis, setAnalysis] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');

  const fetchAnalysis = useCallback(async () => {
    setLoading(true);
    setError('');
    
    try {
      const response = await fetch('/api/documents/11/analysis');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data = await response.json();
      console.log('Analysis data received:', data);
      setAnalysis(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analysis');
    } finally {
      setLoading(false);
    }
  }, []);

  const renderStep = () => {
    switch (step) {
      case 1:
        return <p>Step 1: Basic modal - just text</p>;
      
      case 2:
        return (
          <div>
            <p>Step 2: With loading state</p>
            {loading && <p>Loading...</p>}
            {error && <p>Error: {error}</p>}
            {analysis && <p>Analysis loaded! ID: {analysis.id}</p>}
          </div>
        );
      
      case 3:
        return (
          <div>
            <p>Step 3: With basic analysis data</p>
            {loading && <p>Loading...</p>}
            {error && <p>Error: {error}</p>}
            {analysis && (
              <div>
                <p>ID: {analysis.id}</p>
                <p>Raw text length: {analysis.raw_text?.length || 0}</p>
              </div>
            )}
          </div>
        );
      
      case 4:
        return (
          <div>
            <p>Step 4: With extracted data</p>
            {loading && <p>Loading...</p>}
            {error && <p>Error: {error}</p>}
            {analysis && (
              <div>
                <p>ID: {analysis.id}</p>
                <p>Raw text length: {analysis.raw_text?.length || 0}</p>
                {analysis.extracted_data && (
                  <div>
                    <p>Has extracted_data: Yes</p>
                    <p>Financial metrics: {analysis.extracted_data.financial_metrics ? 'Yes' : 'No'}</p>
                    <p>Company info: {analysis.extracted_data.company_info ? 'Yes' : 'No'}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      
      case 5:
        return (
          <div>
            <p>Step 5: With comparables analysis</p>
            {loading && <p>Loading...</p>}
            {error && <p>Error: {error}</p>}
            {analysis && (
              <div>
                <p>ID: {analysis.id}</p>
                <p>Raw text length: {analysis.raw_text?.length || 0}</p>
                {analysis.comparables_analysis && (
                  <div>
                    <p>Companies found: {analysis.comparables_analysis.companies_found}</p>
                    <p>M&A transactions: {analysis.comparables_analysis.ma_transactions?.length || 0}</p>
                    <p>M&A deals: {analysis.comparables_analysis.ma_deals?.length || 0}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      
      default:
        return <p>Unknown step</p>;
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <h1 className="text-3xl font-bold mb-8">Analysis Step Test</h1>
      
      <div className="space-y-4 mb-8">
        <p>Current step: {step}</p>
        <div className="flex space-x-2">
          <Button onClick={() => setStep(1)} disabled={step === 1}>Step 1</Button>
          <Button onClick={() => setStep(2)} disabled={step === 2}>Step 2</Button>
          <Button onClick={() => setStep(3)} disabled={step === 3}>Step 3</Button>
          <Button onClick={() => setStep(4)} disabled={step === 4}>Step 4</Button>
          <Button onClick={() => setStep(5)} disabled={step === 5}>Step 5</Button>
        </div>
        <Button onClick={() => setIsOpen(true)}>
          Open Modal (Step {step})
        </Button>
        {step >= 2 && (
          <Button onClick={fetchAnalysis}>
            Fetch Analysis Data
          </Button>
        )}
      </div>

      {isOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold">Step {step} Test</h2>
              <Button onClick={() => setIsOpen(false)} variant="ghost" size="sm">
                ✕
              </Button>
            </div>
            
            <div className="space-y-4">
              {renderStep()}
              <Button onClick={() => setIsOpen(false)}>
                Close Modal
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
} 