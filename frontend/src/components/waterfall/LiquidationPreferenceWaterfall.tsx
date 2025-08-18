'use client';

import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Legend } from 'recharts';
import { Slider } from '@/components/ui/slider';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Info, TrendingUp, AlertTriangle } from 'lucide-react';
import { agentBehaviorSystem } from '@/lib/agent-skills/learned-behaviors';
import { colorCodingSystem } from '@/lib/color-coding-system';

interface LiquidationPreference {
  round: string;
  amount: number;
  type: 'non-participating' | 'participating' | 'participating-capped';
  cap?: number; // For participating with cap (e.g., 2x)
  conversionThreshold?: number;
}

interface LiquidationPreferenceWaterfallProps {
  preferences: LiquidationPreference[];
  commonShares: number;
  totalShares: number;
  companyName?: string;
}

export const LiquidationPreferenceWaterfall: React.FC<LiquidationPreferenceWaterfallProps> = ({
  preferences,
  commonShares,
  totalShares,
  companyName = 'Company'
}) => {
  const [maxExitValue, setMaxExitValue] = useState(500); // $500M default
  const [selectedExitValue, setSelectedExitValue] = useState(100); // $100M default

  // Calculate total preference stack
  const preferenceStack = useMemo(() => 
    preferences.reduce((sum, pref) => sum + pref.amount, 0),
    [preferences]
  );

  // Generate waterfall data points
  const waterfallData = useMemo(() => {
    const points = [];
    const step = maxExitValue / 100; // 100 data points
    
    for (let exitValue = 0; exitValue <= maxExitValue; exitValue += step) {
      const distribution = calculateDistribution(exitValue, preferences, commonShares, totalShares);
      
      points.push({
        exitValue,
        nonParticipating: distribution.nonParticipating,
        participating: distribution.participating,
        common: distribution.common,
        total: distribution.total,
        commonPercentage: exitValue > 0 ? (distribution.common / exitValue) * 100 : 0
      });
    }
    
    return points;
  }, [preferences, commonShares, totalShares, maxExitValue]);

  // Calculate distribution at specific exit value
  function calculateDistribution(
    exitValue: number,
    prefs: LiquidationPreference[],
    common: number,
    total: number
  ) {
    let remainingProceeds = exitValue;
    let nonParticipatingProceeds = 0;
    let participatingProceeds = 0;
    let commonProceeds = 0;

    // Sort preferences by seniority (typically reverse chronological)
    const sortedPrefs = [...prefs].reverse();

    // Phase 1: Pay liquidation preferences
    for (const pref of sortedPrefs) {
      if (remainingProceeds <= 0) break;

      const prefPayment = Math.min(pref.amount, remainingProceeds);
      
      if (pref.type === 'non-participating') {
        // Check if should convert to common
        const asCommonValue = (exitValue * (pref.amount / total));
        if (asCommonValue > pref.amount) {
          // Convert to common - don't take preference
          continue;
        }
        nonParticipatingProceeds += prefPayment;
      } else {
        participatingProceeds += prefPayment;
      }
      
      remainingProceeds -= prefPayment;
    }

    // Phase 2: Participating preferred get their pro-rata share
    if (remainingProceeds > 0) {
      for (const pref of sortedPrefs) {
        if (pref.type === 'participating' || pref.type === 'participating-capped') {
          const proRataShare = remainingProceeds * (pref.amount / total);
          
          if (pref.type === 'participating-capped' && pref.cap) {
            // Check cap
            const totalReceived = pref.amount + proRataShare;
            const cappedAmount = Math.min(totalReceived, pref.amount * pref.cap) - pref.amount;
            participatingProceeds += Math.max(0, cappedAmount);
          } else {
            participatingProceeds += proRataShare;
          }
        }
      }
    }

    // Phase 3: Common gets remainder
    commonProceeds = Math.max(0, exitValue - nonParticipatingProceeds - participatingProceeds);

    return {
      nonParticipating: nonParticipatingProceeds,
      participating: participatingProceeds,
      common: commonProceeds,
      total: nonParticipatingProceeds + participatingProceeds + commonProceeds
    };
  }

  // Calculate key thresholds
  const keyThresholds = useMemo(() => {
    const thresholds = [];
    
    // Preference stack threshold
    thresholds.push({
      value: preferenceStack,
      label: 'Preference Stack',
      description: 'Total liquidation preferences'
    });

    // First conversion threshold (when first non-participating converts)
    const firstNonPart = preferences.find(p => p.type === 'non-participating');
    if (firstNonPart) {
      const conversionValue = (firstNonPart.amount * totalShares) / firstNonPart.amount;
      thresholds.push({
        value: conversionValue,
        label: `${firstNonPart.round} Converts`,
        description: 'First conversion to common'
      });
    }

    // 2x cap threshold for participating
    const partWithCap = preferences.find(p => p.type === 'participating-capped');
    if (partWithCap && partWithCap.cap) {
      thresholds.push({
        value: partWithCap.amount * partWithCap.cap,
        label: `${partWithCap.cap}x Cap`,
        description: `${partWithCap.round} participation cap`
      });
    }

    // Common breakeven (when common starts getting meaningful proceeds)
    const commonBreakeven = preferenceStack * 1.5;
    thresholds.push({
      value: commonBreakeven,
      label: 'Common Breakeven',
      description: 'Common gets meaningful returns'
    });

    return thresholds;
  }, [preferences, preferenceStack, totalShares]);

  // Get distribution at selected exit value
  const selectedDistribution = useMemo(() => 
    calculateDistribution(selectedExitValue, preferences, commonShares, totalShares),
    [selectedExitValue, preferences, commonShares, totalShares]
  );

  // Apply agent color coding
  const getStageColor = (type: string) => {
    return agentBehaviorSystem.applyBehavior('color_code', type, { 
      type: 'liquidation_preference' 
    });
  };

  // Custom tooltip
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const exitVal = label;
      const data = payload[0].payload;
      
      return (
        <div className="bg-white p-4 border rounded-lg shadow-lg">
          <p className="font-semibold">Exit Value: ${exitVal}M</p>
          <div className="space-y-1 mt-2">
            <p className="text-sm">
              <span className="inline-block w-3 h-3 rounded mr-2" style={{ backgroundColor: '#e5e7eb' }}></span>
              Non-Participating: ${data.nonParticipating.toFixed(1)}M
            </p>
            <p className="text-sm">
              <span className="inline-block w-3 h-3 rounded mr-2" style={{ backgroundColor: '#93c5fd' }}></span>
              Participating: ${data.participating.toFixed(1)}M
            </p>
            <p className="text-sm">
              <span className="inline-block w-3 h-3 rounded mr-2" style={{ backgroundColor: '#1e40af' }}></span>
              Common: ${data.common.toFixed(1)}M ({data.commonPercentage.toFixed(1)}%)
            </p>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-6">
      {/* Header with key metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Preference Stack</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${(preferenceStack / 1e6).toFixed(1)}M</div>
            <p className="text-xs text-muted-foreground">Total liquidation preferences</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Common Shares</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{((commonShares / totalShares) * 100).toFixed(1)}%</div>
            <p className="text-xs text-muted-foreground">Of total ownership</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Participating</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {preferences.filter(p => p.type.includes('participating')).length}
            </div>
            <p className="text-xs text-muted-foreground">Of {preferences.length} rounds</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Break-even Exit</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              ${(preferenceStack * 1.5 / 1e6).toFixed(0)}M
            </div>
            <p className="text-xs text-muted-foreground">For common returns</p>
          </CardContent>
        </Card>
      </div>

      {/* Main Waterfall Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Liquidation Waterfall Analysis</CardTitle>
          <p className="text-sm text-muted-foreground">
            How proceeds are distributed across different exit values
          </p>
        </CardHeader>
        <CardContent>
          <div className="h-[400px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={waterfallData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis 
                  dataKey="exitValue" 
                  label={{ value: 'Exit Value ($M)', position: 'insideBottom', offset: -5 }}
                  tickFormatter={(value) => `$${value}`}
                />
                <YAxis 
                  label={{ value: 'Proceeds ($M)', angle: -90, position: 'insideLeft' }}
                  tickFormatter={(value) => `$${value}`}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend />
                
                {/* Add reference lines for key thresholds */}
                {keyThresholds.map((threshold, idx) => (
                  <ReferenceLine
                    key={idx}
                    x={threshold.value / 1e6}
                    stroke={colorCodingSystem.getColor(threshold.label, 'threshold')}
                    strokeDasharray="5 5"
                    label={{
                      value: threshold.label,
                      position: 'top',
                      fontSize: 10
                    }}
                  />
                ))}
                
                {/* Stack areas for each class */}
                <Area
                  type="monotone"
                  dataKey="nonParticipating"
                  stackId="1"
                  stroke="#e5e7eb"
                  fill="#e5e7eb"
                  name="Non-Participating"
                />
                <Area
                  type="monotone"
                  dataKey="participating"
                  stackId="1"
                  stroke="#93c5fd"
                  fill="#93c5fd"
                  name="Participating"
                />
                <Area
                  type="monotone"
                  dataKey="common"
                  stackId="1"
                  stroke="#1e40af"
                  fill="#1e40af"
                  name="Common"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Interactive Exit Value Slider */}
          <div className="mt-6 space-y-4">
            <div>
              <Label>Select Exit Value: ${selectedExitValue}M</Label>
              <Slider
                value={[selectedExitValue]}
                onValueChange={(v) => setSelectedExitValue(v[0])}
                min={0}
                max={maxExitValue}
                step={5}
                className="mt-2"
              />
            </div>

            {/* Distribution at selected exit value */}
            <div className="grid grid-cols-3 gap-4 p-4 bg-gray-50 rounded-lg">
              <div>
                <p className="text-sm text-muted-foreground">Non-Participating</p>
                <p className="text-lg font-semibold">
                  ${(selectedDistribution.nonParticipating / 1e6).toFixed(2)}M
                </p>
                <p className="text-xs">
                  {((selectedDistribution.nonParticipating / selectedExitValue) * 100).toFixed(1)}%
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Participating</p>
                <p className="text-lg font-semibold">
                  ${(selectedDistribution.participating / 1e6).toFixed(2)}M
                </p>
                <p className="text-xs">
                  {((selectedDistribution.participating / selectedExitValue) * 100).toFixed(1)}%
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Common</p>
                <p className="text-lg font-semibold">
                  ${(selectedDistribution.common / 1e6).toFixed(2)}M
                </p>
                <p className="text-xs">
                  {((selectedDistribution.common / selectedExitValue) * 100).toFixed(1)}%
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Preference Details */}
      <Card>
        <CardHeader>
          <CardTitle>Liquidation Preference Structure</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {preferences.map((pref, idx) => (
              <div key={idx} className="flex items-center justify-between p-3 border rounded-lg">
                <div className="flex items-center gap-3">
                  <Badge variant={pref.type === 'non-participating' ? 'secondary' : 'default'}>
                    {pref.round}
                  </Badge>
                  <div>
                    <p className="font-medium">${(pref.amount / 1e6).toFixed(1)}M</p>
                    <p className="text-xs text-muted-foreground">
                      {pref.type.replace('-', ' ')}
                      {pref.cap && ` (${pref.cap}x cap)`}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm">
                    At ${selectedExitValue}M exit:
                  </p>
                  <p className="font-semibold">
                    ${(calculateDistribution(selectedExitValue, [pref], 0, totalShares).nonParticipating / 1e6).toFixed(2)}M
                  </p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Insights */}
      {preferenceStack > selectedExitValue * 0.5 && (
        <div className="flex items-start gap-2 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
          <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5" />
          <div>
            <p className="font-medium text-yellow-900">High Preference Stack</p>
            <p className="text-sm text-yellow-800">
              The liquidation preference stack ({(preferenceStack / 1e6).toFixed(1)}M) represents over 50% of the selected exit value. 
              Common shareholders may see limited returns at this exit level.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};