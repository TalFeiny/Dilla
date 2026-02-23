/**
 * Matrix cell formatters — single source of truth for display and parse.
 *
 * Rules (all values in full units, e.g. dollars for currency):
 * - Currency (ARR, invested, valuation, burn, cash): >= 1B → $X.XXB, >= 1M → $X.XXM,
 *   >= 1K → $X.XXK, else $X,XXX.XX (2 decimals for values < 1K).
 * - Percentage (ownership, gross margin): X.X% (1 decimal).
 * - Runway (months): integer + "m" suffix (e.g. 18m).
 * - Number (general): locale-aware with appropriate decimals.
 *
 * Multi-currency: Not supported. All values are USD; no currency_code or FX conversion.
 */

export type CellColumnType = 'currency' | 'percentage' | 'number' | 'boolean' | 'date' | 'text' | 'runway';

// --- Column format map: single source of truth for column ID → type ---

/**
 * Maps known column IDs to their display type and human-readable label.
 * Used by suggestions, formatters, and column auto-creation.
 * When a suggestion references a columnId, look it up here to know how to format
 * and what column definition to create if the column doesn't exist yet.
 */
export const COLUMN_FORMAT_MAP: Record<string, { type: CellColumnType; label: string }> = {
  // Financial
  arr:                    { type: 'currency',   label: 'ARR' },
  revenue:                { type: 'currency',   label: 'Revenue' },
  burnRate:               { type: 'currency',   label: 'Burn Rate' },
  cashInBank:             { type: 'currency',   label: 'Cash in Bank' },
  valuation:              { type: 'currency',   label: 'Valuation' },
  totalFunding:           { type: 'currency',   label: 'Total Funding' },
  investmentAmount:       { type: 'currency',   label: 'Investment Amount' },
  // Market sizing
  tamUsd:                 { type: 'currency',   label: 'TAM' },
  samUsd:                 { type: 'currency',   label: 'SAM' },
  somUsd:                 { type: 'currency',   label: 'SOM' },
  // LP / fund
  commitment:             { type: 'currency',   label: 'Commitment' },
  called:                 { type: 'currency',   label: 'Called' },
  distributed:            { type: 'currency',   label: 'Distributed' },
  unfunded:               { type: 'currency',   label: 'Unfunded' },
  capacity:               { type: 'currency',   label: 'Capacity' },
  // Percentages
  grossMargin:            { type: 'percentage', label: 'Gross Margin' },
  ownership:              { type: 'percentage', label: 'Ownership %' },
  founderOwnership:       { type: 'percentage', label: 'Founder Ownership' },
  revenueGrowthAnnual:    { type: 'percentage', label: 'Annual Revenue Growth' },
  revenueGrowthMonthly:   { type: 'percentage', label: 'Monthly Revenue Growth' },
  // Numbers
  runway:                 { type: 'runway',     label: 'Runway (mo)' },
  runwayMonths:           { type: 'runway',     label: 'Runway (mo)' },
  headcount:              { type: 'number',     label: 'Headcount' },
  optionPool:             { type: 'number',     label: 'Option Pool (bps)' },
  customerCount:          { type: 'number',     label: 'Customer Count' },
  dpi:                    { type: 'number',     label: 'DPI' },
  vintageYear:            { type: 'number',     label: 'Vintage' },
  // Text
  company:                { type: 'text',       label: 'Company' },
  sector:                 { type: 'text',       label: 'Sector' },
  latestUpdate:           { type: 'text',       label: 'Latest Update' },
  productUpdates:         { type: 'text',       label: 'Product Updates' },
  lpName:                 { type: 'text',       label: 'LP Name' },
  lpType:                 { type: 'text',       label: 'Type' },
  status:                 { type: 'text',       label: 'Status' },
  contactName:            { type: 'text',       label: 'Contact' },
  // Boolean
  coInvest:               { type: 'boolean',    label: 'Co-Invest' },
};

/**
 * Get the CellColumnType for a column ID.
 * Falls back to 'currency' for unknown numeric-looking columns, 'text' otherwise.
 */
export function getColumnType(columnId: string): CellColumnType {
  return COLUMN_FORMAT_MAP[columnId]?.type ?? 'text';
}

/**
 * Get the human-readable label for a column ID.
 */
export function getColumnLabel(columnId: string): string {
  return COLUMN_FORMAT_MAP[columnId]?.label ?? columnId;
}

/**
 * Format a suggestion value for display, using the column's known type.
 * Handles wrapped objects ({value, fair_value, displayValue, amount}), arrays, and primitives.
 */
