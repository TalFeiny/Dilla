'use client';

import React from 'react';

export function DebugWrapper({ data, label }: { data: any; label: string }) {
  React.useEffect(() => {
    console.log(`[DEBUG ${label}]:`, data);
    
    // Check for any undefined values that might have toFixed called on them
    const checkForUndefined = (obj: any, path: string = ''): void => {
      if (obj === null || obj === undefined) {
        console.warn(`[DEBUG ${label}] Undefined/null value at path: ${path}`);
        return;
      }
      
      if (typeof obj === 'object') {
        Object.keys(obj).forEach(key => {
          checkForUndefined(obj[key], path ? `${path}.${key}` : key);
        });
      }
    };
    
    checkForUndefined(data);
  }, [data, label]);
  
  return null;
}