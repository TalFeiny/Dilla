"use client";

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScenarioCanvas } from './ScenarioCanvas';
import { getBackendUrl } from '@/lib/backend-url';

interface WorldModelViewerProps {
  modelId: string;
  fundId?: string;
}

export function WorldModelViewer({ modelId, fundId }: WorldModelViewerProps) {
  const [model, setModel] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [scenarioResults, setScenarioResults] = useState<any>(null);

  useEffect(() => {
    loadModel();
  }, [modelId]);

  const loadModel = async () => {
    try {
      const backendUrl = getBackendUrl();
      const response = await fetch(`${backendUrl}/api/world-models/${modelId}`);
      if (response.ok) {
        const data = await response.json();
        setModel(data);
      }
    } catch (error) {
      console.error('Error loading world model:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleScenarioComposed = (scenario: any) => {
    setScenarioResults(scenario);
  };

  if (loading) {
    return <div>Loading world model...</div>;
  }

  return (
    <div className="w-full h-full flex flex-col space-y-4">
      {/* Model Info */}
      {model && (
        <Card>
          <CardHeader>
            <CardTitle>{model.model?.name || 'World Model'}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <strong>Entities:</strong> {model.entities?.length || 0}
              </div>
              <div>
                <strong>Factors:</strong> {model.factors?.length || 0}
              </div>
              <div>
                <strong>Relationships:</strong> {model.relationships?.length || 0}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Scenario Canvas */}
      <div className="flex-1 min-h-[600px]">
        <ScenarioCanvas
          modelId={modelId}
          fundId={fundId}
          onScenarioComposed={handleScenarioComposed}
        />
      </div>

      {/* Scenario Results */}
      {scenarioResults && (
        <Card>
          <CardHeader>
            <CardTitle>Scenario Impact</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <strong>Factors Changed:</strong>{' '}
                {scenarioResults.impact_summary?.factors_changed || 0}
              </div>
              
              {scenarioResults.execution && (
                <div>
                  <strong>Model Outputs:</strong>
                  <pre className="mt-2 p-4 bg-gray-100 rounded text-sm overflow-auto">
                    {JSON.stringify(scenarioResults.execution.model_outputs, null, 2)}
                  </pre>
                </div>
              )}

              {scenarioResults.execution?.factor_changes && (
                <div>
                  <strong>Key Changes:</strong>
                  <div className="mt-2 space-y-2">
                    {Object.entries(scenarioResults.execution.factor_changes)
                      .slice(0, 5)
                      .map(([factorId, change]: [string, any]) => (
                        <div key={factorId} className="flex items-center gap-2">
                          <Badge>{change.factor_name}</Badge>
                          <span>
                            {change.base_value} → {change.scenario_value}
                            {change.change !== 0 && (
                              <span className="text-sm text-gray-600 ml-2">
                                ({change.change > 0 ? '+' : ''}{change.change})
                              </span>
                            )}
                          </span>
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
