/**
 * Dynamic CSV Field Mapping System
 * 
 * Intelligently maps CSV headers to database columns using:
 * - Fuzzy matching for different nomenclatures
 * - Synonym detection
 * - Type inference
 * - Automatic column creation for unmapped fields
 */

export interface FieldMapping {
  csvHeader: string;
  columnId: string;
  columnName: string;
  dbField?: string; // Database field name if it maps to a known company field
  type: 'text' | 'number' | 'currency' | 'percentage' | 'date' | 'boolean';
  confidence: number; // 0-1, how confident we are in this mapping
  isNewColumn: boolean; // Whether this is a new column we're creating
}

export interface ColumnDefinition {
  id: string;
  name: string;
  type: 'text' | 'number' | 'currency' | 'percentage' | 'date' | 'boolean';
  width?: number;
  editable?: boolean;
  formula?: string;
}

/**
 * Database field mappings with multiple synonyms
 */
const DB_FIELD_SYNONYMS: Record<string, string[]> = {
  // Company name
  name: ['name', 'company', 'company name', 'company_name', 'companyname', 'firm', 'organization'],
  
  // Financial metrics
  current_arr_usd: [
    'arr', 'annual recurring revenue', 'annual_recurring_revenue', 'recurring revenue',
    'recurring_revenue', 'mrr', 'monthly recurring revenue', 'monthly_recurring_revenue',
    'revenue', 'annual revenue', 'annual_revenue', 'total revenue', 'total_revenue'
  ],
  total_invested_usd: [
    'investment', 'invested', 'total invested', 'total_invested', 'investment amount',
    'investment_amount', 'capital invested', 'capital_invested', 'check size', 'check_size',
    'investment size', 'investment_size', 'amount invested', 'amount_invested'
  ],
  current_valuation_usd: [
    'valuation', 'company valuation', 'company_valuation', 'post money', 'post_money',
    'post-money valuation', 'post_money_valuation', 'enterprise value', 'enterprise_value',
    'ev', 'market cap', 'market_cap', 'market capitalization', 'market_capitalization'
  ],
  burn_rate_monthly_usd: [
    'burn rate', 'burn_rate', 'monthly burn', 'monthly_burn', 'cash burn', 'cash_burn',
    'burn', 'monthly burn rate', 'monthly_burn_rate', 'runway burn', 'runway_burn'
  ],
  runway_months: [
    'runway', 'runway months', 'runway_months', 'months runway', 'months_runway',
    'cash runway', 'cash_runway', 'months of runway', 'months_of_runway'
  ],
  cash_in_bank_usd: [
    'cash', 'cash in bank', 'cash_in_bank', 'bank balance', 'bank_balance',
    'cash balance', 'cash_balance', 'available cash', 'available_cash', 'liquidity'
  ],
  gross_margin: [
    'gross margin', 'gross_margin', 'gm', 'gross margin %', 'gross_margin_percent',
    'gross margin percentage', 'gross_margin_percentage', 'margin', 'gross profit margin'
  ],
  ownership_percentage: [
    'ownership', 'ownership %', 'ownership_percent', 'ownership percentage',
    'ownership_percentage', 'stake', 'equity stake', 'equity_stake', '% ownership',
    'percent ownership', 'percent_ownership', 'equity %', 'equity_percent'
  ],
  
  // Company attributes
  sector: [
    'sector', 'industry', 'vertical', 'category', 'business sector', 'business_sector',
    'industry sector', 'industry_sector', 'market', 'market segment', 'market_segment'
  ],
  stage: [
    'stage', 'investment stage', 'investment_stage', 'round', 'funding round',
    'funding_round', 'round stage', 'round_stage', 'company stage', 'company_stage'
  ],
  first_investment_date: [
    'first investment', 'first_investment', 'investment date', 'investment_date',
    'date invested', 'date_invested', 'first investment date', 'first_investment_date',
    'initial investment date', 'initial_investment_date', 'entry date', 'entry_date'
  ],
  investment_lead: [
    'lead', 'investment lead', 'investment_lead', 'deal lead', 'deal_lead',
    'partner', 'investment partner', 'investment_partner', 'sponsor', 'deal sponsor'
  ],
  last_contacted_date: [
    'last contacted', 'last_contacted', 'last contact', 'last_contact',
    'last contacted date', 'last_contacted_date', 'contact date', 'contact_date'
  ],

  // extra_data keys (companies.extra_data JSONB — no new columns)
  option_pool_bps: [
    'option pool', 'option_pool', 'option pool bps', 'option_pool_bps',
    'esop', 'option pool %', 'option pool basis points'
  ],
  latest_update: [
    'latest update', 'latest_update', 'last update', 'last_update',
    'update', 'business update', 'achievement', 'achievements'
  ],
  latest_update_date: [
    'latest update date', 'latest_update_date', 'last update date', 'last_updated'
  ],
  product_updates: [
    'product updates', 'product_updates', 'product update', 'product news',
    'releases', 'launches'
  ],
};

