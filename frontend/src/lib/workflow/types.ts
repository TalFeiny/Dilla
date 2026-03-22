// ---------------------------------------------------------------------------
// Workflow Builder — Types
// ---------------------------------------------------------------------------

import type { ChipDef, ChipDomain } from '../chips/types';
import type { PortDef } from './port-types';

/** Node categories in the visual builder */
export type WorkflowNodeKind =
  | 'trigger'    // Entry point — where workflow starts
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
  | 'transform'
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
  /** Row/subcategory targeting — e.g. ['revenue', 'revenue/product', 'opex_rd'] */
  targetRows?: string[];
  /** Period targeting — e.g. ['2025-01', '2025-02']; empty = all periods */
  targetPeriods?: string[];
  /** Per-node driver/lever overrides — e.g. { revenue_growth: 30, churn_rate: 5 } */
  driverOverrides?: Record<string, number>;
  /** For operator nodes */
  operatorType?: OperatorType;
  /** For output nodes */
  outputFormat?: OutputFormat;
  /** Typed input ports */
  inputPorts?: PortDef[];
  /** Typed output ports */
  outputPorts?: PortDef[];
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
  /** Typed ports from chip definition */
  inputPorts?: PortDef[];
  outputPorts?: PortDef[];
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
