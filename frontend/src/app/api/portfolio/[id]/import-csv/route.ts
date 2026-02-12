import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

export const maxDuration = 120;

/**
 * POST /api/portfolio/[id]/import-csv
 * Accepts multipart form data with a CSV file.
 * Parses CSV, maps columns flexibly, and upserts into `companies` table.
 * Handles irregular columns via fuzzy matching + keyword extraction.
 * Returns column mapping used + results summary.
 */

// ── Fuzzy header matching ──────────────────────────────────────────
// Strips punctuation, collapses whitespace, removes common noise words
function normalizeHeader(h: string): string {
  return h
    .toLowerCase()
    .replace(/[_\-()[\]{}#*]/g, ' ')
    .replace(/\b(the|of|in|for|our|total|current|latest|usd|eur|gbp)\b/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

// Keyword-based fallback: if exact match fails, check if header *contains* a keyword
const KEYWORD_FALLBACKS: Array<[RegExp, string]> = [
  [/\b(company|portfolio|co)\b.*\bname\b|\bname\b.*\b(company|portfolio|co)\b/, 'name'],
  [/\bcompany\b/, 'name'],
  [/\barr\b|annual\s*recurring|annual\s*rev/, 'current_arr_usd'],
  [/\bmrr\b|monthly\s*recurring/, '_mrr'],
  [/\brevenue\b|\brev\b/, 'current_arr_usd'],
  [/\bvaluation\b|\bpost.?money\b|\bpre.?money\b/, 'current_valuation_usd'],
  [/\binvest(ed|ment)?\b|\bcheck\s*size\b|\bdeployed\b/, 'total_invested_usd'],
  [/\bownership\b|\bstake\b|\bequity\b.*%/, 'ownership_percentage'],
  [/\bburn\b|\bmonthly\s*spend\b|\bopex\b/, 'burn_rate_monthly_usd'],
  [/\brunway\b|\bmonths\s*(left|remaining)\b/, 'runway_months'],
  [/\bcash\b|\bbank\b|\bcash\s*balance\b/, 'cash_in_bank_usd'],
  [/\bgross\s*margin\b|\bgm\b/, 'gross_margin'],
  [/\bsector\b|\bindustry\b|\bvertical\b/, 'sector'],
  [/\bstage\b|\bround\b|\bseries\b/, 'funding_stage'],
  [/\bstatus\b|\bfunnel\b|\bdeal\s*stage\b/, 'funnel_status'],
  [/\bexit\s*(value|amount)\b/, 'exit_value_usd'],
  [/\bexit\s*(date|when)\b/, 'exit_date'],
  [/\bmoic\b|\bexit\s*multiple\b|\bmultiple\b/, 'exit_multiple'],
  [/\blead\b|\bpartner\b|\bdeal\s*lead\b/, 'investment_lead'],
  [/\bwebsite\b|\burl\b|\bdomain\b/, 'website'],
  [/\bhq\b|\bheadquarter\b|\blocation\b|\bcity\b|\bcountry\b/, 'headquarters'],
  [/\bdescription\b|\bnotes?\b|\bwhat\s*they\s*do\b/, 'description'],
  [/\bcurrency\b|\bccy\b/, '_currency'],
  [/\bfunding\b|\braised\b/, 'total_funding'],
  [/\bdate\b|\binvestment\s*date\b|\bfirst\b.*\bdate\b/, 'first_investment_date'],
];

function fuzzyMatchHeader(raw: string, exactMap: Record<string, string>): string | null {
  const norm = normalizeHeader(raw);
  // 1. Exact match on normalized
  if (exactMap[norm]) return exactMap[norm];
  // 2. Exact match on original lowercase
  const lower = raw.toLowerCase().trim();
  if (exactMap[lower]) return exactMap[lower];
  // 3. Keyword fallback
  for (const [pattern, field] of KEYWORD_FALLBACKS) {
    if (pattern.test(norm)) return field;
  }
  return null;
}

// ── Exact column map ───────────────────────────────────────────────
const COLUMN_MAP: Record<string, string> = {
  // Name
  'company': 'name', 'company name': 'name', 'name': 'name', 'portfolio company': 'name', 'companyname': 'name',
  // Sector
  'sector': 'sector', 'industry': 'sector', 'vertical': 'sector',
  // Stage
  'stage': 'funding_stage', 'funding stage': 'funding_stage', 'round': 'funding_stage', 'funding_stage': 'funding_stage',
  // Status
  'status': 'funnel_status', 'funnel status': 'funnel_status', 'deal status': 'funnel_status',
  // Revenue / ARR
  'arr': 'current_arr_usd', 'revenue': 'current_arr_usd', 'annual revenue': 'current_arr_usd',
  'mrr': '_mrr', // special handling: multiply by 12
  'current_arr_usd': 'current_arr_usd', 'current arr': 'current_arr_usd',
  // Investment
  'invested': 'total_invested_usd', 'total invested': 'total_invested_usd', 'check size': 'total_invested_usd',
  'investment amount': 'total_invested_usd', 'investment': 'total_invested_usd',
  'total_invested_usd': 'total_invested_usd',
  // Ownership
  'ownership': 'ownership_percentage', 'ownership %': 'ownership_percentage', 'ownership_pct': 'ownership_percentage',
  'ownership_percentage': 'ownership_percentage', 'stake': 'ownership_percentage',
  // Valuation
  'valuation': 'current_valuation_usd', 'current valuation': 'current_valuation_usd',
  'post-money': 'current_valuation_usd', 'post money': 'current_valuation_usd',
  'current_valuation_usd': 'current_valuation_usd',
  // Financials
  'burn rate': 'burn_rate_monthly_usd', 'monthly burn': 'burn_rate_monthly_usd', 'burn': 'burn_rate_monthly_usd',
  'runway': 'runway_months', 'runway months': 'runway_months',
  'gross margin': 'gross_margin', 'gm': 'gross_margin', 'gm%': 'gross_margin',
  'cash': 'cash_in_bank_usd', 'cash in bank': 'cash_in_bank_usd',
  // Dates
  'first investment date': 'first_investment_date', 'investment date': 'first_investment_date', 'date': 'first_investment_date',
  'exit date': 'exit_date',
  // Exit
  'exit value': 'exit_value_usd', 'exit_value_usd': 'exit_value_usd',
  'exit multiple': 'exit_multiple', 'moic': 'exit_multiple',
  // Lead
  'lead': 'investment_lead', 'deal lead': 'investment_lead', 'partner': 'investment_lead',
  // Description
  'description': 'description', 'notes': 'description', 'what they do': 'description',
  // Website
  'website': 'website', 'url': 'website',
  // Location
  'hq': 'headquarters', 'headquarters': 'headquarters', 'location': 'headquarters', 'city': 'headquarters',
  // Currency
  'currency': '_currency',
  // Total funding (external)
  'total funding': 'total_funding', 'total raised': 'total_funding',
};

function parseCSV(text: string): Array<Record<string, string>> {
  const lines = text.split(/\r?\n/).filter(l => l.trim());
  if (lines.length < 2) return [];

  // Parse header
  const headers = parseCSVLine(lines[0]);
  const rows: Array<Record<string, string>> = [];

  for (let i = 1; i < lines.length; i++) {
    const values = parseCSVLine(lines[i]);
    if (values.length === 0 || values.every(v => !v.trim())) continue;
    const row: Record<string, string> = {};
    headers.forEach((h, idx) => {
      row[h] = values[idx] || '';
    });
    rows.push(row);
  }
  return rows;
}

function parseCSVLine(line: string): string[] {
  const result: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (ch === ',' && !inQuotes) {
      result.push(current.trim());
      current = '';
    } else {
      current += ch;
    }
  }
  result.push(current.trim());
  return result;
}

function parseNumber(raw: string): number | null {
  if (!raw) return null;
  let str = raw.trim();

  // Handle parentheses as negative: (1,234) → -1234
  const isNegParen = str.startsWith('(') && str.endsWith(')');
  if (isNegParen) str = str.slice(1, -1);

  // Remove currency symbols and whitespace
  str = str.replace(/[$€£¥₹₹\s]/g, '');

  // Detect European notation (1.234.567,89 → 1234567.89)
  const europeanMatch = str.match(/^-?[\d.]+(,\d{1,2})$/);
  if (europeanMatch) {
    str = str.replace(/\./g, '').replace(',', '.');
  } else {
    // Standard: remove commas
    str = str.replace(/,/g, '');
  }

  if (!str) return null;

  // Handle suffixes: 1.5B, 200M, 50K, 1.2bn, 200mm, 50k
  const match = str.match(/^(-?[\d.]+)\s*([BMKbmk][nNmM]?)?$/);
  if (!match) return null;

  let value = parseFloat(match[1]);
  if (isNaN(value)) return null;

  const suffix = (match[2] || '').toUpperCase().charAt(0);
  if (suffix === 'B') value *= 1_000_000_000;
  else if (suffix === 'M') value *= 1_000_000;
  else if (suffix === 'K') value *= 1_000;

  return isNegParen ? -value : value;
}

function parseDate(raw: string): string | null {
  if (!raw) return null;
  const str = raw.trim();
  // Try ISO format first
  const iso = Date.parse(str);
  if (!isNaN(iso)) return new Date(iso).toISOString().split('T')[0];
  // Try DD/MM/YYYY or DD-MM-YYYY
  const dmy = str.match(/^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$/);
  if (dmy) {
    const year = dmy[3].length === 2 ? `20${dmy[3]}` : dmy[3];
    const month = dmy[2].padStart(2, '0');
    const day = dmy[1].padStart(2, '0');
    // If day > 12, it's DD/MM/YYYY; otherwise ambiguous, assume MM/DD/YYYY
    if (parseInt(dmy[1]) > 12) return `${year}-${month}-${day}`;
    return `${year}-${dmy[1].padStart(2, '0')}-${dmy[2].padStart(2, '0')}`;
  }
  // Try "Jan 2024", "March 2025" etc.
  const monthYear = str.match(/^(\w+)\s+(\d{4})$/);
  if (monthYear) {
    const d = new Date(`${monthYear[1]} 1, ${monthYear[2]}`);
    if (!isNaN(d.getTime())) return d.toISOString().split('T')[0];
  }
  return null;
}

function parsePercentage(raw: string): number | null {
  if (!raw) return null;
  const cleaned = raw.replace(/%/g, '').trim();
  const val = parseFloat(cleaned);
  if (isNaN(val)) return null;
  // If > 1, assume it's already a percentage (e.g., 15 = 15%)
  return val > 1 ? val : val * 100;
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: fundId } = await params;

    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase not configured' }, { status: 500 });
    }

    // Parse multipart form data
    const formData = await request.formData();
    const file = formData.get('file') as File | null;
    const columnOverrides = formData.get('columnMapping') as string | null;

    if (!file) {
      return NextResponse.json({ error: 'No file uploaded. Send as multipart form with field name "file".' }, { status: 400 });
    }

    const text = await file.text();
    const rows = parseCSV(text);

    if (rows.length === 0) {
      return NextResponse.json({ error: 'CSV is empty or has no data rows' }, { status: 400 });
    }

    // Build effective column mapping using exact + fuzzy matching
    const csvHeaders = Object.keys(rows[0]);
    let userOverrides: Record<string, string> = {};
    if (columnOverrides) {
      try { userOverrides = JSON.parse(columnOverrides); } catch { /* ignore */ }
    }

    const effectiveMapping: Record<string, string> = {};
    const unmappedHeaders: string[] = [];
    const usedDbFields = new Set<string>(); // prevent double-mapping

    for (const header of csvHeaders) {
      if (userOverrides[header]) {
        effectiveMapping[header] = userOverrides[header];
        usedDbFields.add(userOverrides[header]);
      } else {
        const match = fuzzyMatchHeader(header, COLUMN_MAP);
        if (match && !usedDbFields.has(match)) {
          effectiveMapping[header] = match;
          usedDbFields.add(match);
        } else {
          unmappedHeaders.push(header);
        }
      }
    }

    // Must have at least a name column
    const hasName = Object.values(effectiveMapping).includes('name');
    if (!hasName) {
      return NextResponse.json({
        error: 'Could not detect a company name column. Please include a "Company" or "Name" header.',
        detected_headers: csvHeaders,
        mapping: effectiveMapping,
      }, { status: 400 });
    }

    // Detect currency from mapping or data
    const currencyHeader = Object.entries(effectiveMapping).find(([, v]) => v === '_currency')?.[0];
    const defaultCurrency = 'USD';

    // Transform rows into company records
    const now = new Date().toISOString();
    const companyRecords: Array<Record<string, unknown>> = [];
    const skipped: string[] = [];

    const numericFields = new Set([
      'current_arr_usd', 'total_invested_usd', 'current_valuation_usd',
      'burn_rate_monthly_usd', 'runway_months', 'cash_in_bank_usd',
      'exit_value_usd', 'exit_multiple', 'total_funding',
    ]);
    const percentFields = new Set(['ownership_percentage', 'gross_margin']);
    const dateFields = new Set(['first_investment_date', 'exit_date']);

    for (const row of rows) {
      const record: Record<string, unknown> = {
        fund_id: fundId,
        updated_at: now,
      };

      let hasMRR = false;
      let mrrValue = 0;
      const currency = currencyHeader ? (row[currencyHeader] || defaultCurrency).toUpperCase().trim() : defaultCurrency;

      for (const [csvHeader, dbField] of Object.entries(effectiveMapping)) {
        const raw = row[csvHeader];
        if (!raw || !raw.trim()) continue;

        if (dbField === '_mrr') {
          const n = parseNumber(raw);
          if (n !== null) { hasMRR = true; mrrValue = n; }
          continue;
        }
        if (dbField === '_currency') continue;

        if (numericFields.has(dbField)) {
          const n = parseNumber(raw);
          if (n !== null) record[dbField] = n;
        } else if (percentFields.has(dbField)) {
          const p = parsePercentage(raw);
          if (p !== null) record[dbField] = p;
        } else if (dateFields.has(dbField)) {
          const d = parseDate(raw);
          if (d) record[dbField] = d;
        } else {
          record[dbField] = raw.trim();
        }
      }

      // MRR → ARR conversion
      if (hasMRR && !record.current_arr_usd) {
        record.current_arr_usd = mrrValue * 12;
      }

      // Store currency for non-USD entries in extra_data
      if (currency !== 'USD') {
        record.extra_data = { ...(record.extra_data as Record<string, unknown> || {}), reporting_currency: currency };
      }

      // Unmapped columns go into extra_data
      for (const header of unmappedHeaders) {
        const val = row[header]?.trim();
        if (val) {
          if (!record.extra_data) record.extra_data = {};
          (record.extra_data as Record<string, unknown>)[header] = val;
        }
      }

      if (!record.name) {
        skipped.push(`Row missing name: ${JSON.stringify(row).slice(0, 100)}`);
        continue;
      }

      companyRecords.push(record);
    }

    // Upsert in batches of 50 (match on name + fund_id)
    const batchSize = 50;
    let upserted = 0;
    let created = 0;
    let updated = 0;
    const errors: string[] = [];

    for (let i = 0; i < companyRecords.length; i += batchSize) {
      const batch = companyRecords.slice(i, i + batchSize);

      // Check which companies already exist
      const names = batch.map(r => r.name as string);
      const { data: existing } = await supabaseService
        .from('companies')
        .select('id, name')
        .eq('fund_id', fundId)
        .in('name', names);

      const existingMap = new Map((existing || []).map(c => [c.name.toLowerCase(), c.id]));

      const toInsert: Array<Record<string, unknown>> = [];
      const toUpdate: Array<{ id: string; data: Record<string, unknown> }> = [];

      for (const record of batch) {
        const existingId = existingMap.get((record.name as string).toLowerCase());
        if (existingId) {
          toUpdate.push({ id: existingId, data: record });
        } else {
          record.created_at = now;
          toInsert.push(record);
        }
      }

      // Insert new companies
      if (toInsert.length > 0) {
        const { data: insertResult, error: insertError } = await supabaseService
          .from('companies')
          .insert(toInsert)
          .select('id');

        if (insertError) {
          errors.push(`Insert batch ${Math.floor(i / batchSize) + 1}: ${insertError.message}`);
        } else {
          created += insertResult?.length || 0;
        }
      }

      // Update existing companies
      for (const { id, data } of toUpdate) {
        const { error: updateError } = await supabaseService
          .from('companies')
          .update(data)
          .eq('id', id);

        if (updateError) {
          errors.push(`Update ${data.name}: ${updateError.message}`);
        } else {
          updated++;
        }
      }

      upserted += batch.length;
    }

    return NextResponse.json({
      success: true,
      summary: {
        csvRows: rows.length,
        created,
        updated,
        skipped: skipped.length,
        errors: errors.length,
      },
      columnMapping: effectiveMapping,
      unmappedHeaders,
      skippedRows: skipped.slice(0, 10),
      errors: errors.slice(0, 10),
    });
  } catch (error) {
    console.error('Portfolio CSV import error:', error);
    return NextResponse.json(
      { error: 'Import failed', details: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}
