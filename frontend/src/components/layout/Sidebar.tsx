'use client';

import { useState, useEffect, useMemo } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import { useSession, signOut } from 'next-auth/react';
import {
  LayoutDashboard,
  FileText,
  BarChart3,
  Building2,
  Briefcase,
  ActivitySquare,
  Users,
  Grid3X3,
  Settings2,
  ShieldCheck,
  CreditCard,
  FileSearch,
  Boxes,
  LogOut,
  Moon,
  Sun,
  Presentation,
} from 'lucide-react';


export function Sidebar() {
  const { data: session } = useSession();
  const [isDark, setIsDark] = useState(false);
  const [mounted, setMounted] = useState(false);
  const router = useRouter();
  const pathname = usePathname();
  const user = session?.user ?? null;

  useEffect(() => {
    setMounted(true);
    const theme = document.documentElement.getAttribute('data-theme');
    setIsDark(theme === 'night');
  }, []);

  const toggleTheme = () => {
    const newTheme = isDark ? 'day' : 'night';
    document.documentElement.setAttribute('data-theme', newTheme);
    setIsDark(!isDark);
  };

  const handleSignOut = async () => {
    await signOut({ redirect: false });
    router.push('/');
  };

  // Don't show sidebar on landing, login, signup pages
  if (pathname === '/login' || pathname === '/signup') {
    return null;
  }

  const navItems = useMemo(() => [
    { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
    { label: 'Documents', href: '/documents', icon: FileText },
    { label: 'Deck Agent', href: '/deck-agent', icon: Presentation },
    { label: 'PWERM', href: '/pwerm', icon: BarChart3 },
    { label: 'Companies', href: '/companies', icon: Building2 },
    { label: 'Portfolio', href: '/portfolio', icon: Briefcase },
    { label: 'Pacing', href: '/portfolio/pacing', icon: ActivitySquare },
    { label: 'Investor Relations', href: '/investor-relations', icon: Users },
    { label: 'Grid', href: '/management-accounts', icon: Grid3X3 },
    { label: 'Fund Admin', href: '/fund_admin', icon: Settings2 },
    { label: 'Audit', href: '/audit', icon: ShieldCheck },
    { label: 'Subscription', href: '/subscription', icon: CreditCard },
    { label: 'Docs', href: '/docs', icon: FileSearch },
    { label: 'Matrix', href: '/matrix-control-panel', icon: Boxes },
  ], []);

  return (
    <div className="fixed left-0 top-0 h-screen w-10 md:w-12 lg:w-16 z-40">
      <div className="h-full flex flex-col bg-white dark:bg-black backdrop-blur-md border-r border-gray-200 dark:border-gray-800">
        <div className="h-12 flex items-center justify-center relative border-b border-gray-200 dark:border-gray-800">
          <Link href="/dashboard" aria-label="Home" className="flex items-center justify-center">
            <img src="/dilla-logo.svg" alt="Dilla" className="h-8 w-auto opacity-80 hover:opacity-100 transition-opacity" />
          </Link>
          <button
            onClick={toggleTheme}
            className="absolute top-1 right-1 w-4 h-4 rounded-full bg-gray-200 dark:bg-gray-800 hover:bg-gray-300 dark:hover:bg-gray-700 transition-colors flex items-center justify-center"
            aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {!mounted ? (
              <div className="w-2.5 h-2.5" />
            ) : isDark ? (
              <Sun className="w-2.5 h-2.5 text-primary" strokeWidth={2} />
            ) : (
              <Moon className="w-2.5 h-2.5 text-primary" strokeWidth={2} />
            )}
          </button>
        </div>
        <nav className="flex-1 py-2 overflow-y-auto scrollbar-hide">
          <ul className="space-y-1 px-1">
            {navItems.map((item) => {
              const isActive = pathname.startsWith(item.href) || (item.href === '/dashboard' && pathname === '/');
              const Icon = item.icon;
              return (
                <li key={item.href} className="group relative">
                  <Link
                    href={item.href}
                    className={
                      `relative flex items-center justify-center h-8 mx-1 rounded transition-colors
                       ${isActive 
                         ? 'bg-gray-100 dark:bg-gray-800 text-primary crystal-glow' 
                         : 'text-secondary hover:text-primary hover:bg-gray-50 dark:hover:bg-gray-900'
                       }`
                    }
                    aria-label={item.label}
                  >
                    <Icon className="w-4 h-4" strokeWidth={1.5} />
                  </Link>
                  <div 
                    className="absolute left-12 md:left-14 lg:left-18 ml-2 px-2 py-1 bg-gray-900 dark:bg-gray-800 text-white text-xs rounded shadow border border-gray-600
                               opacity-0 group-hover:opacity-100 pointer-events-none transition-all duration-200 whitespace-nowrap z-50 crystal-accent"
                  >
                    {item.label}
                  </div>
                </li>
              );
            })}
          </ul>
        </nav>
        {user && (
          <div className="border-t border-gray-200 dark:border-gray-800 p-2">
            <button 
              onClick={handleSignOut} 
              className="w-full h-8 flex items-center justify-center text-secondary hover:text-primary hover:bg-gray-100/50 dark:hover:bg-gray-900/50 rounded-lg transition-all duration-200"
              aria-label="Sign Out"
            >
              <LogOut className="w-4 h-4" strokeWidth={1.5} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}