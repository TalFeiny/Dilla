/**
 * Agent Visual Formatting Skills
 * Teachable behaviors for color-coding, dropdowns, and interactive elements
 * Maintains Excel export compatibility
 */

import { colorCodingSystem } from '../color-coding-system';

export interface AgentVisualSkills {
  colorCode: (data: any, context: string) => any;
  createDropdown: (options: string[], selected?: string) => any;
  createMultiSelect: (options: string[], selected?: string[]) => any;
  formatAsTable: (data: any[], options?: TableFormatOptions) => any;
  applyConditionalFormatting: (cells: any[], rules: ConditionalRule[]) => any;
  generateHeatmap: (matrix: number[][]) => any;
  createSparkline: (values: number[]) => string;
}

export interface TableFormatOptions {
  zebra?: boolean;
  sortable?: boolean;
  filterable?: boolean;
  exportable?: boolean;
  colorCodeColumns?: { [column: string]: string };
  conditionalFormatting?: ConditionalRule[];
}

export interface ConditionalRule {
  condition: (value: any, row?: any) => boolean;
  style: CellStyle;
  priority?: number;
}

export interface CellStyle {
  backgroundColor?: string;
  color?: string;
  fontWeight?: 'normal' | 'bold';
  fontStyle?: 'normal' | 'italic';
  border?: string;
  icon?: string;
}

export class VisualFormattingAgent {
  private learningMemory: Map<string, any> = new Map();
  private formattingPatterns: Map<string, ConditionalRule[]> = new Map();

  /**
   * Learn from user corrections and preferences
   */
  learnFromFeedback(context: string, feedback: {
    original: any;
    corrected: any;
    preference: string;
  }) {
    const pattern = this.extractPattern(feedback);
    const existing = this.formattingPatterns.get(context) || [];
    existing.push(pattern);
    this.formattingPatterns.set(context, existing);
    
    // Store in memory for future use
    this.learningMemory.set(`${context}_${Date.now()}`, feedback);
  }

  /**
   * Apply color coding with learned behaviors
   */
  colorCode(data: any, context: string): any {
    // Check if we have learned patterns for this context
    const learnedPatterns = this.formattingPatterns.get(context);
    
    if (Array.isArray(data)) {
      return data.map(item => this.applyColorToItem(item, context, learnedPatterns));
    } else if (typeof data === 'object' && data !== null) {
      return this.applyColorToItem(data, context, learnedPatterns);
    } else {
      // Simple value - apply direct color
      const color = this.determineColor(data, context, learnedPatterns);
      return { value: data, color };
    }
  }

  private applyColorToItem(item: any, context: string, patterns?: ConditionalRule[]): any {
    if (typeof item !== 'object' || item === null) {
      return item;
    }

    const colored = { ...item };
    
    // Apply learned patterns first
    if (patterns) {
      for (const pattern of patterns) {
        if (pattern.condition(item)) {
          colored._style = pattern.style;
          break;
        }
      }
    }

    // Apply default color schemes if no pattern matched
    if (!colored._style) {
      colored._style = this.getDefaultStyle(item, context);
    }

    return colored;
  }

  private determineColor(value: any, context: string, patterns?: ConditionalRule[]): string {
    // Check learned patterns first
    if (patterns) {
      for (const pattern of patterns) {
        if (pattern.condition(value)) {
          return pattern.style.backgroundColor || '#ffffff';
        }
      }
    }

    // Use color coding system
    return colorCodingSystem.getColor(value, context);
  }

  /**
   * Create dropdown with Excel compatibility
   */
  createDropdown(options: string[], selected?: string, allowCustom: boolean = false): {
    type: 'dropdown';
    options: string[];
    selected: string | null;
    allowCustom: boolean;
    excelValidation: any;
  } {
    return {
      type: 'dropdown',
      options,
      selected: selected || null,
      allowCustom,
      excelValidation: {
        type: 'list',
        formulae: [options.join(',')],
        allowBlank: true,
        showDropdown: true,
        errorTitle: 'Invalid Selection',
        error: `Please select from: ${options.join(', ')}`
      }
    };
  }

