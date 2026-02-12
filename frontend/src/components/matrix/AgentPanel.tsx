'use client';

/**
 * Agent Panel — Cursor-style single chat panel (no tabs)
 * All actions (including document suggestion accept/reject) live inside the chat.
 * Plan, Activity, Charts & suggestions merged into chat or removed.
 */

import React from 'react';
import { Button } from '@/components/ui/button';
import type { ExportFormat } from '@/components/agent/AgentChat';
import { MatrixData } from './UnifiedMatrix';
import { DocumentSuggestion, DocumentInsight, type SuggestionAcceptPayload } from './DocumentSuggestions';
import type { CellAction } from '@/lib/matrix/cell-action-registry';
import AgentChat from '@/components/agent/AgentChat';

export type ToolCallEntry = {
  id: string;
  action_id: string;
  row_id: string;
  column_id: string;
  status: 'running' | 'success' | 'error';
  error?: string;
  at: string;
  companyName?: string;
  explanation?: string;
  reasoning?: string;
};

export type PlanStep = {
  id: string;
  label: string;
  status: 'pending' | 'running' | 'done' | 'failed';
  detail?: string;
};

export interface AgentPanelProps {
  matrixData: MatrixData | null;
  fundId?: string;
  mode?: 'portfolio' | 'query' | 'custom' | 'lp';
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  /** ChartViewport / suggestions */
  suggestions?: DocumentSuggestion[];
  insights?: DocumentInsight[];
  suggestionsLoading?: boolean;
  suggestionsError?: string | null;
  refreshSuggestions?: () => Promise<void>;
  onSuggestionAccept?: (suggestionId: string, payload?: SuggestionAcceptPayload) => void;
  onSuggestionReject?: (suggestionId: string) => void;
  onApplySuggestions?: (suggestions: DocumentSuggestion[]) => void;
  /** Run from panel + activity */
  availableActions?: CellAction[];
  toolCallEntries?: ToolCallEntry[];
  planSteps?: PlanStep[];
  /** Run service: (actionId, rowId, columnId) → execute and add suggestion */
  onRunService?: (actionId: string, rowId: string, columnId: string) => Promise<void>;
  /** Retry suggestion (re-run service for a suggestion card) */
  onRetrySuggestion?: (suggestion: DocumentSuggestion) => Promise<void>;
  /** Control centre: edit cell from chat (rowId, columnId, value) */
  onCellEdit?: (rowId: string, columnId: string, value: unknown, options?: { data_source?: string; metadata?: Record<string, unknown> }) => Promise<void>;
  /** When provided, grid commands go through this callback for accept/reject flow instead of executing directly */
  onGridCommandsFromBackend?: (commands: Array<{ action: 'edit' | 'run' | 'add_document'; rowId?: string; columnId?: string; value?: unknown; actionId?: string }>) => Promise<void>;
  /** Control centre: log tool calls for Activity tab */
  onToolCallLog?: (entry: Omit<ToolCallEntry, 'id' | 'at'>) => void;
  /** Export from chat: matrix CSV/XLS/PDF */
  onExportRequest?: (format: ExportFormat, payload?: { matrixData?: MatrixData; messageContent?: string }) => void;
  /** Chart from chat: NAV or DPI Sankey */
  onRequestChart?: (chartType: 'nav' | 'dpi_sankey') => Promise<Array<{ type: string; title?: string; data: unknown }>>;
  /** Document upload from chat: bulk upload to company → Celery */
  onUploadDocument?: (files: File[], opts: { companyId?: string; fundId?: string }) => Promise<void>;
  /** Plan steps callback - AgentChat updates when backend returns plan_steps */
  onPlanStepsUpdate?: (steps: PlanStep[]) => void;
  /** Memo sections — passed to AgentChat for context forwarding */
  memoSections?: Array<{ type: string; content?: string }>;
  /** Callback when agent returns memo_updates */
  onMemoUpdates?: (updates: { action: string; sections: Array<{ type: string; content?: string; chart?: unknown; items?: string[]; table?: unknown }> }) => void;
}

export function AgentPanel({
  matrixData,
  fundId,
  mode = 'portfolio',
  isOpen,
  onOpenChange,
  suggestions = [],
  insights = [],
  suggestionsLoading = false,
  suggestionsError = null,
  refreshSuggestions = async () => {},
  onSuggestionAccept,
  onSuggestionReject,
  onApplySuggestions,
  availableActions = [],
  onRunService,
  onRetrySuggestion,
  onCellEdit,
  onGridCommandsFromBackend,
  onToolCallLog,
  onExportRequest,
  onRequestChart,
  onUploadDocument,
  onPlanStepsUpdate,
  memoSections,
  onMemoUpdates,
  toolCallEntries = [],
  planSteps = [],
}: AgentPanelProps) {
  return (
    <div className="flex flex-col h-full min-h-0 w-full border-l bg-background">
      <div className="shrink-0 border-b px-2 py-1.5 flex items-center justify-between">
        <h2 className="font-medium text-xs">Chat</h2>
        <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={() => onOpenChange(false)}>
          <span className="sr-only">Close panel</span>
          ✕
        </Button>
      </div>

      <div className="flex flex-col flex-1 min-h-0 min-w-0 overflow-hidden">
        <AgentChat
          sessionId={fundId ? `matrix-${fundId}` : 'matrix'}
          matrixData={matrixData}
          fundId={fundId}
          mode={mode}
          onCellEdit={onCellEdit}
          onRunService={onRunService}
          onGridCommandsFromBackend={onGridCommandsFromBackend}
          onToolCallLog={onToolCallLog}
          availableActions={availableActions}
          onExportRequest={onExportRequest}
          onRequestChart={onRequestChart}
          onUploadDocument={onUploadDocument}
          onPlanStepsUpdate={onPlanStepsUpdate}
          memoSections={memoSections}
          onMemoUpdates={onMemoUpdates}
          suggestions={suggestions}
          suggestionsLoading={suggestionsLoading}
          suggestionsError={suggestionsError}
          refreshSuggestions={refreshSuggestions}
          onSuggestionAccept={onSuggestionAccept}
          onSuggestionReject={onSuggestionReject}
          onRetrySuggestion={onRetrySuggestion}
          toolCallEntries={toolCallEntries}
        />
      </div>
    </div>
  );
}
