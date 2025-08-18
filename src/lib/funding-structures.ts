/**
 * Advanced Funding Structures & Cap Table Dynamics
 * Handles SAFEs, convertible notes, debt, and complex funding scenarios
 */

export interface SAFE {
  investor: string;
  amount: number;
  valuationCap?: number;
  discount?: number;
  type: 'pre-money' | 'post-money';
  mfn?: boolean; // Most Favored Nation
}

export interface ConvertibleNote {
  investor: string;
  principal: number;
  interestRate: number;
  maturityDate: Date;
  valuationCap?: number;
  discount?: number;
  qualified: boolean; // Qualified financing threshold
  qualifiedAmount?: number;
}

export interface DebtFacility {
  lender: string;
  principal: number;
  interestRate: number;
  type: 'venture-debt' | 'revenue-based' | 'asset-backed';
  warrantCoverage?: number; // Percentage of loan as warrants
  covenants?: {
    minimumCash?: number;
    minimumRevenue?: number;
    maximumBurnRate?: number;
  };
  maturityMonths: number;
}

export interface FundReserves {
  fund: string;
  totalCommitment: number;
  deployed: number;
  reserved: number;
  available: number;
  reserveRatio: number; // Typical reserve/initial investment ratio
  followOnStrategy: 'pro-rata' | 'double-down' | 'selective';
}

export class FundingStructureAnalyzer {
  
  /**
   * Calculate SAFE conversion at priced round
   */
  convertSAFEs(
    safes: SAFE[],
    pricedRoundValuation: number,
    newInvestment: number
  ): {
    conversionDetails: Array<{
      investor: string;
      conversionPrice: number;
      sharesIssued: number;
      ownership: number;
      dilutionToFounders: number;
    }>;
    totalDilution: number;
    effectivePreMoney: number;
  } {
    const conversionDetails = [];
    let totalSharesFromSAFEs = 0;
    
    for (const safe of safes) {
      let conversionPrice: number;
      
      if (safe.type === 'post-money') {
        // YC-style post-money SAFE
        const effectiveValuation = safe.valuationCap 
          ? Math.min(safe.valuationCap, pricedRoundValuation)
          : pricedRoundValuation;
        
        conversionPrice = safe.discount 
          ? effectiveValuation * (1 - safe.discount)
          : effectiveValuation;
        
        // Post-money SAFE ownership = investment / cap
        const ownership = safe.amount / conversionPrice;
        
        conversionDetails.push({
          investor: safe.investor,
          conversionPrice,
          sharesIssued: safe.amount / conversionPrice,
          ownership,
          dilutionToFounders: ownership
        });
        
      } else {
        // Traditional pre-money SAFE
        let effectiveValuation = pricedRoundValuation;
        
        if (safe.valuationCap) {
          effectiveValuation = Math.min(safe.valuationCap, pricedRoundValuation);
        }
        
        if (safe.discount) {
          conversionPrice = effectiveValuation * (1 - safe.discount);
        } else {
          conversionPrice = effectiveValuation;
        }
        
        const sharesIssued = safe.amount / conversionPrice;
        totalSharesFromSAFEs += sharesIssued;
        
        conversionDetails.push({
          investor: safe.investor,
          conversionPrice,
          sharesIssued,
          ownership: 0, // Calculate after all conversions
          dilutionToFounders: 0
        });
      }
    }
    
    // Calculate actual ownership percentages
    const postMoneyValuation = pricedRoundValuation + newInvestment;
    const totalDilution = totalSharesFromSAFEs / (postMoneyValuation / conversionDetails[0]?.conversionPrice || 1);
    
    // Effective pre-money after SAFE conversion
    const effectivePreMoney = pricedRoundValuation - safes.reduce((sum, s) => sum + s.amount, 0);
    
    return {
      conversionDetails,
      totalDilution,
      effectivePreMoney
    };
  }
  
