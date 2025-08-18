'use client';

import { SimpleEmbeddings as LocalEmbeddings } from './simple-embeddings';
import { rlStorage } from './local-storage';

export interface Experience {
  stateEmbedding: number[];
  actionEmbedding: number[];
  nextStateEmbedding: number[];
  reward: number;
  metadata: {
    actionText: string;
    actionType: string;
    gridBeforeSize: number;
    gridAfterSize: number;
    modelType?: string;
    company?: string;
    userIntent?: string;
    feedbackType?: string;
    specificFeedback?: string;
    timestamp: Date;
  };
}

export class ExperienceCollector {
  private embeddings: LocalEmbeddings;
  private buffer: Experience[] = [];
  private maxBufferSize = 100;
  
  constructor() {
    this.embeddings = LocalEmbeddings.getInstance();
  }
  
  async collectExperience(
    gridBefore: Record<string, any>,
    action: string,
    gridAfter: Record<string, any>,
    reward: number,
    metadata?: Partial<Experience['metadata']>
  ): Promise<Experience> {
    // Ensure embeddings are initialized
    await this.embeddings.initialize();
    
    // Parse action to determine type
    const actionType = this.parseActionType(action);
    
    // Create embeddings in parallel for efficiency
    const [stateEmb, actionEmb, nextStateEmb] = await Promise.all([
      this.embeddings.embedGrid(gridBefore),
      this.embeddings.embedAction(action),
      this.embeddings.embedGrid(gridAfter)
    ]);
    
    const experience: Experience = {
      stateEmbedding: stateEmb,
      actionEmbedding: actionEmb,
      nextStateEmbedding: nextStateEmb,
      reward,
      metadata: {
        actionText: action,
        actionType,
        gridBeforeSize: Object.keys(gridBefore).length,
        gridAfterSize: Object.keys(gridAfter).length,
        timestamp: new Date(),
        ...metadata
      }
    };
    
    // Add to local buffer
    this.addToBuffer(experience);
    
    // Store in database
    await this.storeExperience(experience);
    
    return experience;
  }
  
  private parseActionType(action: string): string {
    if (action.includes('.write')) return 'write';
    if (action.includes('.formula')) return 'formula';
    if (action.includes('.format')) return 'format';
    if (action.includes('.style')) return 'style';
    if (action.includes('.clear')) return 'clear';
    if (action.includes('.link')) return 'link';
    if (action.includes('.writeRange')) return 'writeRange';
    return 'unknown';
  }
  
  private addToBuffer(experience: Experience) {
    this.buffer.push(experience);
    if (this.buffer.length > this.maxBufferSize) {
      this.buffer.shift(); // Remove oldest
    }
  }
  
  async storeExperience(experience: Experience) {
    // Try API first, fall back to local storage
    try {
      const response = await fetch('/api/agent/rl-experience', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          state_embedding: experience.stateEmbedding,
          action_embedding: experience.actionEmbedding,
          next_state_embedding: experience.nextStateEmbedding,
          reward: experience.reward,
          metadata: experience.metadata
        })
      });
      
      if (!response.ok) {
        console.warn('API storage failed, using local storage');
        await rlStorage.storeExperience(experience);
      }
    } catch (error) {
      console.warn('API unavailable, using local storage:', error);
      // Fall back to local storage
      await rlStorage.storeExperience(experience);
    }
  }
  
  // Get recent experiences from buffer
  getRecentExperiences(count: number = 10): Experience[] {
    return this.buffer.slice(-count);
  }
  
  // Get experiences with high rewards
  getSuccessfulExperiences(minReward: number = 0.5): Experience[] {
    return this.buffer.filter(exp => exp.reward >= minReward);
  }
  
  // Calculate average reward for recent experiences
  getAverageReward(): number {
    if (this.buffer.length === 0) return 0;
    const sum = this.buffer.reduce((acc, exp) => acc + exp.reward, 0);
    return sum / this.buffer.length;
  }
  
  // Find similar past experiences
  async findSimilarExperiences(
    currentGrid: Record<string, any>,
    threshold: number = 0.8
  ): Promise<Experience[]> {
    const currentEmbedding = await this.embeddings.embedGrid(currentGrid);
    
    return this.buffer
      .map(exp => ({
        exp,
        similarity: this.embeddings.cosineSimilarity(currentEmbedding, exp.stateEmbedding)
      }))
      .filter(({ similarity }) => similarity >= threshold)
      .sort((a, b) => b.similarity - a.similarity)
      .map(({ exp }) => exp);
  }
  
  // Clear buffer
  clearBuffer() {
    this.buffer = [];
  }
  
  // Export buffer for analysis
  exportBuffer(): Experience[] {
    return [...this.buffer];
  }
  
  // Import experiences (for testing or replay)
  importBuffer(experiences: Experience[]) {
    this.buffer = experiences.slice(0, this.maxBufferSize);
  }
}