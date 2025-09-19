'use client';

import React from 'react';

interface MCPOrchestratorProps {
  onResultsReceived?: (results: any) => void;
}

export function MCPOrchestrator({ onResultsReceived }: MCPOrchestratorProps) {
  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      <div className="text-center text-gray-500 py-12">
        <p className="text-xl font-semibold mb-2">MCP Orchestrator</p>
        <p className="text-sm">Component temporarily disabled for build</p>
      </div>
    </div>
  );
}