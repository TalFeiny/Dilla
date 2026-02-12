/**
 * Service Output Transformer
 * 
 * Transforms service outputs (arrays, objects, different JSON schemas) into matrix rows.
 * Handles flexible field mapping and automatic schema detection.
 */

import { MatrixRow, MatrixCell, MatrixColumn } from '@/components/matrix/UnifiedMatrix';

export interface ServiceOutput {
  type: 'array' | 'object' | 'scalar';
  data: any;
  schema?: JSONSchema;
  metadata?: {
    service?: string;
    timestamp?: string;
    confidence?: number;
    output_structure?: string;
  };
}

export interface JSONSchema {
  type?: string;
  properties?: Record<string, { type?: string; format?: string }>;
  items?: JSONSchema;
  required?: string[];
}

export interface FieldMapping {
  sourceField: string;
  targetColumn: string;
  transform?: (value: any) => any;
}

/**
 * Transform service output into matrix rows
 */
export function transformServiceOutput(
  output: ServiceOutput,
  targetColumns: MatrixColumn[],
  fieldMappings?: FieldMapping[]
): MatrixRow[] {
  const { type, data } = output;

  switch (type) {
    case 'array':
      return transformArray(data, targetColumns, fieldMappings);
    
    case 'object':
      return [transformObject(data, targetColumns, fieldMappings)];
    
    case 'scalar':
      return [transformScalar(data, targetColumns)];
    
    default:
      throw new Error(`Unsupported output type: ${type}`);
  }
}

/**
 * Transform array of objects into multiple matrix rows
 */
function transformArray(
  array: any[],
  targetColumns: MatrixColumn[],
  fieldMappings?: FieldMapping[]
): MatrixRow[] {
  if (!Array.isArray(array)) {
    throw new Error('Expected array but got: ' + typeof array);
  }

  return array.map((item, index) => {
    const rowId = `service-row-${Date.now()}-${index}`;
    const cells: Record<string, MatrixCell> = {};

    targetColumns.forEach((column) => {
      const mapping = fieldMappings?.find(m => m.targetColumn === column.id);
      const sourceField = mapping?.sourceField || column.id;
      
      let value = getNestedValue(item, sourceField);
      
      if (mapping?.transform) {
        value = mapping.transform(value);
      }
      
      // Apply column type formatting
      value = formatValueForColumn(value, column);

      cells[column.id] = {
        value,
        source: 'api',
        lastUpdated: new Date().toISOString(),
      };
    });

    return {
      id: rowId,
      cells,
    };
  });
}

/**
 * Transform single object into one matrix row
 */
function transformObject(
  obj: any,
  targetColumns: MatrixColumn[],
  fieldMappings?: FieldMapping[]
): MatrixRow {
  if (typeof obj !== 'object' || obj === null || Array.isArray(obj)) {
    throw new Error('Expected object but got: ' + typeof obj);
  }

  const rowId = `service-row-${Date.now()}`;
  const cells: Record<string, MatrixCell> = {};

  targetColumns.forEach((column) => {
    const mapping = fieldMappings?.find(m => m.targetColumn === column.id);
    const sourceField = mapping?.sourceField || column.id;
    
    let value = getNestedValue(obj, sourceField);
    
    if (mapping?.transform) {
      value = mapping.transform(value);
    }
    
    // Apply column type formatting
    value = formatValueForColumn(value, column);

    cells[column.id] = {
      value,
      source: 'api',
      lastUpdated: new Date().toISOString(),
    };
  });

  return {
    id: rowId,
    cells,
  };
}

/**
 * Transform scalar value into single cell row
 */
function transformScalar(
  value: any,
  targetColumns: MatrixColumn[]
): MatrixRow {
  const rowId = `service-row-${Date.now()}`;
  const cells: Record<string, MatrixCell> = {};

  // Put scalar value in first column
  if (targetColumns.length > 0) {
    const firstColumn = targetColumns[0];
    cells[firstColumn.id] = {
      value: formatValueForColumn(value, firstColumn),
      source: 'api',
      lastUpdated: new Date().toISOString(),
    };
  }

  // Fill remaining columns with empty values
  targetColumns.slice(1).forEach((column) => {
    cells[column.id] = {
      value: null,
      source: 'api',
      lastUpdated: new Date().toISOString(),
    };
  });

  return {
    id: rowId,
    cells,
  };
}

/**
 * Get nested value from object using dot notation
 */
function getNestedValue(obj: any, path: string): any {
  if (!path) return undefined;
  
  const parts = path.split('.');
  let current = obj;
  
  for (const part of parts) {
    if (current === null || current === undefined) {
      return undefined;
    }
    current = current[part];
  }
  
  return current;
}

/**
 * Format value according to column type
 */
