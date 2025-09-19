import { IFormatHandler } from './types';
import { SpreadsheetHandler } from './spreadsheet-handler';
import { DeckHandler } from './deck-handler';
import { MatrixHandler } from './matrix-handler';
import { DocsHandler } from './docs-handler';
import { MarketAnalysisHandler } from './market-analysis-handler';
import { AnalysisHandler } from './analysis-handler';
import { DefaultHandler } from './default-handler';

/**
 * Factory for creating format handlers
 * Maps output formats to their specific handler implementations
 */
export class FormatHandlerFactory {
  private static handlers: Map<string, IFormatHandler> = new Map();
  
  // Initialize default handlers
  static {
    this.registerHandler('spreadsheet', new SpreadsheetHandler());
    this.registerHandler('deck', new DeckHandler());
    this.registerHandler('matrix', new MatrixHandler());
    this.registerHandler('docs', new DocsHandler());
    this.registerHandler('market-analysis', new MarketAnalysisHandler());
    this.registerHandler('audit-analysis', new MarketAnalysisHandler());
    this.registerHandler('fund-operations', new MarketAnalysisHandler());
    this.registerHandler('analysis', new AnalysisHandler());
    
    // Aliases for alternative format names
    this.registerHandler('excel', new SpreadsheetHandler());
    this.registerHandler('presentation', new DeckHandler());
    this.registerHandler('table', new MatrixHandler());
    this.registerHandler('csv', new MatrixHandler());
    this.registerHandler('document', new DocsHandler());
  }
  
  /**
   * Get a handler for the specified format
   */
  static getHandler(format: string): IFormatHandler | null {
    return this.handlers.get(format.toLowerCase()) || null;
  }
  
  /**
   * Register a new handler for a format
   */
  static registerHandler(format: string, handler: IFormatHandler): void {
    this.handlers.set(format.toLowerCase(), handler);
  }
  
  /**
   * Check if a format is supported
   */
  static isFormatSupported(format: string): boolean {
    return this.handlers.has(format.toLowerCase());
  }
  
  /**
   * Get all supported formats
   */
  static getSupportedFormats(): string[] {
    return Array.from(this.handlers.keys());
  }
}