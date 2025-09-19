import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Sidebar } from '@/components/layout/Sidebar';
import SessionProvider from '@/components/providers/SessionProvider';

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
  return (
    <html lang="en" className={inter.className}>
      <body className="antialiased bg-gray-50">
        <SessionProvider>
          <Sidebar />
          {/* Main Content - with left margin for fixed sidebar */}
          <div className="ml-16 min-h-screen p-4 lg:p-8">
            {children}
          </div>
        </SessionProvider>
      </body>
    </html>
  );
}