/** extra_data keys → canonical matrix column id (so cells API and scripts use same ids) */
const EXTRA_DATA_COLUMN_IDS: Record<string, string> = {
  option_pool_bps: 'optionPool',
  latest_update: 'latestUpdate',
  latest_update_date: 'latestUpdateDate',
  product_updates: 'productUpdates',
};

/**
 * Type inference patterns
 */
const TYPE_PATTERNS: Array<{ pattern: RegExp; type: FieldMapping['type'] }> = [
  // Currency patterns
  { pattern: /^(arr|revenue|investment|invested|valuation|cash|burn|amount|price|cost|funding|capital|check size)/i, type: 'currency' },
  { pattern: /(usd|dollar|currency|price|cost|amount|investment|valuation|cash|burn)/i, type: 'currency' },
  
  // Percentage patterns
  { pattern: /(margin|ownership|stake|equity|percent|percentage|%|ratio|rate)/i, type: 'percentage' },
  
  // Number patterns
  { pattern: /(runway|months|count|number|employees|headcount|customers|users|deals|rounds)/i, type: 'number' },
  
  // Date patterns
  { pattern: /(date|when|time|created|updated|contacted|investment date|founded)/i, type: 'date' },
  
  // Boolean patterns
  { pattern: /(is|has|active|status|flag|enabled|disabled|live)/i, type: 'boolean' },
];

/**
 * Calculate similarity between two strings (Levenshtein-based)
 */
function stringSimilarity(str1: string, str2: string): number {
  const longer = str1.length > str2.length ? str1 : str2;
  const shorter = str1.length > str2.length ? str2 : str1;
  
  if (longer.length === 0) return 1.0;
  
  const distance = levenshteinDistance(longer.toLowerCase(), shorter.toLowerCase());
  return (longer.length - distance) / longer.length;
}

/**
 * Calculate Levenshtein distance between two strings
 */
function levenshteinDistance(str1: string, str2: string): number {
  const matrix: number[][] = [];
  
  for (let i = 0; i <= str2.length; i++) {
    matrix[i] = [i];
  }
  
  for (let j = 0; j <= str1.length; j++) {
    matrix[0][j] = j;
  }
  
  for (let i = 1; i <= str2.length; i++) {
    for (let j = 1; j <= str1.length; j++) {
      if (str2.charAt(i - 1) === str1.charAt(j - 1)) {
        matrix[i][j] = matrix[i - 1][j - 1];
      } else {
        matrix[i][j] = Math.min(
          matrix[i - 1][j - 1] + 1, // substitution
          matrix[i][j - 1] + 1,     // insertion
          matrix[i - 1][j] + 1      // deletion
        );
      }
    }
  }
  
  return matrix[str2.length][str1.length];
}

/**
 * Infer column type from header name
 */
function inferColumnType(header: string): FieldMapping['type'] {
  const normalized = header.toLowerCase().trim();
  
  for (const { pattern, type } of TYPE_PATTERNS) {
    if (pattern.test(normalized)) {
      return type;
    }
  }
  
  return 'text'; // Default to text
}

/**
 * Find best matching database field for a CSV header
 */
