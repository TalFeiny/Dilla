/**
 * Private Credit Models
 * Specialized models for data center and football financing
 */

export interface PrivateCreditDeal {
  dealName: string;
  assetClass: 'data_center' | 'football' | 'infrastructure' | 'real_estate' | 'other';
  dealSize: number;
  currency: string;
  tenor: number; // years
  structure: 'senior' | 'mezzanine' | 'unitranche' | 'junior';
  geography: string;
  sponsor?: string;
}

/**
 * Data Center Financing Model
 */
export interface DataCenterDeal extends PrivateCreditDeal {
  assetClass: 'data_center';
  
  // Data center specifics
  location: string;
  tier: 1 | 2 | 3 | 4; // Uptime Institute tier classification
  capacity: {
    totalMW: number;
    leasedMW: number;
    utilization: number;
  };
  
  // Tenant information
  tenants: {
    hyperscale: number; // % from hyperscale (AWS, Azure, Google)
    enterprise: number; // % from enterprise
    colocation: number; // % from colocation
  };
  
  // Contract details
  weightedAverageLeaseLife: number; // WALL in years
  contractType: 'take-or-pay' | 'reserved' | 'on-demand';
  
  // Financial metrics
  revenue: {
    powerRevenue: number;
    spaceRevenue: number;
    interconnectionRevenue: number;
    managedServices: number;
  };
  
  operatingMetrics: {
    pue: number; // Power Usage Effectiveness
    occupancyRate: number;
    churnRate: number;
    arpu: number; // Average revenue per unit
  };
  
  // Debt metrics
  leverage: {
    totalDebtToEBITDA: number;
    seniorDebtToEBITDA: number;
    debtServiceCoverage: number;
    fixedChargeCoverage: number;
  };
  
  // ESG considerations
  esg: {
    renewableEnergyPercent: number;
    carbonNeutralTarget: number; // year
    waterUsageEffectiveness: number;
  };
}

/**
 * Football Financing Model
 */
export interface FootballFinancingDeal extends PrivateCreditDeal {
  assetClass: 'football';
  
  // Club information
  club: {
    name: string;
    league: string;
    country: string;
    uefaRanking?: number;
    domesticPosition: number;
  };
  
  // Revenue streams
  revenueStreams: {
    broadcasting: number;
    matchday: number;
    commercial: number;
    transferFees: number;
    merchandising: number;
    sponsorship: {
      mainSponsor: number;
      kitSponsor: number;
      stadiumNaming: number;
      other: number;
    };
  };
  
  // Stadium details
  stadium: {
    name: string;
    capacity: number;
    ownership: 'owned' | 'leased';
    utilizationRate: number;
    avgTicketPrice: number;
    nonMatchdayRevenue: number;
  };
  
  // Player assets
  squadValue: {
    totalMarketValue: number;
    topPlayerValues: Array<{
      player: string;
      value: number;
      contractExpiry: Date;
    }>;
    youthAcademyValue: number;
  };
  
  // Financial covenants
  covenants: {
    wageToRevenueRatio: number; // UEFA FFP requirement
    squadCostRatio: number;
    breakEvenResult: number;
    netDebtToRevenue: number;
  };
  
  // Security package
  security: {
    mediaRights: boolean;
    transferReceivables: boolean;
    stadiumMortgage: boolean;
    sponsorshipRights: boolean;
    seasonTicketDebentures: boolean;
  };
  
  // Risk factors
  riskFactors: {
    relegationRisk: 'low' | 'medium' | 'high';
    keyManRisk: string[]; // Key players/manager
    competitionPerformance: string;
    fanbaseStability: 'stable' | 'growing' | 'declining';
  };
}

/**
 * Private Credit Pricing Model
 */
export class PrivateCreditPricingModel {
  private baseRate: number = 0.05; // 5% base rate
  
