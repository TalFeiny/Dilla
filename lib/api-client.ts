/**
 * Unified API Client for Frontend
 * Handles communication with both Next.js API routes and FastAPI backend
 */

export type APIError = {
  message: string;
  status: number;
  details?: any;
};

export type FetchOptions = RequestInit & {
  params?: Record<string, any>;
};

class APIClient {
  private baseURL: string;
  private legacyBaseURL: string;
  private useNewAPI: Record<string, boolean>;

  constructor() {
    // Determine base URLs
    this.baseURL = process.env.NEXT_PUBLIC_FASTAPI_URL || 'http://localhost:8000';
    this.legacyBaseURL = process.env.NEXT_PUBLIC_API_URL || '';
    
    // Feature flags for gradual migration
    this.useNewAPI = {
      companies: process.env.NEXT_PUBLIC_USE_FASTAPI_COMPANIES === 'true',
      pwerm: process.env.NEXT_PUBLIC_USE_FASTAPI_PWERM === 'true',
      portfolio: process.env.NEXT_PUBLIC_USE_FASTAPI_PORTFOLIO === 'true',
      documents: process.env.NEXT_PUBLIC_USE_FASTAPI_DOCUMENTS === 'true',
    };
  }

  /**
   * Determine if a route should use the new FastAPI backend
   */
  private shouldUseNewAPI(endpoint: string): boolean {
    // Always use new API for v2 endpoints
    if (endpoint.startsWith('/api/v2/')) {
      return true;
    }

    // Check feature flags for specific endpoints
    for (const [feature, enabled] of Object.entries(this.useNewAPI)) {
      if (endpoint.includes(`/${feature}`) && enabled) {
        return true;
      }
    }

    return false;
  }

  /**
   * Build full URL for the request
   */
  private buildURL(endpoint: string, params?: Record<string, any>): string {
    const useNewAPI = this.shouldUseNewAPI(endpoint);
    const baseURL = useNewAPI ? this.baseURL : this.legacyBaseURL;
    
    // Remove /api prefix for FastAPI routes
    const cleanEndpoint = useNewAPI && endpoint.startsWith('/api/')
      ? endpoint.replace('/api/', '/api/v2/')
      : endpoint;
    
    const url = new URL(cleanEndpoint, baseURL || window.location.origin);
    
    // Add query parameters
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value));
        }
      });
    }
    
    return url.toString();
  }

  /**
   * Make API request
   */
  async fetch<T = any>(
    endpoint: string,
    options: FetchOptions = {}
  ): Promise<T> {
    const { params, ...fetchOptions } = options;
    const url = this.buildURL(endpoint, params);
    
    try {
      const response = await fetch(url, {
        ...fetchOptions,
        headers: {
          'Content-Type': 'application/json',
          ...fetchOptions.headers,
        },
      });

      // Handle error responses
      if (!response.ok) {
        const error: APIError = {
          message: `Request failed: ${response.statusText}`,
          status: response.status,
        };

        // Try to parse error details
        try {
          const errorData = await response.json();
          error.message = errorData.detail || errorData.message || error.message;
          error.details = errorData;
        } catch {
          // Ignore JSON parse errors
        }

        throw error;
      }

      // Parse successful response
      const data = await response.json();
      return data;
    } catch (error) {
      // Re-throw API errors
      if ((error as APIError).status) {
        throw error;
      }

      // Wrap network errors
      throw {
        message: `Network error: ${(error as Error).message}`,
        status: 0,
        details: error,
      } as APIError;
    }
  }

  /**
   * GET request
   */
  async get<T = any>(endpoint: string, params?: Record<string, any>): Promise<T> {
    return this.fetch<T>(endpoint, { method: 'GET', params });
  }

  /**
   * POST request
   */
  async post<T = any>(
    endpoint: string,
    data?: any,
    options: FetchOptions = {}
  ): Promise<T> {
    return this.fetch<T>(endpoint, {
      ...options,
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  /**
   * PUT request
   */
  async put<T = any>(
    endpoint: string,
    data?: any,
    options: FetchOptions = {}
  ): Promise<T> {
    return this.fetch<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  /**
   * DELETE request
   */
  async delete<T = any>(endpoint: string, options: FetchOptions = {}): Promise<T> {
    return this.fetch<T>(endpoint, {
      ...options,
      method: 'DELETE',
    });
  }

  /**
   * Stream response (for SSE/streaming endpoints)
   */
  async stream(
    endpoint: string,
    options: FetchOptions = {},
    onChunk: (chunk: string) => void
  ): Promise<void> {
    const { params, ...fetchOptions } = options;
    const url = this.buildURL(endpoint, params);
    
    const response = await fetch(url, {
      ...fetchOptions,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...fetchOptions.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`Stream request failed: ${response.statusText}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('Response body is not readable');
    }

    const decoder = new TextDecoder();
    
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        onChunk(chunk);
      }
    } finally {
      reader.releaseLock();
    }
  }
}

// Export singleton instance
export const apiClient = new APIClient();

// Export specific API functions for convenience
export const api = {
  // Companies
  companies: {
    list: (params?: { limit?: number; offset?: number; fields?: string }) =>
      apiClient.get('/api/companies', params),
    get: (id: string) => apiClient.get(`/api/companies/${id}`),
    create: (data: any) => apiClient.post('/api/companies', data),
    update: (id: string, data: any) => apiClient.put(`/api/companies/${id}`, data),
    delete: (id: string) => apiClient.delete(`/api/companies/${id}`),
    search: (q: string, limit?: number) =>
      apiClient.get('/api/companies/search', { q, limit }),
  },
  
  // PWERM
  pwerm: {
    analyze: (data: {
      company_name: string;
      arr?: number;
      growth_rate?: number;
      sector?: string;
    }) => apiClient.post('/api/pwerm/analyze', data),
    scenarios: (data: any) => apiClient.post('/api/pwerm/scenarios', data),
    test: () => apiClient.get('/api/pwerm/test'),
    results: (companyName: string) =>
      apiClient.get(`/api/pwerm/results/${companyName}`),
  },
  
  // Portfolio
  portfolio: {
    list: () => apiClient.get('/api/portfolio'),
    get: (id: string) => apiClient.get(`/api/portfolio/${id}`),
    companies: (portfolioId: string) =>
      apiClient.get(`/api/portfolio/${portfolioId}/companies`),
  },
  
  // Documents
  documents: {
    list: () => apiClient.get('/api/documents'),
    get: (id: string) => apiClient.get(`/api/documents/${id}`),
    process: (data: FormData) =>
      apiClient.post('/api/documents/process', data, {
        headers: { 'Content-Type': 'multipart/form-data' },
      }),
  },
};

export default apiClient;