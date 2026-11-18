/** Kleiner Client für die Controller-API (/api). */

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
  }
}

type Listener = () => void;
const unauthorizedListeners = new Set<Listener>();

/** Wird aufgerufen, wenn die API 401 liefert (Session abgelaufen). */
export function onUnauthorized(fn: Listener): () => void {
  unauthorizedListeners.add(fn);
  return () => unauthorizedListeners.delete(fn);
}

function errorMessage(body: unknown, status: number): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => {
          const loc = Array.isArray(d.loc) ? d.loc.filter((x: unknown) => x !== 'body').join('.') : '';
          const msg = String(d.msg ?? '').replace(/^Value error, /, '');
          return loc ? `${loc}: ${msg}` : msg;
        })
        .join(' · ');
    }
  }
  return `Fehler ${status}`;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch('/api' + path, {
    method,
    credentials: 'same-origin',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined
  });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401 && path !== '/auth/login') unauthorizedListeners.forEach((fn) => fn());
    throw new ApiError(res.status, errorMessage(data, res.status));
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body ?? {}),
  put: <T>(path: string, body: unknown) => request<T>('PUT', path, body),
  del: <T>(path: string) => request<T>('DELETE', path)
};

// ---------- Typen der API ----------

export interface Me {
  username: string;
}

export interface NodeRef {
  id: number;
  name: string;
}

export interface Host {
  id: number;
  domain: string;
  node: NodeRef;
  upstream_scheme: 'http' | 'https';
  upstream_host: string;
  upstream_port: number;
  websockets: boolean;
  force_https: boolean;
  compression: boolean;
  access: 'public' | 'mtls';
  enabled: boolean;
  draft: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export type HostInput = Omit<Host, 'id' | 'node' | 'version' | 'created_at' | 'updated_at'> & {
  node_id: number;
  comment?: string;
};

export interface ApplyResult {
  ok: boolean;
  error: string | null;
  skipped: boolean;
}

export interface HostSaved {
  host: Host;
  apply: ApplyResult;
}

export interface Check {
  key: string;
  title: string;
  status: 'ok' | 'warn' | 'bad' | 'info';
  detail: string;
}

export interface Change {
  field: string;
  before: unknown;
  after: unknown;
}

export interface Version {
  version: number;
  created_at: string;
  actor: string;
  comment: string;
  current: boolean;
  changes: Change[];
  snapshot: Record<string, unknown>;
}

export interface VersionDetail extends Version {
  route: unknown;
  previous_route: unknown | null;
}

export interface NodeInfo {
  id: number;
  name: string;
  location: string;
  hosts: number;
  last_applied_at: string | null;
  last_apply_error: string | null;
  in_sync: boolean;
}

export interface GeneralSettings {
  acme_email: string;
  public_ips: string[];
  controller_domain: string;
  version: string;
}

export interface AuditEntry {
  id: number;
  created_at: string;
  actor: string;
  action: string;
  target: string;
  details: Record<string, unknown>;
  ip: string | null;
}

// ---------- Anzeige-Hilfen ----------

const dateFmt = new Intl.DateTimeFormat('de-DE', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit'
});

export const formatDate = (iso: string | null) => (iso ? dateFmt.format(new Date(iso)) : '–');

export function formatAgo(iso: string | null): string {
  if (!iso) return 'nie';
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return 'gerade eben';
  if (s < 3600) return `vor ${Math.round(s / 60)} Min.`;
  if (s < 86400) return `vor ${Math.round(s / 3600)} Std.`;
  return formatDate(iso);
}

export const FIELD_LABELS: Record<string, string> = {
  domain: 'Domain',
  node: 'Node',
  upstream_scheme: 'Protokoll',
  upstream_host: 'Ziel-Adresse',
  upstream_port: 'Port',
  websockets: 'WebSockets',
  force_https: 'HTTP → HTTPS',
  compression: 'Kompression',
  access: 'Zugriff',
  enabled: 'Aktiv',
  draft: 'Entwurf'
};

