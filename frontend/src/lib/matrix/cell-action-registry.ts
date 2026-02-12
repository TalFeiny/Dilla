/**
 * Cell Action Registry Client
 * 
 * Type-safe client for querying and executing cell actions from the backend registry.
 * Handles different output formats from various services.
 */

export type MatrixMode = 'portfolio' | 'query' | 'custom' | 'lp';
export type ActionCategory = 'formula' | 'workflow' | 'document';
export type OutputType = 'number' | 'string' | 'array' | 'time_series' | 'chart' | 'object' | 'boolean';
export type ExecutionType = 'formula' | 'workflow' | 'document';

export interface CellAction {
  action_id: string;
  name: string;
  description?: string;
  category: ActionCategory;
  service_name: string;
  execution_type: ExecutionType;
  required_inputs: Record<string, any>;
  output_type: OutputType;
  mode_availability: MatrixMode[];
  column_compatibility: string[];
  config?: Record<string, any>;
}

export interface ActionExecutionRequest {
  action_id: string;
  row_id: string;
  column_id: string;
  inputs: Record<string, any>;
  mode?: MatrixMode;
  fund_id?: string;
  company_id?: string;
}

export interface ActionExecutionResponse {
  success: boolean;
  action_id: string;
  value: any;
  display_value: string;
  metadata: {
    method?: string;
    explanation?: string;
    reasoning?: string;
    confidence?: number;
    raw_output?: any;
    output_type?: string;
    time_series?: any[];
    chart_config?: any;
    citations?: { id?: string; source?: string; url?: string; title?: string }[];
    // Custom array output structure
    output_structure?: string;
    structured_array?: any[];
    array_length?: number;
    /** Multi-column: new columns to add to matrix. Frontend creates them. */
    columns_to_create?: {
      id: string;
      name: string;
      type?: string;
      values?: Record<string, number | string>;
    }[];
    /** Multi-column: optional chart to attach to trigger cell (chart_config). */
    chart_to_create?: Record<string, unknown>;
    documents?: unknown;
  };
  error?: string;
}

export interface AvailableActionsResponse {
  success: boolean;
  actions: CellAction[];
  count: number;
}

/**
 * Get available cell actions filtered by mode, category, and column
 */
export async function getAvailableActions(
  mode: MatrixMode = 'portfolio',
  category?: ActionCategory,
  columnId?: string,
  columnType?: string
): Promise<CellAction[]> {
  const params = new URLSearchParams({
    mode,
  });
  
  if (category) params.append('category', category);
  if (columnId) params.append('column_id', columnId);
  if (columnType) params.append('column_type', columnType);
  
  const response = await fetch(`/api/cell-actions/actions?${params.toString()}`);
  
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.error ?? err.detail ?? 'Failed to fetch available actions');
  }
  
  const data: AvailableActionsResponse = await response.json();
  return data.actions;
}

/**
 * Get specific action by ID
 */
export async function getAction(actionId: string): Promise<CellAction> {
  const response = await fetch(`/api/cell-actions/actions/${actionId}`);
  
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.error ?? err.detail ?? `Action ${actionId} not found`);
  }
  
  const data = await response.json();
  return data.action;
}

/**
 * Execute a cell action
 */
