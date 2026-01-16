import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import SessionProvider from '@/components/providers/SessionProvider';
import { GridProvider } from '@/contexts/GridContext';
import { AppShell } from '@/components/layout/AppShell';
import { LayoutInstrumentation } from '@/components/debug/LayoutInstrumentation';

const inter = Inter({ 
  subsets: ['latin'],
  display: 'swap',
  preload: true,
  fallback: ['system-ui', 'arial']
});

export const metadata: Metadata = {
  title: 'Dilla AI - VC Platform',
  description: 'Advanced document processing and analysis platform for venture capital',
};

interface RootLayoutProps {
  children: React.ReactNode;
}

export default function RootLayout({ children }: RootLayoutProps): JSX.Element {
  // Instrumentation: Log layout render
  if (typeof window !== 'undefined') {
    console.log('[DEBUG] [RootLayout] Layout rendering on client');
  } else {
    console.log('[DEBUG] [RootLayout] Layout rendering on server');
  }

  return (
    <html lang="en" className={inter.className}>
      <head>
        {/* Instrumentation: Verify CSS is loaded */}
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                console.log('[DEBUG] [RootLayout] CSS import check:', {
                  hasGlobalsCSS: document.querySelector('link[href*="globals"]') !== null,
                  stylesheetCount: document.styleSheets.length,
                  interFontLoaded: document.fonts.check('1em Inter')
                });
              })();
            `
          }}
        />
      </head>
      <body className="antialiased bg-background text-foreground">
        <LayoutInstrumentation />
        <SessionProvider>
          <GridProvider>
            <AppShell>
              {children}
            </AppShell>
          </GridProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
