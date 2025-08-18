/**
 * Test Suite for RL Generalization
 * Ensures the system can handle diverse queries without overfitting
 */

import { adaptiveAgent } from './adaptive-agent';

interface TestCase {
  query: string;
  expectedCategory: string;
  expectedApproach?: string;
  shouldSucceed: boolean;
}

export class GeneralizationTester {
  private testCases: TestCase[] = [
    // Standard financial models (should use templates)
    {
      query: "Create a DCF model for Stripe with 5 year projections",
      expectedCategory: "financial",
      expectedApproach: "template",
      shouldSucceed: true
    },
    {
      query: "Build revenue forecast for TechCo growing at 20% annually",
      expectedCategory: "financial",
      expectedApproach: "template",
      shouldSucceed: true
    },
    
    // Variations requiring adaptation
    {
      query: "Make a cash flow analysis but include seasonal adjustments",
      expectedCategory: "financial",
      expectedApproach: "hybrid",
      shouldSucceed: true
    },
    {
      query: "Generate P&L with custom line items for SaaS metrics",
      expectedCategory: "financial",
      expectedApproach: "hybrid",
      shouldSucceed: true
    },
    
    // Novel queries requiring exploration
    {
      query: "Track customer churn cohorts month over month",
      expectedCategory: "operational",
      expectedApproach: "exploration",
      shouldSucceed: true
    },
    {
      query: "Analyze product-market fit using engagement metrics",
      expectedCategory: "strategic",
      expectedApproach: "exploration",
      shouldSucceed: true
    },
    
    // Edge cases
    {
      query: "something something revenue",
      expectedCategory: "general",
      expectedApproach: "exploration",
      shouldSucceed: false
    },
    {
      query: "42",
      expectedCategory: "general",
      expectedApproach: "exploration",
      shouldSucceed: false
    },
    
    // Complex multi-step
    {
      query: "Create DCF, then add sensitivity analysis, then generate charts",
      expectedCategory: "financial",
      expectedApproach: "hybrid",
      shouldSucceed: true
    },
    
    // Domain variations
    {
      query: "Calculate unit economics for marketplace business",
      expectedCategory: "financial",
      expectedApproach: "learned",
      shouldSucceed: true
    },
    {
      query: "Model network effects impact on valuation",
      expectedCategory: "valuation",
      expectedApproach: "exploration",
      shouldSucceed: true
    }
  ];
  
  /**
   * Run all generalization tests
   */
  async runTests(): Promise<{
    passed: number;
    failed: number;
    results: any[];
  }> {
    const results = [];
    let passed = 0;
    let failed = 0;
    
    for (const testCase of this.testCases) {
      const result = await this.runSingleTest(testCase);
      results.push(result);
      
      if (result.passed) {
        passed++;
      } else {
        failed++;
      }
      
      console.log(`Test: ${testCase.query.substring(0, 50)}...`);
      console.log(`  Expected: ${testCase.expectedCategory}, Got: ${result.classification.category}`);
      console.log(`  Approach: ${result.approach}, Confidence: ${result.confidence.toFixed(2)}`);
      console.log(`  Result: ${result.passed ? '✅' : '❌'}\n`);
    }
    
    return { passed, failed, results };
  }
  
  /**
   * Run single test case
   */
  private async runSingleTest(testCase: TestCase): Promise<any> {
    const mockGrid = this.createMockGrid();
    
    try {
      const result = await adaptiveAgent.processQuery(
        testCase.query,
        mockGrid
      );
      
      // Check category match
      const categoryMatch = result.classification?.category === testCase.expectedCategory;
      
      // Check approach match (if specified)
      const approachMatch = !testCase.expectedApproach || 
                           result.approach === testCase.expectedApproach;
      
      // Check if actions were generated
      const hasActions = result.actions && result.actions.length > 0;
      
      // Determine if test passed
      const passed = categoryMatch && approachMatch && 
                    (hasActions === testCase.shouldSucceed);
      
      return {
        testCase,
        result,
        passed,
        categoryMatch,
        approachMatch,
        hasActions,
        classification: result.classification,
        approach: result.approach,
        confidence: result.confidence
      };
      
    } catch (error) {
      return {
        testCase,
        passed: false,
        error: error.message
      };
    }
  }
  
  /**
   * Test adaptation capability
   */
  async testAdaptation(): Promise<void> {
    console.log("Testing adaptation to feedback...\n");
    
    // Test query
    const query = "Create revenue projections";
    const mockGrid = this.createMockGrid();
    
    // First attempt
    console.log("Initial attempt:");
    let result = await adaptiveAgent.processQuery(query, mockGrid);
    console.log(`Approach: ${result.approach}, Actions: ${result.actions.length}`);
    
    // Provide negative feedback
    console.log("\nProviding negative feedback...");
    await adaptiveAgent.processFeedback(
      query,
      result.approach,
      result.actions,
      {
        success: false,
        reward: -0.5,
        correction: "Revenue should start at 10M with 15% monthly growth"
      }
    );
    
    // Second attempt (should adapt)
    console.log("\nSecond attempt (after learning):");
    result = await adaptiveAgent.processQuery(query, mockGrid);
    console.log(`Approach: ${result.approach}, Actions: ${result.actions.length}`);
    console.log("Actions now include:", result.actions[0]);
  }
  