  /**
   * Analyze seed extension dynamics
   */
  analyzeSeedExtension(
    originalSeed: {
      amount: number;
      valuation: number;
      date: Date;
      investors: string[];
    },
    currentMetrics: {
      revenue: number;
      growth: number;
      runway: number;
    },
    extensionOptions: {
      bridge?: {
        amount: number;
        type: 'note' | 'SAFE' | 'priced';
        terms?: any;
      };
      internalRound?: {
        amount: number;
        leadInvestor: string;
      };
      strategic?: {
        investor: string;
        amount: number;
        strategic_value: string;
      };
    }
  ): {
    recommendation: 'bridge' | 'internal' | 'strategic' | 'push-to-a';
    reasoning: string[];
    prosCons: Record<string, string[]>;
    timeline: number; // months
  } {
    const monthsSinceSeed = (Date.now() - originalSeed.date.getTime()) / (1000 * 60 * 60 * 24 * 30);
    const progressRatio = currentMetrics.revenue / (originalSeed.valuation * 0.1); // Rough progress metric
    
    let recommendation: 'bridge' | 'internal' | 'strategic' | 'push-to-a';
    const reasoning = [];
    const prosCons: Record<string, string[]> = {};
    
    // Decision logic
    if (currentMetrics.runway < 6 && progressRatio < 0.7) {
      // Need money, not ready for A
      recommendation = 'bridge';
      reasoning.push('Runway under 6 months requires immediate funding');
      reasoning.push('Metrics not yet at Series A level');
      
      prosCons.bridge = [
        'Pros: Quick execution, minimal dilution, buys time',
        'Cons: Debt/cap overhang, signals weakness, may need high discount'
      ];
      
    } else if (progressRatio >= 1.5 && currentMetrics.growth > 1.5) {
      // Strong enough for Series A
      recommendation = 'push-to-a';
      reasoning.push('Metrics exceed Series A benchmarks');
      reasoning.push(`${(currentMetrics.growth * 100).toFixed(0)}% growth supports higher valuation`);
      
      prosCons['push-to-a'] = [
        'Pros: Clean cap table, strong signal, institutional capital',
        'Cons: Longer process, higher bar, more dilution'
      ];
      
    } else if (extensionOptions.internalRound && currentMetrics.runway > 9) {
      // Internal round makes sense
      recommendation = 'internal';
      reasoning.push('Existing investors willing to support');
      reasoning.push('Adequate runway for controlled process');
      
      prosCons.internal = [
        'Pros: Fast, friendly terms, maintains momentum',
        'Cons: No new investors/network, may limit upside'
      ];
      
    } else {
      // Strategic investor
      recommendation = 'strategic';
      reasoning.push('Strategic value beyond capital');
      reasoning.push('Bridge to Series A with strategic proof points');
      
      prosCons.strategic = [
        'Pros: Strategic value, validation, potential acquirer',
        'Cons: Potential conflicts, slower decision, complex terms'
      ];
    }
    
    const timeline = recommendation === 'bridge' ? 1 : 
                     recommendation === 'internal' ? 2 :
                     recommendation === 'strategic' ? 3 : 4;
    
    return {
      recommendation,
      reasoning,
      prosCons,
      timeline
    };
  }
  