export function formatSuggestionValue(value: unknown, columnId?: string): string {
  if (value === null || value === undefined) return 'N/A';
  // Unwrap objects: extract .value / .fair_value / .displayValue / first primitive
  if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
    const obj = value as Record<string, unknown>;
    const extracted = obj.value ?? obj.fair_value ?? obj.displayValue ?? obj.display_value ?? obj.amount;
    if (extracted !== null && extracted !== undefined) return formatSuggestionValue(extracted, columnId);
    const firstPrimitive = Object.values(obj).find(v => typeof v === 'string' || typeof v === 'number');
    if (firstPrimitive !== undefined) return formatSuggestionValue(firstPrimitive, columnId);
    return 'N/A';
  }
  if (Array.isArray(value)) return value.length ? `${value.length} items` : 'N/A';

  const type = columnId ? getColumnType(columnId) : 'currency';

  if (typeof value === 'number') {
    // Special case: optionPool uses "bps" suffix
    if (columnId === 'optionPool') return `${value.toLocaleString()} bps`;
    return formatCellValue(value, type);
  }
  if (typeof value === 'string') {
    // Try parsing as number for numeric column types
    if (type !== 'text' && type !== 'boolean' && type !== 'date') {
      const n = Number(value);
      if (!Number.isNaN(n)) return formatCellValue(n, type);
    }
    return value;
  }
  return String(value);
}

// --- Format (display) ---

/**
 * Format currency (full dollars). >= 1B → $X.XXB, >= 1M → $X.XXM, >= 1K → $X.XXK, else $X,XXX.XX.
 */
export function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  const n = Number(value);
  const abs = Math.abs(n);
  const sign = n < 0 ? '-' : '';
  if (abs >= 1_000_000_000) return `${sign}$${(abs / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(2)}K`;
  return `${sign}$${abs.toFixed(2)}`;
}

/**
 * Format percentage (store as 0–1). Display as X.X%.
 */
export function formatPercentage(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  const n = typeof value === 'number' ? value : Number(value);
  return `${(n * 100).toFixed(1)}%`;
}

/**
 * Format runway in months as integer + "m" (e.g. 18m).
 */
export function formatRunway(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  const months = Math.floor(Number(value));
  return `${months}m`;
}

/**
 * Format generic number (locale-aware).
 */
export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  return Number(value).toLocaleString('en-US');
}

/**
 * Format cell value by column type. Handles objects (e.g. API result) by extracting .value / .displayValue.
 */
export function formatCellValue(value: unknown, type: CellColumnType): string {
  if (value === null || value === undefined) return type === 'currency' ? '-' : '-';
  if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
    const obj = value as Record<string, unknown>;
    const v = obj.value ?? obj.fair_value ?? obj.displayValue ?? obj.display_value;
    if (v !== undefined && v !== null && (typeof v === 'number' || typeof v === 'string'))
      return formatCellValue(v, type);
    return '-';
  }
  if (Array.isArray(value)) return value.length ? `${value.length} items` : '-';

  switch (type) {
    case 'currency':
      return formatCurrency(Number(value));
    case 'percentage':
      return formatPercentage(Number(value));
    case 'runway':
      return formatRunway(Number(value));
    case 'number':
      return formatNumber(Number(value));
    case 'boolean':
      return value ? 'Yes' : 'No';
    case 'date':
      return value instanceof Date ? value.toLocaleDateString() : String(value);
    default:
      return String(value);
  }
}

// --- Parse (save path) ---

/**
 * Parse user input for currency: supports "2K", "$2M", "1.5B", "500", "$1,000", etc.
 * Returns numeric value in full units (e.g. 2000 for "2K").
 */
export function parseCurrencyInput(value: string | number | null | undefined): number | null {
  if (typeof value === 'number') return Number.isNaN(value) ? null : value;
  if (value === null || value === undefined) return null;
  const s = String(value).trim();
  if (!s) return null;

  let cleaned = s.replace(/[$€£¥,\s]/g, '');
  const upper = cleaned.toUpperCase();
  let multiplier = 1;

  if (upper.endsWith('B')) {
    multiplier = 1_000_000_000;
    cleaned = cleaned.slice(0, -1);
  } else if (upper.endsWith('M')) {
    multiplier = 1_000_000;
    cleaned = cleaned.slice(0, -1);
  } else if (upper.endsWith('K')) {
    multiplier = 1_000;
    cleaned = cleaned.slice(0, -1);
  }

  const num = parseFloat(cleaned);
  if (Number.isNaN(num)) return null;
  return num * multiplier;
}

/**
 * Parse cell value for save by column type (e.g. from inline edit).
 */
export function parseCellValueForSave(
  raw: unknown,
  type: CellColumnType,
  columnId?: string
): string | number | boolean | null {
  if (raw === null || raw === undefined) return null;
  const obj = raw as Record<string, unknown>;
  const primitive =
    typeof raw === 'object' && raw !== null && !Array.isArray(raw)
      ? (obj.value ?? obj.displayValue ?? obj.display_value ?? '')
      : raw;

  switch (type) {
    case 'currency': {
      const input = typeof primitive === 'string' || typeof primitive === 'number' ? primitive : String(primitive ?? '');
      return parseCurrencyInput(input);
    }
    case 'percentage': {
      const n = Number(primitive);
      if (Number.isNaN(n)) return 0;
      return n > 1 ? n / 100 : n;
    }
    case 'runway':
      return typeof primitive === 'number' ? Math.floor(primitive) : Math.floor(Number(primitive)) || 0;
    case 'number':
      return Number(primitive) || 0;
    case 'boolean':
      return primitive === true || primitive === 'true' || primitive === 1 || primitive === '1' || primitive === 'yes';
    case 'date':
      return primitive != null ? String(primitive).trim() : null;
    default:
      return primitive != null ? String(primitive).trim() : null;
  }
}
