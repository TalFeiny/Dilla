// ---------------------------------------------------------------------------
// Workflow Builder — Types
// ---------------------------------------------------------------------------

import type { ChipDef, ChipDomain } from '../chips/types';
import type { PortDef } from './port-types';
import type { NodeAssumption, CompanyDataSnapshot } from './assumptions';

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

/** Trigger types — how a workflow starts and receives input */
export type TriggerType =
  | 'manual'           // Click run
  | 'schedule'         // Cron-based
  | 'csv_upload'       // Upload a CSV/file — flow runs on that data
  | 'cell_input'       // Select a cell/row from the grid — flow starts from that data
  | 'document_upload'; // Upload a document (PDF, term sheet) — flow processes it

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
  /** For trigger nodes */
  triggerType?: TriggerType;
  /** For output nodes */
  outputFormat?: OutputFormat;
  /** Typed input ports */
  inputPorts?: PortDef[];
  /** Typed output ports */
  outputPorts?: PortDef[];
  /** Assumption-driven model: NL assumptions with probability + magnitude */
  assumptions?: NodeAssumption[];
  /** Base adjustment slider value (deterministic, grounded in actuals) */
  baseAdjustment?: number;
  /** Cached actuals key for this driver (e.g. 'revenue', 'opex_rd') */
  actualsKey?: string;
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
  /** For trigger nodes */
  triggerType?: TriggerType;
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
