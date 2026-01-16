'use client';

import { useEffect } from 'react';
import { debugLog, debugError } from '@/lib/debug';

export function LayoutInstrumentation() {
  useEffect(() => {
    debugLog('RootLayout', 'Layout mounted on client');
    
    // Check CSS loading
    const checkCSS = () => {
      const stylesheets = Array.from(document.styleSheets);
      const globalsCSS = Array.from(document.querySelectorAll('link[rel="stylesheet"]'))
        .find(link => (link as HTMLLinkElement).href.includes('globals') || (link as HTMLLinkElement).href.includes('_next'));
      
      debugLog('RootLayout', 'CSS loading check', {
        stylesheetCount: stylesheets.length,
        hasGlobalsCSS: !!globalsCSS,
        globalsCSSUrl: globalsCSS ? (globalsCSS as HTMLLinkElement).href : null,
        bodyStyles: {
          backgroundColor: window.getComputedStyle(document.body).backgroundColor,
          color: window.getComputedStyle(document.body).color,
          fontFamily: window.getComputedStyle(document.body).fontFamily
        }
      });
    };

    // Check immediately and after a short delay
    checkCSS();
    setTimeout(checkCSS, 100);
    setTimeout(checkCSS, 500);

    // Check provider initialization
    debugLog('RootLayout', 'Provider initialization', {
      hasSessionProvider: true,
      hasGridProvider: true,
      hasAppShell: true
    });

    // Error handler
    const errorHandler = (event: ErrorEvent) => {
      debugError('RootLayout', event.error || event.message);
    };
    
    window.addEventListener('error', errorHandler);
    return () => window.removeEventListener('error', errorHandler);
  }, []);

  return null;
}

