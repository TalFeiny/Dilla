'use client';

/**
 * Dashboard - Redirects to Matrix Control Panel
 * 
 * According to the matrix consolidation plan:
 * "Home = Control Panel" - logged-in app home = matrix control panel
 */
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function Dashboard() {
  const router = useRouter();

  useEffect(() => {
    // Redirect to matrix control panel (the new home)
    router.replace('/matrix-control-panel');
  }, [router]);

  // Show loading state during redirect
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
    </div>
  );
}