  /**
   * Calculate venture debt economics
   */
  analyzeVentureDebt(
    companyMetrics: {
      revenue: number;
      burnRate: number;
      cashBalance: number;
      lastValuation: number;
    },
    debtOptions: DebtFacility[]
  ): {
    maxDebtCapacity: number;
    recommendedAmount: number;
    bestOption: DebtFacility | null;
    analysis: {
      debtToRevenue: number;
      interestCoverage: number;
      dilutionFromWarrants: number;
      covenantRisk: 'low' | 'medium' | 'high';
      recommendation: string;
    };
  } {
    // Typical venture debt is 3-6 months of runway or 20-30% of last round
    const runwayBasedCapacity = companyMetrics.burnRate * 6;
    const valuationBasedCapacity = companyMetrics.lastValuation * 0.25;
    const revenueBasedCapacity = companyMetrics.revenue * 0.5; // 6 months of revenue
    
    const maxDebtCapacity = Math.min(
      runwayBasedCapacity,
      valuationBasedCapacity,
      revenueBasedCapacity
    );
    
    // Conservative recommendation: 50-70% of max capacity
    const recommendedAmount = maxDebtCapacity * 0.6;
    
    // Evaluate options
    let bestOption: DebtFacility | null = null;
    let bestScore = -Infinity;
    
    for (const option of debtOptions) {
      // Score based on cost and flexibility
      let score = 0;
      
      // Interest cost (lower is better)
      score -= option.interestRate * 100;
      
      // Warrant dilution (lower is better)
      score -= (option.warrantCoverage || 0) * 10;
      
      // Covenant flexibility (fewer/looser is better)
      const covenantCount = Object.keys(option.covenants || {}).length;
      score -= covenantCount * 5;
      
      // Appropriate size
      if (option.principal <= recommendedAmount) {
        score += 10;
      }
      
      if (score > bestScore) {
        bestScore = score;
        bestOption = option;
      }
    }
    
    // Analysis
    const debtToRevenue = recommendedAmount / companyMetrics.revenue;
    const monthlyInterest = recommendedAmount * (bestOption?.interestRate || 0.12) / 12;
    const interestCoverage = Math.abs(companyMetrics.burnRate) / monthlyInterest;
    const dilutionFromWarrants = (bestOption?.warrantCoverage || 0) * recommendedAmount / companyMetrics.lastValuation;
    
    // Covenant risk assessment
    let covenantRisk: 'low' | 'medium' | 'high' = 'low';
    if (bestOption?.covenants) {
      const cushion = companyMetrics.cashBalance / (bestOption.covenants.minimumCash || 1);
      if (cushion < 1.5) covenantRisk = 'high';
      else if (cushion < 2) covenantRisk = 'medium';
    }
    
    const recommendation = debtToRevenue > 0.5 
      ? 'High leverage - consider smaller amount or equity instead'
      : interestCoverage < 5
      ? 'Interest burden significant - ensure growth justifies cost'
      : covenantRisk === 'high'
      ? 'Covenant risk high - negotiate flexibility or reduce amount'
      : 'Debt appropriate - provides runway without significant dilution';
    
    return {
      maxDebtCapacity,
      recommendedAmount,
      bestOption,
      analysis: {
        debtToRevenue,
        interestCoverage,
        dilutionFromWarrants,
        covenantRisk,
        recommendation
      }
    };
  }
  
  /**
   * Model fund reserve deployment
   */
  modelReserveDeployment(
    fundReserves: FundReserves,
    portfolioCompany: {
      currentOwnership: number;
      nextRoundSize: number;
      performance: 'outperforming' | 'ontrack' | 'struggling';
    },
    strategy: 'maintain-ownership' | 'double-down' | 'minimize'
  ): {
    recommendedInvestment: number;
    resultingOwnership: number;
    reserveRemaining: number;
    rationale: string[];
  } {
    let recommendedInvestment = 0;
    const rationale = [];
    
    // Pro-rata amount to maintain ownership
    const proRataAmount = portfolioCompany.nextRoundSize * portfolioCompany.currentOwnership;
    
    switch (strategy) {
      case 'maintain-ownership':
        recommendedInvestment = Math.min(proRataAmount, fundReserves.available);
        rationale.push(`Investing $${(recommendedInvestment / 1e6).toFixed(1)}M to maintain ${(portfolioCompany.currentOwnership * 100).toFixed(1)}% ownership`);
        break;
        
      case 'double-down':
        if (portfolioCompany.performance === 'outperforming') {
          // Try to get super pro-rata (1.5-2x)
          recommendedInvestment = Math.min(proRataAmount * 1.5, fundReserves.available);
          rationale.push('Outperforming company - maximizing allocation');
          rationale.push(`Targeting ${((recommendedInvestment / portfolioCompany.nextRoundSize) * 100).toFixed(1)}% of round`);
        } else {
          recommendedInvestment = proRataAmount;
          rationale.push('Performance doesn\'t justify super pro-rata');
        }
        break;
        
      case 'minimize':
        if (portfolioCompany.performance === 'struggling') {
          recommendedInvestment = 0;
          rationale.push('Preserving reserves for better opportunities');
        } else {
          // Token amount to maintain relationship
          recommendedInvestment = Math.min(proRataAmount * 0.5, fundReserves.available);
          rationale.push('Partial pro-rata to preserve reserves');
        }
        break;
    }
    
    // Check reserve policy
    const deploymentRatio = recommendedInvestment / fundReserves.reserved;
    if (deploymentRatio > 0.5 && fundReserves.followOnStrategy !== 'double-down') {
      rationale.push('⚠️ Using >50% of reserves in single round - consider reducing');
    }
    
    // Calculate resulting ownership
    const totalRoundSize = portfolioCompany.nextRoundSize;
    const newShares = recommendedInvestment / totalRoundSize;
    const dilutionFactor = 1 - (totalRoundSize - recommendedInvestment) / (totalRoundSize + 1); // Simplified
    const resultingOwnership = portfolioCompany.currentOwnership * dilutionFactor + newShares;
    
    const reserveRemaining = fundReserves.available - recommendedInvestment;
    
    return {
      recommendedInvestment,
      resultingOwnership,
      reserveRemaining,
      rationale
    };
  }
  
