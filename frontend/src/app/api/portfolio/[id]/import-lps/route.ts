import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

export const maxDuration = 120;

/**
 * POST /api/portfolio/[id]/import-lps
 * Accepts multipart form data with a CSV file.
 * Creates/updates limited_partners AND lp_fund_commitments (many-to-many).
 * Handles: commitments, ownership, side letters, fee agreements, co-invest rights.
 * Fuzzy header matching for irregular CSVs.
 */

// ── Fuzzy header matching ──────────────────────────────────────────
function normalizeHeader(h: string): string {
  return h
    .toLowerCase()
    .replace(/[_\-()[\]{}#*]/g, ' ')
    .replace(/\b(the|of|in|for|our|total|current|latest|usd|eur|gbp)\b/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

const LP_KEYWORD_FALLBACKS: Array<[RegExp, string]> = [
  [/\b(lp|investor|partner)\b.*\bname\b|\bname\b/, 'name'],
  [/\btype\b|\bcategory\b/, 'lp_type'],
  [/\bcommit(ment|ted)?\b/, '_commitment'],
  [/\bcall(ed)?\b|\bdrawn\b|\bdraw\s*down\b/, '_called'],
  [/\bdistribut(ed|ion)\b/, '_distributed'],
  [/\bownership\b|\bstake\b|\bshare\b/, '_ownership'],
  [/\bmanagement\s*fee\b|\bmgmt\b.*\bfee\b/, '_mgmt_fee'],
  [/\bcarr(y|ied)\b|\bperformance\s*fee\b/, '_carry'],
  [/\bhurdle\b|\bpreferred\s*return\b/, '_pref_return'],
  [/\bco.?invest\b/, '_co_invest'],
  [/\bmfn\b|\bfavou?red\s*nation\b/, '_mfn'],
  [/\badvisory\b|\bboard\b/, '_advisory'],
  [/\bopt.?out\b/, '_opt_out'],
  [/\bside\s*letter\b|\bspecial\s*terms\b/, '_side_letter'],
  [/\bnet\s*worth\b|\baum\b|\bassets?\b/, '_net_worth'],
  [/\bcapacity\b/, 'investment_capacity_usd'],
  [/\bvintage\b/, '_vintage'],
  [/\bstatus\b/, '_status'],
  [/\bcurrency\b|\bccy\b/, '_currency'],
  [/\bfund\b.*\bname\b|\bfund\b/, '_fund_name'],
  [/\bemail\b/, 'contact_email'],
  [/\bphone\b/, 'contact_phone'],
  [/\bcontact\b/, 'contact_name'],
];

function fuzzyMatchLPHeader(raw: string, exactMap: Record<string, string>): string | null {
  const norm = normalizeHeader(raw);
  if (exactMap[norm]) return exactMap[norm];
  const lower = raw.toLowerCase().trim();
  if (exactMap[lower]) return exactMap[lower];
  for (const [pattern, field] of LP_KEYWORD_FALLBACKS) {
    if (pattern.test(norm)) return field;
  }
  return null;
}

const LP_COLUMN_MAP: Record<string, string> = {
  // LP identity
  'name': 'name', 'lp name': 'name', 'investor': 'name', 'investor name': 'name', 'limited partner': 'name',
  'lp': 'name',
  // Type
  'type': 'lp_type', 'lp type': 'lp_type', 'investor type': 'lp_type', 'category': 'lp_type',
  // Contact
  'contact': 'contact_name', 'contact name': 'contact_name', 'primary contact': 'contact_name',
  'email': 'contact_email', 'contact email': 'contact_email',
  'phone': 'contact_phone', 'contact phone': 'contact_phone',
  // Commitment / capital account
  'commitment': '_commitment', 'commitment amount': '_commitment', 'committed': '_commitment',
  'commitment_usd': '_commitment', 'total commitment': '_commitment',
  'called': '_called', 'called capital': '_called', 'drawn': '_called', 'called_usd': '_called',
  'distributed': '_distributed', 'distributions': '_distributed', 'distributed_usd': '_distributed',
  'recallable': '_recallable', 'recallable_usd': '_recallable',
  // Ownership
  'ownership': '_ownership', 'ownership %': '_ownership', 'lp ownership': '_ownership', 'share': '_ownership',
  // Fee terms
  'management fee': '_mgmt_fee', 'mgmt fee': '_mgmt_fee', 'management fee %': '_mgmt_fee',
  'carry': '_carry', 'carried interest': '_carry', 'carry %': '_carry',
  'preferred return': '_pref_return', 'hurdle': '_pref_return', 'hurdle rate': '_pref_return',
  // Side letter
  'co-invest': '_co_invest', 'co invest': '_co_invest', 'co-investment': '_co_invest',
  'co-invest rights': '_co_invest',
  'mfn': '_mfn', 'most favored nation': '_mfn', 'mfn clause': '_mfn',
  'advisory board': '_advisory', 'board seat': '_advisory',
  'opt-out': '_opt_out', 'opt out rights': '_opt_out', 'sector opt-out': '_opt_out',
  'side letter': '_side_letter', 'side letter terms': '_side_letter', 'special terms': '_side_letter',
  // Investment capacity
  'capacity': 'investment_capacity_usd', 'investment capacity': 'investment_capacity_usd',
  'net worth': '_net_worth', 'aum': 'investment_capacity_usd',
  // Vintage
  'vintage': '_vintage', 'vintage year': '_vintage',
  // Status
  'status': '_status', 'lp status': '_status',
  // Currency
  'currency': '_currency', 'commitment currency': '_currency',
  // Fund name (for multi-fund CSVs)
  'fund': '_fund_name', 'fund name': '_fund_name',
};

function parseCSV(text: string): Array<Record<string, string>> {
  const lines = text.split(/\r?\n/).filter(l => l.trim());
  if (lines.length < 2) return [];
  const headers = parseCSVLine(lines[0]);
  const rows: Array<Record<string, string>> = [];
  for (let i = 1; i < lines.length; i++) {
    const values = parseCSVLine(lines[i]);
    if (values.length === 0 || values.every(v => !v.trim())) continue;
    const row: Record<string, string> = {};
    headers.forEach((h, idx) => { row[h] = values[idx] || ''; });
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
      if (inQuotes && line[i + 1] === '"') { current += '"'; i++; }
      else inQuotes = !inQuotes;
    } else if (ch === ',' && !inQuotes) {
      result.push(current.trim()); current = '';
    } else { current += ch; }
  }
  result.push(current.trim());
  return result;
}

function parseNumber(raw: string): number | null {
  if (!raw) return null;
  let str = raw.trim();
  const isNegParen = str.startsWith('(') && str.endsWith(')');
  if (isNegParen) str = str.slice(1, -1);
  str = str.replace(/[$€£¥₹\s]/g, '');
  // European notation
  if (/^-?[\d.]+(,\d{1,2})$/.test(str)) {
    str = str.replace(/\./g, '').replace(',', '.');
  } else {
    str = str.replace(/,/g, '');
  }
  if (!str) return null;
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

function parsePercentage(raw: string): number | null {
  if (!raw) return null;
  const cleaned = raw.replace(/%/g, '').trim();
  const val = parseFloat(cleaned);
  if (isNaN(val)) return null;
  return val;
}

function parseBool(raw: string): boolean {
  const v = raw.toLowerCase().trim();
  return ['yes', 'true', '1', 'y', 'x', '✓', '✔'].includes(v);
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

    const formData = await request.formData();
    const file = formData.get('file') as File | null;
    const columnOverrides = formData.get('columnMapping') as string | null;

    if (!file) {
      return NextResponse.json({ error: 'No file uploaded' }, { status: 400 });
    }

    const text = await file.text();
    const rows = parseCSV(text);
    if (rows.length === 0) {
      return NextResponse.json({ error: 'CSV is empty' }, { status: 400 });
    }

    // Build mapping
    const csvHeaders = Object.keys(rows[0]);
    let userOverrides: Record<string, string> = {};
    if (columnOverrides) { try { userOverrides = JSON.parse(columnOverrides); } catch { /* */ } }

    const effectiveMapping: Record<string, string> = {};
    const unmappedHeaders: string[] = [];
    const usedDbFields = new Set<string>();
    for (const header of csvHeaders) {
      if (userOverrides[header]) {
        effectiveMapping[header] = userOverrides[header];
        usedDbFields.add(userOverrides[header]);
      } else {
        const match = fuzzyMatchLPHeader(header, LP_COLUMN_MAP);
        if (match && !usedDbFields.has(match)) {
          effectiveMapping[header] = match;
          usedDbFields.add(match);
        } else {
          unmappedHeaders.push(header);
        }
      }
    }

    const hasName = Object.values(effectiveMapping).includes('name');
    if (!hasName) {
      return NextResponse.json({
        error: 'Could not detect an LP name column.',
        detected_headers: csvHeaders,
      }, { status: 400 });
    }

    // Get org ID from fund or first company
    const { data: orgData } = await supabaseService
      .from('companies')
      .select('organization_id')
      .eq('fund_id', fundId)
      .limit(1)
      .single();
    const orgId = orgData?.organization_id;

    const now = new Date().toISOString();
    let lpCreated = 0;
    let lpUpdated = 0;
    let commitmentsCreated = 0;
    const errors: string[] = [];
    const skipped: string[] = [];

    for (const row of rows) {
      // Extract fields from row
      const lpData: Record<string, unknown> = {};
      const commitmentData: Record<string, unknown> = { fund_id: fundId };
      let netWorth: number | null = null;

      for (const [csvHeader, dbField] of Object.entries(effectiveMapping)) {
        const raw = row[csvHeader]?.trim();
        if (!raw) continue;

        switch (dbField) {
          // LP fields
          case 'name': lpData.name = raw; break;
          case 'lp_type': lpData.lp_type = raw.toLowerCase().replace(/\s+/g, '_'); break;
          case 'contact_name': lpData.contact_name = raw; break;
          case 'contact_email': lpData.contact_email = raw; break;
          case 'contact_phone': lpData.contact_phone = raw; break;
          case 'investment_capacity_usd': lpData.investment_capacity_usd = parseNumber(raw); break;
          case '_net_worth': netWorth = parseNumber(raw); break;
          case '_status': lpData.status = raw.toLowerCase(); break;

          // Commitment fields
          case '_commitment': commitmentData.commitment_usd = parseNumber(raw) || 0; break;
          case '_called': commitmentData.called_usd = parseNumber(raw) || 0; break;
          case '_distributed': commitmentData.distributed_usd = parseNumber(raw) || 0; break;
          case '_recallable': commitmentData.recallable_usd = parseNumber(raw) || 0; break;
          case '_ownership': commitmentData.ownership_pct = parsePercentage(raw) || 0; break;
          case '_mgmt_fee': commitmentData.management_fee_pct = parsePercentage(raw); break;
          case '_carry': commitmentData.carried_interest_pct = parsePercentage(raw); break;
          case '_pref_return': commitmentData.preferred_return_pct = parsePercentage(raw); break;
          case '_vintage': commitmentData.vintage_year = parseInt(raw) || null; break;
          case '_currency': commitmentData.commitment_currency = raw.toUpperCase().slice(0, 3); break;

          // Side letter booleans
          case '_co_invest': commitmentData.co_invest_rights = parseBool(raw); break;
          case '_mfn': commitmentData.mfn_clause = parseBool(raw); break;
          case '_advisory': commitmentData.advisory_board_seat = parseBool(raw); break;
          case '_opt_out':
            commitmentData.opt_out_rights = raw.split(/[,;]/).map(s => s.trim()).filter(Boolean);
            break;
          case '_side_letter':
            commitmentData.side_letter_terms = { notes: raw };
            break;

          // Ignore fund name for now (we use the URL param)
          case '_fund_name': break;

          default:
            // Direct LP fields
            lpData[dbField] = raw;
        }
      }

      // Net worth → investment capacity fallback
      if (netWorth && !lpData.investment_capacity_usd) {
        lpData.investment_capacity_usd = netWorth * 0.01;
        if (!lpData.investment_focus) lpData.investment_focus = {};
        (lpData.investment_focus as Record<string, unknown>).net_worth_usd = netWorth;
      }

      if (!lpData.name) {
        skipped.push(`Row missing name: ${JSON.stringify(row).slice(0, 80)}`);
        continue;
      }

      lpData.updated_at = now;
      if (orgId) lpData.organization_id = orgId;
      if (!lpData.status) lpData.status = 'active';

      try {
        // Upsert LP: check if exists by name
        const { data: existingLP } = await supabaseService
          .from('limited_partners')
          .select('id')
          .ilike('name', lpData.name as string)
          .limit(1)
          .single();

        let lpId: string;

        if (existingLP) {
          // Update existing LP
          const { error: updateErr } = await supabaseService
            .from('limited_partners')
            .update(lpData)
            .eq('id', existingLP.id);

          if (updateErr) {
            errors.push(`Update LP ${lpData.name}: ${updateErr.message}`);
            continue;
          }
          lpId = existingLP.id;
          lpUpdated++;
        } else {
          // Create new LP
          lpData.created_at = now;
          const { data: newLP, error: insertErr } = await supabaseService
            .from('limited_partners')
            .insert(lpData)
            .select('id')
            .single();

          if (insertErr || !newLP) {
            errors.push(`Insert LP ${lpData.name}: ${insertErr?.message || 'no data returned'}`);
            continue;
          }
          lpId = newLP.id;
          lpCreated++;
        }

        // Upsert commitment to lp_fund_commitments join table
        if (commitmentData.commitment_usd || commitmentData.called_usd) {
          commitmentData.lp_id = lpId;
          commitmentData.updated_at = now;

          const { data: existingCommitment } = await supabaseService
            .from('lp_fund_commitments')
            .select('id')
            .eq('lp_id', lpId)
            .eq('fund_id', fundId)
            .limit(1)
            .single();

          if (existingCommitment) {
            const { error: commitErr } = await supabaseService
              .from('lp_fund_commitments')
              .update(commitmentData)
              .eq('id', existingCommitment.id);

            if (commitErr) {
              errors.push(`Update commitment for ${lpData.name}: ${commitErr.message}`);
            }
          } else {
            commitmentData.created_at = now;
            const { error: commitErr } = await supabaseService
              .from('lp_fund_commitments')
              .insert(commitmentData);

            if (commitErr) {
              errors.push(`Insert commitment for ${lpData.name}: ${commitErr.message}`);
            } else {
              commitmentsCreated++;
            }
          }
        }
      } catch (err) {
        errors.push(`${lpData.name}: ${err instanceof Error ? err.message : 'Unknown'}`);
      }
    }

    return NextResponse.json({
      success: true,
      summary: {
        csvRows: rows.length,
        lpCreated,
        lpUpdated,
        commitmentsCreated,
        skipped: skipped.length,
        errors: errors.length,
      },
      columnMapping: effectiveMapping,
      unmappedHeaders,
      skippedRows: skipped.slice(0, 10),
      errors: errors.slice(0, 10),
    });
  } catch (error) {
    console.error('LP CSV import error:', error);
    return NextResponse.json(
      { error: 'Import failed', details: error instanceof Error ? error.message : 'Unknown' },
      { status: 500 }
    );
  }
}
