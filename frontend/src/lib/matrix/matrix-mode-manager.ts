/**
 * Matrix Mode Manager
 * 
 * Manages matrix modes (Portfolio, Query, Custom, LP) and mode-specific configurations
 */

import { MatrixMode } from './matrix-api-service';
import { MatrixColumn } from '@/components/matrix/UnifiedMatrix';

export interface ModeConfig {
  mode: MatrixMode;
  label: string;
  description: string;
  defaultColumns: string[];
  availableFields: string[];
  showQueryBar: boolean;
  showInsights: boolean;
  primaryDataSource: 'portfolio' | 'query' | 'custom' | 'lp';
}

export const MODE_CONFIGS: Record<MatrixMode, ModeConfig> = {
  portfolio: {
    mode: 'portfolio',
    label: 'Portfolio',
    description: 'Fund context, companies, metrics, valuation, docs',
    defaultColumns: ['company', 'sector', 'arr', 'valuation', 'ownership', 'nav'],
    availableFields: [
      'company',
      'company_data',
      'valuation',
      'nav',
      'documents',
      'charts',
      'analytics',
    ],
    showQueryBar: false,
    showInsights: false,
    primaryDataSource: 'portfolio',
  },
  query: {
    mode: 'query',
    label: 'Query / Insights',
    description: 'NL matrix queries, dynamic columns',
    defaultColumns: ['company', 'metric1', 'metric2', 'metric3'],
    availableFields: [
      'company',
      'valuation',
      'documents',
      'charts',
      'analytics',
      'citations',
    ],
    showQueryBar: true,
    showInsights: true,
    primaryDataSource: 'query',
  },
  custom: {
    mode: 'custom',
    label: 'Custom / Sourcing',
    description: '@CompanyName, open-ended queries, portfolio-as-context',
    defaultColumns: ['company', 'sector', 'arr', 'valuation'],
    availableFields: [
      'company',
      'company_data',
      'valuation',
      'documents',
      'charts',
      'analytics',
      'citations',
    ],
    showQueryBar: true,
    showInsights: true,
    primaryDataSource: 'custom',
  },
  lp: {
    mode: 'lp',
    label: 'LP',
    description: 'LP directory, fund accounting, capital calls, DPI tracking',
    defaultColumns: ['lpName', 'lpType', 'status', 'commitment', 'called', 'distributed', 'unfunded', 'dpi', 'coInvest', 'vintageYear', 'contactName', 'capacity'],
    availableFields: [
      'lp_data',
      'fund_metrics',
      'documents',
      'analytics',
    ],
    showQueryBar: false,
    showInsights: false,
    primaryDataSource: 'lp',
  },
};

/**
 * Get configuration for a mode
 */
export function getModeConfig(mode: MatrixMode): ModeConfig {
  return MODE_CONFIGS[mode];
}

/**
 * Get available fields for a mode
 */
export function getAvailableFields(mode: MatrixMode): string[] {
  return MODE_CONFIGS[mode].availableFields;
}

/**
 * Get default columns for a mode
 */
export function getDefaultColumns(mode: MatrixMode): string[] {
  return MODE_CONFIGS[mode].defaultColumns;
}

/**
 * Check if a field is available in a mode
 */
export function isFieldAvailableInMode(fieldId: string, mode: MatrixMode): boolean {
  return MODE_CONFIGS[mode].availableFields.includes(fieldId);
}

/**
 * Get all available modes
 */
export function getAllModes(): MatrixMode[] {
  return Object.keys(MODE_CONFIGS) as MatrixMode[];
}
