'use client';

import React, { useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, CheckCircle2, AlertCircle, TrendingUp, DollarSign, Target } from 'lucide-react';
import { PWERMResultsDisplay } from './PWERMResultsDisplay';

interface ProgressUpdate {
  type: 'progress' | 'complete' | 'error' | 'cache_update';
  message?: string;
  progress?: number;
  data?: any;
}

interface PWERMStreamingAnalysisProps {
  companyName: string;
  currentArr: number;
  growthRate: number;
  sector: string;
}

export default function PWERMStreamingAnalysis({
  companyName,
  currentArr,
  growthRate,
  sector
}: PWERMStreamingAnalysisProps) {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [progressSteps, setProgressSteps] = useState<Array<{message: string, completed: boolean}>>([]);

  const runAnalysis = useCallback(async () => {
    setIsAnalyzing(true);
    setProgress(0);
    setProgressMessage('Starting PWERM analysis...');
    setError(null);
    setResults(null);
    setProgressSteps([]);

    try {
      const response = await fetch('/api/pwerm-stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          company_name: companyName,
          current_arr: currentArr,
          growth_rate: growthRate,
          sector: sector,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No reader available');
      }

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value);
        const lines = text.split('\n').filter(line => line.trim());

        for (const line of lines) {
          try {
            const update: ProgressUpdate = JSON.parse(line);

            switch (update.type) {
              case 'progress':
                setProgress(update.progress || 0);
                setProgressMessage(update.message || '');
                
                // Add to progress steps
                setProgressSteps(prev => {
                  const newSteps = Array.from(prev);
                  const existingIndex = newSteps.findIndex(s => s.message === update.message);
                  
                  if (existingIndex === -1) {
                    newSteps.push({ message: update.message || '', completed: true });
                  }
                  
                  return newSteps;
                });
                break;

              case 'complete':
                setResults(update.data);
                setIsAnalyzing(false);
                setProgress(100);
                setProgressMessage('Analysis complete!');
                break;

              case 'error':
                setError(update.message || 'Analysis failed');
                setIsAnalyzing(false);
                break;
            }
          } catch (e) {
            console.error('Failed to parse update:', e);
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
      setIsAnalyzing(false);
    }
  }, [companyName, currentArr, growthRate, sector]);

  return (
    <div className="space-y-6">
      {/* Analysis Control */}
      <Card>
        <CardHeader>
          <CardTitle>PWERM Analysis</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">Company:</span>
                <span className="ml-2 font-medium">{companyName}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Sector:</span>
                <span className="ml-2 font-medium">{sector}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Current ARR:</span>
                <span className="ml-2 font-medium">${currentArr}M</span>
              </div>
              <div>
                <span className="text-muted-foreground">Growth Rate:</span>
                <span className="ml-2 font-medium">{(growthRate * 100).toFixed(0)}%</span>
              </div>
            </div>

            <Button 
              onClick={runAnalysis} 
              disabled={isAnalyzing}
              className="w-full"
            >
              {isAnalyzing ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Analyzing...
                </>
              ) : (
                'Run PWERM Analysis'
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Progress Display */}
      {(isAnalyzing || progressSteps.length > 0) && (
        <Card>
          <CardHeader>
            <CardTitle>Analysis Progress</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span>{progressMessage}</span>
                  <span>{progress}%</span>
                </div>
                <Progress value={progress} className="h-2" />
              </div>

              {progressSteps.length > 0 && (
                <div className="space-y-2">
                  {progressSteps.map((step, index) => (
                    <div key={index} className="flex items-center text-sm">
                      <CheckCircle2 className="h-4 w-4 text-green-500 mr-2" />
                      <span className="text-muted-foreground">{step.message}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Error Display */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Results Display */}
      {results && (
        <>
          {/* Quick Summary */}
          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Expected Exit Value</CardTitle>
                <DollarSign className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  ${(results.summary?.adjusted_expected_value / 1000).toFixed(1)}B
                </div>
                <p className="text-xs text-muted-foreground">
                  Outlier-adjusted expected value
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Outlier Score</CardTitle>
                <Target className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {results.summary?.outlier_score || 0}/100
                </div>
                <p className="text-xs text-muted-foreground">
                  Company quality score
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Success Probability</CardTitle>
                <TrendingUp className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {((results.summary?.success_probability || 0) * 100).toFixed(0)}%
                </div>
                <p className="text-xs text-muted-foreground">
                  Probability of positive return
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Full Results */}
          <PWERMResultsDisplay results={results} />
        </>
      )}
    </div>
  );
}