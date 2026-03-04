-- Migration: scenario_branches table

create table scenario_branches (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  fund_id uuid references funds(id) on delete set null,
  parent_branch_id uuid references scenario_branches(id),
  name text not null,
  description text,
  fork_period date,
  assumptions jsonb not null default '{}',
  probability float,
  created_by text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index idx_scenario_branches_company on scenario_branches(company_id);
create index idx_scenario_branches_parent on scenario_branches(parent_branch_id) where parent_branch_id is not null;