  /**
   * Calculate yield for data center financing
   */
  priceDataCenterDeal(deal: DataCenterDeal): {
    targetYield: number;
    creditSpread: number;
    expectedLoss: number;
    requiredReturn: number;
    pricing: {
      margin: number;
      upfrontFee: number;
      exitFee: number;
      commitmentFee: number;
    };
  } {
    // Base spread based on structure
    let creditSpread = this.getBaseSpread(deal.structure);
    
    // Adjust for data center specific risks
    // Tier adjustment
    const tierAdjustment = (5 - deal.tier) * 0.0025; // 25bps per tier below 4
    creditSpread += tierAdjustment;
    
    // Utilization adjustment
    if (deal.capacity.utilization < 0.7) {
      creditSpread += 0.005; // 50bps for low utilization
    }
    
    // Tenant concentration adjustment
    if (deal.tenants.hyperscale < 0.3) {
      creditSpread += 0.0025; // 25bps for low hyperscale exposure
    }
    
    // WALL adjustment
    if (deal.weightedAverageLeaseLife < 3) {
      creditSpread += 0.005; // 50bps for short WALL
    }
    
    // Leverage adjustment
    if (deal.leverage.totalDebtToEBITDA > 6) {
      creditSpread += 0.01; // 100bps for high leverage
    }
    
    // ESG bonus
    if (deal.esg.renewableEnergyPercent > 0.5) {
      creditSpread -= 0.0025; // 25bps ESG discount
    }
    
    // Calculate expected loss
    const pd = this.calculatePD(deal.leverage.debtServiceCoverage);
    const lgd = this.calculateLGD(deal.structure, 'data_center');
    const expectedLoss = pd * lgd;
    
    const targetYield = this.baseRate + creditSpread;
    const requiredReturn = targetYield + expectedLoss;
    
    return {
      targetYield,
      creditSpread,
      expectedLoss,
      requiredReturn,
      pricing: {
        margin: creditSpread * 10000, // in bps
        upfrontFee: 0.02, // 2% upfront
        exitFee: 0.01, // 1% exit
        commitmentFee: 0.005 // 50bps commitment
      }
    };
  }

  /**
   * Calculate yield for football financing
   */
  priceFootballDeal(deal: FootballFinancingDeal): {
    targetYield: number;
    creditSpread: number;
    expectedLoss: number;
    requiredReturn: number;
    pricing: {
      margin: number;
      upfrontFee: number;
      exitFee: number;
      arrangementFee: number;
    };
    structuralFeatures: string[];
  } {
    // Base spread for football deals (higher risk)
    let creditSpread = this.getBaseSpread(deal.structure) + 0.01; // Extra 100bps for football
    
    // League quality adjustment
    const leagueMultiplier = this.getLeagueMultiplier(deal.club.league);
    creditSpread *= leagueMultiplier;
    
    // Revenue diversification adjustment
    const broadcastingConcentration = deal.revenueStreams.broadcasting / 
      (deal.revenueStreams.broadcasting + deal.revenueStreams.matchday + 
       deal.revenueStreams.commercial);
    
    if (broadcastingConcentration > 0.6) {
      creditSpread += 0.005; // 50bps for high broadcasting dependence
    }
    
    // Stadium ownership benefit
    if (deal.stadium.ownership === 'owned') {
      creditSpread -= 0.0025; // 25bps benefit for owned stadium
    }
    
    // FFP compliance
    if (deal.covenants.wageToRevenueRatio > 0.7) {
      creditSpread += 0.0075; // 75bps for high wage ratio
    }
    
    // Relegation risk adjustment
    const relegationAdjustment = {
      'low': 0,
      'medium': 0.01, // 100bps
      'high': 0.025 // 250bps
    };
    creditSpread += relegationAdjustment[deal.riskFactors.relegationRisk];
    
    // Security package benefit
    const securityCount = Object.values(deal.security).filter(s => s).length;
    creditSpread -= securityCount * 0.0015; // 15bps per security type
    
    // Calculate expected loss with football-specific parameters
    const pd = this.calculateFootballPD(deal);
    const lgd = this.calculateLGD(deal.structure, 'football', deal.security);
    const expectedLoss = pd * lgd;
    
    const targetYield = this.baseRate + creditSpread;
    const requiredReturn = targetYield + expectedLoss;
    
    // Structural features for football deals
    const structuralFeatures = [];
    if (deal.security.mediaRights) structuralFeatures.push('Media rights assignment');
    if (deal.security.transferReceivables) structuralFeatures.push('Transfer receivables pledge');
    if (deal.covenants.wageToRevenueRatio < 0.6) structuralFeatures.push('Wage cap covenant');
    if (deal.riskFactors.relegationRisk === 'high') structuralFeatures.push('Relegation prepayment clause');
    
    return {
      targetYield,
      creditSpread,
      expectedLoss,
      requiredReturn,
      pricing: {
        margin: creditSpread * 10000, // in bps
        upfrontFee: 0.025, // 2.5% upfront (higher for football)
        exitFee: 0.015, // 1.5% exit
        arrangementFee: 0.02 // 2% arrangement
      },
      structuralFeatures
    };
  }

