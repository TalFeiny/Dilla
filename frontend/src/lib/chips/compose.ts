// ---------------------------------------------------------------------------
// Compose — Parse inline chips + NL text into an executable workflow
// ---------------------------------------------------------------------------

import { nanoid } from 'nanoid';
import type {
  ActiveChip,
  ComposedWorkflow,
  InputSegment,
  WorkflowStep,
} from './types';

/**
 * NL cue words that signal execution ordering between chips.
 * "then" / "and then" → sequential (output feeds forward)
 * "assuming" / "with" / "given" → parameter context (applies to next chip)
 * "and" → parallel if independent, otherwise sequential
 * "compare with" / "vs" → side-by-side output
 */
const SEQUENTIAL_CUES = /\b(then|and then|next|after that|followed by)\b/i;
const CONTEXT_CUES = /\b(assuming|with|given|where|if|when)\b/i;
const PARALLEL_CUES = /\b(and|also|plus)\b/i;

/**
 * Compose an ordered workflow from a list of input segments (text + chips).
 *
 * The NL glue between chips determines execution order:
 *   - "then" signals sequential chaining (output → input)
 *   - "assuming" / "with" signals driver/context application
 *   - "and" between independent operations means parallel
 *   - Driver chips before a tool chip get grouped as assumptions
 */
export function compose(segments: InputSegment[]): ComposedWorkflow {
  const chipSegments = segments.filter((s): s is { type: 'chip'; chip: ActiveChip } => s.type === 'chip');
  const textSegments = segments.filter((s): s is { type: 'text'; text: string } => s.type === 'text');

  // Full NL context (all text joined)
  const nlContext = textSegments.map((s) => s.text).join(' ').trim();

  if (chipSegments.length === 0) {
    return { steps: [], nlContext, segments };
  }

  const steps: WorkflowStep[] = [];
  let prevStepId: string | undefined;

  // Walk segments in order to determine chip relationships
  let lastGlue = '';

  for (const seg of segments) {
    if (seg.type === 'text') {
      lastGlue = seg.text;
      continue;
    }

    const chip = seg.chip;
    const stepId = nanoid(8);

    // Determine dependency based on NL glue before this chip
    let dependsOn: string | undefined;
    if (prevStepId && SEQUENTIAL_CUES.test(lastGlue)) {
      dependsOn = prevStepId;
    } else if (prevStepId && CONTEXT_CUES.test(lastGlue)) {
      // Context cue means this chip receives context from prior
      dependsOn = prevStepId;
    } else if (prevStepId && !PARALLEL_CUES.test(lastGlue)) {
      // Default: if no explicit parallel cue, assume sequential
      dependsOn = prevStepId;
    }

    // Driver chips: group as assumptions for the next non-driver chip
    // (handled downstream — drivers with dependsOn feed into the next step's inputs)

    steps.push({
      id: stepId,
      chip,
      inputs: { ...chip.values },
      dependsOn,
    });

    prevStepId = stepId;
    lastGlue = '';
  }

  // Post-pass: merge consecutive driver chips into the next non-driver step
  return {
    steps: mergeDriverSteps(steps),
    nlContext,
    segments,
  };
}

/**
 * Merge consecutive driver-domain steps into the next non-driver step as assumptions.
 * e.g. [Burn Rate -20%] [Headcount +5] then [Forecast 12mo]
 * → Forecast step gets { driver_overrides: { burn_rate: -20, headcount: 5 } }
 */
function mergeDriverSteps(steps: WorkflowStep[]): WorkflowStep[] {
  const result: WorkflowStep[] = [];
  const pendingDrivers: WorkflowStep[] = [];

  for (const step of steps) {
    if (step.chip.def.domain === 'driver') {
      pendingDrivers.push(step);
      continue;
    }

    // Non-driver step: attach any pending drivers as assumptions
    if (pendingDrivers.length > 0) {
      const driverOverrides: Record<string, any> = {};
      for (const d of pendingDrivers) {
        // Extract driver key from the chip ID (driver_revenue_growth → revenue_growth)
        const driverKey = d.chip.def.id.replace(/^driver_/, '');
        driverOverrides[driverKey] = d.chip.values.value ?? d.chip.def.params[0]?.default;
      }
      step.inputs.driver_overrides = driverOverrides;
      pendingDrivers.length = 0;
    }

    result.push(step);
  }

  // If only driver chips remain (no tool chip after them), keep them as standalone steps
  for (const d of pendingDrivers) {
    result.push(d);
  }

  return result;
}

/**
 * Serialize segments back to a display string (for preview / debugging).
 */
export function segmentsToText(segments: InputSegment[]): string {
  return segments
    .map((s) => {
      if (s.type === 'text') return s.text;
      const chip = s.chip;
      const paramStr = chip.def.params
        .map((p) => {
          const val = chip.values[p.key] ?? p.default;
          return p.chipDisplay ? p.chipDisplay(val) : String(val);
        })
        .filter(Boolean)
        .join(' ');
      return `[${chip.def.label}${paramStr ? ' ' + paramStr : ''}]`;
    })
    .join('');
}

/**
 * Build the prompt string that gets sent to unified-brain.
 * Includes both the NL context and structured chip tool hints.
 */
export function buildPrompt(workflow: ComposedWorkflow): string {
  const parts: string[] = [];

  if (workflow.nlContext) {
    parts.push(workflow.nlContext);
  }

  // Append structured tool instructions for the agent
  if (workflow.steps.length > 0) {
    const toolParts = workflow.steps.map((s, i) => {
      const paramStr = Object.entries(s.inputs)
        .filter(([k]) => k !== 'driver_overrides')
        .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
        .join(', ');
      const driverStr = s.inputs.driver_overrides
        ? ` with drivers: ${JSON.stringify(s.inputs.driver_overrides)}`
        : '';
      return `Step ${i + 1}: ${s.chip.def.tool}(${paramStr})${driverStr}`;
    });
    parts.push('\n[Workflow]\n' + toolParts.join('\n'));
  }

  return parts.join('\n');
}