function formatValueForColumn(value: any, column: MatrixColumn): any {
  if (value === null || value === undefined) {
    return null;
  }

  switch (column.type) {
    case 'number':
    case 'currency':
      return typeof value === 'number' ? value : parseFloat(String(value)) || 0;
    
    case 'percentage':
      if (typeof value === 'number') {
        return value > 1 ? value / 100 : value; // Convert 50 to 0.5 if needed
      }
      return parseFloat(String(value)) || 0;
    
    case 'date':
      if (value instanceof Date) return value;
      if (typeof value === 'string') {
        const date = new Date(value);
        return isNaN(date.getTime()) ? null : date;
      }
      return null;
    
    case 'boolean':
      if (typeof value === 'boolean') return value;
      if (typeof value === 'string') {
        return value.toLowerCase() === 'true' || value === '1' || value === 'yes';
      }
      return Boolean(value);
    
    case 'text':
    default:
      return String(value);
  }
}

/**
 * Auto-detect schema from service output
 */
export function detectSchema(data: any): JSONSchema {
  if (Array.isArray(data)) {
    if (data.length === 0) {
      return { type: 'array', items: { type: 'object' } };
    }
    
    const firstItem = data[0];
    if (typeof firstItem === 'object' && firstItem !== null) {
      return {
        type: 'array',
        items: {
          type: 'object',
          properties: inferProperties(firstItem),
        },
      };
    }
    
    return {
      type: 'array',
      items: { type: typeof firstItem },
    };
  }
  
  if (typeof data === 'object' && data !== null) {
    return {
      type: 'object',
      properties: inferProperties(data),
    };
  }
  
  return {
    type: typeof data,
  };
}

/**
 * Infer properties from object
 */
type InferredSchemaType = 'string' | 'number' | 'boolean' | 'object' | 'null' | 'array';

function inferProperties(obj: any): Record<string, { type?: string; format?: string }> {
  const properties: Record<string, { type?: string; format?: string }> = {};
  
  for (const [key, value] of Object.entries(obj)) {
    let type: InferredSchemaType = typeof value as InferredSchemaType;
    let format: string | undefined;
    
    if (value === null) {
      type = 'null';
    } else if (Array.isArray(value)) {
      type = 'array';
    } else if (value instanceof Date) {
      type = 'string';
      format = 'date-time';
    } else if (typeof value === 'number') {
      // Check if it looks like a date (timestamp)
      if (value > 1000000000000 && value < 9999999999999) {
        type = 'string';
        format = 'date-time';
      }
    }
    
    properties[key] = { type: type as string, format };
  }
  
  return properties;
}

/**
 * Suggest field mappings from schema to columns
 */
export function suggestFieldMappings(
  schema: JSONSchema,
  targetColumns: MatrixColumn[]
): FieldMapping[] {
  const mappings: FieldMapping[] = [];
  
  if (!schema.properties) {
    return mappings;
  }
  
  const sourceFields = Object.keys(schema.properties);
  
  targetColumns.forEach((column) => {
    // Try exact match first
    if (sourceFields.includes(column.id)) {
      mappings.push({
        sourceField: column.id,
        targetColumn: column.id,
      });
      return;
    }
    
    // Try case-insensitive match
    const caseInsensitiveMatch = sourceFields.find(
      field => field.toLowerCase() === column.id.toLowerCase()
    );
    if (caseInsensitiveMatch) {
      mappings.push({
        sourceField: caseInsensitiveMatch,
        targetColumn: column.id,
      });
      return;
    }
    
    // Try partial match (e.g., "company_name" matches "company")
    const partialMatch = sourceFields.find(
      field => field.toLowerCase().includes(column.id.toLowerCase()) ||
                column.id.toLowerCase().includes(field.toLowerCase())
    );
    if (partialMatch) {
      mappings.push({
        sourceField: partialMatch,
        targetColumn: column.id,
      });
      return;
    }
  });
  
  return mappings;
}

/**
 * Common transform functions
 */
export const TransformFunctions = {
  /**
   * Convert percentage string to number (e.g., "50%" -> 0.5)
   */
  percentageToDecimal: (value: any): number => {
    if (typeof value === 'string') {
      const cleaned = value.replace('%', '').trim();
      const num = parseFloat(cleaned);
      return isNaN(num) ? 0 : num / 100;
    }
    return typeof value === 'number' ? (value > 1 ? value / 100 : value) : 0;
  },
  
  /**
   * Convert currency string to number (e.g., "$1,000" -> 1000)
   */
  currencyToNumber: (value: any): number => {
    if (typeof value === 'string') {
      const cleaned = value.replace(/[$,]/g, '').trim();
      return parseFloat(cleaned) || 0;
    }
    return typeof value === 'number' ? value : 0;
  },
  
  /**
   * Extract year from date
   */
  extractYear: (value: any): number => {
    const date = value instanceof Date ? value : new Date(value);
    return isNaN(date.getTime()) ? new Date().getFullYear() : date.getFullYear();
  },
  
  /**
   * Format date to ISO string
   */
  toISOString: (value: any): string => {
    const date = value instanceof Date ? value : new Date(value);
    return isNaN(date.getTime()) ? '' : date.toISOString().split('T')[0];
  },
  
  /**
   * Round to 2 decimal places
   */
  round2: (value: any): number => {
    const num = typeof value === 'number' ? value : parseFloat(String(value)) || 0;
    return Math.round(num * 100) / 100;
  },
};
