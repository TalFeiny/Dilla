'use client';

import { useMemo } from 'react';
import { usePathname } from 'next/navigation';
import { Sidebar } from '@/components/layout/Sidebar';

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
  if (!pathname) return false;
  if (AUTH_ROUTES.has(pathname) || MARKETING_ROUTES.has(pathname)) return false;
  if (pathname.startsWith('/talk-to-sales') || pathname.startsWith('/contact-sales')) return false;
  return true;
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const sidebarVisible = useMemo(() => shouldShowSidebar(pathname), [pathname]);

  return (
    <div className="relative flex h-screen w-full bg-white text-gray-900 overflow-hidden">
      {sidebarVisible && <Sidebar />}
      <main
        className={`flex-1 h-screen overflow-y-auto bg-white ${sidebarVisible ? 'ml-10 md:ml-12 lg:ml-16' : ''}`}
      >
        {children}
      </main>
    </div>
  );
}
