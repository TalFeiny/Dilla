import { useEffect, useState } from 'react';
import { initTheme, toggleTheme, getTheme } from '@/lib/theme';

export default function ThemeToggle() {
  const [mode, setMode] = useState<'day' | 'night'>(() => 'night');

  useEffect(() => {
    setMode(initTheme());
  }, []);

  return (
    <button
      onClick={() => setMode(toggleTheme())}
      className="px-3 py-1.5 rounded-lg border border-[color:var(--border)] text-sm"
      aria-label="Toggle theme"
    >
      {mode === 'night' ? 'Day' : 'Night'}
    </button>
  );
}
