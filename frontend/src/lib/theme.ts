export type Theme = 'day' | 'night';

const THEME_KEY = 'theme';

export function setTheme(theme: Theme): void {
  if (typeof document === 'undefined') return;
  document.documentElement.setAttribute('data-theme', theme);
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {}
}

export function getTheme(): Theme {
  if (typeof document === 'undefined') return 'night';
  const attr = document.documentElement.getAttribute('data-theme') as Theme | null;
  if (attr === 'day' || attr === 'night') return attr;
  try {
    const saved = localStorage.getItem(THEME_KEY) as Theme | null;
    if (saved === 'day' || saved === 'night') return saved;
  } catch {}
  return 'night';
}

export function initTheme(): Theme {
  const theme = getTheme();
  setTheme(theme);
  return theme;
}

export function toggleTheme(): Theme {
  const next = getTheme() === 'night' ? 'day' : 'night';
  setTheme(next);
  return next;
}