export async function executeAction(
  request: ActionExecutionRequest
): Promise<ActionExecutionResponse> {
  const traceId = typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `tr-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
  const body = { ...request, trace_id: traceId };
  if (typeof window !== 'undefined') {
    console.log('[cell-action] traceId=%s action=%s POST', traceId, request.action_id);
  }
  const response = await fetch(
    `/api/cell-actions/actions/${request.action_id}/execute`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    }
  );
  
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.error ?? err.detail ?? 'Action execution failed');
  }
  
  return await response.json();
}

/**
 * Get actions grouped by category
 */
export async function getActionsByCategory(
  mode: MatrixMode = 'portfolio',
  columnType?: string
): Promise<Record<ActionCategory, CellAction[]>> {
  const actions = await getAvailableActions(mode, undefined, undefined, columnType);
  
  const grouped: Record<ActionCategory, CellAction[]> = {
    formula: [],
    workflow: [],
    document: [],
  };
  
  actions.forEach(action => {
    grouped[action.category].push(action);
  });
  
  return grouped;
}

/**
 * Get actions for a specific service
 */
export async function getActionsByService(
  serviceName: string,
  mode: MatrixMode = 'portfolio'
): Promise<CellAction[]> {
  const actions = await getAvailableActions(mode);
  return actions.filter(action => action.service_name === serviceName);
}

/**
 * Check if an action is compatible with a column type
 */
export function isActionCompatible(
  action: CellAction,
  columnType: string
): boolean {
  if (!action.column_compatibility || action.column_compatibility.length === 0) {
    return true; // No restrictions
  }
  
  return action.column_compatibility.includes(columnType);
}

/**
 * Format action output for display based on output type
 */
export function formatActionOutput(
  response: ActionExecutionResponse,
  columnType?: string
): string {
  const { value, display_value, metadata } = response;
  
  // Use display_value if available
  if (display_value) {
    return display_value;
  }
  
  // Format based on output type
  const outputType = metadata.output_type || 'number';
  
  switch (outputType) {
    case 'number':
      if (typeof value === 'number') {
        // Format based on column type
        if (columnType === 'currency') {
          return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 0,
            maximumFractionDigits: 0,
          }).format(value);
        } else if (columnType === 'percentage') {
          return `${(value * 100).toFixed(2)}%`;
        } else {
          return value.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          });
        }
      }
      return String(value);
    
    case 'string':
      return String(value);
    
    case 'time_series':
      if (metadata.time_series && Array.isArray(metadata.time_series)) {
        const last = metadata.time_series[metadata.time_series.length - 1];
        if (last && typeof last === 'object') {
          return String(last.revenue || last.value || last.nav || value);
        }
      }
      return String(value);
    
    case 'chart':
      if (metadata.chart_config) {
        return `${metadata.chart_config.type || 'chart'}: ${metadata.chart_config.title || 'Chart'}`;
      }
      return String(value);
    
    case 'array':
      // Handle custom structured arrays
      if (metadata.structured_array && Array.isArray(metadata.structured_array)) {
        const structure = metadata.output_structure || 'default_array';
        const count = metadata.array_length || metadata.structured_array.length;
        
        // Format based on structure type
        if (structure.includes('company_data')) {
          return `${count} company${count !== 1 ? 'ies' : ''} fetched`;
        } else if (structure.includes('funding_rounds')) {
          return `${count} funding round${count !== 1 ? 's' : ''}`;
        } else if (structure.includes('competitors')) {
          return `${count} competitor${count !== 1 ? 's' : ''} found`;
        } else if (structure.includes('valuation')) {
          return `${count} valuation${count !== 1 ? 's' : ''} calculated`;
        } else if (structure.includes('scenario')) {
          return `${count} scenario${count !== 1 ? 's' : ''} analyzed`;
        } else if (structure.includes('deck_slides')) {
          return `${count} slide${count !== 1 ? 's' : ''} generated`;
        } else if (structure.includes('memo_sections')) {
          return `${count} section${count !== 1 ? 's' : ''} generated`;
        } else if (structure.includes('cap_table')) {
          return `${count} shareholder${count !== 1 ? 's' : ''} in cap table`;
        } else {
          return `${count} item${count !== 1 ? 's' : ''}`;
        }
      }
      // Fallback for regular arrays
      if (Array.isArray(value)) {
        return `${value.length} item${value.length !== 1 ? 's' : ''}`;
      }
      return String(value);
    
    case 'object':
      if (metadata.method) {
        return `${metadata.method}${metadata.explanation ? ` (${metadata.explanation})` : ''}`;
      }
      return String(value);
    
    default:
      return String(value);
  }
}

/**
 * Extract cell value from action response
 */
export function extractCellValue(response: ActionExecutionResponse): any {
  return response.value;
}

/**
 * Get structured array data from action response
 * Returns the structured array if available, otherwise returns the raw value
 * Uses existing service-transformer helpers when converting to matrix rows
 */
export function getStructuredArray(response: ActionExecutionResponse): any[] | null {
  const { metadata } = response;
  
  if (metadata.structured_array && Array.isArray(metadata.structured_array)) {
    return metadata.structured_array;
  }
  
  // Fallback: try to extract array from raw_output
  if (metadata.raw_output) {
    if (Array.isArray(metadata.raw_output)) {
      return metadata.raw_output;
    }
    if (typeof metadata.raw_output === 'object') {
      // Try common array keys
      const arrayKeys = ['comparables', 'companies', 'rounds', 'scenarios', 'results', 'data'];
      for (const key of arrayKeys) {
        if (Array.isArray(metadata.raw_output[key])) {
          return metadata.raw_output[key];
        }
      }
    }
  }
  
  // Fallback: check if value itself is an array
  if (Array.isArray(response.value)) {
    return response.value;
  }
  
  return null;
}

/**
 * Get output structure type from action response
 */
export function getOutputStructure(response: ActionExecutionResponse): string | null {
  return response.metadata.output_structure || null;
}

/**
 * Convert action response to ServiceOutput format for use with transformServiceOutput helper
 * This integrates structured arrays with the existing service-transformer.ts helpers
 */
export function actionResponseToServiceOutput(
  response: ActionExecutionResponse
): import('./service-transformer').ServiceOutput {
  const { metadata, value } = response;
  
  // Prefer structured_array if available
  const arrayData = getStructuredArray(response);
  
  if (arrayData && Array.isArray(arrayData) && arrayData.length > 0) {
    return {
      type: 'array',
      data: arrayData,
      metadata: {
        service: response.action_id,
        output_structure: metadata.output_structure,
      },
    };
  }
  
  // Check output type
  const outputType = metadata.output_type || 'object';
  
  if (outputType === 'array' || Array.isArray(value)) {
    return {
      type: 'array',
      data: Array.isArray(value) ? value : [],
      metadata: {
        service: response.action_id,
        output_structure: metadata.output_structure,
      },
    };
  }
  
  if (outputType === 'object' || (typeof value === 'object' && value !== null && !Array.isArray(value))) {
    return {
      type: 'object',
      data: value,
      metadata: {
        service: response.action_id,
      },
    };
  }
  
  // Scalar value
  return {
    type: 'scalar',
    data: value,
    metadata: {
      service: response.action_id,
    },
  };
}

/**
 * Extract explanation/method for explanation column
 */
export function extractExplanation(response: ActionExecutionResponse): string {
  const { metadata } = response;
  
  if (metadata.method && metadata.explanation) {
    return `${metadata.method}: ${metadata.explanation}`;
  } else if (metadata.method) {
    return metadata.method;
  } else if (metadata.explanation) {
    return metadata.explanation;
  }
  
  return '';
}
