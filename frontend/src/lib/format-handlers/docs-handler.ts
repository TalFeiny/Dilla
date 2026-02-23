import { IFormatHandler, UnifiedBrainContext, FormatHandlerResult } from './types';

/**
 * Parse a markdown table string into structured { headers, rows } format.
 * Returns null if content is not a valid markdown table.
 */
function parseMarkdownTable(content: string): { headers: string[]; rows: (string | number)[][]; formatting?: Record<number, string> } | null {
  const lines = content.trim().split('\n').filter(l => l.trim());
  if (lines.length < 2) return null;
  // Check for pipe-delimited header + separator
  const headerLine = lines[0];
  const sepLine = lines[1];
  if (!headerLine.includes('|') || !sepLine.match(/^[\s|:-]+$/)) return null;

  const parseCells = (line: string) =>
    line.split('|').map(c => c.trim()).filter(Boolean);

  const headers = parseCells(headerLine);
  if (headers.length === 0) return null;

  const rows: (string | number)[][] = [];
  for (let i = 2; i < lines.length; i++) {
    if (!lines[i].includes('|')) continue;
    const cells = parseCells(lines[i]);
    rows.push(cells.map(c => {
      // Try to parse as number (strip currency symbols)
      const cleaned = c.replace(/[$,%]/g, '').trim();
      const num = Number(cleaned);
      return !isNaN(num) && cleaned.length > 0 ? num : c;
    }));
  }

  // Detect formatting: currency columns have $ prefix, percentage have %
  const formatting: Record<number, string> = {};
  if (rows.length > 0) {
    const firstRow = lines[2] ? parseCells(lines[2]) : [];
    firstRow.forEach((cell, i) => {
      if (cell.includes('$')) formatting[i] = 'currency';
      else if (cell.includes('%')) formatting[i] = 'percentage';
    });
  }

  return rows.length > 0 ? { headers, rows, formatting } : null;
}

/**
 * Split a section with mixed markdown content into structured sub-sections.
 * Extracts tables and bullet lists from the content string.
 */
function structurizeSection(section: any): any[] {
  if (!section.content || typeof section.content !== 'string') return [section];
  const content = section.content.trim();
  if (content.length === 0) return [section];

  // Check if the entire content is a single markdown table
  const table = parseMarkdownTable(content);
  if (table) {
    return [{
      ...section,
      type: 'table' as const,
      content: undefined,
      table: { ...table, caption: section.title || '' },
    }];
  }

  // Split content by markdown table blocks and keep prose as paragraphs
  const parts: any[] = [];
  const tableRegex = /(\|[^\n]+\|\n\|[\s:-]+\|\n(?:\|[^\n]+\|\n?)*)/g;
  let lastIdx = 0;
  let match: RegExpExecArray | null;

  while ((match = tableRegex.exec(content)) !== null) {
    // Prose before the table
    const before = content.slice(lastIdx, match.index).trim();
    if (before) {
      parts.push({ ...section, content: before });
    }
    // The table itself
    const tbl = parseMarkdownTable(match[1]);
    if (tbl) {
      parts.push({
        type: 'table' as const,
        title: undefined,
        content: undefined,
        table: tbl,
        level: section.level,
      });
    }
    lastIdx = match.index + match[0].length;
  }

  // Remaining content after last table
  const after = content.slice(lastIdx).trim();
  if (after) {
    parts.push({ ...section, content: after });
  }

  return parts.length > 0 ? parts : [section];
}

/**
 * Parse raw markdown text into an array of structured sections.
 * Splits on headings (# / ## / ###) and detects lists, tables, and paragraphs.
 */
