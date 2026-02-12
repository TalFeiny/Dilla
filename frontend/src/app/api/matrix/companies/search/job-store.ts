/**
 * Shared in-memory store for matrix batch company search jobs.
 * Used by POST (start search) and GET [jobId] (poll status).
 * When backend is unreachable, GET falls back to this store instead of 500.
 */

export type SearchJob = {
  status: 'pending' | 'processing' | 'completed' | 'failed';
  companyNames: string[];
  results: Record<string, any>;
  error?: string;
  createdAt: number;
};

export const searchJobs = new Map<string, SearchJob>();
