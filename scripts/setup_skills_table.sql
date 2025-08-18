-- Comprehensive Skills Table for Agent System
-- Drop existing tables if they exist
DROP TABLE IF EXISTS agent_skill_executions CASCADE;
DROP TABLE IF EXISTS agent_skill_parameters CASCADE;
DROP TABLE IF EXISTS agent_skills CASCADE;
DROP TABLE IF EXISTS skill_categories CASCADE;

-- Create skill categories
CREATE TABLE skill_categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  icon TEXT,
  priority INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert skill categories
INSERT INTO skill_categories (name, description, icon, priority) VALUES
  ('data_retrieval', 'Finding and fetching company/market data', '🔍', 1),
  ('financial_modeling', 'Building DCF, LBO, and other models', '📊', 2),
  ('visualization', 'Creating charts, Sankey diagrams, waterfalls', '📈', 3),
  ('calculation', 'Math operations, formulas, metrics', '🧮', 4),
  ('analysis', 'Company analysis, comparables, scenarios', '🔬', 5),
  ('document_generation', 'Memos, reports, presentations', '📝', 6),
  ('vision', 'Image analysis, logo extraction', '👁️', 7),
  ('waterfall', 'Exit and fund distribution waterfalls', '💧', 8),
  ('portfolio', 'Portfolio construction and optimization', '💼', 9),
  ('market_intelligence', 'TAM, SAM, competitor analysis', '🌍', 10);

-- Create comprehensive skills table
CREATE TABLE agent_skills (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  category_id UUID REFERENCES skill_categories(id),
  name TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  description TEXT,
  
  -- Skill configuration
  required_tools TEXT[], -- Array of tool names needed
  required_context TEXT[], -- What context/data is needed
  output_type TEXT, -- 'commands', 'data', 'visualization', 'document'
  
  -- Model selection
  preferred_model TEXT DEFAULT 'claude-3-haiku-20240307',
  complexity_score INTEGER DEFAULT 1, -- 1-10 scale
  
  -- Execution settings
  timeout_seconds INTEGER DEFAULT 30,
  max_retries INTEGER DEFAULT 2,
  can_parallelize BOOLEAN DEFAULT true,
  
  -- Cost tracking
  estimated_tokens INTEGER,
  estimated_cost_cents NUMERIC(10,2),
  
  -- Learning/improvement
  success_count INTEGER DEFAULT 0,
  failure_count INTEGER DEFAULT 0,
  avg_execution_time_ms INTEGER,
  last_used_at TIMESTAMPTZ,
  
  -- Metadata
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  is_active BOOLEAN DEFAULT true,
  
  -- Skill template/prompt
  system_prompt TEXT,
  user_prompt_template TEXT, -- Template with {{variables}}
  
  -- Example usage
  example_input JSONB,
  example_output JSONB
);