  /**
   * Portfolio analysis for private credit book
   */
  analyzePortfolio(deals: PrivateCreditDeal[]): {
    totalExposure: number;
    assetClassBreakdown: Map<string, number>;
    geographicBreakdown: Map<string, number>;
    structureBreakdown: Map<string, number>;
    weightedAverageYield: number;
    expectedPortfolioLoss: number;
    concentrationRisk: {
      largestExposure: number;
      top5Concentration: number;
      herfindahlIndex: number;
    };
    riskMetrics: {
      portfolioLTV: number;
      portfolioDSCR: number;
      expectedDefaultRate: number;
      stressedDefaultRate: number;
    };
  } {
    const totalExposure = deals.reduce((sum, deal) => sum + deal.dealSize, 0);
    
    // Asset class breakdown
    const assetClassBreakdown = new Map<string, number>();
    deals.forEach(deal => {
      const current = assetClassBreakdown.get(deal.assetClass) || 0;
      assetClassBreakdown.set(deal.assetClass, current + deal.dealSize);
    });
    
    // Geographic breakdown
    const geographicBreakdown = new Map<string, number>();
    deals.forEach(deal => {
      const current = geographicBreakdown.get(deal.geography) || 0;
      geographicBreakdown.set(deal.geography, current + deal.dealSize);
    });
    
    // Structure breakdown
    const structureBreakdown = new Map<string, number>();
    deals.forEach(deal => {
      const current = structureBreakdown.get(deal.structure) || 0;
      structureBreakdown.set(deal.structure, current + deal.dealSize);
    });
    
    // Calculate weighted average yield
    let totalWeightedYield = 0;
    let totalExpectedLoss = 0;
    
    deals.forEach(deal => {
      const weight = deal.dealSize / totalExposure;
      let dealYield = 0;
      let dealExpectedLoss = 0;
      
      if (deal.assetClass === 'data_center') {
        const pricing = this.priceDataCenterDeal(deal as DataCenterDeal);
        dealYield = pricing.targetYield;
        dealExpectedLoss = pricing.expectedLoss;
      } else if (deal.assetClass === 'football') {
        const pricing = this.priceFootballDeal(deal as FootballFinancingDeal);
        dealYield = pricing.targetYield;
        dealExpectedLoss = pricing.expectedLoss;
      }
      
      totalWeightedYield += dealYield * weight;
      totalExpectedLoss += dealExpectedLoss * weight;
    });
    
    // Concentration risk
    const sortedDeals = [...deals].sort((a, b) => b.dealSize - a.dealSize);
    const largestExposure = sortedDeals[0].dealSize / totalExposure;
    const top5Exposure = sortedDeals.slice(0, 5).reduce((sum, d) => sum + d.dealSize, 0);
    const top5Concentration = top5Exposure / totalExposure;
    
    // Herfindahl Index
    const herfindahlIndex = deals.reduce((sum, deal) => {
      const weight = deal.dealSize / totalExposure;
      return sum + Math.pow(weight, 2);
    }, 0);
    
    // Portfolio risk metrics (simplified)
    const portfolioLTV = 0.65; // Placeholder
    const portfolioDSCR = 1.8; // Placeholder
    const expectedDefaultRate = totalExpectedLoss;
    const stressedDefaultRate = expectedDefaultRate * 2.5; // 2.5x stress multiplier
    
    return {
      totalExposure,
      assetClassBreakdown,
      geographicBreakdown,
      structureBreakdown,
      weightedAverageYield: totalWeightedYield,
      expectedPortfolioLoss: totalExpectedLoss,
      concentrationRisk: {
        largestExposure,
        top5Concentration,
        herfindahlIndex
      },
      riskMetrics: {
        portfolioLTV,
        portfolioDSCR,
        expectedDefaultRate,
        stressedDefaultRate
      }
    };
  }

  /**
   * Helper methods
   */
  private getBaseSpread(structure: string): number {
    const spreads = {
      'senior': 0.025, // 250bps
      'unitranche': 0.045, // 450bps
      'mezzanine': 0.065, // 650bps
      'junior': 0.085 // 850bps
    };
    return spreads[structure] || 0.05;
  }

  private getLeagueMultiplier(league: string): number {
    const multipliers = {
      'Premier League': 0.9,
      'La Liga': 0.95,
      'Bundesliga': 0.95,
      'Serie A': 1.0,
      'Ligue 1': 1.05,
      'Championship': 1.3,
      'Other': 1.5
    };
    return multipliers[league] || 1.2;
  }

  private calculatePD(dscr: number): number {
    // Simplified PD calculation based on DSCR
    if (dscr > 2.0) return 0.01; // 1%
    if (dscr > 1.5) return 0.025; // 2.5%
    if (dscr > 1.2) return 0.05; // 5%
    if (dscr > 1.0) return 0.10; // 10%
    return 0.20; // 20%
  }

  private calculateFootballPD(deal: FootballFinancingDeal): number {
    let basePD = 0.03; // 3% base for football
    
    // Adjust for relegation risk
    if (deal.riskFactors.relegationRisk === 'high') basePD *= 3;
    else if (deal.riskFactors.relegationRisk === 'medium') basePD *= 1.5;
    
    // Adjust for wage ratio
    if (deal.covenants.wageToRevenueRatio > 0.8) basePD *= 1.5;
    
    return Math.min(basePD, 0.25); // Cap at 25%
  }

