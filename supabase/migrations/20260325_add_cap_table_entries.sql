-- Migration: cap_table_entries — the cap table equivalent of fpa_actuals.
-- Individual rows per shareholder/instrument instead of JSONB blob.
-- Covers equity, debt, convertibles, SAFEs, warrants, PIK, revenue-based.

-- Clean up any partial creation from previous failed attempt
drop table if exists cap_table_entries cascade;

create table cap_table_entries (
  id                uuid primary key default gen_random_uuid(),
  company_id        uuid not null,
  fund_id           uuid,

  -- Identity
  shareholder_name  text not null,
  stakeholder_type  text not null default 'other'
    check (stakeholder_type in ('founder','investor','employee','advisor','lender','other')),

  -- Instrument classification
  instrument_type   text not null default 'equity'
    check (instrument_type in (
      'equity','debt','convertible','safe','warrant','option','pik',
      'revenue_based','mezzanine','revolver'
    )),
  share_class       text not null default 'common',
    -- equity: common, preferred_a..f, options
    -- debt: term_loan, revolver, venture_debt
    -- convertible: convertible_note
    -- safe: post_money, pre_money, mfn
    -- warrant: common, preferred
    -- pik: mandatory_pik, pik_toggle, pik_cash_split
    -- revenue_based: revenue_share

  -- Core equity fields
  num_shares        numeric not null default 0,
  price_per_share   numeric not null default 0,
  investment_amount numeric generated always as (num_shares * price_per_share) stored,

  -- Round
  round_name        text,
  investment_date   date,

  -- Rights (equity instruments)
  liquidation_pref      numeric default 1.0,
  participating         boolean default false,
  participation_cap     numeric,
  anti_dilution         text,           -- full_ratchet | broad_weighted_average | none
  voting_rights         boolean default true,
  board_seat            boolean default false,
  pro_rata_rights       boolean default false,

  -- Vesting (equity/options)
  vesting_cliff_months  integer,
  vesting_total_months  integer,
  vested_pct            numeric,

  -- Debt fields
  outstanding_principal numeric,          -- current balance (debt, convertible, pik, rbf)
  interest_rate         numeric,          -- annual, decimal (0.12 = 12%)
  coupon_type           text,             -- fixed | floating | pik | zero
  maturity_date         date,
  seniority             text,             -- senior | subordinated | mezzanine
  secured               boolean,
  collateral            text,
  amortization_type     text,             -- bullet | equal_installment | interest_only_then_bullet
  covenants             jsonb,            -- {"dscr": 1.2, "leverage": 3.0, "min_cash": 500000}
  cross_default         boolean default false,

  -- Convertible / SAFE fields
  conversion_discount   numeric,          -- decimal (0.20 = 20%)
  valuation_cap         numeric,
  qualified_financing   numeric,          -- threshold amount
  auto_convert          boolean default true,
  mfn                   boolean default false,

  -- Warrant fields
  exercise_price        numeric,
  warrant_coverage_pct  numeric,          -- % of associated debt principal
  underlying_class      text,             -- what converts into
  expiry_date           date,
  cashless_exercise     boolean,

  -- PIK fields
  pik_rate              numeric,          -- annual PIK rate
  cash_rate             numeric,          -- annual cash rate
  pik_toggle_type       text,             -- mandatory_pik | pik_toggle | pik_cash_split

  -- Revenue-based financing
  repayment_cap         numeric,          -- total repayment as multiple of advance
  revenue_share_pct     numeric,          -- % of monthly revenue

  -- Classification (set by application layer on insert/update)
  is_debt_instrument    boolean not null default false,

  -- Source tracking
  source            text not null default 'manual'
    check (source in ('manual','csv','legal_docs')),
  document_id       text,
  notes             text,

  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

-- Indexes
create index idx_cap_entries_company
  on cap_table_entries(company_id);

create index idx_cap_entries_company_fund
  on cap_table_entries(company_id, fund_id)
  where fund_id is not null;

create index idx_cap_entries_instrument_type
  on cap_table_entries(company_id, instrument_type);

create index idx_cap_entries_debt
  on cap_table_entries(company_id, is_debt_instrument)
  where is_debt_instrument = true;

-- Dedup: same shareholder + class + round = one entry per source
create unique index idx_cap_entries_dedup
  on cap_table_entries(company_id, shareholder_name, share_class, round_name, source)
  where round_name is not null;

-- Auto-update updated_at
create or replace function cap_table_entries_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger trg_cap_table_entries_updated_at
  before update on cap_table_entries
  for each row
  execute function cap_table_entries_updated_at();

-- RLS
alter table cap_table_entries enable row level security;
