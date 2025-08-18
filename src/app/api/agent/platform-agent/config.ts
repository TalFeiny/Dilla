/**
 * Platform Agent Configuration
 * Defines fund priorities, investment thesis, and platform capabilities
 */

export const PLATFORM_CONFIG = {
  // Fund Information
  fund: {
    name: "VC Platform Fund",
    size: 500_000_000, // $500M fund
    vintage: 2024,
    type: "early-growth",
    deploymentPeriod: 3, // years
    harvestPeriod: 7, // years after deployment
    targetMultiple: 3.0,
    targetIRR: 0.25, // 25% IRR
  },

  // Investment Thesis & Priorities
  investmentThesis: {
    stages: ["Series A", "Series B", "Series C"],
    checkSizes: {
      initial: { min: 5_000_000, max: 25_000_000 },
      followOn: { min: 2_000_000, max: 15_000_000 }
    },
    targetOwnership: { min: 0.10, max: 0.25 }, // 10-25% ownership
    
    // Sector Priorities (ranked)
    sectorPriorities: [
      {
        sector: "AI-Gen AI",
        priority: "high",
        subsectors: ["LLM Infrastructure", "Applied AI", "AI Agents", "Computer Vision"],
        thesisPoints: [
          "Foundation model applications with defensible moats",
          "Vertical AI solutions with high ROI",
          "Infrastructure for AI deployment at scale"
        ]
      },
      {
        sector: "SaaS-DevTools",
        priority: "high",
        subsectors: ["Developer Platforms", "CI/CD", "Observability", "Security"],
        thesisPoints: [
          "Tools that 10x developer productivity",
          "Platform plays with network effects",
          "Open source with enterprise monetization"
        ]
      },
      {
        sector: "B2B Fintech",
        priority: "medium",
        subsectors: ["Payments Infrastructure", "Banking as a Service", "Risk/Compliance"],
        thesisPoints: [
          "Embedded finance enablers",
          "Cross-border payment solutions",
          "Next-gen compliance and risk management"
        ]
      },
      {
        sector: "Data Infrastructure",
        priority: "medium",
        subsectors: ["Data Warehousing", "ETL/ELT", "Analytics", "Privacy"],
        thesisPoints: [
          "Real-time data processing at scale",
          "Data privacy and governance solutions",
          "Analytics for AI/ML workflows"
        ]
      }
    ],

    // Key Metrics Thresholds
    metricsThresholds: {
      arr: { min: 5_000_000 }, // Minimum $5M ARR
      growthRate: { min: 1.0 }, // Minimum 100% YoY growth
      burnMultiple: { max: 2.0 }, // Maximum burn multiple of 2x
      ruleOf40: { min: 40 }, // Rule of 40 score
      grossMargin: { min: 0.70 }, // Minimum 70% gross margin
      ltv_cac: { min: 3.0 }, // LTV/CAC ratio minimum
      paybackPeriod: { max: 18 } // Maximum 18 months payback
    },

    // Deal Breakers
    dealBreakers: [
      "Founder integrity issues",
      "Unscalable unit economics",
      "No product-market fit evidence",
      "Regulatory uncertainty",
      "Single customer concentration >30%",
      "Declining growth rate",
      "Unsustainable burn rate"
    ]
  },

  // Platform Capabilities (what the agent can access)
  capabilities: {
    dataAccess: [
      "portfolio_companies", // All portfolio company data
      "processed_documents", // All analyzed documents
      "pwerm_results", // PWERM analysis results
      "companies", // Company database
      "funds", // Fund information
      "lps", // LP information
      "kyc_records", // KYC compliance data
      "market_intelligence" // Cached market research
    ],
    
    tools: [
      "document_analysis", // Process and analyze documents
      "pwerm_calculation", // Run PWERM analysis
      "market_research", // Tavily search integration
      "financial_modeling", // Financial projections
      "competitive_analysis", // Competitor research
      "due_diligence", // DD checklist and tracking
      "portfolio_monitoring", // Track portfolio metrics
      "report_generation" // Generate investment memos
    ],

    integrations: [
      "supabase", // Database
      "openai", // LLM for analysis
      "anthropic", // Claude for reasoning
      "tavily", // Web search
      "sec_edgar", // Public filings
      "crunchbase", // Company data
      "pitchbook" // Deal data (if available)
    ]
  },

  // Decision Framework
  decisionFramework: {
    evaluationCriteria: [
      { factor: "Team Quality", weight: 0.30 },
      { factor: "Market Size & Growth", weight: 0.25 },
      { factor: "Product Differentiation", weight: 0.20 },
      { factor: "Unit Economics", weight: 0.15 },
      { factor: "Competitive Position", weight: 0.10 }
    ],

    scoringRubric: {
      exceptional: { min: 90, action: "Fast track to IC" },
      strong: { min: 75, action: "Full diligence" },
      promising: { min: 60, action: "Further investigation" },
      marginal: { min: 40, action: "Monitor for improvement" },
      pass: { max: 40, action: "Decline with feedback" }
    }
  },

  // Portfolio Construction
  portfolioConstruction: {
    targetPortfolioSize: 25, // companies
    reserveRatio: 0.50, // 50% for follow-ons
    
    allocation: {
      highConviction: { count: 5, percentOfFund: 0.40 },
      core: { count: 10, percentOfFund: 0.40 },
      options: { count: 10, percentOfFund: 0.20 }
    },

    diversification: {
      maxSectorConcentration: 0.40, // Max 40% in one sector
      maxStageConcentration: 0.50, // Max 50% in one stage
      maxVintageConcentration: 0.35 // Max 35% in one year
    }
  },

  // Reporting & Monitoring
  reporting: {
    lpReporting: {
      frequency: "quarterly",
      metrics: ["IRR", "TVPI", "DPI", "Portfolio NAV", "Key Events"]
    },
    
    portfolioMonitoring: {
      frequency: "monthly",
      metrics: ["ARR Growth", "Burn Rate", "Runway", "Key Hires", "Product Milestones"]
    },

    alerts: {
      urgent: ["Runway < 6 months", "Key founder departure", "Major pivot"],
      important: ["Growth deceleration", "Missed milestone", "Competitive threat"],
      informational: ["New funding round", "Key hire", "Product launch"]
    }
  }
};

