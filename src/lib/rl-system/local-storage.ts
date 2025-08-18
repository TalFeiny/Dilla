// Local storage fallback for RL experiences when database is not available

export class LocalRLStorage {
  private experiences: any[] = [];
  private maxSize = 1000;
  
  constructor() {
    this.loadFromLocalStorage();
  }
  
  private loadFromLocalStorage() {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('rl_experiences');
      if (stored) {
        try {
          this.experiences = JSON.parse(stored);
          console.log(`📚 Loaded ${this.experiences.length} past experiences from local storage`);
        } catch (e) {
          console.error('Failed to load experiences:', e);
          this.experiences = [];
        }
      }
    }
  }
  
  private saveToLocalStorage() {
    if (typeof window !== 'undefined') {
      try {
        localStorage.setItem('rl_experiences', JSON.stringify(this.experiences));
      } catch (e) {
        console.error('Failed to save experiences:', e);
      }
    }
  }
  
  async storeExperience(experience: any) {
    this.experiences.push({
      ...experience,
      timestamp: new Date().toISOString()
    });
    
    // Keep only recent experiences
    if (this.experiences.length > this.maxSize) {
      this.experiences = this.experiences.slice(-this.maxSize);
    }
    
    this.saveToLocalStorage();
    console.log(`💾 Stored experience locally (total: ${this.experiences.length})`);
    
    return { success: true, id: this.experiences.length - 1 };
  }
  
  async getSimilarExperiences(embedding: number[], limit: number = 5) {
    if (this.experiences.length === 0) {
      return [];
    }
    
    // Simple similarity based on reward and metadata matching
    const scored = this.experiences
      .filter(exp => exp.reward > 0.5) // Only get successful experiences
      .map(exp => ({
        ...exp,
        similarity: this.calculateSimilarity(exp, embedding)
      }))
      .sort((a, b) => b.similarity - a.similarity)
      .slice(0, limit);
    
    if (scored.length > 0) {
      console.log(`🔍 Found ${scored.length} similar past experiences`);
      console.log(`📈 Best match had ${(scored[0].reward * 100).toFixed(0)}% success rate`);
    }
    
    return scored;
  }
  
  private calculateSimilarity(exp: any, embedding: number[]): number {
    // Simple similarity based on metadata and reward
    let score = exp.reward; // Start with reward as base score
    
    // Boost if it's the same model type
    if (exp.metadata?.modelType === 'DCF') score += 0.2;
    
    // Recent experiences get a small boost
    const hoursSince = (Date.now() - new Date(exp.timestamp).getTime()) / (1000 * 60 * 60);
    if (hoursSince < 24) score += 0.1;
    
    return Math.min(score, 1.0);
  }
  
  getStats() {
    const successfulExperiences = this.experiences.filter(e => e.reward > 0.5);
    const avgReward = this.experiences.length > 0
      ? this.experiences.reduce((sum, e) => sum + e.reward, 0) / this.experiences.length
      : 0;
    
    return {
      totalExperiences: this.experiences.length,
      successfulExperiences: successfulExperiences.length,
      avgReward,
      successRate: this.experiences.length > 0 
        ? (successfulExperiences.length / this.experiences.length * 100).toFixed(1) + '%'
        : '0%'
    };
  }
  
  clearAll() {
    this.experiences = [];
    this.saveToLocalStorage();
    console.log('🗑️ Cleared all RL experiences');
  }
}

export const rlStorage = new LocalRLStorage();