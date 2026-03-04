-- Migration: fpa_actuals table
-- Time-series actuals data. One row per company per period per category.

create table fpa_actuals (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  fund_id uuid references funds(id) on delete set null,
  document_id bigint references processed_documents(id) on delete set null,
  period date not null,
  category text not null,
  subcategory text,
  amount numeric not null,
  source text not null default 'csv_upload',
  created_at timestamptz default now()
);

create index idx_fpa_actuals_company_period on fpa_actuals(company_id, period, category);
create index idx_fpa_actuals_fund on fpa_actuals(fund_id) where fund_id is not null;
create unique index idx_fpa_actuals_dedup on fpa_actuals(company_id, period, category, source);

alter table fpa_actuals enable row level security;

-- Scope to company membership via organization
create policy "Users can view actuals" on fpa_actuals for select to authenticated
  using (exists (
    select 1 from companies c
    where c.id = fpa_actuals.company_id
      and c.organization_id = user_org_id()
  ));

create policy "Users can insert actuals" on fpa_actuals for insert to authenticated
  with check (exists (
    select 1 from companies c
    where c.id = fpa_actuals.company_id
      and c.organization_id = user_org_id()
  ));

create policy "Users can update actuals" on fpa_actuals for update to authenticated
  using (exists (
    select 1 from companies c
    where c.id = fpa_actuals.company_id
      and c.organization_id = user_org_id()
  ));
