'use client';

import React from 'react';
import type { WorkflowResult } from '@/lib/chips/types';
import { cn } from '@/lib/utils';
import { Loader2, CheckCircle2, XCircle, Clock } from 'lucide-react';

interface WorkflowResultsProps {
  results: WorkflowResult[];
  /** Whether the workflow is still executing */
  executing?: boolean;
  /** Current step index (for progress display) */
  currentStep?: number;
  className?: string;
}

/**
 * WorkflowResults — renders the output of a chip workflow execution.
 * Routes each step's result to the appropriate frontend renderer.
 * Shows progress during execution and errors if any step fails.
 */
export function WorkflowResults({
  results,
  executing,
  currentStep,
  className,
}: WorkflowResultsProps) {
  if (results.length === 0 && !executing) return null;

  return (
    <div className={cn('space-y-2', className)}>
      {/* Progress indicator during execution */}
      {executing && currentStep !== undefined && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground px-2 py-1">
          <Loader2 className="h-3 w-3 animate-spin" />
          <span>
            Running step {currentStep + 1}...
          </span>
        </div>
      )}

      {/* Results */}
      {results.map((result) => (
        <StepResult key={result.stepId} result={result} />
      ))}
    </div>
  );
}

function StepResult({ result }: { result: WorkflowResult }) {
  return (
    <div className="rounded-lg border border-border/50 overflow-hidden">
      {/* Step header */}
      <div className="flex items-center gap-2 px-3 py-1.5 bg-muted/30 border-b border-border/30">
        {result.success ? (
          <CheckCircle2 className="h-3 w-3 text-emerald-500" />
        ) : (
          <XCircle className="h-3 w-3 text-red-500" />
        )}
        <span className="text-xs font-medium">{result.chip.def.label}</span>
        <span className="text-[10px] text-muted-foreground ml-auto flex items-center gap-1">
          <Clock className="h-2.5 w-2.5" />
          {(result.durationMs / 1000).toFixed(1)}s
        </span>
      </div>

      {/* Result content */}
      <div className="p-3">
        {result.error ? (
          <p className="text-xs text-red-600">{result.error}</p>
        ) : (
          <ResultRenderer result={result} />
        )}
      </div>
    </div>
  );
}

/**
 * Route result data to the appropriate renderer based on the chip's outputRenderer.
 * This delegates to existing rendering components already in the codebase.
 * Falls back to raw JSON for unhandled types.
 */
function ResultRenderer({ result }: { result: WorkflowResult }) {
  const { data, renderer } = result;

  if (!data) {
    return <p className="text-xs text-muted-foreground">No data returned</p>;
  }

  // Extract response content from unified-brain response envelope
  const content = data.response ?? data.result ?? data;

  switch (renderer) {
    case 'chart':
      // Charts are rendered by the existing AgentChat chart renderer
      // Pass the data up for the parent to render with existing chart components
      return (
        <div className="text-xs">
          {content.charts ? (
            <p className="text-muted-foreground">
              Chart data available ({content.charts.length} chart{content.charts.length !== 1 ? 's' : ''})
            </p>
          ) : (
            <pre className="text-[10px] bg-muted/50 rounded p-2 overflow-x-auto max-h-[200px]">
              {JSON.stringify(content, null, 2)}
            </pre>
          )}
        </div>
      );

    case 'table':
      return (
        <div className="text-xs">
          {typeof content === 'string' ? (
            <p>{content}</p>
          ) : (
            <pre className="text-[10px] bg-muted/50 rounded p-2 overflow-x-auto max-h-[200px]">
              {JSON.stringify(content, null, 2)}
            </pre>
          )}
        </div>
      );

    case 'narrative':
      return (
        <div className="text-xs prose prose-sm max-w-none">
          {typeof content === 'string' ? (
            <p>{content}</p>
          ) : (
            <p>{content.text ?? content.narrative ?? JSON.stringify(content)}</p>
          )}
        </div>
      );

    case 'delta':
      return (
        <div className="text-xs">
          <pre className="text-[10px] bg-muted/50 rounded p-2 overflow-x-auto max-h-[200px]">
            {JSON.stringify(content, null, 2)}
          </pre>
        </div>
      );

    case 'notification':
      return (
        <p className="text-xs text-emerald-600">
          {typeof content === 'string' ? content : content.message ?? 'Action completed'}
        </p>
      );

    case 'deck':
    case 'document':
    case 'memo-section':
    case 'cap-table':
    case 'waterfall':
    case 'sankey':
    case 'tornado':
    case 'matrix':
    case 'tree':
      // These are rendered by existing specialized components in the codebase.
      // The chip workflow will pass this data to AgentChat which already handles them.
      return (
        <div className="text-xs text-muted-foreground">
          {renderer} output ready for rendering
        </div>
      );

    case 'raw':
    default:
      return (
        <pre className="text-[10px] bg-muted/50 rounded p-2 overflow-x-auto max-h-[200px]">
          {typeof content === 'string' ? content : JSON.stringify(content, null, 2)}
        </pre>
      );
  }
}
