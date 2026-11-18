import type { Host, HostInput } from './api';

export function emptyHost(nodeId = 0): HostInput {
  return {
    domain: '',
    node_id: nodeId,
    upstream_scheme: 'http',
    upstream_host: '',
    upstream_port: 80,
    websockets: true,
    force_https: true,
    compression: false,
    access: 'public',
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
    websockets: h.websockets,
    force_https: h.force_https,
    compression: h.compression,
    access: h.access,
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
