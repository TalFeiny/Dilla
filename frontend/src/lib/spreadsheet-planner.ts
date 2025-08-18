/**
 * Two-phase spreadsheet generation:
 * 1. Planning Phase - Lightweight, structured planning
 * 2. Execution Phase - Detailed command generation
 */

export interface ModelPlan {
  modelType: 'dcf' | 'valuation' | 'comparison' | 'saas_metrics' | 'unit_economics' | 'revenue_projection';
  companies: string[];
  placement: {
    startCell: string;
    endCell: string;
    headers: { row: number; columns: string[] };
    dataStartRow: number;
  };
  dataRequired: {
    metric: string;
    source: 'database' | 'benchmark' | 'search' | 'calculate';
    value?: any;
  }[];
  sections: {
    name: string;
    rowStart: number;
    rowEnd: number;
    calculations: string[];
  }[];
  assumptions: {
    name: string;
    value: number | string;
    source: string;
  }[];
}

export interface GridSummary {
  occupied: {
    ranges: string[]; // e.g., ["A1:D10", "F1:H5"]
    companies: string[];
    modelTypes: string[];
  };
  nextEmpty: {
    column: string;
    row: number;
  };
  existingFormulas: {
    cell: string;
    formula: string;
  }[];
}

export function summarizeGridState(gridState: Record<string, any>): GridSummary {
  const cells = Object.keys(gridState).filter(key => gridState[key]);
  
  if (cells.length === 0) {
    return {
      occupied: { ranges: [], companies: [], modelTypes: [] },
      nextEmpty: { column: 'A', row: 1 },
      existingFormulas: []
    };
  }

  // Find occupied ranges
  const occupiedCells = new Set<string>();
  const formulas: { cell: string; formula: string }[] = [];
  const companies = new Set<string>();
  
  let maxRow = 0;
  let maxCol = 'A';
  
  for (const cell of cells) {
    const value = gridState[cell];
    occupiedCells.add(cell);
    
    // Track formulas
    if (typeof value === 'string' && value.startsWith('=')) {
      formulas.push({ cell, formula: value });
    }
    
    // Extract company names (basic heuristic)
    if (typeof value === 'string' && value.length > 2 && value[0] === value[0].toUpperCase()) {
      const possibleCompany = value.trim();
      if (!['Revenue', 'EBITDA', 'Growth', 'Margin', 'Total', 'Year'].includes(possibleCompany)) {
        companies.add(possibleCompany);
      }
    }
    
    // Track max positions
    const match = cell.match(/^([A-Z]+)(\d+)$/);
    if (match) {
      const row = parseInt(match[2]);
      const col = match[1];
      if (row > maxRow) maxRow = row;
      if (col > maxCol) maxCol = col;
    }
  }
  
  // Find contiguous ranges (simplified)
  const ranges: string[] = [];
  if (occupiedCells.size > 0) {
    // Simple approach: find bounding box
    const sortedCells = Array.from(occupiedCells).sort();
    const firstCell = sortedCells[0];
    const lastCell = sortedCells[sortedCells.length - 1];
    ranges.push(`${firstCell}:${lastCell}`);
  }
  
  // Determine next empty position
  const nextCol = String.fromCharCode(maxCol.charCodeAt(0) + 2); // Skip one column
  const nextRow = maxRow + 2; // Skip one row
  
  return {
    occupied: {
      ranges,
      companies: Array.from(companies),
      modelTypes: [] // Would need more sophisticated detection
    },
    nextEmpty: {
      column: occupiedCells.size === 0 ? 'A' : nextCol,
      row: occupiedCells.size === 0 ? 1 : 1
    },
    existingFormulas: formulas
  };
}

