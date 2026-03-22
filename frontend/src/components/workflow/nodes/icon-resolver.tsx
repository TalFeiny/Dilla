import * as LucideIcons from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

const iconCache = new Map<string, LucideIcon>();

/**
 * Resolve a Lucide icon name string (e.g. "TrendingUp") to the actual React component.
 * Falls back to HelpCircle if not found.
 */
export function resolveIcon(name: string): LucideIcon {
  if (iconCache.has(name)) return iconCache.get(name)!;
  const icon = (LucideIcons as Record<string, unknown>)[name] as LucideIcon | undefined;
  const resolved = icon || LucideIcons.HelpCircle;
  iconCache.set(name, resolved);
  return resolved;
}
