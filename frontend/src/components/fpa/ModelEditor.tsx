'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Save, Edit2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

interface ModelEditorProps {
  modelStructure?: {
    steps?: Array<{
      step_id: string;
      name: string;
      formula: string;
      assumptions: Record<string, any>;
      editable: boolean;
    }>;
    formulas?: Record<string, string>;
    assumptions?: Record<string, any>;
  };
  onSave?: (updates: { formulas?: Record<string, string>; assumptions?: Record<string, any> }) => Promise<void>;
  modelId?: string;
}

export function ModelEditor({ modelStructure, onSave, modelId }: ModelEditorProps) {
  const [editingStep, setEditingStep] = useState<string | null>(null);
  const [formulaEdits, setFormulaEdits] = useState<Record<string, string>>({});
  const [assumptionEdits, setAssumptionEdits] = useState<Record<string, any>>({});

  const handleEditFormula = (stepId: string, currentFormula: string) => {
    setEditingStep(stepId);
    setFormulaEdits(prev => ({ ...prev, [stepId]: currentFormula }));
  };

  const handleSaveFormula = async (stepId: string) => {
    if (!onSave || !modelId) return;
    
    const formula = formulaEdits[stepId];
    if (formula) {
      // TODO: Call API to update formula
      await onSave({ formulas: { [stepId]: formula } });
    }
    setEditingStep(null);
  };

  const handleEditAssumption = (stepId: string, key: string, value: any) => {
    setAssumptionEdits(prev => ({
      ...prev,
      [stepId]: {
        ...(prev[stepId] || {}),
        [key]: value
      }
    }));
  };

  const handleSaveAssumptions = async (stepId: string) => {
    if (!onSave || !modelId) return;
    
    const assumptions = assumptionEdits[stepId];
    if (assumptions) {
      // TODO: Call API to update assumptions
      await onSave({ assumptions: { [stepId]: assumptions } });
    }
  };

  if (!modelStructure?.steps || modelStructure.steps.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-gray-500">
          No model structure available
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Model Editor</CardTitle>
        <CardDescription>
          Edit formulas and assumptions for each step
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-6">
          {modelStructure.steps.map((step) => (
            <div key={step.step_id} className="p-4 border rounded-lg">
              <div className="flex items-center justify-between mb-4">
                <h4 className="font-semibold">{step.name}</h4>
                {step.editable && (
                  <Badge variant="outline">Editable</Badge>
                )}
              </div>

              {/* Formula Editor */}
              <div className="mb-4">
                <Label className="mb-2 block">Formula</Label>
                {editingStep === step.step_id ? (
                  <div className="space-y-2">
                    <Textarea
                      value={formulaEdits[step.step_id] || step.formula}
                      onChange={(e) => setFormulaEdits(prev => ({ ...prev, [step.step_id]: e.target.value }))}
                      className="font-mono text-sm"
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={() => handleSaveFormula(step.step_id)}
                      >
                        <Save className="w-4 h-4 mr-2" />
                        Save
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setEditingStep(null)}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center justify-between p-3 bg-gray-50 rounded border">
                    <code className="text-sm flex-1">{step.formula}</code>
                    {step.editable && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleEditFormula(step.step_id, step.formula)}
                      >
                        <Edit2 className="w-4 h-4" />
                      </Button>
                    )}
                  </div>
                )}
              </div>

              {/* Assumptions Editor */}
              {step.assumptions && Object.keys(step.assumptions).length > 0 && (
                <div>
                  <Label className="mb-2 block">Assumptions</Label>
                  <div className="space-y-2">
                    {Object.entries(step.assumptions).map(([key, value]) => (
                      <div key={key} className="flex items-center gap-2">
                        <Label className="w-32 text-sm">{key}:</Label>
                        <Input
                          type="number"
                          value={assumptionEdits[step.step_id]?.[key] ?? value}
                          onChange={(e) => handleEditAssumption(step.step_id, key, parseFloat(e.target.value) || 0)}
                          className="flex-1"
                        />
                      </div>
                    ))}
                    {step.editable && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleSaveAssumptions(step.step_id)}
                        className="mt-2"
                      >
                        <Save className="w-4 h-4 mr-2" />
                        Save Assumptions
                      </Button>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
