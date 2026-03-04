'use client';

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'next/navigation';
import { useAuth } from '@/components/providers/AuthProvider';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  RefreshCw,
  Trash2,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Link2,
} from 'lucide-react';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface XeroConnection {
  id: string;
  xero_tenant_id: string;
  xero_tenant_name: string;
  last_sync_at: string | null;
  sync_status: 'idle' | 'syncing' | 'error';
  sync_error: string | null;
  created_at: string;
}

export default function IntegrationsPage() {
  const { user, profile, loading: authLoading } = useAuth();
  const searchParams = useSearchParams();
  const [connections, setConnections] = useState<XeroConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [companyId, setCompanyId] = useState('');
  const [companies, setCompanies] = useState<{ id: string; name: string }[]>([]);
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const userId = profile?.id || user?.id || '';

  // Check URL params for OAuth callback results
  useEffect(() => {
    const connected = searchParams.get('xero_connected');
    const error = searchParams.get('xero_error');

    if (connected) {
      setToast({ type: 'success', message: `Connected ${connected} Xero organisation(s)` });
      // Clean URL
      window.history.replaceState({}, '', '/settings/integrations');
    } else if (error) {
      const messages: Record<string, string> = {
        token_exchange_failed: 'Failed to complete Xero authorisation. Please try again.',
        no_tenants: 'No Xero organisations found for this account.',
      };
      setToast({ type: 'error', message: messages[error] || `Xero error: ${error}` });
      window.history.replaceState({}, '', '/settings/integrations');
    }
  }, [searchParams]);

  // Fetch connections
  const fetchConnections = useCallback(async () => {
    if (!userId) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/integrations/xero/connections?user_id=${userId}`);
      const data = await res.json();
      if (data.success) {
        setConnections(data.connections);
      }
    } catch (err) {
      console.error('Failed to fetch Xero connections:', err);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  // Fetch companies for the sync dropdown
  const fetchCompanies = useCallback(async () => {
    try {
      const res = await fetch('/api/companies?limit=100');
      const data = await res.json();
      setCompanies(Array.isArray(data) ? data.map((c: any) => ({ id: c.id, name: c.name })) : []);
    } catch {
      // Non-critical — user can type company ID manually
    }
  }, []);

  useEffect(() => {
    if (userId) {
      fetchConnections();
      fetchCompanies();
    }
  }, [userId, fetchConnections, fetchCompanies]);

  // Connect Xero
  const handleConnect = async () => {
    if (!userId) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/integrations/xero/auth-url?user_id=${userId}`);
      const data = await res.json();
      if (data.auth_url) {
        window.location.href = data.auth_url;
      }
    } catch (err) {
      setToast({ type: 'error', message: 'Failed to start Xero connection' });
    }
  };

  // Sync data
  const handleSync = async (connectionId: string) => {
    if (!companyId) {
      setToast({ type: 'error', message: 'Select a company to sync data into' });
      return;
    }

    setSyncing(connectionId);
    try {
      const res = await fetch(`${BACKEND_URL}/api/integrations/xero/sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          connection_id: connectionId,
          user_id: userId,
          company_id: companyId,
          months: 24,
        }),
      });
      const data = await res.json();
      if (data.success) {
        setToast({
          type: 'success',
          message: `Synced ${data.rows_synced} rows across ${data.periods?.length || 0} periods`,
        });
        fetchConnections();
      } else {
        setToast({ type: 'error', message: data.detail || data.error || 'Sync failed' });
      }
    } catch (err) {
      setToast({ type: 'error', message: 'Sync request failed' });
    } finally {
      setSyncing(null);
    }
  };

  // Disconnect
  const handleDisconnect = async (connectionId: string) => {
    if (!confirm('Disconnect this Xero organisation? Existing synced data will remain.')) return;

    try {
      await fetch(
        `${BACKEND_URL}/api/integrations/xero/connections/${connectionId}?user_id=${userId}`,
        { method: 'DELETE' },
      );
      setConnections((prev) => prev.filter((c) => c.id !== connectionId));
      setToast({ type: 'success', message: 'Xero organisation disconnected' });
    } catch {
      setToast({ type: 'error', message: 'Failed to disconnect' });
    }
  };

  // Auto-dismiss toast
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  if (authLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto py-10 px-4 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Integrations</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Connect external data sources to sync financial data into your portfolio companies.
        </p>
      </div>

      {/* Toast */}
      {toast && (
        <div
          className={`flex items-center gap-2 px-4 py-3 rounded-lg text-sm ${
            toast.type === 'success'
              ? 'bg-green-50 text-green-800 border border-green-200 dark:bg-green-950 dark:text-green-200 dark:border-green-800'
              : 'bg-red-50 text-red-800 border border-red-200 dark:bg-red-950 dark:text-red-200 dark:border-red-800'
          }`}
        >
          {toast.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
          )}
          {toast.message}
        </div>
      )}

      {/* Xero Card */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-[#13B5EA]/10 flex items-center justify-center">
              <span className="text-[#13B5EA] font-bold text-lg">X</span>
            </div>
            <div>
              <CardTitle className="text-lg">Xero</CardTitle>
              <p className="text-xs text-muted-foreground">Accounting & financial data</p>
            </div>
          </div>
          <Button onClick={handleConnect} variant="outline" size="sm">
            <Link2 className="w-4 h-4 mr-1.5" />
            Connect Xero
          </Button>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Company selector for sync target */}
          {connections.length > 0 && (
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                Sync into company
              </label>
              <select
                value={companyId}
                onChange={(e) => setCompanyId(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="">Select a portfolio company...</option>
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Connections list */}
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
            </div>
          ) : connections.length === 0 ? (
            <div className="text-center py-8 text-sm text-muted-foreground">
              No Xero organisations connected. Click &quot;Connect Xero&quot; to get started.
            </div>
          ) : (
            <div className="space-y-3">
              {connections.map((conn) => (
                <div
                  key={conn.id}
                  className="flex items-center justify-between p-3 rounded-lg border border-border bg-muted/30"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="flex-shrink-0">
                      {conn.sync_status === 'syncing' ? (
                        <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
                      ) : conn.sync_status === 'error' ? (
                        <AlertCircle className="w-4 h-4 text-red-500" />
                      ) : (
                        <CheckCircle2 className="w-4 h-4 text-green-500" />
                      )}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">
                        {conn.xero_tenant_name || conn.xero_tenant_id}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {conn.last_sync_at
                          ? `Last synced ${new Date(conn.last_sync_at).toLocaleDateString('en-AU', {
                              day: 'numeric',
                              month: 'short',
                              year: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                            })}`
                          : 'Never synced'}
                        {conn.sync_error && (
                          <span className="ml-2 text-red-500">{conn.sync_error}</span>
                        )}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleSync(conn.id)}
                      disabled={syncing === conn.id || conn.sync_status === 'syncing'}
                      className="h-8 px-2.5"
                    >
                      {syncing === conn.id ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <RefreshCw className="w-3.5 h-3.5" />
                      )}
                      <span className="ml-1 text-xs">Sync</span>
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDisconnect(conn.id)}
                      className="h-8 px-2.5 text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Info card */}
      <Card>
        <CardContent className="pt-6">
          <h3 className="text-sm font-medium mb-2">How it works</h3>
          <ol className="text-xs text-muted-foreground space-y-1.5 list-decimal list-inside">
            <li>Connect your Xero account via OAuth2</li>
            <li>Select a portfolio company to map the data to</li>
            <li>Click Sync to pull P&L data (up to 24 months of history)</li>
            <li>Data flows into the FPA grid as actuals with source &quot;xero&quot;</li>
            <li>Forecasting and variance analysis update automatically</li>
          </ol>
        </CardContent>
      </Card>
    </div>
  );
}
