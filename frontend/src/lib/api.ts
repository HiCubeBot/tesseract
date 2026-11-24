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
  /** Passwort kommt aus TESSERACT_ADMIN_PASSWORD (.env) */
  password_from_env?: boolean;
  /** "local" oder "oidc" (SSO, ohne Passwort) */
  source?: 'local' | 'oidc';
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
  off: 'Aus',
  block: 'Sperren',
  allow: 'Nur erlauben'
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

export const WAF_MODES: Record<WafMode, string> = {
  off: 'Aus',
  detect: 'Nur protokollieren',
  block: 'Blockieren'
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
> & {
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
  'http.handlers.waf': 'Coraza WAF',
  'dns.providers.cloudflare': 'DNS · Cloudflare'
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
  /** öffentliche Statusseite /status – standardmäßig aus */
  status_page_enabled: boolean;
  status_page_url: string;
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

/** Kurz für schmale Spalten: wie formatAgo, ältere Einträge „19.11. 22:52“ (Jahr nur, wenn anders) */
export function formatAgoShort(iso: string | null): string {
  if (!iso) return 'nie';
  const d = new Date(iso);
  if (Date.now() - d.getTime() < 86_400_000) return formatAgo(iso);
  const day = d.toLocaleDateString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    ...(d.getFullYear() !== new Date().getFullYear() ? { year: '2-digit' } : {})
  });
  const time = d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  return `${day} ${time}`;
}

export const FIELD_LABELS: Record<string, string> = {
  domain: 'Domain',
  node: 'Node',
  upstream_scheme: 'Protokoll',
  upstream_host: 'Ziel-Adresse',
  upstream_port: 'Port',
  upstream_insecure: 'Zertifikat des Ziels nicht prüfen',
  websockets: 'WebSockets',
  force_https: 'HTTP → HTTPS',
  compression: 'Kompression',
  access: 'Zugriff',
  no_cert_action: 'Ohne Zertifikat',
  paths: 'Pfade',
  grants: 'Freigegeben für',
  waf_mode: 'WAF',
  waf_paranoia: 'Paranoia-Level',
  waf_exclusions: 'Regel-Ausnahmen',
  ip_mode: 'IP-Filter',
  ip_entries: 'IPs/Netze',
  ip_lists: 'IP-Listen',
  authelia: 'Login über Authelia',
  tls_challenge: 'Zertifikats-Prüfung',
  internal: 'Nur intern',
  internal_no_cert: 'Intern ohne Zertifikat',
  allow_controller: 'Tesseract darf zugreifen',
  monitor: 'Überwachung',
  status_public: 'Statusseite',
  status_name: 'Name auf der Statusseite',
  custom_cert: 'Eigenes Zertifikat',
  areas: 'Bereiche',
  enabled: 'Aktiv',
  draft: 'Entwurf'
};

export function formatValue(v: unknown): string {
  if (Array.isArray(v)) return v.length ? v.map(formatValue).join(', ') : '–';
  if (v && typeof v === 'object' && 'paths' in v) {
    const a = v as { name?: string; paths: string[] };
    return `${a.name ? a.name + ' ' : ''}(${a.paths.join(', ')})`;
  }
  if (v === 'reject') return 'Verbindung ablehnen';
  if (v === 'http') return 'HTTP-01';
  if (v === 'dns') return 'DNS-01 (Cloudflare)';
  if (v === 'off') return 'Aus';
  if (v === 'detect') return 'Nur protokollieren';
  if (v === 'block') return 'Blockieren/Sperren';
  if (v === 'allow') return 'Nur erlauben';
  if (v === 'hint') return 'Hinweisseite';
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
  device_revoked: 'Gerät gesperrt',
  device_deleted: 'Gerät gelöscht',
  access_changed: 'Zugriff geändert',
  invite_created: 'Einladung erstellt',
  invite_revoked: 'Einladung widerrufen',
  enrollment_requested: 'Gerät möchte sich registrieren',
  enrollment_approved: 'Gerät freigegeben',
  enrollment_rejected: 'Gerät abgelehnt',
  enrollment_code_wrong: 'Falscher Einladungscode',
  admin_mtls_on: 'Oberfläche nur noch mit Admin-Zertifikat',
  admin_mtls_off: 'Admin-Zertifikat für Oberfläche abgeschaltet',
  iplist_created: 'IP-Liste angelegt',
  iplist_updated: 'IP-Liste geändert',
  iplist_deleted: 'IP-Liste gelöscht',
  ip_banned: 'IP gesperrt',
  ip_unbanned: 'IP entsperrt',
  node_created: 'Node angelegt',
  node_updated: 'Node geändert',
  node_deleted: 'Node gelöscht',
  node_token_created: 'Beitritts-Token erzeugt',
  node_join_requested: 'Agent möchte beitreten',
  node_approved: 'Node bestätigt',
  node_rejected: 'Beitritt abgelehnt',
  node_joined: 'Agent verbunden',
  node_drift_detected: 'Abweichung auf Node erkannt',
  node_drift_overwritten: 'Abweichung überschrieben',
  node_drift_accepted: 'Abweichung übernommen',
  node_offline: 'Node offline',
  host_down: 'Dienst nicht erreichbar',
  host_up: 'Dienst wieder erreichbar',
  node_online: 'Node wieder online',
  backup_created: 'Sicherung erstellt',
  backup_failed: 'Sicherung fehlgeschlagen',
  git_mirrored: 'Git-Spiegel aktualisiert',
  backup_tested: 'Sicherung getestet',
  backup_downloaded: 'Sicherung heruntergeladen',
  backup_restored: 'Sicherung wiederhergestellt',
  ca_rotated: 'Zwischenzertifikat gewechselt',
  device_renewed: 'Gerät verlängert',
  node_cert_renewed: 'Node-Zertifikat erneuert',
  device_expiring: 'Gerätezertifikat läuft bald ab',
  ca_expiring: 'Zwischenzertifikat läuft bald ab',
  node_cert_expiring: 'Node-Zertifikat läuft bald ab',
  custom_cert_expiring: 'Eigenes Zertifikat läuft bald ab',
  passkey_added: 'Passkey hinzugefügt',
  passkey_removed: 'Passkey entfernt',
  ldap_synced: 'Abgleich mit LDAP',
  ldap_sync_failed: 'Abgleich mit LDAP fehlgeschlagen'
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
  pending: { label: 'wartet', tone: 'warn' },
  approved: { label: 'freigegeben', tone: 'ok' },
  delivered: { label: 'installiert', tone: 'ok' },
  rejected: { label: 'abgelehnt', tone: 'bad' }
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
  ok: { label: 'ok', tone: 'ok' },
  waf: { label: 'WAF', tone: 'waf' },
  ip: { label: 'IP-Filter', tone: 'ip' },
  ban: { label: 'IP gesperrt', tone: 'ip' },
  internal: { label: 'nicht intern', tone: 'ip' },
  mtls: { label: 'ohne Zertifikat', tone: 'mtls' },
  websocket: { label: 'WebSocket gesperrt', tone: 'bad' },
  authelia: { label: 'Authelia fehlt', tone: 'bad' }
};

/** Land (ISO-Code) als Name auf Deutsch */
export function countryName(code: string | null): string {
  if (!code) return '';
  try {
    return new Intl.DisplayNames(['de'], { type: 'region' }).of(code) ?? code;
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
  return `${v.toLocaleString('de-DE', { maximumFractionDigits: v < 10 ? 1 : 0 })} ${units[i]}`;
}
