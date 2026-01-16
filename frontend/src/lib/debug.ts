// Debug utility for instrumentation
const DEBUG_PREFIX = '[DEBUG]';

export function debugLog(component: string, message: string, data?: unknown) {
  const timestamp = new Date().toISOString();
  const logMessage = `${DEBUG_PREFIX} [${timestamp}] [${component}] ${message}`;
  
  // Console logging (visible in browser console)
  if (data !== undefined) {
    console.log(logMessage, data);
  } else {
    console.log(logMessage);
  }
  
  // Also log to window for easy access
  if (typeof window !== 'undefined') {
    if (!(window as any).__debugLogs) {
      (window as any).__debugLogs = [];
    }
    (window as any).__debugLogs.push({
      timestamp,
      component,
      message,
      data: data ? JSON.stringify(data, null, 2) : undefined
    });
  }
}

export function debugError(component: string, error: Error | unknown) {
  const timestamp = new Date().toISOString();
  const errorMessage = error instanceof Error ? error.message : String(error);
  const stack = error instanceof Error ? error.stack : undefined;
  
  console.error(`${DEBUG_PREFIX} [${timestamp}] [${component}] ERROR:`, error);
  
  if (typeof window !== 'undefined') {
    if (!(window as any).__debugErrors) {
      (window as any).__debugErrors = [];
    }
    (window as any).__debugErrors.push({
      timestamp,
      component,
      error: errorMessage,
      stack
    });
  }
}

