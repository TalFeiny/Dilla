'use client';

import { useState } from 'react';
import DynamicDataMatrix from '@/components/accounts/DynamicDataMatrix';
import AgentDataGrid from '@/components/accounts/AgentDataGrid';
import AgentRunner from '@/components/accounts/AgentRunner';
import { cn } from '@/lib/utils';

export default function ManagementAccountsPage() {
  const [activeView, setActiveView] = useState<'matrix' | 'spreadsheet'>('spreadsheet');

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Management Accounts</h1>
            <p className="text-gray-600 mt-2">
              {activeView === 'matrix' 
                ? 'Real-time data with clickable citations from database and web sources'
                : 'Agent-powered spreadsheet with full write, edit, and delete capabilities'}
            </p>
          </div>
          
          {/* View Switcher */}
          <div className="flex gap-2">
            <button
              onClick={() => setActiveView('spreadsheet')}
              className={cn(
                "px-4 py-2 rounded-lg font-medium transition-colors",
                activeView === 'spreadsheet'
                  ? "bg-gray-900 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              )}
            >
              Spreadsheet View
            </button>
            <button
              onClick={() => setActiveView('matrix')}
              className={cn(
                "px-4 py-2 rounded-lg font-medium transition-colors",
                activeView === 'matrix'
                  ? "bg-gray-900 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              )}
            >
              Data Matrix View
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {activeView === 'matrix' ? (
          <div className="p-6">
            <DynamicDataMatrix />
          </div>
        ) : (
          <div className="flex h-full">
            {/* Main Grid */}
            <div className="flex-1">
              <AgentDataGrid />
            </div>
            
            {/* Agent Runner Panel */}
            <div className="w-[500px] border-l border-gray-200 p-4 bg-gray-50">
              <AgentRunner />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}