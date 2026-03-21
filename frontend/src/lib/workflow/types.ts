// ---------------------------------------------------------------------------
// Workflow Builder — Types
// ---------------------------------------------------------------------------

import type { ChipDef, ChipDomain } from '../chips/types';

/** Node categories in the visual builder */
export type WorkflowNodeKind =
  | 'tool'       // Backend tool (forecast, P&L, valuation, etc.)
  | 'funding'    // Equity/debt funding event
  | 'driver'     // Single assumption override
  | 'operator'   // Control flow (loop, conditional, bridge, etc.)
  | 'formula'    // Inline expression
  | 'output';    // Terminal — where results land

/** Operator types */
export type OperatorType =
  // Control flow
  | 'loop'
  | 'conditional'
  | 'bridge'
  | 'parallel'
  | 'switch'
  // Data/transform
  | 'filter'
  | 'aggregate'
  | 'map'
  | 'merge'
  // Events
  | 'event_business'
  | 'event_macro'
  | 'event_funding'
  // Probabilistic
  | 'prior';

/** Output format for terminal nodes */
export type OutputFormat =
  | 'memo-section'
  | 'deck-slide'
  | 'chart'
  | 'grid'
  | 'table'
  | 'narrative'
  | 'export';

/** Data stored on each workflow node */
export interface WorkflowNodeData {
  [key: string]: unknown;
  kind: WorkflowNodeKind;
  label: string;
  icon: string;
  domain: ChipDomain;
  color: string;
  /** Reference to chip definition (for tool/driver nodes) */
  chipId?: string;
  chipDef?: ChipDef;
  /** User-configured parameter values */
  params: Record<string, any>;
  /** For operator nodes */
  operatorType?: OperatorType;
  /** For output nodes */
  outputFormat?: OutputFormat;
  /** Execution state */
  status: 'idle' | 'running' | 'done' | 'error';
  /** Execution result (once done) */
  result?: any;
  error?: string;
  durationMs?: number;
}

/** Palette item — what you drag from the sidebar */
export interface PaletteItem {
  id: string;
  label: string;
  icon: string;
  kind: WorkflowNodeKind;
  domain: ChipDomain;
  color: string;
  /** For tool nodes — reference to chip def */
  chipId?: string;
  chipDef?: ChipDef;
  /** For operator nodes */
  operatorType?: OperatorType;
  /** Default params */
  defaultParams?: Record<string, any>;
  description: string;
}

/** Palette category */
export interface PaletteCategory {
  id: string;
  label: string;
  icon: string;
  color: string;
  items: PaletteItem[];
}