export function formatValue(v: unknown): string {
  if (v === true) return 'an';
  if (v === false) return 'aus';
  if (v === 'public') return 'Öffentlich';
  if (v === 'mtls') return 'Nur mit Zertifikat';
  if (v === null || v === undefined || v === '') return '–';
  return String(v);
}

export const ACTION_LABELS: Record<string, string> = {
  login: 'Angemeldet',
  login_failed: 'Anmeldung fehlgeschlagen',
  password_changed: 'Passwort geändert',
  password_reset: 'Passwort zurückgesetzt (CLI)',
  host_created: 'Host angelegt',
  host_updated: 'Host geändert',
  host_deleted: 'Host gelöscht',
  host_restored: 'Host zurückgesetzt',
  config_applied: 'Config übertragen',
  config_apply_failed: 'Übertragen fehlgeschlagen',
  settings_changed: 'Einstellungen geändert',
  ca_created: 'Zertifizierungsstelle eingerichtet',
  group_created: 'Gruppe angelegt',
  group_updated: 'Gruppe geändert',
  group_deleted: 'Gruppe gelöscht',
  person_created: 'Person angelegt',
  person_updated: 'Person geändert',
  person_deleted: 'Person gelöscht',
  device_issued: 'Gerätezertifikat ausgestellt',
  device_revoked: 'Gerät gesperrt'
};

// ---------- Phase 2: CA, Personen, Geräte ----------

export interface AuthorityInfo {
  kind: 'root' | 'intermediate';
  subject: string;
  fingerprint: string;
  not_before: string;
  not_after: string;
  key_on_controller: boolean;
}

export interface CAStatus {
  configured: boolean;
  root: AuthorityInfo | null;
  intermediate: AuthorityInfo | null;
  devices_total: number;
  devices_active: number;
  devices_revoked: number;
  devices_beyond_intermediate: number;
}

export interface Group {
  id: number;
  name: string;
  description: string;
  builtin: boolean;
  members: number;
}

export interface Device {
  id: number;
  person_id: number;
  person_name: string;
  name: string;
  platform: string;
  serial: string;
  fingerprint: string;
  not_before: string;
  not_after: string;
  unlimited: boolean;
  status: 'active' | 'expired' | 'revoked';
  revoked_at: string | null;
  revoke_reason: string;
  last_seen_at: string | null;
  created_at: string;
}

export interface Person {
  id: number;
  name: string;
  note: string;
  max_devices: number;
  disabled: boolean;
  created_at: string;
  groups: { id: number; name: string }[];
  devices: Device[];
  active_devices: number;
}

export interface IssuedDevice {
  device: Device;
  filename: string;
  password: string;
  p12_base64: string;
}

export const PLATFORMS: Record<string, string> = {
  ios: 'iPhone / iPad',
  android: 'Android',
  macos: 'Mac',
  windows: 'Windows',
  linux: 'Linux',
  other: 'Sonstiges'
};

export const DEVICE_STATUS: Record<Device['status'], { label: string; tone: 'ok' | 'warn' | 'bad' }> = {
  active: { label: 'aktiv', tone: 'ok' },
  expired: { label: 'abgelaufen', tone: 'warn' },
  revoked: { label: 'gesperrt', tone: 'bad' }
};

const dayFmt = new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
export const formatDay = (iso: string | null) => (iso ? dayFmt.format(new Date(iso)) : '–');

/** Läuft in weniger als 30 Tagen ab? */
export const expiresSoon = (d: Device) =>
  d.status === 'active' && new Date(d.not_after).getTime() - Date.now() < 30 * 86400_000;

export function downloadFile(filename: string, data: BlobPart, type: string) {
  const url = URL.createObjectURL(new Blob([data], { type }));
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function base64ToBytes(b64: string): Uint8Array<ArrayBuffer> {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}