export function validateCommands(
  commands: string[], 
  gridState: Record<string, any>
): { valid: string[]; warnings: string[]; errors: string[] } {
  const valid: string[] = [];
  const warnings: string[] = [];
  const errors: string[] = [];
  
  const occupiedCells = new Set(
    Object.keys(gridState).filter(k => gridState[k])
  );
  
  for (const cmd of commands) {
    // Parse the command
    const writeMatch = cmd.match(/grid\.write\("([A-Z]+\d+)",\s*(.+)\)/);
    const formulaMatch = cmd.match(/grid\.formula\("([A-Z]+\d+)",\s*"(.+)"\)/);
    const linkMatch = cmd.match(/grid\.link\("([A-Z]+\d+)",/);
    
    if (writeMatch) {
      const [, cell, value] = writeMatch;
      
      // Check for overwrite
      if (occupiedCells.has(cell)) {
        warnings.push(`Cell ${cell} already has data, will overwrite`);
        
        // Suggest alternative empty cell
        const colLetter = cell.match(/[A-Z]+/)?.[0] || 'A';
        const rowNum = parseInt(cell.match(/\d+/)?.[0] || '1');
        const altCell = `${colLetter}${rowNum + 20}`; // Move down 20 rows
        
        if (!occupiedCells.has(altCell)) {
          const adjustedCmd = cmd.replace(cell, altCell);
          valid.push(adjustedCmd);
          warnings.push(`Moved to ${altCell} to avoid overwrite`);
        } else {
          errors.push(`Cannot find safe location for ${cell}`);
        }
      } else {
        valid.push(cmd);
        occupiedCells.add(cell); // Track for subsequent commands
      }
    } else if (formulaMatch) {
      const [, cell, formula] = formulaMatch;
      
      // Validate formula references
      const refs = formula.match(/[A-Z]+\d+/g) || [];
      const missingRefs = refs.filter(ref => !occupiedCells.has(ref));
      
      if (missingRefs.length > 0) {
        warnings.push(`Formula in ${cell} references empty cells: ${missingRefs.join(', ')}`);
      }
      
      if (occupiedCells.has(cell)) {
        warnings.push(`Cell ${cell} already occupied, formula will overwrite`);
      }
      
      valid.push(cmd);
      occupiedCells.add(cell);
    } else if (linkMatch) {
      // Links are generally safe
      valid.push(cmd);
    } else {
      // Unknown command format
      warnings.push(`Unknown command format: ${cmd.substring(0, 50)}...`);
      valid.push(cmd); // Include it anyway
    }
  }
  
  return { valid, warnings, errors };
}

export function generatePlanPrompt(
  task: string,
  gridSummary: GridSummary,
  companyData: any
): string {
  return `Create a STRUCTURED PLAN (not commands) for: ${task}

Current grid state:
- Occupied ranges: ${gridSummary.occupied.ranges.join(', ') || 'Empty'}
- Existing companies: ${gridSummary.occupied.companies.join(', ') || 'None'}
- Next empty area: Column ${gridSummary.nextEmpty.column}, Row ${gridSummary.nextEmpty.row}

Available company data:
${JSON.stringify(companyData, null, 2)}

Return ONLY a JSON plan with this structure:
{
  "modelType": "dcf|valuation|comparison|saas_metrics|unit_economics|revenue_projection",
  "companies": ["company1", "company2"],
  "placement": {
    "startCell": "A1",
    "endCell": "E20",
    "headers": { "row": 1, "columns": ["Metric", "2024", "2025", "2026", "2027"] },
    "dataStartRow": 3
  },
  "dataRequired": [
    { "metric": "Revenue", "source": "database", "value": 1000000 },
    { "metric": "Growth Rate", "source": "benchmark", "value": 0.3 },
    { "metric": "EBITDA Margin", "source": "calculate", "value": null }
  ],
  "sections": [
    { "name": "Revenue", "rowStart": 3, "rowEnd": 5, "calculations": ["growth", "cagr"] },
    { "name": "Costs", "rowStart": 6, "rowEnd": 10, "calculations": ["margin", "efficiency"] },
    { "name": "Valuation", "rowStart": 11, "rowEnd": 15, "calculations": ["dcf", "multiples"] }
  ],
  "assumptions": [
    { "name": "Terminal Growth", "value": 0.03, "source": "Industry standard" },
    { "name": "Discount Rate", "value": 0.12, "source": "WACC calculation" }
  ]
}

Be specific about placement to avoid overwriting existing data.`;
}

export function executePlanPrompt(
  plan: ModelPlan,
  gridSummary: GridSummary
): string {
  return `Execute this financial model plan:

Model Type: ${plan.modelType}
Companies: ${plan.companies.join(', ')}
Location: ${plan.placement.startCell} to ${plan.placement.endCell}

Sections to build:
${plan.sections.map(s => `- ${s.name} (rows ${s.rowStart}-${s.rowEnd})`).join('\n')}

Data available:
${plan.dataRequired.map(d => `- ${d.metric}: ${d.value || 'Calculate'} (${d.source})`).join('\n')}

Assumptions:
${plan.assumptions.map(a => `- ${a.name}: ${a.value} (${a.source})`).join('\n')}

Generate ONLY grid commands (grid.write, grid.formula, grid.link) to build this model.
Start at ${plan.placement.startCell} and build systematically.
Include all sections, calculations, and sources.

IMPORTANT: 
- Use exact cell references from the plan
- Include formulas for all calculations
- Add source citations with grid.link()
- Format numbers appropriately (use M for millions, % for percentages)`;
}