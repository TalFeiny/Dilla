'use client';

import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, TrendingDown, Clock, CheckCircle, XCircle } from 'lucide-react';
import TableauLevelCharts from '@/components/charts/TableauLevelCharts';

interface QueryResultsProps {
  results: {
    parsed_query?: any;
    workflow?: any[];
    results?: any;
    step_results?: any[];
    model_structure?: any;
    execution_time_ms?: number;
  };
}

export function QueryResults({ results }: QueryResultsProps) {
  const { step_results = [], execution_time_ms, model_structure } = results;

  return (
    <div className="space-y-6">
      {/* Execution Summary */}
      <Card>
        <CardHeader>
          <CardTitle>Execution Summary</CardTitle>
          <CardDescription>
            {execution_time_ms && `Completed in ${execution_time_ms}ms`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">{step_results.length}</div>
              <div className="text-sm text-gray-600">Steps</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {step_results.filter((s: any) => s.success).length}
              </div>
              <div className="text-sm text-gray-600">Successful</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">
                {step_results.filter((s: any) => !s.success).length}
              </div>
              <div className="text-sm text-gray-600">Failed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-600">
                {execution_time_ms ? `${execution_time_ms}ms` : '—'}
              </div>
              <div className="text-sm text-gray-600">Duration</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Step Results Timeline */}
      <Card>
        <CardHeader>
          <CardTitle>Workflow Timeline</CardTitle>
          <CardDescription>Step-by-step execution results</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {step_results.map((step: any, idx: number) => (
              <div
                key={step.step_id || idx}
                className="flex items-start gap-4 p-4 border rounded-lg"
              >
                <div className="flex-shrink-0">
                  {step.success ? (
                    <CheckCircle className="w-6 h-6 text-green-600" />
                  ) : (
                    <XCircle className="w-6 h-6 text-red-600" />
                  )}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <h4 className="font-semibold">{step.name || step.step_id}</h4>
                    <Badge variant={step.success ? 'default' : 'destructive'}>
                      {step.success ? 'Success' : 'Failed'}
                    </Badge>
                  </div>
                  {step.error && (
                    <p className="text-sm text-red-600">{step.error}</p>
                  )}
                  {step.output && (
                    <div className="mt-2 text-sm text-gray-600">
                      <pre className="bg-gray-50 p-2 rounded text-xs overflow-x-auto">
                        {JSON.stringify(step.output, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Model Structure */}
      {model_structure && (
        <Card>
          <CardHeader>
            <CardTitle>Model Structure</CardTitle>
            <CardDescription>Formulas and assumptions</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {model_structure.steps?.map((step: any, idx: number) => (
                <div key={idx} className="p-4 border rounded-lg">
                  <h4 className="font-semibold mb-2">{step.name}</h4>
                  <p className="text-sm text-gray-600 mb-2">
                    <strong>Formula:</strong> {step.formula}
                  </p>
                  {step.assumptions && Object.keys(step.assumptions).length > 0 && (
                    <div className="text-sm">
                      <strong>Assumptions:</strong>
                      <pre className="mt-1 bg-gray-50 p-2 rounded text-xs overflow-x-auto">
                        {JSON.stringify(step.assumptions, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Charts - if results contain chartable data */}
      {results.results && (
        <Card>
          <CardHeader>
            <CardTitle>Visualizations</CardTitle>
          </CardHeader>
          <CardContent>
            {/* TODO: Render charts based on results type */}
            <p className="text-sm text-gray-600">Charts will be rendered here based on results</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
