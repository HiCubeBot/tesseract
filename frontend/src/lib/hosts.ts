import { api, type Host, type HostInput, type HostSaved } from './api';
import { reportApply } from './nodes';
import { toasts } from './toast.svelte';

/** Tabs der Host-Seite */
export type HostTab = 'general' | 'access' | 'security' | 'history';

/** Host ein- oder ausschalten (sonst unverändert); gibt den gespeicherten Host zurück */
export async function setEnabled(h: Host, enabled: boolean): Promise<Host | null> {
  try {
    const r = await api.put<HostSaved>(`/hosts/${h.id}`, {
      ...toInput(h),
      enabled,
      comment: enabled ? 'Aktiviert' : 'Deaktiviert'
    });
    reportApply(r.apply, `${r.host.domain} (${enabled ? 'aktiviert' : 'deaktiviert'})`);
    return r.host;
  } catch (e) {
    toasts.show('bad', e instanceof Error ? e.message : String(e));
    return null;
  }
}

export function emptyHost(nodeId = 0): HostInput {
  return {
    domain: '',
    node_id: nodeId,
    upstream_scheme: 'http',
    upstream_host: '',
    upstream_port: 80,
    upstream_insecure: false,
    websockets: true,
    force_https: true,
    compression: false,
    access: 'public',
    no_cert_action: 'reject',
    waf_mode: null,
    waf_paranoia: null,
    waf_exclusions: [],
    ip_mode: 'off',
    ip_entries: [],
    ip_list_ids: [],
    authelia: false,
    tls_challenge: 'http',
    internal: false,
    custom_cert_id: null,
    areas: [],
    paths: [],
    grant_group_ids: [],
    grant_person_ids: [],
    enabled: true,
    draft: false
  };
}

export function toInput(h: Host): HostInput {
  return {
    domain: h.domain,
    node_id: h.node.id,
    upstream_scheme: h.upstream_scheme,
    upstream_host: h.upstream_host,
    upstream_port: h.upstream_port,
    upstream_insecure: h.upstream_insecure,
    websockets: h.websockets,
    force_https: h.force_https,
    compression: h.compression,
    access: h.access,
    no_cert_action: h.no_cert_action,
    waf_mode: h.waf_mode,
    waf_paranoia: h.waf_paranoia,
    waf_exclusions: [...h.waf_exclusions],
    ip_mode: h.ip_mode,
    ip_entries: [...h.ip_entries],
    ip_list_ids: [...h.ip_list_ids],
    authelia: h.authelia,
    tls_challenge: h.tls_challenge,
    internal: h.internal,
    custom_cert_id: h.custom_cert_id,
    areas: h.areas.map(({ id: _id, ...a }) => structuredClone(a)),
    paths: [...h.paths],
    grant_group_ids: h.grants.filter((g) => g.kind === 'group').map((g) => g.id),
    grant_person_ids: h.grants.filter((g) => g.kind === 'person').map((g) => g.id),
    enabled: h.enabled,
    draft: h.draft
  };
}

export function upstreamLabel(h: Pick<Host, 'upstream_scheme' | 'upstream_host' | 'upstream_port'>) {
  const host = h.upstream_host.includes(':') ? `[${h.upstream_host}]` : h.upstream_host;
  return `${h.upstream_scheme}://${host}:${h.upstream_port}`;
}

export function hostStatus(h: Host): { tone: 'ok' | 'warn' | 'neutral'; label: string } {
  if (h.draft) return { tone: 'warn', label: 'Entwurf' };
  if (!h.enabled) return { tone: 'neutral', label: 'deaktiviert' };
  return { tone: 'ok', label: 'aktiv' };
}

/** Schutz-Kurzfassung für Listen, z. B. „WAF“ oder „WAF (Log)“ */
export function protectionLabel(h: Host): string {
  const parts: string[] = [];
  if (h.internal) parts.push('Intern');
  if (h.ip_mode !== 'off') parts.push('IP');
  if (h.waf_mode === 'block') parts.push('WAF');
  if (h.waf_mode === 'detect') parts.push('WAF (Log)');
  if (h.authelia) parts.push('Authelia');
  return parts.join(' · ') || '–';
}

/** Kurzbeschreibung des Zugriffs für Listen */
export function accessLabel(h: Host): string {
  if (h.access === 'mtls') {
    const base = `${h.granted_persons} Personen · ${h.allowed_devices} Geräte`;
    return h.paths.length ? `${base} · ${h.paths.length} Pfad(e) öffentlich` : base;
  }
  return h.paths.length ? `${h.paths.length} Pfad(e) nur mit Zertifikat` : 'Öffentlich';
}
