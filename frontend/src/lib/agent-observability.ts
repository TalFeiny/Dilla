/**
 * Agent Observability System
 * Provides real-time progress tracking for long-running agents
 */

export interface AgentProgress {
  taskId: string;
  startTime: number;
  currentTime: number;
  elapsed: string;
  stage: 'initializing' | 'analyzing' | 'gathering' | 'processing' | 'generating' | 'finalizing' | 'complete' | 'error';
  currentSkill?: string;
  currentTool?: string;
  skillsCompleted: string[];
  toolsUsed: string[];
  dataSourcesAccessed: string[];
  frameworksActivated: string[];
  progress: number; // 0-100
  message: string;
  subTasks?: SubTask[];
  metrics?: {
    apiCalls: number;
    dataPoints: number;
    tokensUsed: number;
    cacheHits: number;
  };
  errors?: string[];
}

export interface SubTask {
  name: string;
  status: 'pending' | 'running' | 'complete' | 'failed';
  startTime?: number;
  endTime?: number;
  duration?: string;
  result?: any;
}

export class AgentObservability {
  private static instance: AgentObservability;
  private progressStreams = new Map<string, (progress: AgentProgress) => void>();
  private activeAgents = new Map<string, AgentProgress>();
  
  static getInstance(): AgentObservability {
    if (!AgentObservability.instance) {
      AgentObservability.instance = new AgentObservability();
    }
    return AgentObservability.instance;
  }
  
  /**
   * Start tracking a new agent task
   */
  startTask(taskId: string, description: string): AgentProgress {
    const progress: AgentProgress = {
      taskId,
      startTime: Date.now(),
      currentTime: Date.now(),
      elapsed: '0s',
      stage: 'initializing',
      skillsCompleted: [],
      toolsUsed: [],
      dataSourcesAccessed: [],
      frameworksActivated: [],
      progress: 0,
      message: `Starting: ${description}`,
      subTasks: [],
      metrics: {
        apiCalls: 0,
        dataPoints: 0,
        tokensUsed: 0,
        cacheHits: 0
      }
    };
    
    this.activeAgents.set(taskId, progress);
    this.broadcast(taskId, progress);
    
    // Start heartbeat
    this.startHeartbeat(taskId);
    
    return progress;
  }
  
  /**
   * Update agent progress
   */
  updateProgress(
    taskId: string, 
    updates: Partial<AgentProgress>
  ): void {
    const progress = this.activeAgents.get(taskId);
    if (!progress) return;
    
    // Update fields
    Object.assign(progress, updates);
    
    // Update timing
    progress.currentTime = Date.now();
    progress.elapsed = this.formatDuration(progress.currentTime - progress.startTime);
    
    // Calculate progress percentage based on stage
    if (updates.stage) {
      const stageProgress = {
        'initializing': 5,
        'analyzing': 15,
        'gathering': 40,
        'processing': 60,
        'generating': 80,
        'finalizing': 95,
        'complete': 100,
        'error': progress.progress
      };
      progress.progress = stageProgress[updates.stage] || progress.progress;
    }
    
    this.broadcast(taskId, progress);
  }
  
  /**
   * Log skill execution
   */
  logSkill(taskId: string, skillName: string, status: 'start' | 'complete' | 'failed'): void {
    const progress = this.activeAgents.get(taskId);
    if (!progress) return;
    
    if (status === 'start') {
      progress.currentSkill = skillName;
      progress.message = `Executing skill: ${skillName}`;
      
      // Add to subtasks
      if (!progress.subTasks) progress.subTasks = [];
      progress.subTasks.push({
        name: skillName,
        status: 'running',
        startTime: Date.now()
      });
    } else if (status === 'complete') {
      progress.skillsCompleted.push(skillName);
      progress.currentSkill = undefined;
      progress.message = `Completed: ${skillName}`;
      
      // Update subtask
      const subtask = progress.subTasks?.find(t => t.name === skillName && t.status === 'running');
      if (subtask) {
        subtask.status = 'complete';
        subtask.endTime = Date.now();
        subtask.duration = this.formatDuration(subtask.endTime - (subtask.startTime || 0));
      }
    } else if (status === 'failed') {
      progress.message = `Failed: ${skillName}`;
      if (!progress.errors) progress.errors = [];
      progress.errors.push(`Skill failed: ${skillName}`);
      
      // Update subtask
      const subtask = progress.subTasks?.find(t => t.name === skillName && t.status === 'running');
      if (subtask) {
        subtask.status = 'failed';
        subtask.endTime = Date.now();
      }
    }
    
    this.broadcast(taskId, progress);
  }
  
