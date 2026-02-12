'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Loader2, Sparkles, CheckCircle2, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';

interface ScenarioInputProps {
  matrixData: any;
  fundId?: string;
  onScenarioParsed?: (result: any) => void;
  onApplyScenario?: (cellUpdates: any[]) => void;
}

export function ScenarioInput({
  matrixData,
  fundId,
  onScenarioParsed,
  onApplyScenario,
}: ScenarioInputProps) {
  const [query, setQuery] = useState('');
  const [isParsing, setIsParsing] = useState(false);
  const [scenarioResult, setScenarioResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleParse = async () => {
    if (!query.trim()) {
      toast.error('Please enter a scenario query');
      return;
    }

    setIsParsing(true);
    setError(null);
    setScenarioResult(null);

    try {
      // Call the scenario.compose action
      const response = await fetch(`/api/cell-actions/actions/${encodeURIComponent('scenario.compose')}/execute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          action_id: 'scenario.compose',
          row_id: '', // Not needed for scenario composition
          column_id: '', // Not needed for scenario composition
          inputs: {
            query: query,
            matrix_data: matrixData,
          },
          mode: 'portfolio',
          fund_id: fundId,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to parse scenario');
      }

      const result = await response.json();
      setScenarioResult(result);
      // Backend puts full payload in metadata.raw_output; resolve from there or top-level
      if (onScenarioParsed) {
        onScenarioParsed(result);
      }

      toast.success('Scenario parsed successfully');
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to parse scenario';
      setError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsParsing(false);
    }
  };

  // Resolve cell updates from actual response shape (metadata.raw_output or top-level)
  const effectiveResult = scenarioResult
    ? (scenarioResult.metadata?.raw_output ?? scenarioResult)
    : null;
  const cellUpdates =
    effectiveResult?.cell_updates ?? scenarioResult?.value?.cell_updates ?? scenarioResult?.cell_updates ?? [];

  const handleApplyScenario = () => {
    if (!cellUpdates.length) {
      toast.error('No cell updates to apply');
      return;
    }

    if (onApplyScenario) {
      onApplyScenario(cellUpdates);
      toast.success(`Applied ${cellUpdates.length} cell updates`);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <Label htmlFor="scenario-query">What if scenario</Label>
        <Textarea
          id="scenario-query"
          placeholder="What happens if growth decelerates in YX in year 2, but Tundex starts a commercial pilot with a tier 1 aerospace company"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="mt-2 min-h-[100px]"
          disabled={isParsing}
        />
        <p className="text-xs text-muted-foreground mt-1">
          Describe your scenario in natural language. The system will parse it and calculate impacts on matrix cells.
        </p>
      </div>

      <Button
        onClick={handleParse}
        disabled={isParsing || !query.trim()}
        className="w-full"
      >
        {isParsing ? (
          <>
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            Parsing scenario...
          </>
        ) : (
          <>
            <Sparkles className="h-4 w-4 mr-2" />
            Parse & Preview
          </>
        )}
      </Button>

      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-4">
            <div className="flex items-start gap-2">
              <AlertCircle className="h-4 w-4 text-red-600 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-red-900">Error</p>
                <p className="text-sm text-red-700">{error}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {scenarioResult && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">
                Scenario: {effectiveResult?.scenario_name ?? scenarioResult.scenario_name ?? 'Scenario'}
              </CardTitle>
              <CardDescription>
                {effectiveResult?.description ?? scenarioResult.description ?? ''}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Events */}
              {(effectiveResult?.composed_scenario ?? scenarioResult.composed_scenario)?.events && (
                <div>
                  <h4 className="text-xs font-semibold mb-2">Events</h4>
                  <div className="space-y-2">
                    {(effectiveResult?.composed_scenario ?? scenarioResult.composed_scenario).events.map((event: any, idx: number) => (
                      <div key={idx} className="flex items-start gap-2 p-2 rounded bg-muted">
                        <Badge variant="outline" className="shrink-0">
                          {event.entity_name}
                        </Badge>
                        <div className="flex-1 text-xs">
                          <p className="font-medium">{event.event_type.replace('_', ' ')}</p>
                          <p className="text-muted-foreground">{event.event_description}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Cell Updates */}
              {cellUpdates.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold mb-2">
                    Cell Updates ({cellUpdates.length})
                  </h4>
                  <div className="space-y-2 max-h-[300px] overflow-y-auto">
                    {cellUpdates.map((update: any, idx: number) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-2 rounded border text-xs"
                      >
                        <div className="flex-1">
                          <p className="font-medium">
                            {update.entity} · {update.column_id}
                          </p>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-muted-foreground line-through">
                              {typeof update.old_value === 'number'
                                ? update.old_value.toLocaleString()
                                : update.old_value}
                            </span>
                            <span>→</span>
                            <span className="font-medium text-green-600">
                              {typeof update.new_value === 'number'
                                ? update.new_value.toLocaleString()
                                : update.new_value}
                            </span>
                            {update.change_pct && (
                              <Badge
                                variant={update.change_pct > 0 ? 'default' : 'destructive'}
                                className="text-xs"
                              >
                                {update.change_pct > 0 ? '+' : ''}
                                {update.change_pct.toFixed(1)}%
                              </Badge>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Impact Summary */}
              {scenarioResult.model_outputs && (
                <div>
                  <h4 className="text-xs font-semibold mb-2">Impact Summary</h4>
                  <div className="space-y-1 text-xs">
                    {scenarioResult.model_outputs.nav_change !== undefined && (
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">NAV Change:</span>
                        <span
                          className={
                            scenarioResult.model_outputs.nav_change >= 0
                              ? 'text-green-600'
                              : 'text-red-600'
                          }
                        >
                          {scenarioResult.model_outputs.nav_change >= 0 ? '+' : ''}
                          {scenarioResult.model_outputs.nav_change.toLocaleString()}
                        </span>
                      </div>
                    )}
                    {scenarioResult.model_outputs.events_count && (
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Events:</span>
                        <span>{scenarioResult.model_outputs.events_count}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <Button
                onClick={handleApplyScenario}
                className="w-full"
                disabled={!cellUpdates.length}
              >
                <CheckCircle2 className="h-4 w-4 mr-2" />
                Apply Scenario to Matrix
              </Button>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
