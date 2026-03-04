-- Migration: budgets + budget_lines tables

create table budgets (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  fund_id uuid references funds(id) on delete set null,
  name text not null,
  fiscal_year int not null,
  version int default 1,
  status text default 'draft',
  created_by text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table budget_lines (
  id uuid primary key default gen_random_uuid(),
  budget_id uuid not null references budgets(id) on delete cascade,
  category text not null,
  subcategory text,
  m1 numeric default 0, m2 numeric default 0, m3 numeric default 0,
  m4 numeric default 0, m5 numeric default 0, m6 numeric default 0,
  m7 numeric default 0, m8 numeric default 0, m9 numeric default 0,
  m10 numeric default 0, m11 numeric default 0, m12 numeric default 0,
  notes text,
  created_at timestamptz default now()
);

create index idx_budgets_company on budgets(company_id, fiscal_year);
create index idx_budget_lines_budget on budget_lines(budget_id);
