/** Hilfen für die Statistik-Seiten: UTC-Stunden-Buckets in Ortszeit zusammenfassen. */

import { locale, t } from './i18n';
export type Range = '24h' | '7d' | '30d';

export interface Bucket {
  start: Date;
  label: string;
  title: string;
  values: Record<string, number>;
}

const STEP: Record<Range, number> = { '24h': 3600e3, '7d': 6 * 3600e3, '30d': 24 * 3600e3 };
const COUNT: Record<Range, number> = { '24h': 24, '7d': 28, '30d': 30 };

function floorLocal(d: Date, range: Range): Date {
  const x = new Date(d);
  x.setMinutes(0, 0, 0);
  if (range === '7d') x.setHours(Math.floor(x.getHours() / 6) * 6);
  if (range === '30d') x.setHours(0);
  return x;
}

/** Stunden-Buckets ({t: ISO, …Werte}) → feste Achse in Ortszeit, leere Buckets mit 0. */
export function bucketize(hourly: { t: string; [k: string]: number | string }[], range: Range, keys: string[]): Bucket[] {
  const step = STEP[range];
  const end = floorLocal(new Date(), range).getTime();
  const out: Bucket[] = [];
  for (let i = COUNT[range] - 1; i >= 0; i--) {
    // Tage über die Zeitumstellung: über das Datum statt über Millisekunden zählen
    const start = range === '30d' ? new Date(new Date(end).setDate(new Date(end).getDate() - i)) : new Date(end - i * step);
    out.push({ start, label: axisLabel(start, range), title: bucketTitle(start, range), values: Object.fromEntries(keys.map((k) => [k, 0])) });
  }
  const index = new Map(out.map((b, i) => [floorLocal(b.start, range).getTime(), i]));
  for (const h of hourly) {
    const i = index.get(floorLocal(new Date(h.t), range).getTime());
    if (i === undefined) continue;
    for (const k of keys) out[i].values[k] += Number(h[k] ?? 0);
  }
  return out;
}

function axisLabel(d: Date, range: Range): string {
  if (range === '24h') return `${String(d.getHours()).padStart(2, '0')}:00`;
  if (range === '7d') return d.toLocaleDateString(locale, { weekday: 'short' });
  return d.toLocaleDateString(locale, { day: '2-digit', month: '2-digit' });
}

function bucketTitle(d: Date, range: Range): string {
  if (range === '24h') return `${d.toLocaleDateString(locale, { weekday: 'short' })} ${axisLabel(d, range)}–${String((d.getHours() + 1) % 24).padStart(2, '0')}:00`;
  if (range === '7d') return t('{0} {1}–{2} Uhr', d.toLocaleDateString(locale, { weekday: 'short', day: '2-digit', month: '2-digit' }), String(d.getHours()).padStart(2, '0'), String(d.getHours() + 6).padStart(2, '0'));
  return d.toLocaleDateString(locale, { weekday: 'long', day: '2-digit', month: '2-digit' });
}

export const fmt = (n: number) => n.toLocaleString(locale);

/** Kompakte Zahl für Achsen: 1.500 → 1,5 k */
export function compact(n: number): string {
  if (n >= 1e6) return `${(n / 1e6).toLocaleString(locale, { maximumFractionDigits: 1 })} M`;
  if (n >= 1e4) return `${(n / 1e3).toLocaleString(locale, { maximumFractionDigits: 0 })} k`;
  return fmt(n);
}

/** Saubere Achsenobergrenze (1, 2, 5 × 10^n) */
export function niceMax(v: number): number {
  if (v <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  for (const m of [1, 2, 5, 10]) if (v <= m * p) return m * p;
  return 10 * p;
}

/** Wochentag (0 = Montag) × Stunde in Ortszeit */
export function weekGrid(hourly: { t: string; n: number }[]): number[][] {
  const grid = Array.from({ length: 7 }, () => Array(24).fill(0));
  for (const h of hourly) {
    const d = new Date(h.t);
    grid[(d.getDay() + 6) % 7][d.getHours()] += h.n;
  }
  return grid;
}

export const WEEKDAYS = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];

/** Farben aus dem Design (gegen die dunkle Fläche geprüft: Farbsehschwäche, Kontrast) */
export const SERIES = {
  mtls: { label: t('Ohne Zertifikat'), color: '#8B7CF6' },
  waf: { label: 'WAF', color: '#14A399' },
  ip: { label: t('IP-Filter'), color: '#CF7D45' },
  other: { label: t('Sonstige'), color: '#5E6573' }
} as const;
