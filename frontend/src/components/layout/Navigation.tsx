'use client';

import { useState, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import supabase from '@/lib/supabase';

export function Navigation() {
  const [user, setUser] = useState<any>(null);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    checkUser();
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });
    return () => subscription.unsubscribe();
  }, []);

  const checkUser = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      setUser(user);
    } catch (error) {
      console.error('Error checking user:', error);
    }
  };

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    router.push('/');
  };

  // Don't show nav on landing, login, signup pages
  if (pathname === '/' || pathname === '/login' || pathname === '/signup') {
    return null;
  }

  const navItems = [
    { label: 'Dashboard', href: '/dashboard', icon: '🏠' },
    { label: 'Documents', href: '/documents', icon: '📄' },
    { label: 'Deck Agent', href: '/deck-agent', icon: '🎯' },
    { label: 'PWERM', href: '/pwerm', icon: '📊' },
    { label: 'Companies', href: '/companies', icon: '🏢' },
    { label: 'Portfolio', href: '/portfolio', icon: '💼' },
    { label: 'Investor Relations', href: '/investor-relations', icon: '👥' },
  ];

  return (
    <nav className="bg-white dark:bg-black border-b border-gray-200 dark:border-gray-800 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center space-x-8">
            <Link href="/dashboard" className="flex items-center">
              <span className="text-xl font-display text-primary">VC Platform</span>
            </Link>
            
            <div className="hidden md:flex items-center space-x-1">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`
                    relative px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200
                    ${pathname.startsWith(item.href)
                      ? 'text-purple-600'
                      : 'text-secondary hover:text-primary'
                    }
                    group
                  `}
                >
                  <div className="flex items-center space-x-2">
                    <span className="text-lg">{item.icon}</span>
                    <span>{item.label}</span>
                  </div>
                  
                  {/* Hover effect bar */}
                  <div className={`
                    absolute bottom-0 left-0 right-0 h-0.5 bg-purple-600 transform transition-transform duration-200 origin-left
                    ${pathname.startsWith(item.href) 
                      ? 'scale-x-100' 
                      : 'scale-x-0 group-hover:scale-x-100'
                    }
                  `} />
                  
                  {/* Active background */}
                  {pathname.startsWith(item.href) && (
                    <div className="absolute inset-0 bg-purple-50 rounded-lg -z-10" />
                  )}
                </Link>
              ))}
            </div>
          </div>

          <div className="flex items-center space-x-4">
            {user && (
              <>
                <span className="font-caption text-secondary">{user.email}</span>
                <button
                  onClick={handleSignOut}
                  className="font-caption text-secondary hover:text-primary px-3 py-2 rounded-md hover:bg-gray-100 transition-colors"
                >
                  Sign Out
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}