  /**
   * Test exploration vs exploitation
   */
  async testExplorationBalance(): Promise<void> {
    console.log("Testing exploration/exploitation balance...\n");
    
    const queries = [
      "Create financial model",
      "Create financial model", // Repeat
      "Create financial model", // Repeat
      "Build something completely new and innovative"
    ];
    
    const approaches = [];
    
    for (const query of queries) {
      const result = await adaptiveAgent.processQuery(
        query,
        this.createMockGrid()
      );
      approaches.push(result.approach);
    }
    
    console.log("Approaches chosen:", approaches);
    
    // Check that system doesn't always use same approach
    const uniqueApproaches = new Set(approaches).size;
    console.log(`Unique approaches: ${uniqueApproaches}/4`);
    console.log(`Balance: ${uniqueApproaches > 1 ? '✅ Good' : '❌ Too rigid'}`);
  }
  
  /**
   * Create mock grid for testing
   */
  private createMockGrid(): any[][] {
    return Array(20).fill(null).map(() => Array(10).fill(null));
  }
  
  /**
   * Generate performance report
   */
  generateReport(results: any): string {
    const report = `
# RL Generalization Test Report

## Summary
- Total Tests: ${results.passed + results.failed}
- Passed: ${results.passed} (${(results.passed / (results.passed + results.failed) * 100).toFixed(1)}%)
- Failed: ${results.failed}

## Category Accuracy
${this.analyzeCategoryAccuracy(results.results)}

## Approach Distribution
${this.analyzeApproachDistribution(results.results)}

## Confidence Analysis
${this.analyzeConfidence(results.results)}

## Recommendations
${this.generateRecommendations(results)}
    `;
    
    return report;
  }
  
  private analyzeCategoryAccuracy(results: any[]): string {
    const categories = {};
    
    for (const r of results) {
      const cat = r.testCase.expectedCategory;
      if (!categories[cat]) {
        categories[cat] = { correct: 0, total: 0 };
      }
      categories[cat].total++;
      if (r.categoryMatch) {
        categories[cat].correct++;
      }
    }
    
    return Object.entries(categories)
      .map(([cat, stats]: [string, any]) => 
        `- ${cat}: ${stats.correct}/${stats.total} (${(stats.correct/stats.total*100).toFixed(1)}%)`
      )
      .join('\n');
  }
  
  private analyzeApproachDistribution(results: any[]): string {
    const approaches = {};
    
    for (const r of results) {
      const approach = r.approach || 'none';
      approaches[approach] = (approaches[approach] || 0) + 1;
    }
    
    return Object.entries(approaches)
      .map(([approach, count]) => 
        `- ${approach}: ${count} (${(count/results.length*100).toFixed(1)}%)`
      )
      .join('\n');
  }
  
  private analyzeConfidence(results: any[]): string {
    const confidences = results.map(r => r.confidence || 0);
    const avg = confidences.reduce((a, b) => a + b, 0) / confidences.length;
    const min = Math.min(...confidences);
    const max = Math.max(...confidences);
    
    return `- Average: ${avg.toFixed(2)}\n- Min: ${min.toFixed(2)}\n- Max: ${max.toFixed(2)}`;
  }
  
  private generateRecommendations(results: any): string {
    const recommendations = [];
    
    if (results.failed > results.passed * 0.2) {
      recommendations.push("- High failure rate detected. Consider expanding training data.");
    }
    
    const lowConfidence = results.results.filter(r => r.confidence < 0.5).length;
    if (lowConfidence > results.results.length * 0.3) {
      recommendations.push("- Many low-confidence classifications. Add more specific patterns.");
    }
    
    const explorationCount = results.results.filter(r => r.approach === 'exploration').length;
    if (explorationCount > results.results.length * 0.5) {
      recommendations.push("- Over-reliance on exploration. Build more learned patterns.");
    }
    
    if (recommendations.length === 0) {
      recommendations.push("- System is performing well! Continue monitoring.");
    }
    
    return recommendations.join('\n');
  }
}

// Export test runner
export async function runGeneralizationTests() {
  const tester = new GeneralizationTester();
  
  console.log("Starting RL Generalization Tests...\n");
  console.log("=" .repeat(50));
  
  // Run main tests
  const results = await tester.runTests();
  
  console.log("=" .repeat(50));
  
  // Run adaptation test
  await tester.testAdaptation();
  
  console.log("=" .repeat(50));
  
  // Run exploration test
  await tester.testExplorationBalance();
  
  console.log("=" .repeat(50));
  
  // Generate report
  const report = tester.generateReport(results);
  console.log(report);
  
  return results;
}