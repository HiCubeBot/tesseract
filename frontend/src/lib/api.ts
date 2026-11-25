/** Kleiner Client für die Controller-API (/api). */

import { locale, t, tApi } from './i18n';
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
    if (typeof detail === 'string') return tApi(detail);
    if (Array.isArray(detail)) {
      return detail
        .map((d) => {
          const loc = Array.isArray(d.loc) ? d.loc.filter((x: unknown) => x !== 'body').join('.') : '';
          const msg = tApi(String(d.msg ?? '').replace(/^Value error, /, ''));
          return loc ? `${loc}: ${msg}` : msg;
        })
        .join(' · ');
    }
  }
  return t('Fehler {0}', status);
}

/**
 * fetch mit Wiederholung bei 421 (Misdirected Request).
 *
 * Browser verwenden bei HTTP/2 und HTTP/3 eine offene Verbindung eines anderen Hosts weiter,
 * wenn dessen Zertifikat (z. B. ein Wildcard) auch diesen Namen abdeckt. Caddy lehnt das bei
 * Client-Zertifikaten mit 421 ab und schließt die Verbindung (Schutz gegen Umgehung von mTLS).
 * Der nächste Versuch geht über eine eigene Verbindung und klappt. Gefahrlos auch für POST:
 * Caddy hat die Anfrage abgewiesen, bevor sie das Backend erreicht hat.
 */
