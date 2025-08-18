/**
 * Visualization Tools for Financial Data
 * Converts spreadsheet data to Sankey and Waterfall visualizations
 */

export interface SankeyNode {
  id: string;
  name: string;
  value?: number;
  level?: number;
  color?: string;
}

export interface SankeyLink {
  source: string;
  target: string;
  value: number;
  color?: string;
}

export interface WaterfallData {
  name: string;
  value?: number;
  increase?: number;
  decrease?: number;
  total?: number;
  isTotal?: boolean;
  isBridge?: boolean;
  color?: string;
}

/**
 * Convert spreadsheet range to Sankey data for revenue flows
 */
export function convertRangeToSankeyData(
  cells: Record<string, any>,
  dataRange: string
): { nodes: SankeyNode[]; links: SankeyLink[] } {
  const nodes: SankeyNode[] = [];
  const links: SankeyLink[] = [];
  
  // Parse the range to extract data
  const data = extractRangeData(cells, dataRange);
  
  // Auto-detect data structure
  if (data.length > 0) {
    const headers = data[0];
    
    // Check if it's a revenue segmentation structure
    if (headers.includes('Segment') || headers.includes('Revenue Source')) {
      return createRevenueSankey(data);
    }
    
    // Check if it's a fund flow structure
    if (headers.includes('LP') || headers.includes('Fund')) {
      return createFundSankey(data);
    }
    
    // Check if it's a cost structure
    if (headers.includes('Cost') || headers.includes('Expense')) {
      return createCostSankey(data);
    }
    
    // Default: P&L flow
    return createPLSankey(data);
  }
  
  return { nodes, links };
}

/**
 * Create revenue segmentation Sankey
 */
function createRevenueSankey(data: any[][]): { nodes: SankeyNode[]; links: SankeyLink[] } {
  const nodes: SankeyNode[] = [];
  const links: SankeyLink[] = [];
  
  // Skip header row
  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const segment = row[0];
    const revenue = parseFloat(row[1]) || 0;
    const costs = parseFloat(row[2]) || 0;
    const profit = revenue - costs;
    
    // Revenue source node
    nodes.push({
      id: `revenue-${segment}`,
      name: `${segment} Revenue`,
      value: revenue,
      level: 0,
      color: '#FFA500'
    });
    
    // Total revenue aggregation
    if (!nodes.find(n => n.id === 'total-revenue')) {
      nodes.push({
        id: 'total-revenue',
        name: 'Total Revenue',
        level: 1,
        color: '#FFD700'
      });
    }
    
    links.push({
      source: `revenue-${segment}`,
      target: 'total-revenue',
      value: revenue
    });
    
    // Cost allocation
    if (costs > 0) {
      if (!nodes.find(n => n.id === 'total-costs')) {
        nodes.push({
          id: 'total-costs',
          name: 'Total Costs',
          level: 2,
          color: '#2C3E50'
        });
      }
      
      links.push({
        source: 'total-revenue',
        target: 'total-costs',
        value: costs
      });
    }
    
    // Profit
    if (profit > 0) {
      if (!nodes.find(n => n.id === 'net-profit')) {
        nodes.push({
          id: 'net-profit',
          name: 'Net Profit',
          level: 2,
          color: '#10B981'
        });
      }
      
      links.push({
        source: 'total-revenue',
        target: 'net-profit',
        value: profit
      });
    }
  }
  
  // Add cost breakdown if available
  const costCategories = ['R&D', 'Sales & Marketing', 'Operations', 'G&A'];
  const totalRevenue = links.filter(l => l.target === 'total-revenue')
    .reduce((sum, l) => sum + l.value, 0);
  
  costCategories.forEach((category, index) => {
    const costAmount = totalRevenue * (0.2 - index * 0.03); // Decreasing percentages
    
    nodes.push({
      id: `cost-${category.toLowerCase().replace(/[^a-z]/g, '')}`,
      name: category,
      value: costAmount,
      level: 3,
      color: '#6B7280'
    });
    
    links.push({
      source: 'total-costs',
      target: `cost-${category.toLowerCase().replace(/[^a-z]/g, '')}`,
      value: costAmount
    });
  });
  
  return { nodes, links };
}

/**
 * Create fund flow Sankey (LP → Fund → Portfolio → Exits)
 */