// Agent System Prompt incorporating platform context
export const PLATFORM_AGENT_PROMPT = `You are the AI Investment Partner for ${PLATFORM_CONFIG.fund.name}, a ${(PLATFORM_CONFIG.fund.size / 1_000_000).toFixed(0)}M ${PLATFORM_CONFIG.fund.type} venture capital fund.

## Your Role
You are a senior investment professional with full visibility into the platform's data, tools, and portfolio. You help the investment team with:
- Deal sourcing and evaluation
- Due diligence and analysis
- Portfolio monitoring and support
- LP reporting and communications
- Market intelligence and research

## Fund Investment Thesis
${PLATFORM_CONFIG.investmentThesis.sectorPriorities.map(s => 
  `- **${s.sector}** (${s.priority} priority): ${s.thesisPoints.join('; ')}`
).join('\n')}

## Key Investment Criteria
- Stages: ${PLATFORM_CONFIG.investmentThesis.stages.join(', ')}
- Check Sizes: $${(PLATFORM_CONFIG.investmentThesis.checkSizes.initial.min / 1_000_000).toFixed(0)}M - $${(PLATFORM_CONFIG.investmentThesis.checkSizes.initial.max / 1_000_000).toFixed(0)}M initial
- Target Ownership: ${(PLATFORM_CONFIG.investmentThesis.targetOwnership.min * 100).toFixed(0)}% - ${(PLATFORM_CONFIG.investmentThesis.targetOwnership.max * 100).toFixed(0)}%
- Minimum ARR: $${(PLATFORM_CONFIG.investmentThesis.metricsThresholds.arr.min / 1_000_000).toFixed(0)}M
- Minimum Growth: ${(PLATFORM_CONFIG.investmentThesis.metricsThresholds.growthRate.min * 100).toFixed(0)}% YoY

## Deal Breakers
${PLATFORM_CONFIG.investmentThesis.dealBreakers.map(d => `- ${d}`).join('\n')}

## Platform Capabilities
You have access to:
${PLATFORM_CONFIG.capabilities.dataAccess.map(d => `- ${d} database`).join('\n')}

Available tools:
${PLATFORM_CONFIG.capabilities.tools.map(t => `- ${t}`).join('\n')}

## Decision Framework
When evaluating opportunities, use our scoring rubric:
${Object.entries(PLATFORM_CONFIG.decisionFramework.scoringRubric).map(([level, config]) => 
  `- **${level.charAt(0).toUpperCase() + level.slice(1)}** (>${config.min || `<${config.max}`}): ${config.action}`
).join('\n')}

## Your Approach
1. **Data-Driven**: Always cite specific metrics and sources
2. **Thesis-Aligned**: Evaluate against our investment thesis
3. **Risk-Aware**: Identify and quantify risks
4. **Action-Oriented**: Provide clear next steps
5. **Portfolio-Conscious**: Consider portfolio construction and reserves

## Current Portfolio Context
- Fund Size: $${(PLATFORM_CONFIG.fund.size / 1_000_000).toFixed(0)}M
- Target Portfolio: ${PLATFORM_CONFIG.portfolioConstruction.targetPortfolioSize} companies
- Reserve Ratio: ${(PLATFORM_CONFIG.portfolioConstruction.reserveRatio * 100).toFixed(0)}%
- Target Net Multiple: ${PLATFORM_CONFIG.fund.targetMultiple}x
- Target IRR: ${(PLATFORM_CONFIG.fund.targetIRR * 100).toFixed(0)}%

Remember: You are a fiduciary to our LPs. Every recommendation should maximize risk-adjusted returns while maintaining portfolio discipline.`;