  /**
   * Create multi-select with Excel compatibility
   * In Excel, this becomes a comma-separated text field with validation
   */
  createMultiSelect(options: string[], selected?: string[]): {
    type: 'multiselect';
    options: string[];
    selected: string[];
    excelValue: string;
    excelValidation: any;
  } {
    return {
      type: 'multiselect',
      options,
      selected: selected || [],
      excelValue: (selected || []).join(', '),
      excelValidation: {
        type: 'textLength',
        operator: 'lessThanOrEqual',
        formulae: [500],
        showInputMessage: true,
        inputTitle: 'Multiple Selection',
        inputMessage: `Available options: ${options.join(', ')}. Separate multiple values with commas.`
      }
    };
  }

  /**
   * Format data as an intelligent table
   */
  formatAsTable(data: any[], options: TableFormatOptions = {}): {
    headers: string[];
    rows: any[][];
    styles: CellStyle[][];
    excelFormat: any;
  } {
    if (!data || data.length === 0) {
      return { headers: [], rows: [], styles: [], excelFormat: {} };
    }

    // Extract headers
    const headers = Object.keys(data[0]);
    
    // Process rows with formatting
    const rows: any[][] = [];
    const styles: CellStyle[][] = [];

    data.forEach((item, rowIndex) => {
      const row: any[] = [];
      const rowStyles: CellStyle[] = [];

      headers.forEach(header => {
        const value = item[header];
        row.push(value);

        // Apply conditional formatting
        let style: CellStyle = {};
        
        if (options.conditionalFormatting) {
          for (const rule of options.conditionalFormatting) {
            if (rule.condition(value, item)) {
              style = { ...style, ...rule.style };
              break;
            }
          }
        }

        // Apply column-specific color coding
        if (options.colorCodeColumns?.[header]) {
          const color = colorCodingSystem.getColor(value, options.colorCodeColumns[header]);
          style.backgroundColor = color;
        }

        // Apply zebra striping
        if (options.zebra && rowIndex % 2 === 1) {
          style.backgroundColor = style.backgroundColor || '#f9fafb';
        }

        rowStyles.push(style);
      });

      rows.push(row);
      styles.push(rowStyles);
    });

    return {
      headers,
      rows,
      styles,
      excelFormat: {
        tableStyle: 'TableStyleMedium2',
        showRowStripes: options.zebra,
        showColumnStripes: false,
        showFirstColumn: false,
        showLastColumn: false,
        autoFilter: options.filterable
      }
    };
  }

  /**
   * Apply conditional formatting rules
   */
  applyConditionalFormatting(cells: any[], rules: ConditionalRule[]): any[] {
    return cells.map(cell => {
      const formatted = { ...cell };
      
      // Sort rules by priority
      const sortedRules = [...rules].sort((a, b) => (b.priority || 0) - (a.priority || 0));
      
      for (const rule of sortedRules) {
        if (rule.condition(cell.value, cell)) {
          formatted.style = { ...(formatted.style || {}), ...rule.style };
          break;
        }
      }
      
      return formatted;
    });
  }

  /**
   * Generate a heatmap visualization
   */
  generateHeatmap(matrix: number[][]): {
    cells: Array<Array<{ value: number; color: string; intensity: number }>>;
    excelConditionalFormat: any;
  } {
    const flat = matrix.flat();
    const min = Math.min(...flat);
    const max = Math.max(...flat);
    const range = max - min;

    const cells = matrix.map(row => 
      row.map(value => {
        const intensity = range > 0 ? (value - min) / range : 0.5;
        const color = this.getHeatmapColor(intensity);
        return { value, color, intensity };
      })
    );

    return {
      cells,
      excelConditionalFormat: {
        type: 'colorScale',
        colorScale: {
          cfvo: [
            { type: 'min' },
            { type: 'percentile', value: 50 },
            { type: 'max' }
          ],
          color: [
            { argb: 'FF63BE7B' }, // Green
            { argb: 'FFFFEB84' }, // Yellow
            { argb: 'FFF8696B' }  // Red
          ]
        }
      }
    };
  }