export function parseMarkdownToSections(md: string): Array<{ type: string; title?: string; content?: string; level?: number; items?: string[]; table?: any }> {
  const lines = md.split('\n');
  const sections: Array<{ type: string; title?: string; content?: string; level?: number; items?: string[]; table?: any }> = [];
  let currentParagraph: string[] = [];
  let currentListItems: string[] = [];
  let currentTable: string[] = [];

  const flushParagraph = () => {
    if (currentParagraph.length > 0) {
      const text = currentParagraph.join('\n').trim();
      if (text) sections.push({ type: 'paragraph', content: text });
      currentParagraph = [];
    }
  };

  const flushList = () => {
    if (currentListItems.length > 0) {
      sections.push({ type: 'list', items: [...currentListItems] });
      currentListItems = [];
    }
  };

  const flushTable = () => {
    if (currentTable.length >= 2) {
      const tbl = parseMarkdownTable(currentTable.join('\n'));
      if (tbl) {
        sections.push({ type: 'table', table: tbl });
      } else {
        // Not a valid table, treat as paragraph
        sections.push({ type: 'paragraph', content: currentTable.join('\n') });
      }
    }
    currentTable = [];
  };

  for (const line of lines) {
    const trimmed = line.trim();

    // Heading
    const headingMatch = trimmed.match(/^(#{1,3})\s+(.+)$/);
    if (headingMatch) {
      flushParagraph();
      flushList();
      flushTable();
      const level = headingMatch[1].length;
      const type = `heading${level}` as 'heading1' | 'heading2' | 'heading3';
      sections.push({ type, title: headingMatch[2], content: headingMatch[2], level });
      continue;
    }

    // Table line (starts and ends with |)
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      flushParagraph();
      flushList();
      currentTable.push(trimmed);
      continue;
    } else if (currentTable.length > 0) {
      flushTable();
    }

    // List item (- or * or numbered)
    const listMatch = trimmed.match(/^[-*]\s+(.+)$/) || trimmed.match(/^\d+[.)]\s+(.+)$/);
    if (listMatch) {
      flushParagraph();
      currentListItems.push(listMatch[1]);
      continue;
    } else if (currentListItems.length > 0) {
      flushList();
    }

    // Empty line = flush paragraph
    if (!trimmed) {
      flushParagraph();
      continue;
    }

    // Regular text → accumulate as paragraph
    currentParagraph.push(trimmed);
  }

  flushParagraph();
  flushList();
  flushTable();

  return sections;
}

export class DocsHandler implements IFormatHandler {
  getFormat(): string {
    return 'docs';
  }