// Export helper functions for agent operations
export const AgentHelpers = {
  /**
   * Check if a company fits the investment thesis
   */
  evaluateThesisFit(company: any): { fit: boolean; score: number; reasons: string[] } {
    const reasons: string[] = [];
    let score = 0;

    // Check sector alignment
    const sectorPriority = PLATFORM_CONFIG.investmentThesis.sectorPriorities.find(
      s => s.sector === company.sector || s.subsectors.includes(company.subsector)
    );
    
    if (sectorPriority) {
      score += sectorPriority.priority === 'high' ? 30 : 20;
      reasons.push(`Aligns with ${sectorPriority.priority} priority sector: ${sectorPriority.sector}`);
    } else {
      reasons.push('Outside of priority sectors');
    }

    // Check metrics
    const metrics = PLATFORM_CONFIG.investmentThesis.metricsThresholds;
    
    if (company.arr >= metrics.arr.min) {
      score += 20;
      reasons.push(`ARR of $${(company.arr / 1_000_000).toFixed(1)}M meets minimum`);
    } else {
      reasons.push(`ARR below $${(metrics.arr.min / 1_000_000).toFixed(0)}M minimum`);
    }

    if (company.growthRate >= metrics.growthRate.min) {
      score += 20;
      reasons.push(`Growth rate of ${(company.growthRate * 100).toFixed(0)}% exceeds minimum`);
    } else {
      reasons.push(`Growth rate below ${(metrics.growthRate.min * 100).toFixed(0)}% minimum`);
    }

    // Rule of 40
    const ruleOf40 = (company.growthRate * 100) + (company.profitMargin || 20);
    if (ruleOf40 >= metrics.ruleOf40.min) {
      score += 15;
      reasons.push(`Rule of 40 score of ${ruleOf40.toFixed(0)} is strong`);
    }

    // Burn multiple
    if (company.burnMultiple && company.burnMultiple <= metrics.burnMultiple.max) {
      score += 15;
      reasons.push(`Burn multiple of ${company.burnMultiple.toFixed(1)}x is efficient`);
    }

    return {
      fit: score >= 60,
      score,
      reasons
    };
  },

  /**
   * Calculate portfolio impact of a new investment
   */
  assessPortfolioImpact(newInvestment: any, currentPortfolio: any[]): any {
    const portfolioSize = currentPortfolio.length;
    const sectorConcentration = currentPortfolio.filter(c => c.sector === newInvestment.sector).length / portfolioSize;
    
    return {
      newPortfolioSize: portfolioSize + 1,
      sectorConcentration: ((sectorConcentration * portfolioSize + 1) / (portfolioSize + 1)),
      diversificationImpact: sectorConcentration > PLATFORM_CONFIG.portfolioConstruction.diversification.maxSectorConcentration 
        ? 'negative' : 'positive',
      reservesRequired: newInvestment.initialCheck * PLATFORM_CONFIG.portfolioConstruction.reserveRatio
    };
  }
};