  /**
   * Log tool usage
   */
  logTool(taskId: string, toolName: string, dataSource?: string): void {
    const progress = this.activeAgents.get(taskId);
    if (!progress) return;
    
    progress.currentTool = toolName;
    progress.toolsUsed.push(toolName);
    progress.message = `Using tool: ${toolName}`;
    
    if (dataSource && !progress.dataSourcesAccessed.includes(dataSource)) {
      progress.dataSourcesAccessed.push(dataSource);
    }
    
    // Increment metrics
    if (progress.metrics) {
      progress.metrics.apiCalls++;
    }
    
    this.broadcast(taskId, progress);
  }
  
  /**
   * Log framework activation
   */
  logFramework(taskId: string, framework: string): void {
    const progress = this.activeAgents.get(taskId);
    if (!progress) return;
    
    if (!progress.frameworksActivated.includes(framework)) {
      progress.frameworksActivated.push(framework);
      progress.message = `Activated framework: ${framework}`;
    }
    
    this.broadcast(taskId, progress);
  }
  
  /**
   * Complete a task
   */
  completeTask(taskId: string, result?: any): void {
    const progress = this.activeAgents.get(taskId);
    if (!progress) return;
    
    progress.stage = 'complete';
    progress.progress = 100;
    progress.message = 'Task completed successfully';
    progress.currentTime = Date.now();
    progress.elapsed = this.formatDuration(progress.currentTime - progress.startTime);
    
    this.broadcast(taskId, progress);
    
    // Clean up after delay
    setTimeout(() => {
      this.activeAgents.delete(taskId);
      this.progressStreams.delete(taskId);
    }, 5000);
  }
  
  /**
   * Fail a task
   */
  failTask(taskId: string, error: string): void {
    const progress = this.activeAgents.get(taskId);
    if (!progress) return;
    
    progress.stage = 'error';
    progress.message = `Error: ${error}`;
    if (!progress.errors) progress.errors = [];
    progress.errors.push(error);
    
    this.broadcast(taskId, progress);
    
    // Clean up after delay
    setTimeout(() => {
      this.activeAgents.delete(taskId);
      this.progressStreams.delete(taskId);
    }, 10000);
  }
  
  /**
   * Subscribe to progress updates
   */
  subscribe(taskId: string, callback: (progress: AgentProgress) => void): () => void {
    this.progressStreams.set(taskId, callback);
    
    // Send current progress immediately
    const currentProgress = this.activeAgents.get(taskId);
    if (currentProgress) {
      callback(currentProgress);
    }
    
    // Return unsubscribe function
    return () => {
      this.progressStreams.delete(taskId);
    };
  }
  
  /**
   * Broadcast progress to subscribers
   */
  private broadcast(taskId: string, progress: AgentProgress): void {
    const callback = this.progressStreams.get(taskId);
    if (callback) {
      callback(progress);
    }
  }
  
  /**
   * Start heartbeat for long-running tasks
   */
  private startHeartbeat(taskId: string): void {
    const interval = setInterval(() => {
      const progress = this.activeAgents.get(taskId);
      if (!progress) {
        clearInterval(interval);
        return;
      }
      
      // Update elapsed time
      progress.currentTime = Date.now();
      progress.elapsed = this.formatDuration(progress.currentTime - progress.startTime);
      
      // Send heartbeat
      this.broadcast(taskId, progress);
      
      // Stop if complete or error
      if (progress.stage === 'complete' || progress.stage === 'error') {
        clearInterval(interval);
      }
    }, 1000); // Update every second
  }
  
  /**
   * Format duration in human-readable format
   */
  private formatDuration(ms: number): string {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    
    if (hours > 0) {
      return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`;
    } else {
      return `${seconds}s`;
    }
  }
  
  /**
   * Get all active agents
   */
  getActiveAgents(): AgentProgress[] {
    return Array.from(this.activeAgents.values());
  }
  
  /**
   * Stream progress updates via Server-Sent Events
   */
  streamProgress(taskId: string): ReadableStream {
    const encoder = new TextEncoder();
    
    return new ReadableStream({
      start: (controller) => {
        // Subscribe to updates
        const unsubscribe = this.subscribe(taskId, (progress) => {
          const data = `data: ${JSON.stringify(progress)}\n\n`;
          controller.enqueue(encoder.encode(data));
          
          // Close stream when complete
          if (progress.stage === 'complete' || progress.stage === 'error') {
            setTimeout(() => {
              controller.close();
              unsubscribe();
            }, 1000);
          }
        });
        
        // Send initial heartbeat
        controller.enqueue(encoder.encode('data: {"type":"connected"}\n\n'));
      }
    });
  }
}

export const agentObservability = AgentObservability.getInstance();