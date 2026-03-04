-- Add status field to scenario_branches for budget approval workflow
-- draft: working scenario, not yet approved
-- approved: this branch IS the budget for variance comparison
-- locked: frozen budget, no further edits allowed

alter table scenario_branches
  add column if not exists status text not null default 'draft'
  check (status in ('draft', 'approved', 'locked'));

-- Only one approved/locked branch per company at a time
create unique index if not exists idx_one_approved_branch_per_company
  on scenario_branches (company_id)
  where status in ('approved', 'locked');
