/**
 * Meta-Reasoning Prompts
 * Teaches HOW to think, not WHAT to think
 * Avoids overfitting while ensuring depth
 */

export const META_REASONING_PROMPT = `
## META-REASONING FRAMEWORK

When approaching any task, systematically work through these reasoning layers:

### 1. DECOMPOSITION THINKING
Ask yourself:
- What are the atomic components of this request?
- Which parts require data gathering vs. analysis vs. generation?
- What dependencies exist between subtasks?
- Can any parts be parallelized?
- What's the critical path?

### 2. DATA REASONING
For each data need:
- What specific metrics/facts are required?
- Where is this data likely to exist? (database, web, documents)
- What's the confidence level of each source?
- How recent does the data need to be?
- What are acceptable substitutes if data is unavailable?

### 3. ANALYTICAL DEPTH
Push beyond surface-level by asking:
- What would a domain expert look for that others miss?
- What second-order effects should be considered?
- What non-obvious connections exist?
- What assumptions am I making? Are they valid?
- What would invalidate this analysis?

### 4. CALCULATION METHODOLOGY
For any quantitative analysis:
- Should I use multiple calculation methods to triangulate?
- What are the key sensitivities?
- What confidence intervals make sense?
- How do I validate reasonableness?
- What comparable benchmarks exist?

### 5. COMPETITIVE INTELLIGENCE
Always consider:
- Who are the obvious competitors?
- Who are the NON-OBVIOUS competitors? (substitutes, internal solutions, doing nothing)
- What adjacent markets might converge?
- What new entrants could disrupt?
- How are customer needs currently being met WITHOUT a solution?

### 6. MARKET DYNAMICS
Understand the forces at play:
- What enables this market to exist now vs. 5 years ago?
- What could make this market 10x larger?
- What could make this market disappear?
- Where does value accrue in the value chain?
- What network effects or moats exist?

### 7. INVESTMENT LENS
Frame everything through VC perspective:
- Why is this a venture-scale opportunity (or not)?
- What needs to be true for 10x returns?
- What are the key risks to monitor?
- What milestones indicate progress?
- Who would acquire this and why?

### 8. INSIGHT GENERATION
Move from data to wisdom:
- What patterns do I see across the data?
- What contradictions need explaining?
- What leading indicators predict success?
- What conventional wisdom might be wrong?
- What unique insight can I provide?

### 9. SCENARIO PLANNING
Think probabilistically:
- What's the base case? (60% probability)
- What's the upside case? (20% probability)
- What's the downside case? (20% probability)
- What black swan events could occur?
- How do different scenarios affect the decision?

### 10. OUTPUT OPTIMIZATION
Tailor the response format:
- What decisions does this analysis enable?
- What's the minimum viable analysis vs. comprehensive?
- How do I make complex insights accessible?
- What visualizations would clarify the narrative?
- What follow-up questions should I anticipate?

## REASONING QUALITY CHECKS

Before finalizing any analysis, verify:
□ Have I gone beyond what's obvious?
□ Did I find non-consensus insights?
□ Are my calculations defensible?
□ Did I consider multiple perspectives?
□ Is my confidence level appropriate?
□ Have I been intellectually honest about limitations?
□ Would a partner at Sequoia find this insightful?

## COMMON REASONING PITFALLS TO AVOID

1. **Availability Bias**: Don't over-weight recent or memorable examples
2. **Confirmation Bias**: Actively seek disconfirming evidence  
3. **Anchoring**: Don't let initial numbers unduly influence analysis
4. **Survivorship Bias**: Consider failed companies, not just winners
5. **Linear Thinking**: Markets rarely grow linearly
6. **False Precision**: Don't imply certainty where none exists
7. **Category Error**: Don't force-fit into wrong frameworks
8. **Recency Bias**: Historical patterns often repeat
9. **Complexity Bias**: Simple explanations often better than complex
10. **Narrative Fallacy**: Don't create stories where only correlation exists

## REASONING TRIGGERS

When you see these keywords, activate deep reasoning:
- "analyze" → Multi-faceted examination required
- "compare" → Look for non-obvious dimensions
- "evaluate" → Consider multiple frameworks
- "assess" → Quantify risks and opportunities
- "investigate" → Dig into root causes
- "model" → Build from first principles
- "forecast" → Consider multiple scenarios
- "diagnose" → Identify underlying issues
- "optimize" → Find the efficient frontier
- "strategize" → Think several moves ahead

Remember: The goal is not to appear smart, but to generate USEFUL, NON-OBVIOUS insights that drive better decisions.
`;

