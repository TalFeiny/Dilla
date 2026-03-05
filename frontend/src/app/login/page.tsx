'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Nuke ALL stale auth artifacts on mount so the SDK singleton
  // (created by AuthProvider in root layout) doesn't find garbage
  // cookies/localStorage and hang trying to refresh an expired session.
  useEffect(() => {
    try {
      const staleKeys: string[] = [];
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k && (k.startsWith('sb-') || k.includes('supabase'))) staleKeys.push(k);
      }
      staleKeys.forEach((k) => localStorage.removeItem(k));
    } catch {}

    document.cookie
      .split('; ')
      .filter(Boolean)
      .forEach((c) => {
        const name = c.split('=')[0];
        if (name.startsWith('sb-')) {
          document.cookie = `${name}=; path=/; max-age=0`;
        }
      });
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
      const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

      // ── 1. Get tokens via direct HTTP — NO SDK, NO Navigator Lock ──
      // The SDK's signInWithPassword() and setSession() both acquire
      // the Web Locks API lock. AuthProvider (root layout) also holds
      // this lock via getUser(). This causes a deadlock. Bypass entirely.
      const res = await fetch(
        `${supabaseUrl}/auth/v1/token?grant_type=password`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            apikey: supabaseKey,
            Authorization: `Bearer ${supabaseKey}`,
          },
          body: JSON.stringify({ email, password }),
        },
      );

      const body = await res.json();

      if (!res.ok) {
        throw new Error(
          body.msg || body.error_description || 'Invalid login credentials',
        );
      }

      // ── 2. Write session cookie in @supabase/ssr tokens-only format ──
      // Matches exactly what createBrowserClient's storage.setItem() produces:
      //   JSON.stringify(session) → "base64-" + base64url → cookie chunks
      // With tokens-only, _saveSession strips the user object before storing.
      const ref = supabaseUrl.match(/\/\/([^.]+)\./)?.[1] || '';
      const cookieName = `sb-${ref}-auth-token`;

      const session = {
        access_token: body.access_token,
        token_type: body.token_type || 'bearer',
        expires_in: body.expires_in,
        expires_at: Math.floor(Date.now() / 1000) + body.expires_in,
        refresh_token: body.refresh_token,
      };

      const encoded =
        'base64-' +
        btoa(JSON.stringify(session))
          .replace(/\+/g, '-')
          .replace(/\//g, '_')
          .replace(/=+$/, '');

      // Cookie options matching @supabase/ssr DEFAULT_COOKIE_OPTIONS
      const cookieOpts = '; path=/; max-age=34560000; SameSite=Lax';

      // Chunk if > 3180 chars (unlikely for tokens-only but be safe)
      const MAX_CHUNK = 3180;
      if (encoded.length <= MAX_CHUNK) {
        document.cookie = `${cookieName}=${encodeURIComponent(encoded)}${cookieOpts}`;
      } else {
        let remaining = encoded;
        let i = 0;
        while (remaining.length > 0) {
          const chunk = remaining.slice(0, MAX_CHUNK);
          remaining = remaining.slice(MAX_CHUNK);
          document.cookie = `${cookieName}.${i}=${encodeURIComponent(chunk)}${cookieOpts}`;
          i++;
        }
      }

      // ── 3. Store user in localStorage (tokens-only mode reads it from here) ──
      if (body.user) {
        try {
          localStorage.setItem(
            `${cookieName}-user`,
            JSON.stringify({ user: body.user }),
          );
        } catch {}
      }

      // ── 4. Full page navigation — middleware reads cookies, allows through ──
      window.location.href = '/dashboard';
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'An error occurred during login';
      setError(message);
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <Link href="/" className="inline-block">
            <h2 className="text-3xl font-bold text-black">
              Dilla AI
            </h2>
          </Link>
          <p className="mt-2 text-gray-600">Sign in to your account</p>
        </div>

        <form className="mt-8 space-y-6 bg-white p-8 rounded-2xl shadow-lg border border-gray-200" onSubmit={handleLogin}>
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                Email address
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="appearance-none relative block w-full px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg placeholder-gray-400 dark:placeholder-gray-500 font-body text-primary bg-white dark:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="block font-caption text-secondary mb-1">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="appearance-none relative block w-full px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg placeholder-gray-400 dark:placeholder-gray-500 font-body text-primary bg-white dark:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Enter your password"
              />
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <input
                id="remember-me"
                name="remember-me"
                type="checkbox"
                className="h-4 w-4 text-purple-600 focus:ring-purple-500 border-gray-300 rounded"
              />
              <label htmlFor="remember-me" className="ml-2 block text-sm text-gray-700">
                Remember me
              </label>
            </div>

            <div className="text-sm">
              <Link href="/forgot-password" className="font-medium text-purple-600 hover:text-purple-700">
                Forgot password?
              </Link>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full flex justify-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>

          <div className="text-center text-sm">
            <span className="text-gray-600">Don&apos;t have an account? </span>
            <Link href="/signup" className="font-medium text-purple-600 hover:text-purple-700">
              Sign up
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
