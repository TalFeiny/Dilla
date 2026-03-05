/**
 * Shared in-memory store for matrix batch company search jobs.
 * Used by POST (start search) and GET [jobId] (poll status).
 * Both routes import this single Map so polling finds jobs the POST created.
 */

export type SearchJob = {
  status: 'pending' | 'processing' | 'completed' | 'failed';
  companyNames: string[];
  results: Record<string, any>;
  error?: string;
  createdAt: number;
};

export const searchJobs = new Map<string, SearchJob>();

// Clean up old jobs (older than 1 hour)
if (typeof setInterval !== 'undefined') {
  setInterval(() => {
    const oneHourAgo = Date.now() - 3600000;
    for (const [jobId, job] of searchJobs.entries()) {
      if (job.createdAt < oneHourAgo) searchJobs.delete(jobId);
    }
  }, 60000);
}