  private calculateLGD(structure: string, assetClass: string, security?: any): number {
    let baseLGD = {
      'senior': 0.30,
      'unitranche': 0.40,
      'mezzanine': 0.60,
      'junior': 0.75
    }[structure] || 0.50;
    
    // Adjust for asset class
    if (assetClass === 'data_center') {
      baseLGD *= 0.8; // Better recovery for data centers
    } else if (assetClass === 'football') {
      baseLGD *= 1.2; // Worse recovery for football
      
      // Adjust for security package
      if (security) {
        const securityCount = Object.values(security).filter(s => s).length;
        baseLGD *= (1 - securityCount * 0.05); // 5% LGD reduction per security
      }
    }
    
    return Math.min(baseLGD, 1.0);
  }
}

/**
 * Create sample portfolio of private credit deals
 */
export function createSamplePortfolio(): PrivateCreditDeal[] {
  const deals: PrivateCreditDeal[] = [];
  
  // Data center deals
  deals.push({
    dealName: 'HyperScale DC Portfolio',
    assetClass: 'data_center',
    dealSize: 500000000, // $500M
    currency: 'USD',
    tenor: 5,
    structure: 'senior',
    geography: 'US',
    sponsor: 'Infrastructure Fund I',
    location: 'Northern Virginia',
    tier: 4,
    capacity: {
      totalMW: 100,
      leasedMW: 85,
      utilization: 0.85
    },
    tenants: {
      hyperscale: 0.70,
      enterprise: 0.20,
      colocation: 0.10
    },
    weightedAverageLeaseLife: 7.5,
    contractType: 'take-or-pay',
    revenue: {
      powerRevenue: 120000000,
      spaceRevenue: 80000000,
      interconnectionRevenue: 20000000,
      managedServices: 30000000
    },
    operatingMetrics: {
      pue: 1.3,
      occupancyRate: 0.85,
      churnRate: 0.05,
      arpu: 2500
    },
    leverage: {
      totalDebtToEBITDA: 5.5,
      seniorDebtToEBITDA: 4.0,
      debtServiceCoverage: 1.85,
      fixedChargeCoverage: 2.1
    },
    esg: {
      renewableEnergyPercent: 0.60,
      carbonNeutralTarget: 2030,
      waterUsageEffectiveness: 1.6
    }
  } as DataCenterDeal);
  
  // Football deals
  deals.push({
    dealName: 'Premier League Club Facility',
    assetClass: 'football',
    dealSize: 250000000, // £250M
    currency: 'GBP',
    tenor: 7,
    structure: 'unitranche',
    geography: 'UK',
    sponsor: 'Sports Capital Partners',
    club: {
      name: 'Mid-Table FC',
      league: 'Premier League',
      country: 'England',
      uefaRanking: 25,
      domesticPosition: 10
    },
    revenueStreams: {
      broadcasting: 150000000,
      matchday: 40000000,
      commercial: 60000000,
      transferFees: 30000000,
      merchandising: 20000000,
      sponsorship: {
        mainSponsor: 15000000,
        kitSponsor: 10000000,
        stadiumNaming: 5000000,
        other: 10000000
      }
    },
    stadium: {
      name: 'Historic Ground',
      capacity: 45000,
      ownership: 'owned',
      utilizationRate: 0.92,
      avgTicketPrice: 45,
      nonMatchdayRevenue: 5000000
    },
    squadValue: {
      totalMarketValue: 400000000,
      topPlayerValues: [
        { player: 'Star Striker', value: 60000000, contractExpiry: new Date('2026-06-30') },
        { player: 'Key Midfielder', value: 45000000, contractExpiry: new Date('2025-06-30') },
        { player: 'Top Defender', value: 35000000, contractExpiry: new Date('2027-06-30') }
      ],
      youthAcademyValue: 50000000
    },
    covenants: {
      wageToRevenueRatio: 0.65,
      squadCostRatio: 0.70,
      breakEvenResult: 5000000,
      netDebtToRevenue: 0.8
    },
    security: {
      mediaRights: true,
      transferReceivables: true,
      stadiumMortgage: false,
      sponsorshipRights: true,
      seasonTicketDebentures: false
    },
    riskFactors: {
      relegationRisk: 'low',
      keyManRisk: ['Manager', 'Star Striker'],
      competitionPerformance: 'Europa League Qualification',
      fanbaseStability: 'stable'
    }
  } as FootballFinancingDeal);
  
  return deals;
}