  /**
   * Complex cap table with all instruments
   */
  buildCompleteCapTable(
    equity: Record<string, number>,
    safes: SAFE[],
    notes: ConvertibleNote[],
    options: {
      allocated: number;
      available: number;
      strikePrice: number;
    },
    nextRound: {
      amount: number;
      preMoneyValuation: number;
    }
  ): {
    preConversion: Record<string, number>;
    postConversion: Record<string, number>;
    fullyDiluted: Record<string, number>;
    waterfall: Array<{
      event: string;
      impact: Record<string, number>;
    }>;
  } {
    const waterfall = [];
    
    // Start with current equity
    const preConversion = { ...equity };
    waterfall.push({
      event: 'Current Cap Table',
      impact: { ...preConversion }
    });
    
    // Convert SAFEs
    const safeConversion = this.convertSAFEs(safes, nextRound.preMoneyValuation, nextRound.amount);
    const postSAFE: Record<string, number> = {};
    
    // Apply SAFE dilution
    const safeDilution = 1 - safeConversion.totalDilution;
    for (const [holder, ownership] of Object.entries(preConversion)) {
      postSAFE[holder] = ownership * safeDilution;
    }
    
    // Add SAFE investors
    for (const safe of safeConversion.conversionDetails) {
      postSAFE[safe.investor] = (postSAFE[safe.investor] || 0) + safe.ownership;
    }
    
    waterfall.push({
      event: 'SAFE Conversion',
      impact: { ...postSAFE }
    });
    
    // Convert notes (simplified)
    const noteConversion = notes.reduce((sum, note) => {
      const interest = note.principal * note.interestRate * 
        ((Date.now() - note.maturityDate.getTime()) / (365 * 24 * 60 * 60 * 1000));
      const totalAmount = note.principal + interest;
      const conversionPrice = note.valuationCap 
        ? Math.min(note.valuationCap, nextRound.preMoneyValuation) * (1 - (note.discount || 0))
        : nextRound.preMoneyValuation * (1 - (note.discount || 0));
      
      return sum + (totalAmount / conversionPrice);
    }, 0);
    
    // Apply note dilution
    const postNotes = { ...postSAFE };
    const noteDilution = 1 - noteConversion;
    for (const holder in postNotes) {
      postNotes[holder] *= noteDilution;
    }
    
    waterfall.push({
      event: 'Note Conversion',
      impact: { ...postNotes }
    });
    
    // New round dilution
    const newInvestorOwnership = nextRound.amount / (nextRound.preMoneyValuation + nextRound.amount);
    const postConversion: Record<string, number> = {};
    
    for (const [holder, ownership] of Object.entries(postNotes)) {
      postConversion[holder] = ownership * (1 - newInvestorOwnership);
    }
    postConversion['Series New'] = newInvestorOwnership;
    
    waterfall.push({
      event: 'New Investment',
      impact: { ...postConversion }
    });
    
    // Fully diluted (including option pool)
    const optionPoolSize = options.allocated + options.available;
    const fullyDiluted: Record<string, number> = {};
    const optionDilution = 1 - optionPoolSize;
    
    for (const [holder, ownership] of Object.entries(postConversion)) {
      fullyDiluted[holder] = ownership * optionDilution;
    }
    fullyDiluted['Option Pool'] = optionPoolSize;
    
    waterfall.push({
      event: 'Fully Diluted',
      impact: { ...fullyDiluted }
    });
    
    return {
      preConversion,
      postConversion,
      fullyDiluted,
      waterfall
    };
  }
}

export const fundingAnalyzer = new FundingStructureAnalyzer();