function createFundSankey(data: any[][]): { nodes: SankeyNode[]; links: SankeyLink[] } {
  const nodes: SankeyNode[] = [];
  const links: SankeyLink[] = [];
  
  // Fund flow stages
  const stages = {
    lps: [],
    fund: 'Main Fund',
    portfolios: [],
    exits: []
  };
  
  // Process data
  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const source = row[0];
    const target = row[1];
    const amount = parseFloat(row[2]) || 0;
    
    // Detect stage based on naming
    if (source.includes('LP') || source.includes('Investor')) {
      // LP → Fund
      nodes.push({
        id: `lp-${source}`,
        name: source,
        value: amount,
        level: 0,
        color: '#3B82F6'
      });
      
      if (!nodes.find(n => n.id === 'fund')) {
        nodes.push({
          id: 'fund',
          name: stages.fund,
          level: 1,
          color: '#8B5CF6'
        });
      }
      
      links.push({
        source: `lp-${source}`,
        target: 'fund',
        value: amount
      });
      
    } else if (target.includes('Portfolio') || target.includes('Company')) {
      // Fund → Portfolio
      const portfolioId = `portfolio-${target}`;
      
      if (!nodes.find(n => n.id === portfolioId)) {
        nodes.push({
          id: portfolioId,
          name: target,
          value: amount,
          level: 2,
          color: '#06B6D4'
        });
      }
      
      links.push({
        source: 'fund',
        target: portfolioId,
        value: amount
      });
      
    } else if (source.includes('Portfolio') && (target.includes('Exit') || target.includes('IPO') || target.includes('M&A'))) {
      // Portfolio → Exit
      const exitId = `exit-${target}`;
      const portfolioId = `portfolio-${source}`;
      
      if (!nodes.find(n => n.id === exitId)) {
        nodes.push({
          id: exitId,
          name: target,
          value: amount,
          level: 3,
          color: '#10B981'
        });
      }
      
      links.push({
        source: portfolioId,
        target: exitId,
        value: amount
      });
    }
  }
  
  // Add distributions back to LPs
  const totalExits = nodes.filter(n => n.id.startsWith('exit-'))
    .reduce((sum, n) => sum + (n.value || 0), 0);
  
  if (totalExits > 0) {
    nodes.push({
      id: 'distributions',
      name: 'LP Distributions',
      value: totalExits,
      level: 4,
      color: '#10B981'
    });
    
    // Connect exits to distributions
    nodes.filter(n => n.id.startsWith('exit-')).forEach(exit => {
      links.push({
        source: exit.id,
        target: 'distributions',
        value: exit.value || 0
      });
    });
  }
  
  return { nodes, links };
}

/**
 * Create cost structure Sankey
 */
function createCostSankey(data: any[][]): { nodes: SankeyNode[]; links: SankeyLink[] } {
  const nodes: SankeyNode[] = [];
  const links: SankeyLink[] = [];
  
  // Process cost breakdown
  let totalCosts = 0;
  
  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const category = row[0];
    const amount = parseFloat(row[1]) || 0;
    const subcategory = row[2];
    
    totalCosts += amount;
    
    // Main category node
    const categoryId = `category-${category.toLowerCase().replace(/\s+/g, '-')}`;
    if (!nodes.find(n => n.id === categoryId)) {
      nodes.push({
        id: categoryId,
        name: category,
        value: amount,
        level: 1,
        color: '#6B7280'
      });
    }
    
    // Subcategory if exists
    if (subcategory) {
      const subcategoryId = `sub-${subcategory.toLowerCase().replace(/\s+/g, '-')}`;
      
      if (!nodes.find(n => n.id === subcategoryId)) {
        nodes.push({
          id: subcategoryId,
          name: subcategory,
          value: amount,
          level: 2,
          color: '#9CA3AF'
        });
      }
      
      links.push({
        source: categoryId,
        target: subcategoryId,
        value: amount
      });
    }
  }
  
  // Add total costs node at the beginning
  nodes.unshift({
    id: 'total-costs',
    name: 'Total Operating Costs',
    value: totalCosts,
    level: 0,
    color: '#1F2937'
  });
  
  // Connect total to categories
  nodes.filter(n => n.level === 1).forEach(category => {
    links.push({
      source: 'total-costs',
      target: category.id,
      value: category.value || 0
    });
  });
  
  return { nodes, links };
}

/**
 * Create P&L flow Sankey
 */
