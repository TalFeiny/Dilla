import type { Metadata } from 'next';
import { Suspense } from 'react';
import './globals.css';
import { AuthProvider } from '@/components/providers/AuthProvider';
import { GridProvider } from '@/contexts/GridContext';
import { AppShell } from '@/components/layout/AppShell';
import { Toaster } from '@/components/ui/toaster';

export const metadata: Metadata = {
  title: 'Dilla AI',
  description: 'Advanced document processing and analysis platform for venture capital',
  icons: {
    icon: '/dilla-logo.svg',
    shortcut: '/dilla-logo.svg',
    apple: '/dilla-logo.svg',
  },
  robots: {
    index: true,
    follow: true,
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
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('theme');if(t!=='day'&&t!=='night')t='night';document.documentElement.setAttribute('data-theme',t);if(t==='night')document.documentElement.classList.add('dark');else document.documentElement.classList.remove('dark')}catch(e){document.documentElement.setAttribute('data-theme','night');document.documentElement.classList.add('dark')}})();`,
          }}
        />
        <Suspense fallback={null}>
          <AuthProvider>
            <GridProvider>
              <AppShell>
                {children}
              </AppShell>
            </GridProvider>
          </AuthProvider>
        </Suspense>
        <Suspense fallback={null}>
          <Toaster />
        </Suspense>
      </body>
    </html>
  );
}