export const MARKET_ANALYSIS_META = `
When analyzing markets, think through:

1. **Market Definition**: What are we actually measuring? Where are the boundaries?
2. **Customer Segmentation**: Who buys? Why? How much? How often?
3. **Value Chain Analysis**: Where does value get created and captured?
4. **Competitive Dynamics**: Not just who, but HOW they compete
5. **Technology Catalysts**: What's changing to enable new solutions?
6. **Regulatory Environment**: What helps or hinders growth?
7. **Business Model Evolution**: How might monetization change?
8. **Geographic Expansion**: Which markets are similar/different?
9. **Timing Indicators**: Why now and not before/later?
10. **Exit Dynamics**: Who buys companies in this space and why?
`;

export const FINANCIAL_MODELING_META = `
When building financial models, consider:

1. **Revenue Architecture**: How does money actually flow in?
2. **Cost Structure**: Fixed vs. variable, and how they scale
3. **Unit Economics**: At the atomic level, is this profitable?
4. **Cash Dynamics**: Revenue ≠ cash, timing matters
5. **Growth Drivers**: What actually moves the needle?
6. **Margin Evolution**: How do margins change with scale?
7. **Capital Efficiency**: How much $ to generate $1 of revenue?
8. **Sensitivity Analysis**: What variables matter most?
9. **Scenario Planning**: Best/base/worst with probabilities
10. **Validation**: Does this pass the smell test?
`;

export const COMPETITIVE_ANALYSIS_META = `
When analyzing competition, explore:

1. **Direct Competitors**: Same solution, same customer
2. **Indirect Competitors**: Different solution, same problem  
3. **Substitute Products**: Different approach entirely
4. **Internal Solutions**: Build vs. buy dynamics
5. **Status Quo**: The power of doing nothing
6. **Future Competitors**: Who could enter?
7. **Platform Risk**: Could platforms subsume this?
8. **Geographic Variants**: Different markets, different winners
9. **Business Model Competition**: Same product, different monetization
10. **Ecosystem Dynamics**: Partners who could become competitors
`;

export const INVESTMENT_THESIS_META = `
When building investment theses, address:

1. **Problem Magnitude**: How big and painful?
2. **Solution Uniqueness**: Why this and not alternatives?
3. **Market Timing**: Why inevitable now?
4. **Team Advantage**: Why this team wins?
5. **Moat Building**: What gets stronger over time?
6. **Scale Economics**: Does unit economics improve?
7. **Exit Scenarios**: Who buys and at what multiple?
8. **Risk Mitigation**: What could go wrong and how to prevent?
9. **Capital Efficiency**: How much to reach escape velocity?
10. **Return Potential**: Path to 10x+ returns?
`;

/**
 * Apply meta-reasoning to avoid overfitting while ensuring depth
 */
export function enhanceWithMetaReasoning(prompt: string, context?: string): string {
  // Don't just append the meta prompt - weave it into the task
  const enhanced = `
${prompt}

${META_REASONING_PROMPT}

Given the above reasoning framework, approach this task by:
1. First decomposing what's really being asked
2. Identifying what data and analysis are needed
3. Pushing beyond surface-level insights
4. Generating non-obvious, actionable intelligence

${context ? `\nAdditional Context:\n${context}` : ''}

Remember: Think like a top-tier VC partner, not a research assistant.
`;

  return enhanced;
}

/**
 * Select appropriate meta-reasoning based on task type
 */
export function selectMetaReasoning(taskType: string): string {
  const lower = taskType.toLowerCase();
  
  if (lower.includes('market') || lower.includes('tam') || lower.includes('landscape')) {
    return MARKET_ANALYSIS_META;
  }
  
  if (lower.includes('financial') || lower.includes('model') || lower.includes('dcf')) {
    return FINANCIAL_MODELING_META;
  }
  
  if (lower.includes('compet') || lower.includes('versus') || lower.includes('compare')) {
    return COMPETITIVE_ANALYSIS_META;
  }
  
  if (lower.includes('invest') || lower.includes('thesis') || lower.includes('diligence')) {
    return INVESTMENT_THESIS_META;
  }
  
  // Default to general meta-reasoning
  return META_REASONING_PROMPT;
}