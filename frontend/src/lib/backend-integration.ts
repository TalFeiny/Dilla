/**
 * Backend Integration Module - Complete wiring between Next.js and FastAPI
 * This replaces all duplicate API route logic in frontend
 */

import { getClientBackendUrl } from './backend-url';

const BACKEND_URL = getClientBackendUrl();

export class BackendIntegration {
  private static instance: BackendIntegration;
  
  private constructor() {}
  
  static getInstance(): BackendIntegration {
    if (!BackendIntegration.instance) {
      BackendIntegration.instance = new BackendIntegration();
    }
    return BackendIntegration.instance;
  }

  /**
   * Unified Brain - Single entry point for all agent operations
   */
  async unifiedBrain(request: {
    prompt: string;
    companies?: string[];
    format?: 'analysis' | 'deck' | 'spreadsheet' | 'cim' | 'matrix';
    context?: any;
    stream?: boolean;
  }) {
    const response = await fetch(`${BACKEND_URL}/api/agent/unified-brain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    });
    
    if (!response.ok) {
      throw new Error(`Backend error: ${response.statusText}`);
    }
    
    return response.json();
  }

  /**
   * PWERM Calculation with M&A opportunities
   */
  async calculatePWERM(params: {
    company: string;
    valuation: number;
    stage: string;
    sector?: string;
    revenue?: number;
    growthRate?: number;
  }) {
    const response = await fetch(`${BACKEND_URL}/api/pwerm/calculate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params)
    });
    
    return response.json();
  }

  /**
   * Get available skills
   */
  async getSkills() {
    const response = await fetch(`${BACKEND_URL}/api/agent/skills`);
    return response.json();
  }

  /**
   * Execute specific skill
   */
  async executeSkill(skillName: string, inputs: any) {
    const response = await fetch(`${BACKEND_URL}/api/agent/skills/${skillName}/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(inputs)
    });
    
    return response.json();
  }

  /**
   * Get task status
   */
  async getTaskStatus(taskId: string) {
    const response = await fetch(`${BACKEND_URL}/api/agent/task/${taskId}/status`);
    return response.json();
  }

  /**
   * Cancel running task
   */
  async cancelTask(taskId: string) {
    const response = await fetch(`${BACKEND_URL}/api/agent/task/${taskId}/cancel`, {
      method: 'POST'
    });
    
    return response.json();
  }

  /**
   * Company operations
   */
  async fetchCompanyData(companies: string[]) {
    return this.executeSkill('company-data-fetcher', { companies });
  }

  async sourceCompanies(criteria: string) {
    return this.executeSkill('company-sourcer', { criteria });
  }

  /**
   * Financial calculations
   */
  async calculateValuation(params: any) {
    return this.executeSkill('valuation-engine', params);
  }

  async priceConvertibles(params: any) {
    return this.executeSkill('convertible-pricer', params);
  }

  /**
   * Document generation
   */
  async generateDeck(data: any) {
    return this.executeSkill('deck-builder', data);
  }

  async generateCIM(data: any) {
    return this.executeSkill('cim-generator', data);
  }

  /**
   * Market analysis
   */
  async analyzeMarket(sector: string) {
    return this.executeSkill('market-researcher', { market: sector });
  }

  async analyzeCompetition(companies: string[]) {
    return this.executeSkill('competitive-intelligence', { companies });
  }

  /**
   * WebSocket connection for streaming
   */
  connectWebSocket(onMessage: (data: any) => void) {
    const ws = new WebSocket(`ws://localhost:8000/ws`);
    
    ws.onopen = () => {
      console.log('WebSocket connected');
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      onMessage(data);
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
    
    return ws;
  }
}

// Export singleton instance
export const backend = BackendIntegration.getInstance();