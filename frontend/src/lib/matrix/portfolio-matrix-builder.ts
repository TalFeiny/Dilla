/**
 * Build MatrixData from portfolio companies for instant display.
 * Used when portfolio page already has companies from the initial load - avoids
 * a second fetch and ensures the grid shows data immediately.
 */
import type { MatrixData, MatrixColumn, MatrixRow, MatrixCell } from '@/components/matrix/UnifiedMatrix';
import { formatCurrency } from '@/lib/matrix/cell-formatters';

const DEFAULT_PORTFOLIO_COLUMNS: MatrixColumn[] = [
  { id: 'company', name: 'Company', type: 'text', width: 200, editable: true },
  { id: 'documents', name: 'Documents', type: 'text', width: 140, editable: false },
  { id: 'sector', name: 'Sector', type: 'text', width: 120, editable: true },
  { id: 'arr', name: 'ARR', type: 'currency', width: 120, editable: true },
  { id: 'burnRate', name: 'Burn Rate', type: 'currency', width: 120, editable: true },
  { id: 'runway', name: 'Runway (mo)', type: 'number', width: 100, editable: true },
  { id: 'grossMargin', name: 'Gross Margin', type: 'percentage', width: 120, editable: true },
  { id: 'cashInBank', name: 'Cash in Bank', type: 'currency', width: 140, editable: true },
  { id: 'valuation', name: 'Valuation', type: 'currency', width: 140, editable: true },
  { id: 'ownership', name: 'Ownership %', type: 'percentage', width: 120, editable: true },
  { id: 'optionPool', name: 'Option Pool (bps)', type: 'number', width: 120, editable: true },
  { id: 'latestUpdate', name: 'Latest Update', type: 'text', width: 160, editable: true },
  { id: 'productUpdates', name: 'Product Updates', type: 'text', width: 160, editable: true },
];

export interface PortfolioCompanyForMatrix {
  id: string;
  name: string;
  sector?: string;
  stage?: string;
  investmentAmount?: number;
  ownershipPercentage?: number;
  currentArr?: number;
  valuation?: number;
  investmentDate?: string;
  investmentLead?: string;
  lastContacted?: string;
  burnRate?: number;
  runwayMonths?: number;
  grossMargin?: number;
  cashInBank?: number;
  [key: string]: unknown;
}

export function buildMatrixDataFromPortfolioCompanies(
  companies: PortfolioCompanyForMatrix[],
  fundId: string
): MatrixData {
  const columns = DEFAULT_PORTFOLIO_COLUMNS;
  const rows: MatrixRow[] = companies.map((company) => {
    const currentArr = company.currentArr ?? 0;
    const investmentAmount = company.investmentAmount ?? 0;
    const ownershipPercentage = company.ownershipPercentage ?? 0;
    const valuation = company.valuation ?? (currentArr * 10);
    const ownership = ownershipPercentage / 100;

    const cells: Record<string, MatrixCell> = {};
    columns.forEach((col) => {
      const colId = col.id.toLowerCase();
      let value: unknown = null;
      let source: MatrixCell['source'] = 'manual';
      let displayValue: string | undefined;

      if (colId === 'company' || colId === 'companyname') {
        value = company.name;
        source = 'api';
      } else if (colId === 'sector') {
        value = company.sector || '-';
        source = 'api';
      } else if (colId === 'arr') {
        value = currentArr;
        displayValue = formatCurrency(currentArr);
        source = 'document';
      } else if (colId === 'burnrate' || colId === 'burn_rate') {
        value = company.burnRate ?? 0;
        displayValue = formatCurrency(company.burnRate);
        source = 'document';
      } else if (colId === 'runway') {
        value = company.runwayMonths ?? 0;
        displayValue = company.runwayMonths ? `${company.runwayMonths}m` : '-';
        source = 'document';
      } else if (colId === 'grossmargin' || colId === 'gross_margin') {
        const gm = company.grossMargin ?? 0;
        value = gm > 1 ? gm / 100 : gm; // API may return 75 for 75% or 0.75
        displayValue = company.grossMargin != null ? `${((value as number) * 100).toFixed(1)}%` : '-';
        source = 'document';
      } else if (colId === 'cashinbank' || colId === 'cash_in_bank') {
        value = company.cashInBank ?? 0;
        displayValue = formatCurrency(company.cashInBank);
        source = 'document';
      } else if (colId === 'valuation') {
        value = valuation;
        displayValue = formatCurrency(valuation);
        source = 'formula';
      } else if (colId === 'ownership' || colId === 'ownership%') {
        value = ownershipPercentage;
        displayValue = ownershipPercentage ? `${ownershipPercentage.toFixed(1)}%` : '-';
        source = 'api';
      } else if (colId === 'invested') {
        value = investmentAmount;
        displayValue = formatCurrency(investmentAmount);
        source = 'api';
      } else if (colId === 'investmentdate' || colId === 'first_investment_date') {
        value = company.investmentDate ?? null;
        displayValue = value ? String(value) : undefined;
        source = 'api';
      } else if (colId === 'lead' || colId === 'investment_lead') {
        value = company.investmentLead ?? null;
        displayValue = value != null && value !== '' ? String(value) : undefined;
        source = 'api';
      } else if (colId === 'documents') {
        const docs = company.documents;
        const docList = Array.isArray(docs) ? docs : [];
        value = docList.length > 0 ? docList : null;
        displayValue = docList.length === 0 ? undefined : docList.length === 1 ? '1 document' : `${docList.length} documents`;
        source = docList.length > 0 ? 'document' : 'manual';
      }

      cells[col.id] = {
        value,
        source,
        ...(displayValue !== undefined && { displayValue }),
      };
    });

    return {
      id: company.id,
      companyId: company.id,
      companyName: company.name,
      cells,
    };
  });

  return {
    columns,
    rows,
    metadata: {
      lastUpdated: new Date().toISOString(),
      dataSource: 'portfolio',
      fundId,
    },
  };
}
