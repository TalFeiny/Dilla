'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { AlertCircle } from 'lucide-react';

interface PWERMResultsDisplaySafeProps {
  results: any;
}

export function PWERMResultsDisplaySafe({ results }: PWERMResultsDisplaySafeProps) {
  try {
    // Dynamically import the actual component to isolate errors
    const [Component, setComponent] = React.useState<React.ComponentType<any> | null>(null);
    const [error, setError] = React.useState<Error | null>(null);
    
    React.useEffect(() => {
      import('./PWERMResultsDisplay')
        .then(module => {
          setComponent(() => module.PWERMResultsDisplay);
        })
        .catch(err => {
          console.error('Failed to load PWERMResultsDisplay:', err);
          setError(err);
        });
    }, []);
    
    if (error) {
      return (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error Loading Results Display</AlertTitle>
          <AlertDescription>
            Failed to load the results display component: {error.message}
          </AlertDescription>
        </Alert>
      );
    }
    
    if (!Component) {
      return (
        <Card>
          <CardContent className="p-6">
            <p>Loading results display...</p>
          </CardContent>
        </Card>
      );
    }
    
    // Wrap in error boundary
    return (
      <ErrorBoundary>
        <Component results={results} />
      </ErrorBoundary>
    );
  } catch (err) {
    console.error('Error in PWERMResultsDisplaySafe:', err);
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Error Displaying Results</AlertTitle>
        <AlertDescription>
          {err instanceof Error ? err.message : 'Unknown error occurred'}
        </AlertDescription>
      </Alert>
    );
  }
}

// Simple error boundary component
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('PWERMResultsDisplay Error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error Rendering Results</AlertTitle>
          <AlertDescription>
            {this.state.error?.message || 'An error occurred while rendering the results'}
            <pre className="mt-2 text-xs">{this.state.error?.stack}</pre>
          </AlertDescription>
        </Alert>
      );
    }

    return this.props.children;
  }
}