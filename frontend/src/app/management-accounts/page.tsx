'use client';

import { useState } from 'react';
import EnhancedSpreadsheet from '@/components/accounts/EnhancedSpreadsheet';
import AgentRunner from '@/components/accounts/AgentRunner';

export default function ManagementAccountsPage() {
  const [showAgent, setShowAgent] = useState(true);
  
  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Management Accounts</h1>
            <p className="text-gray-600 mt-2">
              Excel-like spreadsheet with full formula support and agent capabilities
            </p>
          </div>
          <button
            onClick={() => setShowAgent(!showAgent)}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            {showAgent ? 'Hide Agent' : 'Show Agent'}
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        <div className="relative flex h-full">
          {/* Main Spreadsheet */}
          <div className={showAgent ? "flex-1 min-w-0 overflow-auto" : "w-full overflow-auto"}>
            <EnhancedSpreadsheet />
          </div>
          
          {/* Agent Runner Panel - Fixed width, no overlap */}
          {showAgent && (
            <div className="w-[400px] flex-shrink-0 border-l border-gray-200 bg-gray-50 h-full overflow-hidden">
              <div className="h-full overflow-y-auto p-3">
                <AgentRunner />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}