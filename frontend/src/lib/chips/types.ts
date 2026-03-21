// ---------------------------------------------------------------------------
// Chip System — Types
// ---------------------------------------------------------------------------

/** Chip kind — what this chip DOES (not just which tool it wraps) */
export type ChipKind =
  | 'tool'          // Backend tool execution (default)
  | 'driver'        // Single assumption override
  | 'bridge'        // Cross-domain data transform (multi-tool chain)
  | 'formula'       // Computed metric / inline expression
  | 'assumption'    // Parameter bundle (multi-driver)
  | 'loop'          // Iterate over collection
  | 'conditional'   // Branch on condition
  | 'chart'         // Visualization specification
  | 'operational'   // Business ops action
  | 'event'         // Business/macro/funding event (model construction)
  | 'prior';        // Uncertainty / confidence specification

/** Domain groupings for the chip tray */
export type ChipDomain =
  | 'fpa'
  | 'analytics'
  | 'scenario'
  | 'driver'
  | 'capital'
  | 'macro'
  | 'intel'
  | 'report'
  | 'compliance'
  | 'data'
  | 'comms'
  | 'funding'
  | 'portfolio'
  // V2 additions:
  | 'modeling'
  | 'ops'
  | 'transform'
  | 'chart'
  | 'bridge';

/** What frontend component renders this chip's output */
export type OutputRenderer =
  | 'chart'
  | 'table'
  | 'delta'
  | 'deck'
  | 'narrative'
  | 'memo-section'
  | 'cap-table'
  | 'waterfall'
  | 'sankey'
  | 'tornado'
  | 'matrix'
  | 'tree'
  | 'document'
  | 'notification'
  | 'raw';

/** Domain display metadata */
export interface DomainMeta {
  label: string;
  color: string;       // tailwind color class (e.g. 'emerald')
  icon: string;        // lucide icon name
}

/** Parameter definition for a chip */
export interface ChipParamDef {
  key: string;
  label: string;
  type: 'number' | 'percent' | 'currency' | 'select' | 'text' | 'months' | 'days' | 'metric';
  default: any;
  step?: number;
  min?: number;
  max?: number;
  options?: { label: string; value: any }[];
  /** Shown in the chip label when configured, e.g. "10k" for iterations=10000 */
  chipDisplay?: (value: any) => string;
}

/** Static chip definition */
export interface ChipDef {
  id: string;
  label: string;
  domain: ChipDomain;
  icon: string;
  description: string;
  /** Backend tool name (unified-brain tool_hint) */
  tool: string;
  /** Configurable parameters */
  params: ChipParamDef[];
  /** What domains can precede this chip in a workflow */
  accepts?: ChipDomain[];
  /** What this chip outputs (for chaining) */
  produces?: string[];
  /** Frontend renderer for output */
  outputRenderer: OutputRenderer;
  /** Cost indicator */
  costTier: 'free' | 'cheap' | 'expensive';
  /** Expected execution time */
  timeoutMs: number;

  // ── V2: Kind-aware fields ──────────────────────────────────

  /** Chip kind — defaults to 'tool' if omitted */
  kind?: ChipKind;
  /** For loops: what collection to iterate over */
  loopOver?: 'companies' | 'scenarios' | 'periods';
  /** For conditionals: metric to evaluate */
  conditionMetric?: string;
  /** For conditionals: comparison operator */
  conditionOp?: '<' | '>' | '==' | '<=' | '>=';
  /** For assumptions: which driver keys this bundles */
  assumptionKeys?: string[];
  /** For bridges: ordered tool chain to execute */
  bridgeTools?: string[];
  /** For events: event category */
  eventCategory?: 'business' | 'market' | 'macro' | 'funding' | 'operational';
  /** For priors: which parameters to set confidence on */
  priorKeys?: string[];
}

/** A chip instance in the input — has configured values + position */
export interface ActiveChip {
  /** Unique instance ID (multiple of same chip type allowed) */
  instanceId: string;
  /** Reference to the chip definition */
  def: ChipDef;
  /** User-configured parameter values */
  values: Record<string, any>;
}

/** A segment of the input — either text or a chip */
export type InputSegment =
  | { type: 'text'; text: string }
  | { type: 'chip'; chip: ActiveChip };

/** Parsed workflow from chips + NL */
export interface ComposedWorkflow {
  steps: WorkflowStep[];
  /** The full NL glue text for agent interpretation */
  nlContext: string;
  /** Raw segments for display/serialization */
  segments: InputSegment[];
}

export interface WorkflowStep {
  id: string;
  chip: ActiveChip;
  /** Resolved inputs from chip values + prior step outputs */
  inputs: Record<string, any>;
  /** Step ID this depends on (from NL cues like "then") */
  dependsOn?: string;
}

export interface WorkflowResult {
  stepId: string;
  chip: ActiveChip;
  /** Raw response from unified-brain */
  data: any;
  /** Renderer to use */
  renderer: OutputRenderer;
  /** Execution metadata */
  durationMs: number;
  success: boolean;
  error?: string;
}

/** Domain metadata registry */
export const DOMAIN_META: Record<ChipDomain, DomainMeta> = {
  fpa:        { label: 'FP&A',       color: 'emerald',  icon: 'TrendingUp' },
  analytics:  { label: 'Analyze',    color: 'blue',     icon: 'BarChart3' },
  scenario:   { label: 'Scenario',   color: 'amber',    icon: 'GitBranch' },
  driver:     { label: 'Drivers',    color: 'purple',   icon: 'Sliders' },
  capital:    { label: 'Capital',    color: 'indigo',   icon: 'Landmark' },
  macro:      { label: 'Macro',      color: 'red',      icon: 'Globe' },
  intel:      { label: 'Intel',      color: 'cyan',     icon: 'Search' },
  report:     { label: 'Report',     color: 'slate',    icon: 'FileText' },
  compliance: { label: 'Comply',     color: 'rose',     icon: 'Shield' },
  data:       { label: 'Data',       color: 'zinc',     icon: 'Database' },
  comms:      { label: 'Send',       color: 'orange',   icon: 'Send' },
  funding:    { label: 'Funding',    color: 'teal',     icon: 'Banknote' },
  portfolio:  { label: 'Portfolio',  color: 'violet',   icon: 'Briefcase' },
  // V2 domains:
  modeling:   { label: 'Model',      color: 'lime',     icon: 'Cpu' },
  ops:        { label: 'Ops',        color: 'yellow',   icon: 'Settings' },
  transform:  { label: 'Transform',  color: 'sky',      icon: 'ArrowLeftRight' },
  chart:      { label: 'Chart',      color: 'pink',     icon: 'BarChart' },
  bridge:     { label: 'Bridge',     color: 'fuchsia',  icon: 'Link' },
};
