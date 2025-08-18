import { ReactNode } from 'react';

export default function PortfolioLayout({
  children,
}: {
  children: ReactNode
}) {
  return (
    <div className="portfolio-layout">
      {children}
    </div>
  )
}
