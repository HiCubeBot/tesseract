// Farbschema: System (Standard), hell oder dunkel – pro Browser gemerkt
import { t } from './i18n';
export type ThemeChoice = 'system' | 'light' | 'dark';

const KEY = 'tesseract-theme';

function read(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY);
    if (v === 'light' || v === 'dark') return v;
  } catch {
    /* privates Fenster o. ä. – dann eben System */
  }
  return 'system';
}

function apply(choice: ThemeChoice) {
  const el = document.documentElement;
  if (choice === 'system') delete el.dataset.theme;
  else el.dataset.theme = choice;
}

export const THEME_LABELS: Record<ThemeChoice, string> = {
  system: t('Wie System'),
  light: t('Hell'),
  dark: t('Dunkel')
};

class Theme {
  choice = $state<ThemeChoice>(read());

  constructor() {
    apply(this.choice);
  }

  set(choice: ThemeChoice) {
    this.choice = choice;
    apply(choice);
    try {
      if (choice === 'system') localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, choice);
    } catch {
      /* nicht speicherbar – gilt bis zum Neuladen */
    }
  }

  /** System → Hell → Dunkel → System */
  next() {
    const order: ThemeChoice[] = ['system', 'light', 'dark'];
    this.set(order[(order.indexOf(this.choice) + 1) % order.length]);
  }
}

export const theme = new Theme();
