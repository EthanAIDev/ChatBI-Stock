import { create } from 'zustand';

type ThemeMode = 'light' | 'dark';

interface UiState {
  themeMode: ThemeMode;
  setThemeMode: (mode: ThemeMode) => void;
  toggleThemeMode: () => void;
}

function getInitialThemeMode(): ThemeMode {
  const customized = localStorage.getItem('theme_mode_customized');
  if (customized !== '1') {
    localStorage.setItem('theme_mode', 'dark');
    return 'dark';
  }
  const stored = localStorage.getItem('theme_mode');
  if (stored === 'light' || stored === 'dark') {
    return stored;
  }
  return 'dark';
}

export const useUiStore = create<UiState>((set, get) => ({
  themeMode: getInitialThemeMode(),
  setThemeMode: (mode) => {
    localStorage.setItem('theme_mode', mode);
    localStorage.setItem('theme_mode_customized', '1');
    set({ themeMode: mode });
  },
  toggleThemeMode: () => {
    const next = get().themeMode === 'light' ? 'dark' : 'light';
    localStorage.setItem('theme_mode', next);
    localStorage.setItem('theme_mode_customized', '1');
    set({ themeMode: next });
  },
}));