export async function fetchRetry(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const delays = [0, 150, 500];
  let res = await fetch(input, init);
  for (const ms of delays) {
    if (res.status !== 421) break;
    if (ms) await new Promise((r) => setTimeout(r, ms));
    res = await fetch(input, init);
  }
  return res;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetchRetry('/api' + path, {
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
  /** Passwort kommt aus TESSERACT_ADMIN_PASSWORD (.env) */
  password_from_env?: boolean;
  /** "local" oder "oidc" (SSO, ohne Passwort), "mtls" = Person per Gerätezertifikat */
  source?: 'local' | 'oidc' | 'mtls';
  /** "admin" für Konten; bei Personen per Zertifikat ihre Rolle */
  role?: UiRole;
  person?: string | null;
  device?: string | null;
}

/** Zugriff auf Tesseract per Gerätezertifikat */
export type UiRole = 'none' | 'read' | 'own' | 'admin';
export const UI_ROLES: Record<UiRole, string> = {
  none: t('Kein Zugriff'),
  read: t('Lesen'),
  own: t('Eigene Dienste'),
  admin: t('Admin')
};
export const UI_ROLE_HINTS: Record<UiRole, string> = {
  none: t('Tesseract selbst ist für diese Person nicht erreichbar.'),
  read: t('Übersicht, Hosts, Statistik und Logs ansehen – nichts ändern.'),
  own: t('Nur die Hosts, für die die Person freigegeben ist (Statistik, Verlauf), und die eigenen Geräte.'),
  admin: t('Alles wie ein Admin – nur Passwort und Passkeys gibt es nicht.')
};

export interface MyAccess {
  person: string;
  role: UiRole;
  current_device: string;
  devices: Device[];
  hosts: string[];
}

export interface DeviceInfo {
  certificate: boolean;
  admin_device: string | null;
  person: string | null;
}

export interface AdminAccess {
  enabled: boolean;
  admin_devices: number;
  current_device: string | null;
  can_enable: boolean;
  reason: string | null;
  apply_error: string | null;
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
  /** https zum Ziel ohne Zertifikatsprüfung */
  upstream_insecure: boolean;
  websockets: boolean;
  force_https: boolean;
  compression: boolean;
  access: 'public' | 'mtls';
  no_cert_action: 'reject' | 'hint';
  waf_mode: WafMode;
  waf_paranoia: number;
  waf_exclusions: number[];
  ip_mode: IpMode;
  ip_entries: string[];
  ip_list_ids: number[];
  authelia: boolean;
  tls_challenge: 'http' | 'dns';
  internal: boolean;
  /** mTLS: aus den internen Netzen auch ohne Zertifikat */
  internal_no_cert: boolean;
  /** mTLS: Tesseract selbst (Controller-Zertifikat) darf zugreifen, z. B. für ntfy */
  allow_controller: boolean;
  /** Uptime-Monitor: Ziel regelmäßig prüfen */
  monitor: boolean;
  /** auf der öffentlichen Statusseite zeigen, mit Anzeigename */
  status_public: boolean;
  status_name: string;
  /** robots.txt direkt von Caddy */
  robots: RobotsMode;
  robots_paths: string[];
  robots_sitemap: string;
  robots_text: string;
  custom_cert_id: number | null;
  wildcard_cert: string | null;
  areas: (AreaInput & { id: number })[];
  paths: string[];
  grants: GrantRef[];
  granted_persons: number;
  allowed_devices: number;
  enabled: boolean;
  draft: boolean;
  /** "ui" oder "docker" (aus Container-Labels) */
  source: 'ui' | 'docker';
  /** bei Docker: "<Node-ID>:<Container>" */
  source_ref: string | null;
  source_disabled: boolean;
  /** DNS-Eintrag bei Cloudflare: null = keiner, "cname" oder "address" (A/AAAA) */
  dns_type: 'cname' | 'address' | null;
  /** leer = Wert der Domain-Einstellung; bei "address" IPs kommagetrennt */
  dns_target: string;
  dns_proxied: boolean;
  dns_records: DnsRecord[];
  dns_error: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export type WafMode = 'off' | 'detect' | 'block';

/** Host-Bereich: null = wie beim Host */
export interface AreaInput {
  name: string;
  paths: string[];
  access: 'public' | 'mtls' | null;
  grant_group_ids: number[];
  grant_person_ids: number[];
  waf_mode: WafMode | null;
  waf_exclusions: number[];
  authelia: boolean | null;
  ip_mode: 'off' | 'block' | 'allow' | null;
  ip_entries: string[];
  ip_list_ids: number[];
}
export type IpMode = 'off' | 'block' | 'allow';

export interface CustomCert {
  id: number;
  name: string;
  names: string[];
  issuer: string;
  fingerprint: string;
  not_before: string;
  not_after: string;
  used_by: string[];
  created_at: string;
}

export interface CertificateInfo {
  fingerprint: string;
  names: string[];
  issuer: string;
  issuer_raw: string;
  not_before: string;
  not_after: string;
  days_left: number;
  status: 'ok' | 'soon' | 'expired';
  source: 'http-01' | 'dns-01' | 'wildcard' | 'lokal' | 'eigenes' | 'unbekannt';
  hosts: string[];
  node: string;
}

export interface CertificateOverview {
  checked_at: string;
  certificates: CertificateInfo[];
  errors: { name: string; node: string; error: string }[];
}

export interface Ban {
  id: number;
  ip: string;
  created_at: string;
  expires_at: string | null; // null = dauerhaft
  reason: string;
  hits: number;
  host: string;
  created_by: string;
  lifted_at: string | null;
  lifted_by: string | null;
  active: boolean;
}

export const IP_MODES: Record<IpMode, string> = {
  off: t('Aus'),
  block: t('Sperren'),
  allow: t('Nur erlauben')
};

export interface IpList {
  id: number;
  name: string;
  description: string;
  entries: string[];
  used_by: string[];
  updated_at: string;
}

/** Welches geteilte Wildcard-Zertifikat deckt den Namen ab? (eine Ebene darunter) */
export function coveringWildcard(domain: string, wildcards: string[]): string | null {
  const d = domain.trim().toLowerCase();
  if (d.startsWith('*.')) return wildcards.includes(d) ? d : null;
  const dot = d.indexOf('.');
  if (dot < 1) return null;
  const candidate = '*.' + d.slice(dot + 1);
  return wildcards.includes(candidate) ? candidate : null;
}

/** Vorlage: Netze von Cloudflare (Stand der Veröffentlichung, bitte gelegentlich prüfen) */
export const CLOUDFLARE_RANGES = [
  '173.245.48.0/20', '103.21.244.0/22', '103.22.200.0/22', '103.31.4.0/22', '141.101.64.0/18',
  '108.162.192.0/18', '190.93.240.0/20', '188.114.96.0/20', '197.234.240.0/22', '198.41.128.0/17',
  '162.158.0.0/15', '104.16.0.0/13', '104.24.0.0/14', '172.64.0.0/13', '131.0.72.0/22',
  '2400:cb00::/32', '2606:4700::/32', '2803:f800::/32', '2405:b500::/32', '2405:8100::/32',
  '2a06:98c0::/29', '2c0f:f248::/32'
];

export type RobotsMode = 'off' | 'allow' | 'deny' | 'deny_ai' | 'paths' | 'custom';
export const ROBOTS_MODES: Record<RobotsMode, string> = {
  off: t('Aus – der Dienst antwortet selbst'),
  allow: t('Alles erlauben'),
  deny: t('Alles verbieten'),
  deny_ai: t('KI-Crawler verbieten, Suchmaschinen erlauben'),
  paths: t('Nur bestimmte Pfade sperren'),
  custom: t('Eigener Text')
};

export interface RobotsPreview {
  text: string;
  errors: string[];
  warnings: string[];
  /** greift „mTLS-Hosts: alles verbieten“ aus den Einstellungen */
  from_settings: boolean;
}

export const WAF_MODES: Record<WafMode, string> = {
  off: t('Aus'),
  detect: t('Nur protokollieren'),
  block: t('Blockieren')
};

export interface GrantRef {
  kind: 'group' | 'person';
  id: number;
  name: string;
}

export type HostInput = Omit<
  Host,
  | 'id'
  | 'node'
  | 'version'
  | 'created_at'
  | 'updated_at'
  | 'grants'
  | 'granted_persons'
  | 'allowed_devices'
  | 'wildcard_cert'
  | 'source'
  | 'source_ref'
  | 'source_disabled'
  | 'dns_records'
  | 'dns_error'
  | 'waf_mode'
  | 'waf_paranoia'
  | 'areas'
  | 'robots'
> & {
  /** null = Standard aus den Einstellungen (nur beim Anlegen) */
  robots: RobotsMode | null;
  node_id: number;
  grant_group_ids: number[];
  grant_person_ids: number[];
  /** null = Standard aus den Einstellungen */
  waf_mode: WafMode | null;
  waf_paranoia: number | null;
  areas: AreaInput[];
  comment?: string;
};

export interface AccessMatrix {
  hosts: { id: number; domain: string; access: 'public' | 'mtls'; paths: string[] }[];
  groups: { id: number; name: string; members: number[] }[];
  persons: { id: number; name: string; disabled: boolean; group_ids: number[] }[];
  grants: { host_id: number; kind: 'group' | 'person'; id: number }[];
}

export interface DnsRecord {
  id: string;
  type: string;
  name: string;
  content: string;
  proxied: boolean;
}

/** Einstellungen › Integrationen › DNS-Einträge: Standard pro Domain */
export interface DnsZone {
  zone: string;
  type: 'cname' | 'address';
  cname_target: string;
  ip_source: 'node' | 'custom';
  ips: string[];
  proxied: boolean;
}

export interface DnsResult {
  ok: boolean;
  skipped: boolean;
  error: string | null;
}

/** Passende Domain für einen Host (längste Übereinstimmung) */
export function zoneFor(domain: string, zones: DnsZone[]): DnsZone | null {
  const name = domain.trim().toLowerCase().replace(/^\*\./, '').replace(/\.$/, '');
  let best: DnsZone | null = null;
  for (const z of zones) {
    if ((name === z.zone || name.endsWith('.' + z.zone)) && (!best || z.zone.length > best.zone.length)) best = z;
  }
  return best;
}

export interface ApplyResult {
  ok: boolean;
  error: string | null;
  skipped: boolean;
}

export interface HostSaved {
  host: Host;
  apply: ApplyResult;
  dns?: DnsResult;
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

export type NodeState = 'pending' | 'online' | 'offline' | 'drift' | 'error';

export interface NodeInfo {
  id: number;
  name: string;
  location: string;
  /** "local" = Caddy im selben Stack, "agent" = entfernter Node mit Agent */
  kind: 'local' | 'agent';
  /** öffentliche IPs des Servers – für die DNS-Prüfung bei „Host anlegen“ */
  public_ips: string[];
  state: NodeState;
  hosts: number;
  last_applied_at: string | null;
  last_apply_error: string | null;
  in_sync: boolean;
  last_seen_at: string | null;
  agent_version: string | null;
  caddy_version: string | null;
  modules: string[] | null;
  drift: boolean;
  drift_since: string | null;
  accepted: boolean;
  join_state: 'pending' | 'approved' | 'rejected' | null;
  join_open: boolean;
  join_expires_at: string | null;
  join_hostname: string | null;
  join_key_fingerprint: string | null;
  join_requested_at: string | null;
  cert_not_after: string | null;
  /** davon öffentlich (ohne Zertifikat, nicht nur intern) */
  hosts_public: number;
  /** Adresse, unter der der Agent den Controller erreicht */
  controller_url: string | null;
  /** IP, von der der Agent kommt, und ihre Art */
  agent_ip: string | null;
  network: 'intern' | 'privat' | 'internet' | null;
}

export interface JoinToken {
  token: string;
  expires_at: string;
  /** nur der Agent, per Kommandozeile */
  command: string;
  /** ein Befehl für den neuen Server (Installationsskript vom Controller) */
  install_command: string;
  install_sha256: string;
}

export interface DriftChange {
  path: string;
  before: unknown;
  after: unknown;
  kind: 'added' | 'removed' | 'changed';
  /** Host, zu dessen Route der Pfad gehört */
  host: string | null;
}

export interface NodeDrift {
  drift: boolean;
  since: string | null;
  changes: DriftChange[];
}

/** Bekannte Caddy-Module, die Tesseract nutzt */
export const MODULES: Record<string, string> = {
  'http.handlers.waf': t('Coraza WAF'),
  'dns.providers.cloudflare': t('DNS · Cloudflare')
};

export interface GeneralSettings {
  acme_email: string;
  waf_default_mode: WafMode;
  waf_default_paranoia: number;
  controller_waf_mode: WafMode;
  trusted_proxies: string[];
  trusted_proxy_list_ids: number[];
  authelia_url: string;
  authelia_headers: string[];
  cloudflare_token_set: boolean;
  docker_enabled: boolean;
  docker_auto_activate: boolean;
  /** TESSERACT_DOCKER_HOST ist gesetzt */
  docker_local: boolean;
  /** TESSERACT_ADMIN_NETWORKS – Netze, aus denen die Oberfläche erreichbar ist */
  admin_networks: string[];
  admin_networks_open: boolean;
  /** Node-Schnittstelle von admin_networks ausgenommen */
  agent_api_public: boolean;
  autoban_enabled: boolean;
  autoban_hits: number;
  autoban_window_minutes: number;
  autoban_hours: number;
  autoban_exempt: string[];
  autoban_log_ready: boolean;
  internal_networks: string[];
  internal_list_ids: number[];
  wildcard_certs: string[];
  device_self_renew: boolean;
  device_self_renew_days: number;
  device_self_renew_url: string;
  /** .p12 neuer Geräte verschlüsselt aufbewahren */
  device_keep_p12: boolean;
  device_p12_stored: number;
  /** öffentliche Statusseite /status – standardmäßig aus */
  status_page_enabled: boolean;
  status_page_url: string;
  /** robots.txt: Standard für neue Hosts, mTLS-Hosts sperren, KI-Crawler */
  robots_default: RobotsMode;
  robots_mtls_deny: boolean;
  robots_ai_bots: string[];
  controller_domain: string;
  /** über die Umgebung (.env) festgelegt – wird beim Start überschrieben */
  env_managed: string[];
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
  hash: string | null;
}

export interface AuditVerify {
  ok: boolean;
  checked: number;
  broken_id: number | null;
  last_hash: string;
}

// ---------- Anzeige-Hilfen ----------

const dateFmt = new Intl.DateTimeFormat(locale, {
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
  if (s < 60) return t('gerade eben');
  if (s < 3600) return t('vor {0} Min.', Math.round(s / 60));
  if (s < 86400) return t('vor {0} Std.', Math.round(s / 3600));
  return formatDate(iso);
}

/** Kurz für schmale Spalten: wie formatAgo, ältere Einträge „19.11. 22:52“ (Jahr nur, wenn anders) */
export function formatAgoShort(iso: string | null): string {
  if (!iso) return 'nie';
  const d = new Date(iso);
  if (Date.now() - d.getTime() < 86_400_000) return formatAgo(iso);
  const day = d.toLocaleDateString(locale, {
    day: '2-digit',
    month: '2-digit',
    ...(d.getFullYear() !== new Date().getFullYear() ? { year: '2-digit' } : {})
  });
  const time = d.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });
  return `${day} ${time}`;
}

export const FIELD_LABELS: Record<string, string> = {
  domain: t('Domain'),
  node: t('Node'),
  upstream_scheme: t('Protokoll'),
  upstream_host: t('Ziel-Adresse'),
  upstream_port: t('Port'),
  upstream_insecure: t('Zertifikat des Ziels nicht prüfen'),
  websockets: t('WebSockets'),
  force_https: t('HTTP → HTTPS'),
  compression: t('Kompression'),
  access: t('Zugriff'),
  no_cert_action: t('Ohne Zertifikat'),
  paths: t('Pfade'),
  grants: t('Freigegeben für'),
  waf_mode: 'WAF',
  waf_paranoia: t('Paranoia-Level'),
  waf_exclusions: t('Regel-Ausnahmen'),
  ip_mode: t('IP-Filter'),
  ip_entries: 'IPs/Netze',
  ip_lists: t('IP-Listen'),
  authelia: t('Login über Authelia'),
  tls_challenge: t('Zertifikats-Prüfung'),
  internal: t('Nur intern'),
  internal_no_cert: t('Intern ohne Zertifikat'),
  allow_controller: t('Tesseract darf zugreifen'),
  monitor: t('Überwachung'),
  status_public: t('Statusseite'),
  status_name: t('Name auf der Statusseite'),
  robots: 'robots.txt',
  robots_paths: t('robots.txt: gesperrte Pfade'),
  robots_sitemap: t('robots.txt: Sitemap'),
  robots_text: t('robots.txt: eigener Text'),
  custom_cert: t('Eigenes Zertifikat'),
  areas: t('Bereiche'),
  enabled: t('Aktiv'),
  draft: t('Entwurf')
};

export function formatValue(v: unknown): string {
  if (Array.isArray(v)) return v.length ? v.map(formatValue).join(', ') : '–';
  if (v && typeof v === 'object' && 'paths' in v) {
    const a = v as { name?: string; paths: string[] };
    return `${a.name ? a.name + ' ' : ''}(${a.paths.join(', ')})`;
  }
  if (v === 'reject') return t('Verbindung ablehnen');
  if (v === 'http') return 'HTTP-01';
  if (v === 'dns') return t('DNS-01 (Cloudflare)');
  if (v === 'off') return t('Aus');
  if (v === 'detect') return t('Nur protokollieren');
  if (v === 'block') return 'Blockieren/Sperren';
  if (v === 'allow') return t('Nur erlauben');
  if (v === 'hint') return t('Hinweisseite');
  if (v === true) return 'an';
  if (v === false) return 'aus';
  if (v === 'public') return t('Öffentlich');
  if (v === 'mtls') return t('Nur mit Zertifikat');
  if (v === null || v === undefined || v === '') return '–';
  return String(v);
}

export const ACTION_LABELS: Record<string, string> = {
  login: t('Angemeldet'),
  login_failed: t('Anmeldung fehlgeschlagen'),
  password_changed: t('Passwort geändert'),
  password_reset: t('Passwort zurückgesetzt (CLI)'),
  host_created: t('Host angelegt'),
  host_updated: t('Host geändert'),
  host_deleted: t('Host gelöscht'),
  host_restored: t('Host zurückgesetzt'),
  config_applied: t('Config übertragen'),
  config_apply_failed: t('Übertragen fehlgeschlagen'),
  settings_changed: t('Einstellungen geändert'),
  ca_created: t('Zertifizierungsstelle eingerichtet'),
  group_created: t('Gruppe angelegt'),
  group_updated: t('Gruppe geändert'),
  group_deleted: t('Gruppe gelöscht'),
  person_created: t('Person angelegt'),
  person_updated: t('Person geändert'),
  person_deleted: t('Person gelöscht'),
  device_issued: t('Gerätezertifikat ausgestellt'),
  device_revoked: t('Gerät gesperrt'),
  device_deleted: t('Gerät gelöscht'),
  access_changed: t('Zugriff geändert'),
  invite_created: t('Einladung erstellt'),
  invite_revoked: t('Einladung widerrufen'),
  enrollment_requested: t('Gerät möchte sich registrieren'),
  enrollment_approved: t('Gerät freigegeben'),
  enrollment_rejected: t('Gerät abgelehnt'),
  enrollment_code_wrong: t('Falscher Einladungscode'),
  admin_mtls_on: t('Oberfläche nur noch mit Admin-Zertifikat'),
  admin_mtls_off: t('Admin-Zertifikat für Oberfläche abgeschaltet'),
  iplist_created: t('IP-Liste angelegt'),
  iplist_updated: t('IP-Liste geändert'),
  iplist_deleted: t('IP-Liste gelöscht'),
  ip_banned: t('IP gesperrt'),
  ip_unbanned: t('IP entsperrt'),
  node_created: t('Node angelegt'),
  node_updated: t('Node geändert'),
  node_deleted: t('Node gelöscht'),
  node_token_created: t('Beitritts-Token erzeugt'),
  node_join_requested: t('Agent möchte beitreten'),
  node_approved: t('Node bestätigt'),
  node_rejected: t('Beitritt abgelehnt'),
  node_joined: t('Agent verbunden'),
  node_drift_detected: t('Abweichung auf Node erkannt'),
  node_drift_overwritten: t('Abweichung überschrieben'),
  node_drift_accepted: t('Abweichung übernommen'),
  node_offline: t('Node offline'),
  host_down: t('Dienst nicht erreichbar'),
  host_up: t('Dienst wieder erreichbar'),
  node_online: t('Node wieder online'),
  backup_created: t('Sicherung erstellt'),
  backup_failed: t('Sicherung fehlgeschlagen'),
  git_mirrored: t('Git-Spiegel aktualisiert'),
  backup_tested: t('Sicherung getestet'),
  backup_downloaded: t('Sicherung heruntergeladen'),
  backup_restored: t('Sicherung wiederhergestellt'),
  ca_rotated: t('Zwischenzertifikat gewechselt'),
  device_renewed: t('Gerät verlängert'),
  node_cert_renewed: t('Node-Zertifikat erneuert'),
  device_expiring: t('Gerätezertifikat läuft bald ab'),
  ca_expiring: t('Zwischenzertifikat läuft bald ab'),
  node_cert_expiring: t('Node-Zertifikat läuft bald ab'),
  custom_cert_expiring: t('Eigenes Zertifikat läuft bald ab'),
  passkey_added: t('Passkey hinzugefügt'),
  passkey_removed: t('Passkey entfernt'),
  ldap_synced: t('Abgleich mit LDAP'),
  ldap_sync_failed: t('Abgleich mit LDAP fehlgeschlagen')
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
  /** ältere Zwischenzertifikate, denen nach einem Wechsel noch vertraut wird */
  previous: {
    authority: AuthorityInfo;
    devices: { id: number; name: string; person: string }[];
    /** Nodes mit Zertifikat davon – erneuern es nach einem Wechsel selbst */
    nodes: { id: number; name: string }[];
  }[];
}

export interface Group {
  id: number;
  name: string;
  description: string;
  builtin: boolean;
  members: number;
  /** aus LDAP übernommen – Mitglieder pflegt der Abgleich */
  ldap: boolean;
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
  /** .p12 und Passwort hinterlegt – unter Geräte erneut abrufbar */
  p12_stored: boolean;
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
  email: string | null;
  /** aus LDAP übernommen */
  ldap: boolean;
  /** Zugriff auf Tesseract per Gerätezertifikat */
  ui_role: UiRole;
}

export interface IssuedDevice {
  device: Device;
  filename: string;
  password: string;
  p12_base64: string;
}

export const PLATFORMS: Record<string, string> = {
  ios: t('iPhone / iPad'),
  android: t('Android'),
  macos: t('Mac'),
  windows: t('Windows'),
  linux: t('Linux'),
  other: t('Sonstiges')
};

export const DEVICE_STATUS: Record<Device['status'], { label: string; tone: 'ok' | 'warn' | 'bad' }> = {
  active: { label: t('aktiv'), tone: 'ok' },
  expired: { label: t('abgelaufen'), tone: 'warn' },
  revoked: { label: t('gesperrt'), tone: 'bad' }
};

const dayFmt = new Intl.DateTimeFormat(locale, { day: '2-digit', month: '2-digit', year: 'numeric' });
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

// ---------- Phase 2: Einladungen ----------

export interface Enrollment {
  id: number;
  device_name: string;
  platform: string;
  user_agent: string;
  ip: string | null;
  status: 'pending' | 'approved' | 'rejected' | 'delivered';
  created_at: string;
  decided_at: string | null;
  decided_by: string | null;
  delivered_at: string | null;
}

export interface Invite {
  id: number;
  person_id: number;
  person_name: string;
  url: string;
  code: string;
  state: 'open' | 'expired' | 'revoked';
  created_by: string;
  created_at: string;
  expires_at: string;
  slots_left: number;
  enrollments: Enrollment[];
}

export interface PublicInvite {
  person_name: string;
  slots_left: number;
  max_devices: number;
  expires_at: string;
  services: string[];
}

export interface GuestCertificate {
  filename: string;
  password: string;
  p12_base64: string;
  not_after: string;
  services: string[];
  slots_left: number;
  renew_url: string | null;
}

export const ENROLLMENT_STATUS: Record<Enrollment['status'], { label: string; tone: 'ok' | 'warn' | 'bad' | 'neutral' }> = {
  pending: { label: t('wartet'), tone: 'warn' },
  approved: { label: t('freigegeben'), tone: 'ok' },
  delivered: { label: t('installiert'), tone: 'ok' },
  rejected: { label: t('abgelehnt'), tone: 'bad' }
};

// ---------- Phase 5: Logs ----------

export type LogReason = 'ok' | 'waf' | 'ip' | 'ban' | 'mtls' | 'internal' | 'websocket' | 'authelia';

export interface LogEntry {
  id: number;
  ts: string;
  node: string;
  host: string;
  method: string;
  uri: string;
  status: number;
  duration_ms: number;
  size: number;
  ip: string;
  country: string | null;
  device: string | null;
  person: string | null;
  reason: LogReason;
  waf_rules: number[];
  waf_msg: string | null;
  waf_score: number | null;
  user_agent: string | null;
}

export interface LogSource {
  node: string;
  kind: 'local' | 'agent';
  state: NodeState;
  last_entry_at: string | null;
}

export interface LogPage {
  entries: LogEntry[];
  sources: LogSource[];
  /** "local" (eigene Datenbank) oder "loki" / "victorialogs" */
  store: 'local' | 'loki' | 'victorialogs';
  geoip: boolean;
}

export interface LogDetail extends LogEntry {
  host_id: number | null;
  waf_mode: WafMode | null;
  waf_exclusions: number[];
  ip_requests: number;
  ip_denied: number;
  ip_banned: boolean;
}

export const LOG_REASONS: Record<LogReason, { label: string; tone: 'ok' | 'waf' | 'mtls' | 'ip' | 'bad' }> = {
  ok: { label: t('ok'), tone: 'ok' },
  waf: { label: 'WAF', tone: 'waf' },
  ip: { label: t('IP-Filter'), tone: 'ip' },
  ban: { label: t('IP gesperrt'), tone: 'ip' },
  internal: { label: t('nicht intern'), tone: 'ip' },
  mtls: { label: t('ohne Zertifikat'), tone: 'mtls' },
  websocket: { label: t('WebSocket gesperrt'), tone: 'bad' },
  authelia: { label: t('Authelia fehlt'), tone: 'bad' }
};

/** Land (ISO-Code) als Name auf Deutsch */
export function countryName(code: string | null): string {
  if (!code) return '';
  try {
    return new Intl.DisplayNames([locale], { type: 'region' }).of(code) ?? code;
  } catch {
    return code;
  }
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let v = n / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toLocaleString(locale, { maximumFractionDigits: v < 10 ? 1 : 0 })} ${units[i]}`;
}
