/**
 * Was Personen sehen, die per Gerätezertifikat angemeldet sind (Rolle „Lesen“ oder
 * „Eigene Dienste“). Admins dürfen alles. Die eigentliche Prüfung macht der Controller
 * (backend/src/tesseract/uiaccess.py) – hier geht es nur darum, was die Oberfläche anbietet.
 */
import type { UiRole } from './api';

const READ = [
  '',
  'hosts',
  'hosts/:id/stats',
  'hosts/:id/history',
  'certificates',
  'nodes',
  'logs',
  'stats',
  'stats-traffic',
  'stats-usage',
  'stats-map',
  'stats-ops',
  'me'
];
const OWN = ['hosts', 'hosts/:id/stats', 'hosts/:id/history', 'me'];

export function pageAllowed(role: UiRole | undefined, pattern: string): boolean {
  if (!role || role === 'admin') return true;
  if (pattern === 'login') return true;
  if (role === 'read') return READ.includes(pattern);
  if (role === 'own') return OWN.includes(pattern);
  return false;
}

/** Startseite der Rolle */
export function homeFor(role: UiRole | undefined): string {
  return role === 'own' ? '#/hosts' : '#/';
}

/** Ziel beim Klick auf einen Host: Admins bearbeiten, alle anderen sehen die Statistik */
export function hostHref(role: UiRole | undefined, id: number): string {
  return !role || role === 'admin' ? `#/hosts/${id}` : `#/hosts/${id}/stats`;
}
