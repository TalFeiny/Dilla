// ---------------------------------------------------------------------------
// Workflow Execution Hook
// ---------------------------------------------------------------------------
// Serializes the graph, sends to backend, streams results back,
// and updates node execution state.

import { useCallback, useRef } from 'react';
import { useWorkflowStore } from '@/lib/workflow/store';
import { graphToWorkflow, getOutputRoutes, stepsToBackendShape } from '@/lib/workflow/serializer';
import { buildPrompt } from '@/lib/chips/compose';

interface ExecutionOptions {
  companyId?: string;
  onStepComplete?: (stepId: string, result: any) => void;
  onComplete?: (results: Record<string, any>) => void;
  onError?: (error: string) => void;
  onOutputReady?: (nodeId: string, format: string, data: any) => void;
  onScenarioBranchCreated?: (result: any) => void;
}

export function useWorkflowExecution(options: ExecutionOptions = {}) {
  const abortRef = useRef<AbortController | null>(null);

  const execute = useCallback(async () => {
    const { nodes, edges, setExecuting, setNodeStatus, resetExecution } =
      useWorkflowStore.getState();

    if (nodes.length === 0) return;

    // Reset previous run
    resetExecution();
    setExecuting(true);

    const abortController = new AbortController();
    abortRef.current = abortController;

    try {
      // Serialize graph → workflow
      const workflow = graphToWorkflow(nodes, edges);
      const outputRoutes = getOutputRoutes(nodes, edges);
      const prompt = buildPrompt(workflow);

      // Convert steps to backend-expected shape (kind, chip_id, depends_on)
      const backendSteps = stepsToBackendShape(workflow.steps, nodes);

      // Mark all executable nodes as running
      for (const step of workflow.steps) {
        setNodeStatus(step.id, 'running');
      }

      // Send to backend — use chip_workflow key that backend expects
      const response = await fetch('/api/agent/unified-brain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: prompt,
          context: {
            type: 'chip_workflow',
            company_id: options.companyId,
            output_routes: outputRoutes,
          },
          // chip_workflow at top level — route.ts forwards this directly
          chip_workflow: {
            steps: backendSteps,
            nl_context: workflow.nlContext,
          },
        }),
        signal: abortController.signal,
      });

      if (!response.ok) {
        throw new Error(`Backend error: ${response.status}`);
      }

      const data = await response.json();

      // Process results — backend returns step results in multiple possible shapes
      const stepResults: any[] =
        data.step_results ||                    // direct
        data.result?.steps ||                   // non-streaming path
        data.data?.steps ||                     // normalized
        (data.steps && Array.isArray(data.steps) ? data.steps : null) ||
        [];

      if (stepResults.length > 0) {
        // Build node ID → step index mapping for fallback
        const stepNodeIds = workflow.steps.map((s) => s.id);

        for (const stepResult of stepResults) {
          // chip_id is the node ID we sent; fall back to step index
          const nodeId =
            stepResult.chip_id ||
            stepResult.step_id ||
            stepResult.id ||
            stepNodeIds[stepResult.step] ||
            null;

          if (nodeId) {
            const hasError = stepResult.error || !stepResult.success;
            setNodeStatus(
              nodeId,
              hasError ? 'error' : 'done',
              stepResult.data || stepResult.result,
              stepResult.error || undefined
            );
            options.onStepComplete?.(nodeId, stepResult);

            // Detect scenario branch creation and dispatch for persistence
            const stepData = stepResult.data || stepResult.result;
            if (stepData?.branch && options.onScenarioBranchCreated) {
              options.onScenarioBranchCreated(stepData);
            }
          }
        }
      } else {
        // Single result — mark all as done
        for (const step of workflow.steps) {
          setNodeStatus(step.id, 'done', data);
        }
      }

      // ── Process output format routes ──────────────────────────────
      const outputs: any[] =
        data.outputs ||
        data.result?.outputs ||
        data.data?.outputs ||
        [];
      for (const output of outputs) {
        if (output.nodeId) {
          setNodeStatus(
            output.nodeId,
            output.success ? 'done' : 'error',
            output.data,
            output.error || undefined
          );
          if (output.success && options.onOutputReady) {
            options.onOutputReady(output.nodeId, output.format, output.data);
          }
        }
      }

      options.onComplete?.(data);
    } catch (err: any) {
      if (err.name === 'AbortError') return;

      const errorMsg = err.message || 'Execution failed';
      // Mark all running nodes as error
      const { nodes: currentNodes } = useWorkflowStore.getState();
      for (const node of currentNodes) {
        if ((node.data as any).status === 'running') {
          setNodeStatus(node.id, 'error', undefined, errorMsg);
        }
      }
      options.onError?.(errorMsg);
    } finally {
      setExecuting(false);
      abortRef.current = null;
    }
  }, [options]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    useWorkflowStore.getState().setExecuting(false);
  }, []);

  return { execute, stop };
}
