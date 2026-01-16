'use client';

import { useMemo, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { Sidebar } from '@/components/layout/Sidebar';
import ThemeToggle from '@/components/ThemeToggle';
import { debugLog, debugError } from '@/lib/debug';

interface AppShellProps {
  children: React.ReactNode;
}

const AUTH_ROUTES = new Set(['/login', '/signin', '/signup', '/forgot-password']);
const MARKETING_ROUTES = new Set([
  '/',
  '/pricing',
  '/talk-to-sales',
  '/contact-sales'
]);

function shouldShowSidebar(pathname: string | null): boolean {
  if (!pathname) {
    return false;
  }

  if (AUTH_ROUTES.has(pathname) || MARKETING_ROUTES.has(pathname)) {
    return false;
  }

  // Hide sidebar for nested marketing routes e.g. /talk-to-sales/success
  if (pathname.startsWith('/talk-to-sales') || pathname.startsWith('/contact-sales')) {
    return false;
  }

  return true;
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const sidebarVisible = useMemo(() => shouldShowSidebar(pathname), [pathname]);

  // Instrumentation: Route detection and sidebar logic
  useEffect(() => {
    debugLog('AppShell', 'AppShell mounted', {
      pathname,
      sidebarVisible,
      isAuthRoute: AUTH_ROUTES.has(pathname || ''),
      isMarketingRoute: MARKETING_ROUTES.has(pathname || ''),
      shouldShowSidebarResult: shouldShowSidebar(pathname)
    });
  }, [pathname, sidebarVisible]);

  // Instrumentation: Children render check
  useEffect(() => {
    debugLog('AppShell', 'Children rendered', {
      hasChildren: !!children,
      childrenType: typeof children
    });
  }, [children]);

  // Instrumentation: Error handler
  useEffect(() => {
    const errorHandler = (event: ErrorEvent) => {
      debugError('AppShell', event.error || event.message);
    };
    
    window.addEventListener('error', errorHandler);
    return () => window.removeEventListener('error', errorHandler);
  }, []);

  return (
    <div 
      className="relative flex h-screen bg-white dark:dark-city-bg text-primary overflow-hidden"
      data-debug="appshell-container"
      data-pathname={pathname}
      data-sidebar-visible={sidebarVisible}
    >
      {sidebarVisible && <Sidebar />}
      <main
        className={sidebarVisible
          ? `ml-10 md:ml-12 lg:ml-16 flex-1 h-screen overflow-y-auto`
          : `flex-1 h-screen overflow-y-auto`}
        data-debug="appshell-main"
      >
        {children}
      </main>
    </div>
  );
}