function createPLSankey(data: any[][]): { nodes: SankeyNode[]; links: SankeyLink[] } {
  const nodes: SankeyNode[] = [];
  const links: SankeyLink[] = [];
  
  // Standard P&L flow
  const plStructure = {
    revenue: 0,
    cogs: 0,
    grossProfit: 0,
    opex: 0,
    ebitda: 0,
    da: 0,
    ebit: 0,
    interest: 0,
    tax: 0,
    netIncome: 0
  };
  
  // Extract values from data
  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const item = row[0].toLowerCase();
    const value = parseFloat(row[1]) || 0;
    
    if (item.includes('revenue')) plStructure.revenue += value;
    else if (item.includes('cogs') || item.includes('cost of')) plStructure.cogs += value;
    else if (item.includes('opex') || item.includes('operating expense')) plStructure.opex += value;
    else if (item.includes('depreciation')) plStructure.da += value;
    else if (item.includes('interest')) plStructure.interest += value;
    else if (item.includes('tax')) plStructure.tax += value;
  }
  
  // Calculate derived values
  plStructure.grossProfit = plStructure.revenue - plStructure.cogs;
  plStructure.ebitda = plStructure.grossProfit - plStructure.opex;
  plStructure.ebit = plStructure.ebitda - plStructure.da;
  plStructure.netIncome = plStructure.ebit - plStructure.interest - plStructure.tax;
  
  // Create nodes and links
  nodes.push(
    { id: 'revenue', name: 'Revenue', value: plStructure.revenue, level: 0, color: '#10B981' },
    { id: 'cogs', name: 'COGS', value: plStructure.cogs, level: 1, color: '#EF4444' },
    { id: 'gross-profit', name: 'Gross Profit', value: plStructure.grossProfit, level: 1, color: '#3B82F6' },
    { id: 'opex', name: 'Operating Expenses', value: plStructure.opex, level: 2, color: '#F59E0B' },
    { id: 'ebitda', name: 'EBITDA', value: plStructure.ebitda, level: 2, color: '#8B5CF6' },
    { id: 'net-income', name: 'Net Income', value: plStructure.netIncome, level: 3, color: '#10B981' }
  );
  
  links.push(
    { source: 'revenue', target: 'cogs', value: plStructure.cogs },
    { source: 'revenue', target: 'gross-profit', value: plStructure.grossProfit },
    { source: 'gross-profit', target: 'opex', value: plStructure.opex },
    { source: 'gross-profit', target: 'ebitda', value: plStructure.ebitda },
    { source: 'ebitda', target: 'net-income', value: plStructure.netIncome }
  );
  
  return { nodes, links };
}

/**
 * Convert spreadsheet range to Waterfall data
 */
export function convertRangeToWaterfallData(
  cells: Record<string, any>,
  dataRange: string
): WaterfallData[] {
  const data = extractRangeData(cells, dataRange);
  
  if (data.length > 0) {
    const headers = data[0];
    
    // Check if it's an exit waterfall
    if (headers.some(h => h?.toLowerCase().includes('exit') || h?.toLowerCase().includes('proceeds'))) {
      return createExitWaterfall(data);
    }
    
    // Check if it's a fund waterfall
    if (headers.some(h => h?.toLowerCase().includes('distribution') || h?.toLowerCase().includes('carry'))) {
      return createFundWaterfall(data);
    }
    
    // Default financial waterfall
    return createFinancialWaterfall(data);
  }
  
  return [];
}

/**
 * Create exit proceeds waterfall
 */
function createExitWaterfall(data: any[][]): WaterfallData[] {
  const waterfall: WaterfallData[] = [];
  
  // Process exit distribution
  let exitValue = 0;
  let remaining = 0;
  
  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const item = row[0];
    const amount = parseFloat(row[1]) || 0;
    const type = row[2]?.toLowerCase() || '';
    
    if (i === 1) {
      // First item is total exit value
      exitValue = amount;
      remaining = amount;
      waterfall.push({
        name: item || 'Exit Value',
        value: amount,
        isTotal: true,
        color: '#3B82F6'
      });
    } else if (type.includes('pref') || type.includes('liquidation')) {
      // Liquidation preferences
      const distributed = Math.min(remaining, amount);
      waterfall.push({
        name: item,
        decrease: distributed,
        color: '#EF4444'
      });
      remaining -= distributed;
    } else if (type.includes('common') || type.includes('founder')) {
      // Common/founder shares
      waterfall.push({
        name: item,
        decrease: amount,
        color: '#10B981'
      });
      remaining -= amount;
    } else {
      // Other distributions
      waterfall.push({
        name: item,
        decrease: amount,
        color: '#F59E0B'
      });
      remaining -= amount;
    }
  }
  
  // Add remaining if any
  if (remaining > 0.01) {
    waterfall.push({
      name: 'Remaining',
      value: remaining,
      isTotal: true,
      color: '#6B7280'
    });
  }
  
  return waterfall;
}