function findBestDbFieldMatch(csvHeader: string): { dbField: string; confidence: number } | null {
  const normalized = csvHeader.toLowerCase().trim();
  let bestMatch: { dbField: string; confidence: number } | null = null;
  
  for (const [dbField, synonyms] of Object.entries(DB_FIELD_SYNONYMS)) {
    // Check exact match first
    if (synonyms.some(s => s === normalized)) {
      return { dbField, confidence: 1.0 };
    }
    
    // Check if header contains any synonym
    const containsMatch = synonyms.some(synonym => {
      const regex = new RegExp(`\\b${synonym.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i');
      return regex.test(normalized);
    });
    
    if (containsMatch) {
      return { dbField, confidence: 0.9 };
    }
    
    // Calculate similarity with each synonym
    for (const synonym of synonyms) {
      const similarity = stringSimilarity(normalized, synonym);
      if (similarity > 0.7 && (!bestMatch || similarity > bestMatch.confidence)) {
        bestMatch = { dbField, confidence: similarity };
      }
    }
  }
  
  return bestMatch;
}

/**
 * Generate column ID from header name
 */
function generateColumnId(header: string): string {
  return `col-${header
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')}`;
}

/**
 * Map CSV headers to database columns and create new columns as needed
 * 
 * @param csvHeaders Array of CSV header names
 * @param existingColumns Existing matrix columns
 * @returns Array of field mappings
 */
export function mapCsvHeadersToColumns(
  csvHeaders: string[],
  existingColumns: ColumnDefinition[]
): FieldMapping[] {
  const mappings: FieldMapping[] = [];
  const usedColumnIds = new Set<string>();
  
  // First pass: Try to match to existing columns
  for (const csvHeader of csvHeaders) {
    const normalized = csvHeader.toLowerCase().trim();
    
    // Try exact match first (case-insensitive)
    let matched = existingColumns.find(
      col => col.name.toLowerCase().trim() === normalized
    );
    
    // Try fuzzy match if no exact match
    if (!matched) {
      let bestSimilarity = 0;
      for (const col of existingColumns) {
        const similarity = stringSimilarity(normalized, col.name.toLowerCase().trim());
        if (similarity > 0.8 && similarity > bestSimilarity) {
          bestSimilarity = similarity;
          matched = col;
        }
      }
    }
    
    if (matched && !usedColumnIds.has(matched.id)) {
      // Found existing column match
      const dbFieldMatch = findBestDbFieldMatch(csvHeader);
      mappings.push({
        csvHeader,
        columnId: matched.id,
        columnName: matched.name,
        dbField: dbFieldMatch?.dbField,
        type: matched.type,
        confidence: dbFieldMatch ? dbFieldMatch.confidence : 0.7,
        isNewColumn: false,
      });
      usedColumnIds.add(matched.id);
    } else {
      // Need to create new column
      const dbFieldMatch = findBestDbFieldMatch(csvHeader);
      const inferredType = inferColumnType(csvHeader);
      const columnId = dbFieldMatch?.dbField && EXTRA_DATA_COLUMN_IDS[dbFieldMatch.dbField]
        ? EXTRA_DATA_COLUMN_IDS[dbFieldMatch.dbField]
        : generateColumnId(csvHeader);

      mappings.push({
        csvHeader,
        columnId,
        columnName: csvHeader.trim(),
        dbField: dbFieldMatch?.dbField,
        type: inferredType,
        confidence: dbFieldMatch ? dbFieldMatch.confidence * 0.8 : 0.5,
        isNewColumn: true,
      });
    }
  }
  
  return mappings;
}

/**
 * Get database field name for a mapped field
 */
export function getDbFieldName(columnId: string, mappings: FieldMapping[]): string | undefined {
  const mapping = mappings.find(m => m.columnId === columnId);
  return mapping?.dbField;
}

/**
 * Create column definitions from mappings
 */
export function createColumnDefinitions(mappings: FieldMapping[]): ColumnDefinition[] {
  return mappings
    .filter(m => m.isNewColumn)
    .map(m => ({
      id: m.columnId,
      name: m.columnName,
      type: m.type,
      width: m.type === 'currency' || m.type === 'number' ? 150 : 120,
      editable: true,
    }));
}

/**
 * Map CSV value to appropriate type based on column mapping
 */
export function mapCsvValue(
  rawValue: string,
  mapping: FieldMapping
): { value: any; error?: string } {
  if (!rawValue || rawValue.trim() === '') {
    return { value: null };
  }
  
  const trimmed = rawValue.trim();
  
  try {
    switch (mapping.type) {
      case 'currency':
      case 'number': {
        // Remove currency symbols and whitespace
        let cleaned = trimmed.replace(/[$€£¥,\s]/g, '');
        
        // Handle suffixes (M/K/B)
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
        if (isNaN(num)) {
          return { value: null, error: `Invalid ${mapping.type} format: ${trimmed}` };
        }
        
        return { value: num * multiplier };
      }
      
      case 'percentage': {
        const cleaned = trimmed.replace(/[%,]/g, '');
        const num = parseFloat(cleaned);
        if (isNaN(num)) {
          return { value: null, error: `Invalid percentage format: ${trimmed}` };
        }
        // Normalize to 0-1 range
        return { value: num > 1 ? num / 100 : num };
      }
      
      case 'boolean': {
        const lower = trimmed.toLowerCase();
        return {
          value: lower === 'true' || lower === '1' || lower === 'yes' || lower === 'y',
        };
      }
      
      case 'date': {
        // Try multiple date formats
        const dateFormats = [
          /^\d{4}-\d{2}-\d{2}$/, // YYYY-MM-DD
          /^\d{2}\/\d{2}\/\d{4}$/, // MM/DD/YYYY
          /^\d{2}-\d{2}-\d{4}$/, // MM-DD-YYYY
          /^Q\d\s+\d{4}$/i, // Q1 2024
        ];
        
        let parsedDate: Date | null = null;
        
        // Try ISO format first
        parsedDate = new Date(trimmed);
        if (!isNaN(parsedDate.getTime())) {
          return { value: parsedDate.toISOString().split('T')[0] };
        }
        
        // Try parsing as-is
        for (const format of dateFormats) {
          if (format.test(trimmed)) {
            parsedDate = new Date(trimmed);
            if (!isNaN(parsedDate.getTime())) {
              return { value: parsedDate.toISOString().split('T')[0] };
            }
          }
        }
        
        return { value: trimmed, error: `Could not parse date: ${trimmed}` };
      }
      
      default:
        return { value: trimmed };
    }
  } catch (error) {
    return {
      value: trimmed,
      error: error instanceof Error ? error.message : 'Unknown parsing error',
    };
  }
}
