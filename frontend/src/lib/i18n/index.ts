/**
 * Mehrsprachigkeit (i18n). Quelle ist Deutsch: Der deutsche Text ist zugleich der Schlüssel,
 * Übersetzungen liegen in `<sprache>.json` (deutscher Text → Übersetzung). Fehlt eine
 * Übersetzung, bleibt der deutsche Text stehen.
 *
 *   t('Gespeichert.')                    → „Saved.“
 *   t('{0} von {1} Geräten', a, b)       → Platzhalter {0}, {1} … werden ersetzt
 *
 * Die Sprache gilt für die ganze Seite und steht beim Laden fest (Browser-Sprache oder die
 * Wahl in der Seitenleiste, gespeichert im Browser). Umschalten lädt die Seite neu – so sind
 * auch Texte in Konstanten und Tabellen übersetzt. Zahlen und Daten über `locale`.
 *
 * Neue Sprache: `xx.json` neben `en.json` anlegen und in LANGUAGES eintragen.
 * `npm run check` meldet feste Texte ohne t() und fehlende englische Übersetzungen.
 */
import en from './en.json';
// Texte, die vom Backend kommen (Fehlermeldungen, Ereignisse, Metriken …) – siehe tApi()
import enApi from './en.api.json';

export type Lang = 'de' | 'en';

export const LANGUAGES: Record<Lang, { label: string; locale: string }> = {
  de: { label: 'Deutsch', locale: 'de-DE' },
  en: { label: 'English', locale: 'en-GB' }
};

const DICTS: Record<Lang, Record<string, string>> = { de: {}, en: { ...enApi, ...en } };
const STORAGE_KEY = 'tesseract-lang';

function stored(): Lang | null {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return v && v in LANGUAGES ? (v as Lang) : null;
  } catch {
    return null;
  }
}

function detect(): Lang {
  const prefs = typeof navigator !== 'undefined' ? navigator.languages ?? [navigator.language] : [];
  for (const p of prefs) {
    const code = (p || '').slice(0, 2).toLowerCase();
    if (code in LANGUAGES) return code as Lang;
  }
  return 'de';
}

/** Aktuelle Sprache der Seite */
export const lang: Lang = stored() ?? detect();
/** Für Intl/toLocaleString */
export const locale: string = LANGUAGES[lang].locale;
/** wurde die Sprache von Hand gewählt (sonst: Browser) */
export const langChosen: boolean = stored() !== null;

if (typeof document !== 'undefined') document.documentElement.lang = lang;

const dict = DICTS[lang];

/** Text übersetzen; {0}, {1} … durch die Werte ersetzen */
export function t(text: string, ...args: unknown[]): string {
  const out = dict[text] ?? text;
  if (!args.length) return out;
  return out.replace(/\{(\d+)\}/g, (m, i) => (Number(i) < args.length ? String(args[Number(i)] ?? '') : m));
}

let patterns: [RegExp, string][] | null = null;

/**
 * Text vom Backend übersetzen (API-Fehler, Ereignisnamen …): erst wörtlich, dann über Muster
 * mit Platzhaltern – „IP-Liste 5 unbekannt“ passt zu „IP-Liste {0} unbekannt“. Unbekanntes
 * bleibt, wie es ist.
 */
export function tApi(text: string, depth = 0): string {
  if (lang === 'de' || !text) return text;
  if (text in dict) return dict[text];
  if (depth > 2) return text;
  if (!patterns) {
    patterns = Object.keys(dict)
      .filter((k) => /\{\d+\}/.test(k))
      .map((k) => {
        const parts = k.split(/(\{\d+\})/);
        const re = parts
          .map((p) => {
            const m = /^\{(\d+)\}$/.exec(p);
            return m ? `(?<p${m[1]}>[\\s\\S]+?)` : p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
          })
          .join('');
        return [new RegExp(`^${re}$`), k] as [RegExp, string];
      })
      // genauere Muster (mehr fester Text) zuerst
      .sort((a, b) => b[1].replace(/\{\d+\}/g, '').length - a[1].replace(/\{\d+\}/g, '').length);
  }
  for (const [re, key] of patterns) {
    const m = re.exec(text);
    if (m?.groups) return dict[key].replace(/\{(\d+)\}/g, (_, i) => tApi(m.groups![`p${i}`] ?? '', depth + 1));
  }
  return text;
}

/** Sprache wählen (null = wieder nach Browser) und Seite neu laden */
export function setLang(next: Lang | null): void {
  try {
    if (next) localStorage.setItem(STORAGE_KEY, next);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ohne Speicher gilt die Browser-Sprache
  }
  location.reload();
}