-- Create skill parameters table
CREATE TABLE agent_skill_parameters (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  skill_id UUID REFERENCES agent_skills(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  type TEXT NOT NULL, -- 'string', 'number', 'boolean', 'array', 'object'
  required BOOLEAN DEFAULT false,
  default_value JSONB,
  description TEXT,
  validation_regex TEXT,
  min_value NUMERIC,
  max_value NUMERIC,
  enum_values TEXT[],
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create skill execution history
CREATE TABLE agent_skill_executions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  skill_id UUID REFERENCES agent_skills(id),
  user_id UUID,
  
  -- Request details
  prompt TEXT,
  input_params JSONB,
  context JSONB,
  
  -- Execution details
  started_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  execution_time_ms INTEGER,
  
  -- Results
  status TEXT CHECK (status IN ('pending', 'running', 'success', 'failed', 'timeout')),
  output JSONB,
  error_message TEXT,
  
  -- Model used
  model_used TEXT,
  tokens_used INTEGER,
  cost_cents NUMERIC(10,2),
  
  -- Quality metrics
  user_feedback INTEGER, -- 1-5 rating
  auto_score NUMERIC(3,2), -- 0-1 automated quality score
  
  -- Metadata
  session_id UUID,
  parent_execution_id UUID REFERENCES agent_skill_executions(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert comprehensive skills
INSERT INTO agent_skills (category_id, name, display_name, description, required_tools, required_context, output_type, preferred_model, complexity_score) VALUES
  -- Data Retrieval Skills
  ((SELECT id FROM skill_categories WHERE name = 'data_retrieval'), 
   'company_search', 'Company Search', 'Find companies by name or criteria',
   ARRAY['search_companies', 'fetch_company_data'], ARRAY['company_name', 'filters'], 
   'data', 'claude-3-haiku-20240307', 2),
   
  ((SELECT id FROM skill_categories WHERE name = 'data_retrieval'),
   'market_research', 'Market Research', 'Get TAM, SAM, SOM, and market data',
   ARRAY['fetch_market_data', 'web_search'], ARRAY['market', 'geography'],
   'data', 'claude-3-haiku-20240307', 3),
   
  ((SELECT id FROM skill_categories WHERE name = 'data_retrieval'),
   'competitor_analysis', 'Competitor Analysis', 'Find and analyze competitors',
   ARRAY['fetch_competitors', 'company_search'], ARRAY['company', 'industry'],
   'data', 'claude-3-5-sonnet-20241022', 4),
   
  ((SELECT id FROM skill_categories WHERE name = 'data_retrieval'),
   'funding_history', 'Funding History', 'Get company funding rounds',
   ARRAY['fetch_funding_rounds', 'web_search'], ARRAY['company_name'],
   'data', 'claude-3-haiku-20240307', 2),
   
  -- Financial Modeling Skills
  ((SELECT id FROM skill_categories WHERE name = 'financial_modeling'),
   'dcf_model', 'DCF Model', 'Build discounted cash flow model',
   ARRAY['calculate_dcf', 'grid.write', 'grid.formula'], ARRAY['revenue', 'growth_rates', 'wacc'],
   'commands', 'claude-3-5-sonnet-20241022', 7),
   
  ((SELECT id FROM skill_categories WHERE name = 'financial_modeling'),
   'lbo_model', 'LBO Model', 'Build leveraged buyout model',
   ARRAY['grid.write', 'grid.formula'], ARRAY['purchase_price', 'debt_structure', 'exit_multiple'],
   'commands', 'claude-3-5-sonnet-20241022', 8),
   
  ((SELECT id FROM skill_categories WHERE name = 'financial_modeling'),
   'startup_model', 'Startup Financial Model', 'Build SaaS/startup financial model',
   ARRAY['grid.write', 'grid.formula'], ARRAY['mrr', 'growth_rate', 'churn'],
   'commands', 'claude-3-5-sonnet-20241022', 6),
   
  ((SELECT id FROM skill_categories WHERE name = 'financial_modeling'),
   'three_statement', 'Three Statement Model', 'Build integrated financial statements',
   ARRAY['grid.write', 'grid.formula'], ARRAY['revenue', 'costs', 'capex'],
   'commands', 'claude-3-5-sonnet-20241022', 9),
   
  -- Visualization Skills
  ((SELECT id FROM skill_categories WHERE name = 'visualization'),
   'revenue_sankey', 'Revenue Sankey Diagram', 'Create revenue flow visualization',
   ARRAY['grid.createSankey'], ARRAY['revenue_segments', 'cost_structure'],
   'visualization', 'claude-3-haiku-20240307', 3),
   
  ((SELECT id FROM skill_categories WHERE name = 'visualization'),
   'fund_sankey', 'Fund Flow Sankey', 'Visualize LP → Fund → Portfolio flow',
   ARRAY['grid.createSankey'], ARRAY['lp_commitments', 'portfolio_investments'],
   'visualization', 'claude-3-haiku-20240307', 3),
   
  ((SELECT id FROM skill_categories WHERE name = 'visualization'),
   'exit_waterfall', 'Exit Waterfall', 'Create exit proceeds distribution',
   ARRAY['grid.createWaterfall'], ARRAY['exit_value', 'preferences', 'ownership'],
   'visualization', 'claude-3-haiku-20240307', 4),
   
  ((SELECT id FROM skill_categories WHERE name = 'visualization'),
   'fund_waterfall', 'Fund Distribution Waterfall', 'LP/GP distribution waterfall',
   ARRAY['grid.createWaterfall'], ARRAY['gross_proceeds', 'hurdle_rate', 'carry'],
   'visualization', 'claude-3-haiku-20240307', 4),
   
  -- Calculation Skills
  ((SELECT id FROM skill_categories WHERE name = 'calculation'),
   'basic_math', 'Basic Calculations', 'Simple math operations',
   ARRAY['grid.formula', 'grid.write'], ARRAY['formula', 'cells'],
   'commands', 'claude-3-haiku-20240307', 1),
   
  ((SELECT id FROM skill_categories WHERE name = 'calculation'),
   'irr_calculation', 'IRR Calculation', 'Calculate internal rate of return',
   ARRAY['calculate_irr'], ARRAY['cashflows', 'dates'],
   'data', 'claude-3-haiku-20240307', 2),
   
  ((SELECT id FROM skill_categories WHERE name = 'calculation'),
   'npv_calculation', 'NPV Calculation', 'Calculate net present value',
   ARRAY['calculate_npv'], ARRAY['cashflows', 'discount_rate'],
   'data', 'claude-3-haiku-20240307', 2),
   
  ((SELECT id FROM skill_categories WHERE name = 'calculation'),
   'valuation_multiples', 'Valuation Multiples', 'Calculate EV/Revenue, P/E, etc.',
   ARRAY['fetch_market_multiples', 'grid.formula'], ARRAY['company_metrics', 'industry'],
   'commands', 'claude-3-haiku-20240307', 3),
   
  -- Analysis Skills
  ((SELECT id FROM skill_categories WHERE name = 'analysis'),
   'financial_health', 'Financial Health Analysis', 'Analyze company financial health',
   ARRAY['analyze_financial_health'], ARRAY['financial_statements', 'metrics'],
   'document', 'claude-3-5-sonnet-20241022', 5),
   
  ((SELECT id FROM skill_categories WHERE name = 'analysis'),
   'scenario_analysis', 'Scenario Analysis', 'Run multiple scenarios',
   ARRAY['run_scenario_analysis'], ARRAY['base_case', 'scenarios', 'variables'],
   'data', 'claude-3-5-sonnet-20241022', 6),
   
  ((SELECT id FROM skill_categories WHERE name = 'analysis'),
   'sensitivity_analysis', 'Sensitivity Analysis', 'Test sensitivity to variables',
   ARRAY['grid.formula', 'grid.writeRange'], ARRAY['model', 'variables', 'ranges'],
   'commands', 'claude-3-5-sonnet-20241022', 5),
   
  ((SELECT id FROM skill_categories WHERE name = 'analysis'),
   'comparable_analysis', 'Comparable Company Analysis', 'Comps analysis',
   ARRAY['search_companies', 'fetch_market_multiples'], ARRAY['company', 'peer_group'],
   'data', 'claude-3-5-sonnet-20241022', 5),
   
  -- Document Generation Skills
  ((SELECT id FROM skill_categories WHERE name = 'document_generation'),
   'investment_memo', 'Investment Memo', 'Generate detailed investment memo',
   ARRAY['generate_investment_memo'], ARRAY['company', 'thesis', 'data'],
   'document', 'claude-3-5-sonnet-20241022', 8),
   
  ((SELECT id FROM skill_categories WHERE name = 'document_generation'),
   'executive_summary', 'Executive Summary', 'Create executive summary',
   ARRAY['generate_summary'], ARRAY['data', 'key_points'],
   'document', 'claude-3-5-sonnet-20241022', 4),
   
  ((SELECT id FROM skill_categories WHERE name = 'document_generation'),
   'pitch_deck', 'Pitch Deck Analysis', 'Analyze pitch deck',
   ARRAY['vision_analyze', 'generate_summary'], ARRAY['deck_url', 'company'],
   'document', 'claude-3-5-sonnet-20241022', 7),
   
  -- Vision Skills
  ((SELECT id FROM skill_categories WHERE name = 'vision'),
   'logo_extraction', 'Logo Extraction', 'Extract logos from documents',
   ARRAY['vision_analyze'], ARRAY['document_url'],
   'data', 'claude-3-5-sonnet-20241022', 3),
   
  ((SELECT id FROM skill_categories WHERE name = 'vision'),
   'product_extraction', 'Product Extraction', 'Extract product screenshots',
   ARRAY['vision_analyze'], ARRAY['website_url', 'company_name'],
   'data', 'claude-3-5-sonnet-20241022', 4),
   
  ((SELECT id FROM skill_categories WHERE name = 'vision'),
   'chart_extraction', 'Chart Data Extraction', 'Extract data from charts',
   ARRAY['vision_analyze'], ARRAY['chart_image'],
   'data', 'claude-3-5-sonnet-20241022', 5),
   
  -- Waterfall Skills
  ((SELECT id FROM skill_categories WHERE name = 'waterfall'),
   'liquidation_waterfall', 'Liquidation Preference Waterfall', 'Model liquidation preferences',
   ARRAY['grid.createWaterfall', 'grid.write'], ARRAY['exit_value', 'pref_stack'],
   'visualization', 'claude-3-5-sonnet-20241022', 6),
   
  ((SELECT id FROM skill_categories WHERE name = 'waterfall'),
   'carry_waterfall', 'Carried Interest Waterfall', 'Model GP/LP carry distribution',
   ARRAY['grid.createWaterfall', 'grid.formula'], ARRAY['fund_size', 'returns', 'carry_terms'],
   'visualization', 'claude-3-5-sonnet-20241022', 7),
   
  -- Portfolio Skills
  ((SELECT id FROM skill_categories WHERE name = 'portfolio'),
   'portfolio_construction', 'Portfolio Construction', 'Build optimal portfolio',
   ARRAY['optimize_portfolio'], ARRAY['companies', 'constraints', 'objectives'],
   'data', 'claude-3-5-sonnet-20241022', 8),
   
  ((SELECT id FROM skill_categories WHERE name = 'portfolio'),
   'portfolio_returns', 'Portfolio Returns Analysis', 'Calculate portfolio returns',
   ARRAY['calculate_portfolio_returns'], ARRAY['investments', 'exits', 'dates'],
   'data', 'claude-3-5-sonnet-20241022', 5),
   
  -- Market Intelligence Skills
  ((SELECT id FROM skill_categories WHERE name = 'market_intelligence'),
   'tam_analysis', 'TAM/SAM/SOM Analysis', 'Market size analysis',
   ARRAY['fetch_market_data', 'web_search'], ARRAY['market', 'product', 'geography'],
   'data', 'claude-3-5-sonnet-20241022', 4),
   
  ((SELECT id FROM skill_categories WHERE name = 'market_intelligence'),
   'industry_trends', 'Industry Trends', 'Analyze industry trends',
   ARRAY['web_search', 'analyze_trends'], ARRAY['industry', 'timeframe'],
   'document', 'claude-3-5-sonnet-20241022', 5);

-- Create indexes for better performance
CREATE INDEX idx_skills_category ON agent_skills(category_id);
CREATE INDEX idx_skills_name ON agent_skills(name);
CREATE INDEX idx_skills_active ON agent_skills(is_active);
CREATE INDEX idx_executions_skill ON agent_skill_executions(skill_id);
CREATE INDEX idx_executions_user ON agent_skill_executions(user_id);
CREATE INDEX idx_executions_status ON agent_skill_executions(status);
CREATE INDEX idx_executions_created ON agent_skill_executions(created_at);

-- Create function to get best skill for task
CREATE OR REPLACE FUNCTION get_best_skill_for_task(task_description TEXT)
RETURNS TABLE (
  skill_id UUID,
  skill_name TEXT,
  confidence NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    s.id as skill_id,
    s.name as skill_name,
    ts_rank(
      to_tsvector('english', s.description || ' ' || s.display_name),
      plainto_tsquery('english', task_description)
    )::NUMERIC as confidence
  FROM agent_skills s
  WHERE s.is_active = true
  ORDER BY confidence DESC
  LIMIT 5;
END;
$$ LANGUAGE plpgsql;

-- Create function to track skill execution
CREATE OR REPLACE FUNCTION track_skill_execution(
  p_skill_name TEXT,
  p_status TEXT,
  p_execution_time_ms INTEGER
) RETURNS VOID AS $$
BEGIN
  UPDATE agent_skills
  SET 
    success_count = CASE WHEN p_status = 'success' THEN success_count + 1 ELSE success_count END,
    failure_count = CASE WHEN p_status = 'failed' THEN failure_count + 1 ELSE failure_count END,
    avg_execution_time_ms = CASE 
      WHEN avg_execution_time_ms IS NULL THEN p_execution_time_ms
      ELSE (avg_execution_time_ms * (success_count + failure_count) + p_execution_time_ms) / (success_count + failure_count + 1)
    END,
    last_used_at = NOW(),
    updated_at = NOW()
  WHERE name = p_skill_name;
END;
$$ LANGUAGE plpgsql;

-- Create view for skill performance metrics
CREATE OR REPLACE VIEW skill_performance AS
SELECT 
  s.name,
  s.display_name,
  c.name as category,
  s.success_count,
  s.failure_count,
  CASE 
    WHEN (s.success_count + s.failure_count) > 0 
    THEN s.success_count::NUMERIC / (s.success_count + s.failure_count)
    ELSE 0 
  END as success_rate,
  s.avg_execution_time_ms,
  s.estimated_cost_cents,
  s.last_used_at,
  s.complexity_score
FROM agent_skills s
JOIN skill_categories c ON s.category_id = c.id
WHERE s.is_active = true
ORDER BY s.last_used_at DESC NULLS LAST;

-- Grant permissions
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated;