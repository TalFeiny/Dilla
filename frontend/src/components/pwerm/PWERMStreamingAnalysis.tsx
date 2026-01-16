'use client';

import React from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle } from 'lucide-react';

interface PWERMStreamingAnalysisProps {
  companyName: string;
  currentArr: number;
  growthRate: number;
  sector: string;
}

// STREAMING DISABLED - This component is no longer functional
export default function PWERMStreamingAnalysis({
  companyName,
  currentArr,
  growthRate,
  sector
}: PWERMStreamingAnalysisProps) {
  return (
    <div className="space-y-6">
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          <strong>Streaming Analysis Disabled</strong><br />
          The streaming analysis feature has been disabled. Please use the non-streaming PWERM analysis instead.
        </AlertDescription>
      </Alert>
    </div>
  );
}