  private getHeatmapColor(intensity: number): string {
    // Green -> Yellow -> Red gradient
    if (intensity < 0.5) {
      // Green to Yellow
      const factor = intensity * 2;
      const r = Math.round(99 + (255 - 99) * factor);
      const g = Math.round(190 + (235 - 190) * factor);
      const b = Math.round(123 + (132 - 123) * factor);
      return `rgb(${r}, ${g}, ${b})`;
    } else {
      // Yellow to Red
      const factor = (intensity - 0.5) * 2;
      const r = Math.round(255 + (248 - 255) * factor);
      const g = Math.round(235 + (105 - 235) * factor);
      const b = Math.round(132 + (107 - 132) * factor);
      return `rgb(${r}, ${g}, ${b})`;
    }
  }

  /**
   * Create inline sparkline visualization
   */
  createSparkline(values: number[]): string {
    if (values.length === 0) return '';
    
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    
    // Use Unicode block characters for sparkline
    const blocks = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█'];
    
    return values.map(v => {
      const normalized = (v - min) / range;
      const index = Math.floor(normalized * (blocks.length - 1));
      return blocks[index];
    }).join('');
  }

  /**
   * Extract pattern from user feedback
   */
  private extractPattern(feedback: any): ConditionalRule {
    // Analyze the difference between original and corrected
    const condition = (value: any) => {
      // This would be more sophisticated in production
      return JSON.stringify(value) === JSON.stringify(feedback.original);
    };

    const style: CellStyle = {};
    
    // Extract style preferences from correction
    if (feedback.corrected.color) {
      style.backgroundColor = feedback.corrected.color;
    }
    if (feedback.corrected.bold) {
      style.fontWeight = 'bold';
    }
    
    return { condition, style };
  }

  /**
   * Get default style based on context
   */
  private getDefaultStyle(item: any, context: string): CellStyle {
    const style: CellStyle = {};
    
    // Apply context-specific defaults
    switch (context) {
      case 'performance':
        if (item.growth > 20) {
          style.backgroundColor = '#10b981';
          style.fontWeight = 'bold';
        } else if (item.growth < 0) {
          style.backgroundColor = '#ef4444';
          style.color = '#ffffff';
        }
        break;
        
      case 'status':
        if (item.status === 'active') {
          style.backgroundColor = '#10b981';
        } else if (item.status === 'at_risk') {
          style.backgroundColor = '#f59e0b';
        }
        break;
        
      default:
        // No default style
        break;
    }
    
    return style;
  }

  /**
   * Export learning data for persistence
   */
  exportLearning(): any {
    return {
      memory: Array.from(this.learningMemory.entries()),
      patterns: Array.from(this.formattingPatterns.entries()).map(([key, rules]) => ({
        context: key,
        rules: rules.map(r => ({
          priority: r.priority,
          style: r.style
        }))
      }))
    };
  }

  /**
   * Import learning data
   */
  importLearning(data: any) {
    if (data.memory) {
      this.learningMemory = new Map(data.memory);
    }
    if (data.patterns) {
      data.patterns.forEach((p: any) => {
        this.formattingPatterns.set(p.context, p.rules);
      });
    }
  }
}

// Export singleton instance
export const visualFormattingAgent = new VisualFormattingAgent();

// Excel export helper
export function prepareForExcelExport(formattedData: any): any {
  // Convert our formatted data to Excel-compatible structure
  if (formattedData.type === 'dropdown') {
    return {
      value: formattedData.selected,
      validation: formattedData.excelValidation
    };
  }
  
  if (formattedData.type === 'multiselect') {
    return {
      value: formattedData.excelValue,
      validation: formattedData.excelValidation
    };
  }
  
  if (formattedData.cells) {
    // Heatmap or table
    return formattedData.cells.map((row: any[]) => 
      row.map((cell: any) => ({
        value: cell.value,
        style: {
          fill: cell.color ? {
            type: 'pattern',
            pattern: 'solid',
            fgColor: { argb: cell.color.replace('#', 'FF') }
          } : undefined
        }
      }))
    );
  }
  
  return formattedData;
}