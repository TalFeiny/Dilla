'use client';

import React, { useState, useEffect } from 'react';

interface LP {
  id: number;
  name: string;
  email: string;
  phone: string;
  status: string;
  investment_amount: number;
  created_at: string;
}

export default function LPsPage() {
  const [lps, setLps] = useState<LP[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 50; // Show 50 LPs per page

  useEffect(() => {
    fetchLPs();
  }, []);

  const fetchLPs = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/lps?limit=500'); // Increased limit to 500
      if (!response.ok) {
        throw new Error('Failed to fetch LPs');
      }
      const data = await response.json();
      console.log(`Fetched ${data.length} LPs from API`);
      setLps(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-8 m:px-8 lg:px-12">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-foreground">Limited Partners</h1>
          <p className="text-muted-foreground text-lg">Loading LPs...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-8 m:px-8 lg:px-12">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-foreground">Limited Partners</h1>
          <p className="text-red-600">Error: {error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 m:px-8 lg:px-12">
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Limited Partners</h1>
            <p className="text-muted-foreground text-lg">
              {lps.length} LPs in your investor network
            </p>
          </div>
        </div>
      </div>

      <div className="bg-card rounded-lg shadow-sm border border-border overflow-hidden">
        {lps.length === 0 ? (
          <div className="p-8 text-center">
            <p className="text-muted-foreground">No LPs found. Add your first LP to get started.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border">
              <thead className="bg-muted/50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Email
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Phone
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Investment Amount
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Added
                  </th>
                </tr>
              </thead>
              <tbody className="bg-card divide-y divide-border">
                {lps
                  .slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage)
                  .map((lp) => (
                  <tr key={lp.id} className="hover:bg-muted/50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-foreground">{lp.name}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-foreground">{lp.email || 'N/A'}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-foreground">{lp.phone || 'N/A'}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-foreground">
                        ${lp.investment_amount?.toLocaleString() || '0'}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                        lp.status === 'active' ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' :
                        lp.status === 'inactive' ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400' :
                        'bg-muted text-muted-foreground'
                      }`}>
                        {lp.status || 'Unknown'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">
                      {new Date(lp.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination controls */}
        {lps.length > itemsPerPage && (
          <div className="px-6 py-4 border-t border-border flex items-center justify-between">
            <div className="flex items-center">
              <p className="text-sm text-muted-foreground">
                Showing{' '}
                <span className="font-medium">
                  {(currentPage - 1) * itemsPerPage + 1}
                </span>{' '}
                to{' '}
                <span className="font-medium">
                  {Math.min(currentPage * itemsPerPage, lps.length)}
                </span>{' '}
                of{' '}
                <span className="font-medium">{lps.length}</span> LPs
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                disabled={currentPage === 1}
                className="px-3 py-1 text-sm border border-border rounded-md hover:bg-muted/50 disabled:opacity-50 disabled:cursor-not-allowed text-foreground"
              >
                Previous
              </button>
              {Array.from({ length: Math.ceil(lps.length / itemsPerPage) }, (_, i) => i + 1)
                .filter(page =>
                  page === 1 ||
                  page === Math.ceil(lps.length / itemsPerPage) ||
                  Math.abs(page - currentPage) <= 2
                )
                .map((page, idx, arr) => (
                  <React.Fragment key={page}>
                    {idx > 0 && arr[idx - 1] !== page - 1 && (
                      <span className="px-2 py-1 text-muted-foreground">...</span>
                    )}
                    <button
                      onClick={() => setCurrentPage(page)}
                      className={`px-3 py-1 text-sm border rounded-md ${
                        currentPage === page
                          ? 'bg-primary text-primary-foreground border-primary'
                          : 'border-border hover:bg-muted/50 text-foreground'
                      }`}
                    >
                      {page}
                    </button>
                  </React.Fragment>
                ))}
              <button
                onClick={() => setCurrentPage(Math.min(Math.ceil(lps.length / itemsPerPage), currentPage + 1))}
                disabled={currentPage === Math.ceil(lps.length / itemsPerPage)}
                className="px-3 py-1 text-sm border border-border rounded-md hover:bg-muted/50 disabled:opacity-50 disabled:cursor-not-allowed text-foreground"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
