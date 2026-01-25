"use client";

import React, { useState } from 'react';
import { WorldModelViewer } from '@/components/world-models/WorldModelViewer';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { getBackendUrl } from '@/lib/backend-url';

export default function WorldModelsPage() {
  const [modelId, setModelId] = useState<string>('');
  const [fundId, setFundId] = useState<string>('');
  const [createdModelId, setCreatedModelId] = useState<string | null>(null);

  const createModel = async () => {
    try {
      const backendUrl = getBackendUrl();
      const response = await fetch(`${backendUrl}/api/world-models/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: 'My World Model',
          model_type: 'portfolio',
          fund_id: fundId || undefined,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setCreatedModelId(data.id);
        setModelId(data.id);
      }
    } catch (error) {
      console.error('Error creating model:', error);
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>World Models - Paint Your Scenarios</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex gap-4">
              <Input
                placeholder="Model ID (or leave empty to create new)"
                value={modelId}
                onChange={(e) => setModelId(e.target.value)}
                className="flex-1"
              />
              <Input
                placeholder="Fund ID (optional)"
                value={fundId}
                onChange={(e) => setFundId(e.target.value)}
                className="flex-1"
              />
              <Button onClick={createModel}>Create New Model</Button>
            </div>
            
            {createdModelId && (
              <div className="text-sm text-green-600">
                Created model: {createdModelId}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {modelId && (
        <WorldModelViewer modelId={modelId} fundId={fundId || undefined} />
      )}

      {!modelId && (
        <Card>
          <CardContent className="p-12 text-center text-gray-500">
            <p className="text-lg mb-2">No Model Selected</p>
            <p>Enter a model ID or create a new model to start painting scenarios</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
