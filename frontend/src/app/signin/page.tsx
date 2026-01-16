'use client';

import { signIn } from 'next-auth/react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Suspense, useState, useEffect, useRef } from 'react';
import { debugLog, debugError } from '@/lib/debug';

function SignInContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const callbackUrl = searchParams.get('callbackUrl') || '/';
  const error = searchParams.get('error');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const mountedRef = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Instrumentation: Component mount/unmount
  useEffect(() => {
    if (!mountedRef.current) {
      mountedRef.current = true;
      debugLog('SignInContent', 'Component mounted');
      
      // Check if React is hydrating
      if (typeof window !== 'undefined') {
        debugLog('SignInContent', 'Window available, checking hydration', {
          hasReact: typeof window !== 'undefined' && !!(window as any).React,
          hasNextAuth: typeof signIn === 'function'
        });
      }
    }

    return () => {
      debugLog('SignInContent', 'Component unmounting');
    };
  }, []);

  // Instrumentation: CSS class application check
  useEffect(() => {
    if (containerRef.current) {
      const container = containerRef.current;
      const computedStyles = window.getComputedStyle(container);
      const hasClasses = container.className.length > 0;
      
      debugLog('SignInContent', 'CSS classes check', {
        className: container.className,
        hasClasses,
        display: computedStyles.display,
        backgroundColor: computedStyles.backgroundColor,
        color: computedStyles.color,
        fontFamily: computedStyles.fontFamily
      });
    }
  }, []);

  // Instrumentation: Error boundary
  useEffect(() => {
    const errorHandler = (event: ErrorEvent) => {
      debugError('SignInContent', event.error || event.message);
    };
    
    window.addEventListener('error', errorHandler);
    return () => window.removeEventListener('error', errorHandler);
  }, []);

  // Set error message from URL params
  useEffect(() => {
    if (error) {
      setErrorMessage(
        error === 'CredentialsSignin' ? 'Invalid email or password. Please try again.' :
        error === 'Default' ? 'An error occurred. Please try again.' :
        'An error occurred during sign in. Please try again.'
      );
    }
  }, [error]);

  // Instrumentation: Render logging
  try {
    debugLog('SignInContent', 'Rendering component', {
      hasCallbackUrl: !!callbackUrl,
      hasError: !!error,
      searchParams: Object.fromEntries(searchParams.entries())
    });
  } catch (err) {
    debugError('SignInContent', err);
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage('');
    setLoading(true);

    try {
      debugLog('SignInContent', 'Attempting sign in', { email });
      const result = await signIn('credentials', {
        email,
        password,
        callbackUrl,
        redirect: false,
      });

      if (result?.error) {
        setErrorMessage('Invalid email or password. Please try again.');
        debugError('SignInContent', new Error(result.error));
      } else if (result?.ok) {
        debugLog('SignInContent', 'Sign in successful, redirecting');
        router.push(callbackUrl);
        router.refresh();
      }
    } catch (err) {
      debugError('SignInContent', err);
      setErrorMessage('An error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div 
      ref={containerRef}
      className="min-h-screen flex items-center justify-center bg-white dark:bg-black"
      data-debug="signin-container"
    >
      <div className="max-w-md w-full space-y-6">
        <div>
          <h2 className="mt-6 text-center font-display text-primary">
            Sign in to Dilla AI
          </h2>
          <p className="mt-2 text-center font-caption text-secondary">
            Get instant access to institutional-grade VC analysis
          </p>
        </div>
        
        {(errorMessage || error) && (
          <div className="bg-red-50 border border-red-200 rounded-md p-4">
            <p className="text-sm text-red-600">
              {errorMessage || 'An error occurred. Please try again.'}
            </p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-primary mb-1">
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
              className="appearance-none relative block w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg placeholder-gray-400 dark:placeholder-gray-500 font-body text-primary bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="you@example.com"
            />
          </div>
          
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-primary mb-1">
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
              className="appearance-none relative block w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg placeholder-gray-400 dark:placeholder-gray-500 font-body text-primary bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Enter your password"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full flex justify-center py-2.5 px-4 border border-transparent rounded-lg font-body text-white bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default function SignInPage() {
  useEffect(() => {
    debugLog('SignInPage', 'SignInPage component mounted');
    return () => {
      debugLog('SignInPage', 'SignInPage component unmounting');
    };
  }, []);

  return (
    <Suspense fallback={<div>Loading...</div>}>
      <SignInContent />
    </Suspense>
  );
}