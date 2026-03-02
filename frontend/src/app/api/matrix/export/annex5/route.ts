import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';
import { MatrixData } from '@/components/matrix/UnifiedMatrix';

/**
 * Generate Annex 5 XML export for EU AIFMD compliance
 * This follows the EU AIFMD Annex 5 schema for portfolio holdings reporting
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { matrixData, fundId }: { matrixData: MatrixData; fundId?: string } = body;

    if (!matrixData) {
      return NextResponse.json({ error: 'Matrix data is required' }, { status: 400 });
    }

    // Get fund information if fundId provided
    let fundInfo: any = null;
    let navTimeSeries: Record<string, Array<{ date: string; value: number }>> = {};
    
    if (fundId && supabaseService) {
      const { data: fund } = await supabaseService
        .from('funds')
        .select('*')
        .eq('id', fundId)
        .single();
      fundInfo = fund;

      // Fetch NAV time series for companies in the matrix
      const companyIds = matrixData.rows
        .filter(row => row.companyId)
        .map(row => row.companyId!)
        .filter((id): id is string => !!id);

      if (companyIds.length > 0) {
        try {
          const navResponse = await fetch(
            `${process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000'}/api/portfolio/${fundId}/nav-timeseries?companyIds=${companyIds.join(',')}`
          );
          if (navResponse.ok) {
            navTimeSeries = await navResponse.json();
          }
        } catch (err) {
          console.warn('Could not fetch NAV time series:', err);
          // Continue without NAV data
        }
      }
    }

    // Determine reporting period (default to last quarter)
    const now = new Date();
    const quarterStart = new Date(now.getFullYear(), Math.floor(now.getMonth() / 3) * 3, 1);
    const quarterEnd = new Date(quarterStart.getFullYear(), quarterStart.getMonth() + 3, 0);

    // Build EU AIFMD XML structure
    const xmlLines: string[] = [];
    xmlLines.push('<?xml version="1.0" encoding="UTF-8"?>');
    xmlLines.push('<AIFMDReport xmlns="http://www.esma.europa.eu/aifmd/reporting">');
    
    // Report Header
    xmlLines.push('  <ReportHeader>');
    xmlLines.push('    <AIFMIdentifier>');
    if (fundInfo?.lei_code) {
      xmlLines.push(`      <LEI>${escapeXml(fundInfo.lei_code)}</LEI>`);
    }
    xmlLines.push(`      <Name>${escapeXml(fundInfo?.name || 'Unknown AIFM')}</Name>`);
    xmlLines.push('    </AIFMIdentifier>');
    
    xmlLines.push('    <AIFIdentifier>');
    if (fundInfo?.lei_code) {
      xmlLines.push(`      <LEI>${escapeXml(fundInfo.lei_code)}</LEI>`);
    }
    xmlLines.push(`      <Name>${escapeXml(fundInfo?.name || 'Unknown AIF')}</Name>`);
    if (fundInfo?.jurisdiction) {
      xmlLines.push(`      <Jurisdiction>${escapeXml(fundInfo.jurisdiction)}</Jurisdiction>`);
    }
    xmlLines.push('    </AIFIdentifier>');
    
    xmlLines.push('    <ReportingPeriod>');
    xmlLines.push(`      <StartDate>${quarterStart.toISOString().split('T')[0]}</StartDate>`);
    xmlLines.push(`      <EndDate>${quarterEnd.toISOString().split('T')[0]}</EndDate>`);
    xmlLines.push('    </ReportingPeriod>');
    xmlLines.push(`    <ReportDate>${now.toISOString().split('T')[0]}</ReportDate>`);
    xmlLines.push('  </ReportHeader>');
    
    // Portfolio Holdings
    xmlLines.push('  <PortfolioHoldings>');
    
    for (const row of matrixData.rows) {
      const companyName = row.companyName || row.cells['company']?.value || 'Unknown';
      const companyId = row.companyId;
      
      xmlLines.push('    <Holding>');
      
      // Company Identifier
      xmlLines.push('      <CompanyIdentifier>');
      xmlLines.push(`        <Name>${escapeXml(String(companyName))}</Name>`);
      // Try to get LEI from company data if available
      const companyLEI = row.cells['lei']?.value || row.cells['LEI']?.value;
      if (companyLEI) {
        xmlLines.push(`        <LEI>${escapeXml(String(companyLEI))}</LEI>`);
      }
      const jurisdiction = row.cells['jurisdiction']?.value || row.cells['country']?.value;
      if (jurisdiction) {
        xmlLines.push(`        <Jurisdiction>${escapeXml(String(jurisdiction))}</Jurisdiction>`);
      }
      xmlLines.push('      </CompanyIdentifier>');
      
      // Investment Details
      xmlLines.push('      <InvestmentDetails>');
      const ownership = row.cells['ownership']?.value || row.cells['ownership_percentage']?.value;
      if (ownership !== undefined && ownership !== null) {
        xmlLines.push(`        <OwnershipPercentage>${escapeXml(String(ownership))}</OwnershipPercentage>`);
      }
      const investmentDate = row.cells['investment_date']?.value || row.cells['date']?.value;
      if (investmentDate) {
        xmlLines.push(`        <InvestmentDate>${escapeXml(String(investmentDate))}</InvestmentDate>`);
      }
      xmlLines.push('      </InvestmentDetails>');
      
      // Valuation
      xmlLines.push('      <Valuation>');
      const valuation = row.cells['valuation']?.value || row.cells['fair_value']?.value;
      if (valuation !== undefined && valuation !== null) {
        xmlLines.push(`        <FairValue>${escapeXml(String(valuation))}</FairValue>`);
      }
      
      // Valuation Method
      const valuationMethod = row.cells['valuation_method']?.value || 'Market Multiple';
      xmlLines.push(`        <ValuationMethod>${escapeXml(String(valuationMethod))}</ValuationMethod>`);
      
      // Confidence Score
      const confidence = row.cells['valuation']?.metadata?.confidence || 
                        row.cells['valuation']?.metadata?.confidence ||
                        matrixData.metadata?.confidence;
      if (confidence !== undefined) {
        xmlLines.push(`        <ConfidenceScore>${(confidence * 100).toFixed(1)}</ConfidenceScore>`);
      }
      xmlLines.push('      </Valuation>');
      
      // NAV with Time Series
      xmlLines.push('      <NAV>');
      if (companyId && navTimeSeries[companyId] && navTimeSeries[companyId].length > 0) {
        const latestNav = navTimeSeries[companyId][navTimeSeries[companyId].length - 1];
        xmlLines.push(`        <Value>${latestNav.value.toFixed(2)}</Value>`);
        
        xmlLines.push('        <TimeSeries>');
        for (const point of navTimeSeries[companyId]) {
          xmlLines.push('          <DataPoint>');
          xmlLines.push(`            <Date>${point.date}</Date>`);
          xmlLines.push(`            <Value>${point.value.toFixed(2)}</Value>`);
          xmlLines.push('          </DataPoint>');
        }
        xmlLines.push('        </TimeSeries>');
      } else {
        // Fallback to calculated NAV if time series not available
        const arr = row.cells['arr']?.value || 0;
        const ownershipPct = (ownership || 0) / 100;
        const estimatedNav = arr * 10 * ownershipPct; // Simple multiple
        xmlLines.push(`        <Value>${estimatedNav.toFixed(2)}</Value>`);
      }
      xmlLines.push('      </NAV>');
      
      // Financial Metrics
      xmlLines.push('      <FinancialMetrics>');
      
      // Export all relevant financial metrics from matrix
      const metricColumns = ['arr', 'revenue', 'burn_rate', 'runway', 'gross_margin', 'cash_in_bank'];
      for (const column of matrixData.columns) {
        const columnId = column.id.toLowerCase();
        if (metricColumns.includes(columnId) || column.type === 'currency' || column.type === 'number') {
          const cell = row.cells[column.id];
          if (cell && (cell.value !== null && cell.value !== undefined)) {
            xmlLines.push(`        <${escapeXml(column.name)}>`);
            xmlLines.push(`          <Value>${escapeXml(String(cell.value))}</Value>`);
            if (cell.lastUpdated) {
              xmlLines.push(`          <LastUpdated>${escapeXml(cell.lastUpdated)}</LastUpdated>`);
            }
            if (cell.source) {
              xmlLines.push(`          <Source>${escapeXml(cell.source)}</Source>`);
            }
            xmlLines.push(`        </${escapeXml(column.name)}>`);
          }
        }
      }
      
      xmlLines.push('      </FinancialMetrics>');
      xmlLines.push('    </Holding>');
    }
    
    xmlLines.push('  </PortfolioHoldings>');
    
    // Fund Context
    xmlLines.push('  <FundContext>');
    if (fundInfo?.fund_size_usd) {
      xmlLines.push(`    <FundSize>${fundInfo.fund_size_usd}</FundSize>`);
    }
    if (fundInfo?.strategy) {
      xmlLines.push(`    <Strategy>${escapeXml(fundInfo.strategy)}</Strategy>`);
    }
    if (fundInfo?.stage_focus) {
      xmlLines.push(`    <StageFocus>${escapeXml(fundInfo.stage_focus)}</StageFocus>`);
    }
    xmlLines.push(`    <TotalHoldings>${matrixData.rows.length}</TotalHoldings>`);
    xmlLines.push('  </FundContext>');
    
    // Audit Trail
    xmlLines.push('  <AuditTrail>');
    xmlLines.push(`    <TotalEdits>${matrixData.rows.reduce((count, row) => {
      return count + Object.values(row.cells).filter(cell => cell?.source === 'manual').length;
    }, 0)}</TotalEdits>`);
    xmlLines.push(`    <TotalCompanies>${matrixData.rows.length}</TotalCompanies>`);
    xmlLines.push(`    <ExportTimestamp>${new Date().toISOString()}</ExportTimestamp>`);
    xmlLines.push('  </AuditTrail>');
    
    // Data Source Metadata
    xmlLines.push('  <DataSourceMetadata>');
    xmlLines.push(`    <LastUpdated>${matrixData.metadata?.lastUpdated || new Date().toISOString()}</LastUpdated>`);
    if (matrixData.metadata?.query) {
      xmlLines.push(`    <Query>${escapeXml(matrixData.metadata.query)}</Query>`);
    }
    xmlLines.push(`    <DataSource>${escapeXml(matrixData.metadata?.dataSource || 'matrix-export')}</DataSource>`);
    xmlLines.push('  </DataSourceMetadata>');
    
    xmlLines.push('</AIFMDReport>');
    
    const xml = xmlLines.join('\n');
    
    // Return as XML file
    return new NextResponse(xml, {
      headers: {
        'Content-Type': 'application/xml',
        'Content-Disposition': `attachment; filename="aifmd-annex5-${Date.now()}.xml"`,
      },
    });
  } catch (error) {
    console.error('Error generating AIFMD Annex 5 XML export:', error);
    return NextResponse.json(
      { error: 'Failed to generate XML export', message: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}

function escapeXml(str: string): string {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}