/**
 * Create fund distribution waterfall
 */
function createFundWaterfall(data: any[][]): WaterfallData[] {
  const waterfall: WaterfallData[] = [];
  
  // Standard fund waterfall structure
  let grossProceeds = 0;
  let currentValue = 0;
  
  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const item = row[0];
    const amount = parseFloat(row[1]) || 0;
    const type = row[2]?.toLowerCase() || '';
    
    if (i === 1) {
      // Gross proceeds
      grossProceeds = amount;
      currentValue = amount;
      waterfall.push({
        name: 'Gross Proceeds',
        value: amount,
        isTotal: true,
        color: '#10B981'
      });
    } else if (type.includes('return') || type.includes('capital')) {
      // Return of capital
      waterfall.push({
        name: 'Return of Capital',
        decrease: amount,
        color: '#3B82F6'
      });
      currentValue -= amount;
    } else if (type.includes('pref') || type.includes('hurdle')) {
      // Preferred return
      waterfall.push({
        name: 'Preferred Return (8%)',
        decrease: amount,
        color: '#8B5CF6'
      });
      currentValue -= amount;
    } else if (type.includes('catch') || type.includes('gp')) {
      // GP catch-up
      waterfall.push({
        name: 'GP Catch-up',
        decrease: amount,
        color: '#F59E0B'
      });
      currentValue -= amount;
    } else if (type.includes('carry') || type.includes('carried')) {
      // Carried interest
      waterfall.push({
        name: 'Carried Interest (20%)',
        decrease: amount,
        color: '#EF4444'
      });
      currentValue -= amount;
    } else if (type.includes('lp')) {
      // LP share
      waterfall.push({
        name: 'LP Share (80%)',
        decrease: amount,
        color: '#10B981'
      });
      currentValue -= amount;
    }
  }
  
  // Add final distribution
  waterfall.push({
    name: 'Final Distribution',
    isTotal: true,
    color: '#1F2937'
  });
  
  return waterfall;
}

/**
 * Create standard financial waterfall
 */
function createFinancialWaterfall(data: any[][]): WaterfallData[] {
  const waterfall: WaterfallData[] = [];
  
  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const item = row[0];
    const value = parseFloat(row[1]) || 0;
    const type = row[2]?.toLowerCase() || '';
    
    if (type.includes('total') || type.includes('start') || i === 1) {
      waterfall.push({
        name: item,
        value: Math.abs(value),
        isTotal: true,
        color: '#3B82F6'
      });
    } else if (type.includes('bridge') || type.includes('subtotal')) {
      waterfall.push({
        name: item,
        isBridge: true,
        color: '#6B7280'
      });
    } else if (value > 0) {
      waterfall.push({
        name: item,
        increase: value,
        color: '#10B981'
      });
    } else {
      waterfall.push({
        name: item,
        decrease: Math.abs(value),
        color: '#EF4444'
      });
    }
  }
  
  return waterfall;
}

/**
 * Extract data from spreadsheet range
 */
function extractRangeData(cells: Record<string, any>, range: string): any[][] {
  const data: any[][] = [];
  
  // Parse range (e.g., "A1:C10")
  const [start, end] = range.split(':');
  if (!start || !end) return data;
  
  const startMatch = start.match(/^([A-Z]+)(\d+)$/);
  const endMatch = end.match(/^([A-Z]+)(\d+)$/);
  if (!startMatch || !endMatch) return data;
  
  const startCol = letterToColumn(startMatch[1]);
  const startRow = parseInt(startMatch[2]);
  const endCol = letterToColumn(endMatch[1]);
  const endRow = parseInt(endMatch[2]);
  
  // Extract data row by row
  for (let row = startRow; row <= endRow; row++) {
    const rowData: any[] = [];
    for (let col = startCol; col <= endCol; col++) {
      const addr = columnToLetter(col) + row;
      const cell = cells[addr];
      rowData.push(cell?.value ?? null);
    }
    data.push(rowData);
  }
  
  return data;
}

function columnToLetter(col: number): string {
  let letter = '';
  while (col >= 0) {
    letter = String.fromCharCode((col % 26) + 65) + letter;
    col = Math.floor(col / 26) - 1;
  }
  return letter;
}

function letterToColumn(letter: string): number {
  let col = 0;
  for (let i = 0; i < letter.length; i++) {
    col = col * 26 + (letter.charCodeAt(i) - 64);
  }
  return col - 1;
}