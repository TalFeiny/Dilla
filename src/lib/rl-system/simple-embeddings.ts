'use client';

// Simple client-side embeddings without heavy ML libraries
export class SimpleEmbeddings {
  private static instance: SimpleEmbeddings;

  static getInstance(): SimpleEmbeddings {
    if (!SimpleEmbeddings.instance) {
      SimpleEmbeddings.instance = new SimpleEmbeddings();
    }
    return SimpleEmbeddings.instance;
  }

  // Add initialize method for compatibility
  async initialize(): Promise<void> {
    // No initialization needed for simple embeddings
    return Promise.resolve();
  }

  // Simple hash-based embedding for client-side
  async embed(text: string, dimensions: number = 384): Promise<number[]> {
    const embedding = new Array(dimensions).fill(0);
    
    // Simple but deterministic embedding
    for (let i = 0; i < text.length; i++) {
      const charCode = text.charCodeAt(i);
      const index = (charCode * (i + 1)) % dimensions;
      embedding[index] = (embedding[index] + charCode / 255) / 2;
    }
    
    // Normalize
    const norm = Math.sqrt(embedding.reduce((sum, val) => sum + val * val, 0));
    if (norm > 0) {
      for (let i = 0; i < dimensions; i++) {
        embedding[i] = embedding[i] / norm;
      }
    }
    
    return embedding;
  }

  async embedGrid(grid: Record<string, any>): Promise<number[]> {
    const gridText = Object.entries(grid)
      .map(([key, value]) => `${key}:${JSON.stringify(value)}`)
      .join(',');
    return this.embed(gridText);
  }

  async embedAction(action: string): Promise<number[]> {
    return this.embed(action);
  }

  async embedFeedback(feedback: string): Promise<number[]> {
    return this.embed(feedback);
  }
}