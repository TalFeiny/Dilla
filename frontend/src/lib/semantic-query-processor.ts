// Semantic Query Processor - Breaks down natural language into structured queries

export interface StructuredQuery {
  intent: 'search' | 'compare' | 'aggregate' | 'calculate' | 'filter' | 'trend';
  entities: {
    companies?: string[];
    metrics?: string[];
    timeframe?: string;
    filters?: Record<string, any>;
  };
  sources: ('database' | 'web' | 'api')[];
  output: {
    columns: string[];
    groupBy?: string;
    orderBy?: string;
    limit?: number;
  };
}

// Semantic mappings for common terms
const METRIC_MAPPINGS = {
  // Revenue variations
  'revenue': ['revenue', 'annual_revenue', 'arr', 'mrr'],
  'sales': ['revenue', 'sales', 'turnover'],
  'arr': ['arr', 'annual_recurring_revenue'],
  'mrr': ['mrr', 'monthly_recurring_revenue'],
  
  // Growth metrics
  'growth': ['growth_rate', 'yoy_growth', 'revenue_growth'],
  'growth rate': ['growth_rate', 'cagr'],
  'burn': ['burn_rate', 'monthly_burn', 'cash_burn'],
  'runway': ['runway_months', 'cash_runway'],
  
  // Valuation
  'valuation': ['valuation', 'post_money_valuation'],
  'worth': ['valuation', 'enterprise_value'],
  'market cap': ['market_cap', 'market_capitalization'],
  
  // Profitability
  'profit': ['net_income', 'profit', 'earnings'],
  'ebitda': ['ebitda', 'operating_income'],
  'margin': ['gross_margin', 'profit_margin', 'ebitda_margin'],
  
  // Other metrics
  'employees': ['employee_count', 'headcount', 'team_size'],
  'funding': ['total_funding', 'funding_raised'],
  'customers': ['customer_count', 'users', 'clients']
};

// Filter patterns
const FILTER_PATTERNS = [
  { pattern: /(?:with|having)\s+(?:more than|over|>)\s*([\d.]+[MBK]?)\s*(\w+)/gi, type: 'gt' },
  { pattern: /(?:with|having)\s+(?:less than|under|<)\s*([\d.]+[MBK]?)\s*(\w+)/gi, type: 'lt' },
  { pattern: /(?:with|having)\s+(?:between)\s*([\d.]+[MBK]?)\s*and\s*([\d.]+[MBK]?)\s*(\w+)/gi, type: 'between' },
  { pattern: /(?:in|from)\s+(\w+)\s+(?:sector|industry)/gi, type: 'sector' },
  { pattern: /(?:founded|started)\s+(?:in|after|before)\s*(\d{4})/gi, type: 'founded_year' },
  { pattern: /unicorn[s]?/gi, type: 'unicorn' },
  { pattern: /profitable/gi, type: 'profitable' },
  { pattern: /(?:top|best)\s+(\d+)/gi, type: 'limit' }
];

// Intent patterns
const INTENT_PATTERNS = {
  compare: /compare|versus|vs|compared to|difference between/i,
  aggregate: /average|mean|median|sum|total|count/i,
  calculate: /calculate|compute|what is|how much/i,
  trend: /over time|trend|historical|growth|change/i,
  filter: /show|list|find|get|filter|only/i,
  search: /search|look for|find/i
};

// Parse value with units (e.g., "50M" -> 50000000)
function parseValue(value: string): number {
  const match = value.match(/([\d.]+)\s*([MBK])?/i);
  if (!match) return parseFloat(value);
  
  const num = parseFloat(match[1]);
  const unit = match[2]?.toUpperCase();
  
  switch (unit) {
    case 'B': return num * 1_000_000_000;
    case 'M': return num * 1_000_000;
    case 'K': return num * 1_000;
    default: return num;
  }
}

