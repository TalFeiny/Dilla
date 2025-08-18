'use client';

import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';

export type ValuationMethod = 
  | 'ipev-pwerm'      // Strict IPEV compliant PWERM
  | 'enhanced-pwerm'  // Our enhanced PWERM with outlier scoring
  | 'public-comps'    // Public SaaS multiples
  | 'transaction-comps' // Recent M&A comparables
  | 'dcf'            // Discounted Cash Flow
  | 'vc-method'      // Classic VC method (exit value / return multiple)
  | 'berkus'         // Berkus method for early stage
  | 'scorecard'      // Scorecard valuation
  | 'combined';      // Weighted average of multiple methods

interface ValuationMethodSelectorProps {
  selectedMethod: ValuationMethod;
  onMethodChange: (method: ValuationMethod) => void;
  stage?: string;
}

const methodDescriptions: Record<ValuationMethod, { name: string; description: string; bestFor: string; compliance: string }> = {
  'ipev-pwerm': {
    name: 'IPEV PWERM',
    description: 'Strict International Private Equity and Venture Capital (IPEV) compliant probability-weighted expected return method',
    bestFor: 'Fund reporting, LP reporting, audit compliance',
    compliance: 'IPEV Compliant'
  },
  'enhanced-pwerm': {
    name: 'Enhanced PWERM',
    description: 'PWERM with outlier scoring, momentum analysis, and acquirer-specific scenarios',
    bestFor: 'Investment decisions, portfolio strategy',
    compliance: 'Modified IPEV'
  },
  'public-comps': {
    name: 'Public Comparables',
    description: 'Valuation based on public SaaS company revenue multiples',
    bestFor: 'Late-stage companies with clear public comparables',
    compliance: 'Market-based'
  },
  'transaction-comps': {
    name: 'M&A Comparables',
    description: 'Based on recent acquisition multiples in the sector',
    bestFor: 'Companies with clear acquisition targets',
    compliance: 'Market-based'
  },
  'dcf': {
    name: 'DCF Analysis',
    description: 'Discounted cash flow based on projected revenues and margins',
    bestFor: 'Mature companies with predictable cash flows',
    compliance: 'IPEV Secondary'
  },
  'vc-method': {
    name: 'VC Method',
    description: 'Work backwards from expected exit value using required return multiples',
    bestFor: 'Early-stage venture investments',
    compliance: 'Industry Standard'
  },
  'berkus': {
    name: 'Berkus Method',
    description: 'Scorecard approach for pre-revenue startups',
    bestFor: 'Pre-revenue, idea-stage companies',
    compliance: 'Early-stage'
  },
  'scorecard': {
    name: 'Scorecard Valuation',
    description: 'Comparative method using weighted scoring factors',
    bestFor: 'Seed and early-stage companies',
    compliance: 'Angel/Seed'
  },
  'combined': {
    name: 'Weighted Combination',
    description: 'Weighted average of multiple valuation methods',
    bestFor: 'Comprehensive valuation with multiple perspectives',
    compliance: 'Hybrid'
  }
};

export const ValuationMethodSelector: React.FC<ValuationMethodSelectorProps> = ({
  selectedMethod,
  onMethodChange,
  stage = 'unknown'
}) => {
  const currentMethodInfo = methodDescriptions[selectedMethod];

  // Recommend methods based on stage
  const getRecommendedMethods = (stage: string): ValuationMethod[] => {
    const stageMap: Record<string, ValuationMethod[]> = {
      'seed': ['berkus', 'scorecard', 'vc-method'],
      'series_a': ['enhanced-pwerm', 'vc-method', 'transaction-comps'],
      'series_b': ['enhanced-pwerm', 'public-comps', 'transaction-comps'],
      'series_c': ['ipev-pwerm', 'public-comps', 'dcf'],
      'late_stage': ['ipev-pwerm', 'public-comps', 'dcf'],
      'unknown': ['enhanced-pwerm', 'combined']
    };
    return stageMap[stage] || stageMap['unknown'];
  };

  const recommendedMethods = getRecommendedMethods(stage);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Valuation Method</CardTitle>
        <CardDescription>
          Select the valuation methodology for analysis
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <Label htmlFor="valuation-method">Method</Label>
          <Select value={selectedMethod} onValueChange={(value) => onMethodChange(value as ValuationMethod)}>
            <SelectTrigger id="valuation-method">
              <SelectValue placeholder="Select a valuation method" />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(methodDescriptions).map(([key, info]) => (
                <SelectItem key={key} value={key}>
                  <div className="flex items-center gap-2">
                    <span>{info.name}</span>
                    {recommendedMethods.includes(key as ValuationMethod) && (
                      <Badge variant="secondary" className="text-xs">Recommended</Badge>
                    )}
                    {key === 'ipev-pwerm' && (
                      <Badge variant="outline" className="text-xs">Compliant</Badge>
                    )}
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {currentMethodInfo && (
          <div className="space-y-2 pt-2 border-t">
            <div>
              <Label className="text-sm text-muted-foreground">Description</Label>
              <p className="text-sm">{currentMethodInfo.description}</p>
            </div>
            <div>
              <Label className="text-sm text-muted-foreground">Best For</Label>
              <p className="text-sm">{currentMethodInfo.bestFor}</p>
            </div>
            <div>
              <Label className="text-sm text-muted-foreground">Compliance</Label>
              <Badge variant="outline">{currentMethodInfo.compliance}</Badge>
            </div>
          </div>
        )}

        {stage && stage !== 'unknown' && (
          <div className="text-sm text-muted-foreground">
            Stage detected: <span className="font-medium">{stage.replace('_', ' ').toUpperCase()}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
};