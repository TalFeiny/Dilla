import type { Metadata } from 'next';
import { Suspense } from 'react';
import './globals.css';
import SessionProvider from '@/components/providers/SessionProvider';
import { GridProvider } from '@/contexts/GridContext';
import { AppShell } from '@/components/layout/AppShell';
import { Toaster } from '@/components/ui/toaster';

export const metadata: Metadata = {
  title: 'Dilla AI - VC Platform',
  description: 'Advanced document processing and analysis platform for venture capital',
  icons: {
    icon: '/dilla-logo.svg',
    shortcut: '/dilla-logo.svg',
    apple: '/dilla-logo.svg',
  },
};

interface RootLayoutProps {
  children: React.ReactNode;
}

export default function RootLayout({ children }: RootLayoutProps): JSX.Element {
  return (
    <html lang="en" className="font-sans" suppressHydrationWarning>
      <head>
        <link rel="icon" href="/dilla-logo.svg" type="image/svg+xml" />
        <link rel="preconnect" href="https://api.fontshare.com" crossOrigin="anonymous" />
        <link href="https://api.fontshare.com/v2/css?f[]=satoshi@300,400,500,600,700,800,900&display=swap" rel="stylesheet" />
      </head>
      <body className="antialiased bg-white text-gray-900" suppressHydrationWarning>
        <Suspense fallback={null}>
          <SessionProvider>
            <GridProvider>
              <AppShell>
                {children}
              </AppShell>
            </GridProvider>
          </SessionProvider>
        </Suspense>
        <Suspense fallback={null}>
          <Toaster />
        </Suspense>
      </body>
    </html>
  );
}