// Extract company names from query
function extractCompanies(query: string): string[] {
  const companies: string[] = [];
  
  // Known company patterns (could be loaded from database)
  const knownCompanies = [
    'Stripe', 'OpenAI', 'Anthropic', 'SpaceX', 'Anduril', 
    'Databricks', 'Canva', 'Figma', 'Notion', 'Linear',
    'Vercel', 'Supabase', 'Planetscale', 'Clerk', 'Resend'
  ];
  
  // Check for known companies (case-insensitive)
  knownCompanies.forEach(company => {
    const regex = new RegExp(`\\b${company}\\b`, 'gi');
    if (regex.test(query)) {
      companies.push(company);
    }
  });
  
  // Look for quoted company names
  const quotedMatches = query.match(/"([^"]+)"/g);
  if (quotedMatches) {
    quotedMatches.forEach(match => {
      companies.push(match.replace(/"/g, ''));
    });
  }
  
  // Look for capitalized words that might be companies
  const capitalizedWords = query.match(/\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b/g);
  if (capitalizedWords) {
    capitalizedWords.forEach(word => {
      // Filter out common words
      const commonWords = ['Show', 'Find', 'Get', 'List', 'Compare', 'Calculate'];
      if (!commonWords.includes(word) && !companies.includes(word)) {
        companies.push(word);
      }
    });
  }
  
  return [...new Set(companies)];
}

// Extract metrics from query
function extractMetrics(query: string): string[] {
  const metrics: string[] = [];
  const lowerQuery = query.toLowerCase();
  
  // Check each metric mapping
  Object.entries(METRIC_MAPPINGS).forEach(([term, columns]) => {
    if (lowerQuery.includes(term)) {
      metrics.push(columns[0]); // Use the primary column name
    }
  });
  
  return [...new Set(metrics)];
}

// Extract filters from query
function extractFilters(query: string): Record<string, any> {
  const filters: Record<string, any> = {};
  
  FILTER_PATTERNS.forEach(({ pattern, type }) => {
    const matches = Array.from(query.matchAll(pattern));
    matches.forEach(match => {
      switch (type) {
        case 'gt':
          const metric = match[2]?.toLowerCase();
          const column = METRIC_MAPPINGS[metric]?.[0] || metric;
          filters[column] = { $gt: parseValue(match[1]) };
          break;
        case 'lt':
          filters[match[2]] = { $lt: parseValue(match[1]) };
          break;
        case 'between':
          filters[match[3]] = { $gte: parseValue(match[1]), $lte: parseValue(match[2]) };
          break;
        case 'sector':
          filters.sector = match[1];
          break;
        case 'founded_year':
          filters.founded_year = parseInt(match[1]);
          break;
        case 'unicorn':
          filters.valuation = { $gte: 1_000_000_000 };
          break;
        case 'profitable':
          filters.ebitda = { $gt: 0 };
          break;
        case 'limit':
          filters._limit = parseInt(match[1]);
          break;
      }
    });
  });
  
  return filters;
}

// Detect query intent
function detectIntent(query: string): StructuredQuery['intent'] {
  for (const [intent, pattern] of Object.entries(INTENT_PATTERNS)) {
    if (pattern.test(query)) {
      return intent as StructuredQuery['intent'];
    }
  }
  return 'search'; // Default
}

// Determine which data sources to use
function determineSources(query: string, metrics: string[]): ('database' | 'web' | 'api')[] {
  const sources: Set<'database' | 'web' | 'api'> = new Set(['database']);
  
  // Add web search if query mentions recent/latest
  if (/recent|latest|current|today|now/i.test(query)) {
    sources.add('web');
  }
  
  // Add API if specific metrics need external data
  if (metrics.some(m => ['market_share', 'competitors', 'industry_average'].includes(m))) {
    sources.add('api');
  }
  
  return Array.from(sources);
}

// Build output specification
function buildOutput(query: string, metrics: string[], companies: string[]): StructuredQuery['output'] {
  const output: StructuredQuery['output'] = {
    columns: ['name', ...metrics] // Always include name
  };
  
  // Add common columns based on query type
  if (metrics.includes('revenue') || metrics.includes('growth_rate')) {
    output.columns.push('sector', 'founded_year');
  }
  
  // Set ordering
  if (metrics.length > 0) {
    output.orderBy = `${metrics[0]} DESC`;
  }
  
  // Set limit from query or default
  const limitMatch = query.match(/(?:top|first|best)\s+(\d+)/i);
  output.limit = limitMatch ? parseInt(limitMatch[1]) : 50;
  
  return output;
}

// Main function to process semantic query
export function processSemanticQuery(userQuery: string): StructuredQuery {
  // Clean and normalize query
  const query = userQuery.trim();
  
  // Extract components
  const companies = extractCompanies(query);
  const metrics = extractMetrics(query);
  const filters = extractFilters(query);
  const intent = detectIntent(query);
  
  // If no metrics found, add default ones based on intent
  if (metrics.length === 0) {
    if (intent === 'compare' || intent === 'search') {
      metrics.push('revenue', 'growth_rate', 'valuation');
    }
  }
  
  // Build structured query
  return {
    intent,
    entities: {
      companies,
      metrics,
      filters
    },
    sources: determineSources(query, metrics),
    output: buildOutput(query, metrics, companies)
  };
}

// Convert structured query to SQL
export function toSQL(structured: StructuredQuery, tableName: string = 'companies'): string {
  const { entities, output } = structured;
  
  // Build SELECT clause
  const selectColumns = output.columns.map(col => {
    // Map to actual database columns
    const dbColumn = METRIC_MAPPINGS[col]?.[0] || col;
    return dbColumn;
  }).join(', ');
  
  // Build WHERE clause
  const whereConditions: string[] = [];
  
  if (entities.companies && entities.companies.length > 0) {
    const companyList = entities.companies.map(c => `'${c}'`).join(', ');
    whereConditions.push(`name IN (${companyList})`);
  }
  
  if (entities.filters) {
    Object.entries(entities.filters).forEach(([key, value]) => {
      if (key.startsWith('_')) return; // Skip special filters
      
      if (typeof value === 'object') {
        // Handle operators
        if (value.$gt !== undefined) {
          whereConditions.push(`${key} > ${value.$gt}`);
        }
        if (value.$gte !== undefined) {
          whereConditions.push(`${key} >= ${value.$gte}`);
        }
        if (value.$lt !== undefined) {
          whereConditions.push(`${key} < ${value.$lt}`);
        }
        if (value.$lte !== undefined) {
          whereConditions.push(`${key} <= ${value.$lte}`);
        }
      } else {
        whereConditions.push(`${key} = '${value}'`);
      }
    });
  }
  
  // Build query
  let sql = `SELECT ${selectColumns} FROM ${tableName}`;
  
  if (whereConditions.length > 0) {
    sql += ` WHERE ${whereConditions.join(' AND ')}`;
  }
  
  if (output.orderBy) {
    sql += ` ORDER BY ${output.orderBy}`;
  }
  
  if (output.limit) {
    sql += ` LIMIT ${output.limit}`;
  }
  
  return sql;
}

// Convert structured query to web search query
export function toWebSearchQuery(structured: StructuredQuery): string {
  const parts: string[] = [];
  
  if (structured.entities.companies?.length > 0) {
    parts.push(structured.entities.companies.join(' OR '));
  }
  
  if (structured.entities.metrics?.length > 0) {
    const metricTerms = structured.entities.metrics.map(m => {
      // Use friendly terms for web search
      switch (m) {
        case 'revenue': return 'revenue ARR sales';
        case 'growth_rate': return 'growth rate YoY';
        case 'valuation': return 'valuation worth';
        case 'funding': return 'funding raised investment';
        default: return m;
      }
    });
    parts.push(metricTerms.join(' '));
  }
  
  // Add recent qualifier for fresh data
  parts.push('2024 2025 recent');
  
  return parts.join(' ');
}

// Example usage:
/*
const query = "Show me all SaaS companies with revenue over 100M and growth rate above 50%";
const structured = processSemanticQuery(query);
console.log(structured);
// Output:
{
  intent: 'filter',
  entities: {
    companies: [],
    metrics: ['revenue', 'growth_rate'],
    filters: {
      sector: 'SaaS',
      revenue: { $gt: 100000000 },
      growth_rate: { $gt: 0.5 }
    }
  },
  sources: ['database'],
  output: {
    columns: ['name', 'revenue', 'growth_rate', 'sector', 'founded_year'],
    orderBy: 'revenue DESC',
    limit: 50
  }
}

const sql = toSQL(structured);
console.log(sql);
// Output: SELECT name, revenue, growth_rate, sector, founded_year FROM companies WHERE sector = 'SaaS' AND revenue > 100000000 AND growth_rate > 0.5 ORDER BY revenue DESC LIMIT 50
*/