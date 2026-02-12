/**
 * Shared script path resolution for Next.js API routes that spawn Python scripts.
 * Use SCRIPTS_DIR or resolve from cwd/scripts or cwd/../scripts so routes work
 * when the app is run from frontend/ or from repo root.
 */

import path from 'path';
import fs from 'fs';

export interface ResolveScriptResult {
  path: string | null;
  tried: string[];
}

/**
 * Resolve the absolute path to a script file under scripts/.
 * Tries: SCRIPTS_DIR/env, process.cwd()/scripts, process.cwd()/../scripts.
 * Returns { path, tried }. path is null if the file does not exist at any location.
 */
export function resolveScriptPath(scriptFileName: string): ResolveScriptResult {
  const candidates: string[] = [];
  if (process.env.SCRIPTS_DIR) {
    candidates.push(path.join(process.env.SCRIPTS_DIR, scriptFileName));
  }
  candidates.push(path.join(process.cwd(), 'scripts', scriptFileName));
  candidates.push(path.join(process.cwd(), '..', 'scripts', scriptFileName));
  for (const p of candidates) {
    try {
      if (fs.existsSync(p)) return { path: p, tried: candidates };
    } catch {
      // ignore
    }
  }
  return { path: null, tried: candidates };
}

/**
 * Get script path or throw with a clear error message (for use in routes that want to fail fast).
 */
export function getScriptPathOrThrow(scriptFileName: string): string {
  const { path: scriptPath, tried } = resolveScriptPath(scriptFileName);
  if (!scriptPath) {
    throw new Error(
      `Script not found: ${scriptFileName}. Tried: ${tried.join(', ')}. Set SCRIPTS_DIR or run from repo root.`
    );
  }
  return scriptPath;
}