  async format(context: UnifiedBrainContext): Promise<FormatHandlerResult> {
    const { text, financialAnalyses, charts, citations, extractedCompanies } = context;

    // Try to parse the backend response
    let parsedData: any = text;
    if (typeof text === 'string') {
      try {
        parsedData = JSON.parse(text);
      } catch {
        // Not JSON, treat as raw content
        parsedData = null;
      }
    }
    
    // Early return for error responses from backend
    if (parsedData?.error && (!Array.isArray(parsedData?.sections) || parsedData.sections.length === 0)) {
      console.warn('[DocsHandler] Backend returned error:', parsedData.error);
      return {
        success: false,
        result: {
          content: parsedData.error,
          sections: [],
          title: parsedData.title || 'Memo Generation Failed',
          date: new Date().toISOString(),
          toc: [],
          charts: [],
          financialAnalyses: [],
          metadata: { format: 'docs' },
        },
        citations: [],
        metadata: { format: 'docs', companies: [], timestamp: new Date().toISOString() },
      };
    }

    // Try multiple paths to find docs sections
    const sections =
      parsedData?.sections ||                    // Direct structure from skill
      parsedData?.memo?.sections ||             // Nested in memo (old format)
      parsedData?.docs?.sections ||             // Nested in docs
      parsedData?.result?.sections ||           // In result
      parsedData?.results?.sections ||          // In results (streaming)
      parsedData?.result?.memo?.sections ||     // Nested in result.memo
      [];

    // Check if we found sections
    if (Array.isArray(sections) && sections.length > 0) {
      console.log('[DocsHandler] Found', sections.length, 'sections');

      // Extract exit modeling data if available
      const exitModeling = parsedData?.exit_modeling || parsedData?.results?.exit_modeling;
      let additionalSections = [];
      const additionalCharts = [];
      
      if (exitModeling) {
        // Add fund-level executive summary section
        if (exitModeling.portfolio_metrics || exitModeling.deployment_discipline) {
          additionalSections.push({
            title: 'Executive Summary - Fund Analysis',
            content: `
## Fund Portfolio Metrics

**Current Performance:**
- Total Expected DPI: ${exitModeling.portfolio_metrics?.total_expected_dpi?.toFixed(2) || 'N/A'}
- Average Expected Multiple: ${exitModeling.portfolio_metrics?.avg_expected_multiple?.toFixed(1) || 'N/A'}x
- Average Expected IRR: ${exitModeling.portfolio_metrics?.avg_expected_irr?.toFixed(1) || 'N/A'}%

**Deployment Status:**
- Remaining Capital: $${(exitModeling.deployment_discipline?.remaining_capital / 1000000)?.toFixed(0) || 'N/A'}M
- Monthly Deployment Target: $${(exitModeling.deployment_discipline?.capital_per_month / 1000000)?.toFixed(1) || 'N/A'}M
- Deployment Pace: ${exitModeling.deployment_discipline?.deployment_pace_rating || 'N/A'}

**Portfolio Construction:**
- Diversification: ${exitModeling.portfolio_construction?.sector_diversity_score?.toFixed(2) || 'N/A'} sector score, ${exitModeling.portfolio_construction?.stage_diversity_score?.toFixed(2) || 'N/A'} stage score
- Concentration Risk: ${exitModeling.portfolio_construction?.concentration_risk || 'N/A'}
- Loss Rate Expectation: ${exitModeling.portfolio_construction?.loss_rate_expectation || 'Standard VC portfolio'}
            `,
            level: 1
          });
          
          // Add portfolio distribution chart
          additionalCharts.push({
            type: 'pie',
            title: 'Expected Portfolio Outcomes',
            data: {
              segments: [
                { name: 'Failures', value: 50, color: '#e15759' },
                { name: 'Return Capital', value: 30, color: '#f28e2c' },
                { name: 'Moderate Winners (3-5x)', value: 15, color: '#76b7b2' },
                { name: 'Home Runs (10x+)', value: 5, color: '#59a14f' }
              ]
            }
          });
        }
        
        // Add individual company analysis sections
        if (exitModeling.scenarios) {
          additionalSections.push({
            title: 'Individual Company Analysis',
            content: `
## Company-by-Company Investment Analysis
            `,
            level: 1
          });
          
          (exitModeling.scenarios || []).forEach((scenario: any) => {
            additionalSections.push({
              title: scenario.company,
              content: `
### ${scenario.company}

**Investment Metrics:**
- Entry Valuation: ${scenario.entry_valuation ? `$${(scenario.entry_valuation / 1000000).toFixed(0)}M` : 'N/A'}
- Initial Check Size: ${scenario.initial_check ? `$${(scenario.initial_check / 1000000).toFixed(0)}M` : 'N/A'}
- Initial Ownership: ${scenario.initial_ownership?.toFixed(1)}%
- Current Diluted Ownership: ${scenario.diluted_ownership?.toFixed(1)}%

**Expected Returns:**
- Expected Multiple: ${scenario.expected_multiple?.toFixed(1)}x
- Expected IRR: ${scenario.expected_irr?.toFixed(1)}%
- DPI Contribution: ${(scenario.expected_dpi_contribution * 100)?.toFixed(1)}%
- Portfolio Fit Score: ${(scenario.portfolio_fit_score * 100)?.toFixed(0)}%

**Recommendation:** ${scenario.investment_recommendation || 'No recommendation available'}
              `,
              level: 2
            });
            
            // Add ownership waterfall data if available
            if (scenario.ownership_evolution?.exit_waterfall) {
              const waterfallTable = scenario.ownership_evolution.exit_waterfall.map((point: any) => 
                `| ${point.exit_value_formatted} | ${point.our_multiple?.toFixed(1)}x | ${point.effective_ownership?.toFixed(1)}% |`
              ).join('\n');
              
              additionalSections.push({
                title: `${scenario.company} - Exit Scenarios`,
                content: `
| Exit Value | Our Multiple | Effective Ownership |
|------------|--------------|-------------------|
${waterfallTable}
                `,
                level: 3
              });
            }
          });
        }
      }
      
      // Also check memo_updates for sections (backend sends this for MemoEditor)
      const memoUpdateSections = parsedData?.memo_updates?.sections || parsedData?.result?.memo_updates?.sections;
      const finalSections = memoUpdateSections && memoUpdateSections.length > sections.length
        ? memoUpdateSections : sections;

      const structuredSections = [...finalSections, ...additionalSections].flatMap(s => structurizeSection(s));

      // Collect charts from the top-level charts array, but exclude any that are already inline in sections
      const inlineChartTypes = new Set(
        structuredSections
          .filter((s: any) => s.type === 'chart' && s.chart?.type)
          .map((s: any) => s.chart.type)
      );
      const externalCharts = [...(parsedData?.charts || parsedData?.result?.charts || charts || []), ...additionalCharts]
        .filter((c: any) => !inlineChartTypes.has(c.type));

      const result = {
        content: parsedData?.content || parsedData?.result?.content || '',
        sections: structuredSections,
        title: parsedData?.title || parsedData?.result?.title || 'Investment Analysis',
        date: parsedData?.date || parsedData?.result?.date || new Date().toISOString(),
        toc: parsedData?.toc || parsedData?.result?.toc || [],
        charts: externalCharts,
        chartBatch: true, // Always batch process charts
        chartPositions: externalCharts.map((_: any, index: number) => ({
          afterParagraph: Math.floor((index + 1) * 3),
          inline: true
        })),
        financialAnalyses: parsedData?.financialAnalyses || financialAnalyses || [],
        metadata: parsedData?.metadata || parsedData?.result?.metadata || {},
        exitModeling: exitModeling,
        // Memo artifact metadata for session state
        memoType: parsedData?.memo_type || parsedData?.result?.memo_type || null,
        isResumable: parsedData?.is_resumable || parsedData?.result?.is_resumable || false,
      };
      
      return {
        success: true,
        result,
        citations: parsedData?.citations || parsedData?.result?.citations || citations || [],
        metadata: {
          companies: parsedData?.companies || parsedData?.result?.companies || extractedCompanies || [],
          timestamp: result.metadata.timestamp || new Date().toISOString(),
          format: 'docs',
          hasCharts: result.charts.length > 0,
          hasExitModeling: Boolean(exitModeling),
          memoType: result.memoType,
          isResumable: result.isResumable,
        }
      };
    }
    
    // Legacy format: parse markdown text into structured sections
    const rawContent = typeof text === 'string' ? text : JSON.stringify(text);
    const parsedSections = parseMarkdownToSections(rawContent);
    const allCharts = charts && charts.length > 0 ? charts : [];

    // If we got structured sections from markdown, use the rich path
    if (parsedSections.length > 0) {
      console.log('[DocsHandler] Parsed markdown into', parsedSections.length, 'sections');
      const result = {
        content: rawContent,
        sections: parsedSections.flatMap(s => structurizeSection(s)),
        title: parsedSections.find(s => s.type === 'heading1')?.title || 'Investment Analysis',
        date: new Date().toISOString(),
        toc: [],
        charts: allCharts,
        chartBatch: true,
        chartPositions: allCharts.map((_: any, index: number) => ({
          afterParagraph: Math.floor((index + 1) * 3),
          inline: true,
        })),
        financialAnalyses: financialAnalyses || [],
        metadata: {},
      };
      return {
        success: true,
        result,
        citations,
        metadata: {
          companies: extractedCompanies,
          timestamp: new Date().toISOString(),
          format: 'docs',
          hasCharts: allCharts.length > 0,
        },
      };
    }

    // Truly raw content — no structure found
    const processedCharts = allCharts.length > 0 ? {
      charts: allCharts,
      chartBatch: true,
      chartPositions: allCharts.map((_: any, index: number) => ({
        afterParagraph: Math.floor((index + 1) * 3),
        inline: true,
      })),
    } : { charts: [] as any[] };

    const result = {
      content: rawContent,
      financialAnalyses: financialAnalyses || [],
      ...processedCharts,
    };

    return {
      success: true,
      result,
      citations,
      metadata: {
        companies: extractedCompanies,
        timestamp: new Date().toISOString(),
        format: 'docs',
        hasCharts: allCharts.length > 0,
      },
    };
  }
  
  validate(result: any): boolean {
    return result?.content !== undefined;
  }
}