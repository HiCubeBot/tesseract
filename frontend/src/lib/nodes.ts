import { api, type NodeInfo } from './api';
import { toasts } from './toast.svelte';

/** Config eines Nodes erneut übertragen und das Ergebnis melden. */
export async function applyNode(node: NodeInfo): Promise<boolean> {
  const r = await api.post<{ ok: boolean; error: string | null }>(`/nodes/${node.id}/apply`);
  if (r.ok) toasts.show('ok', `Config an ${node.name} übertragen.`);
  else toasts.show('bad', `Übertragen an ${node.name} fehlgeschlagen: ${r.error}`, 10000);
  return r.ok;
}

/** Meldung nach „Speichern & übertragen“. */
export function reportApply(apply: { ok: boolean; error: string | null; skipped: boolean }, what: string) {
  if (apply.skipped) toasts.show('info', `${what} gespeichert.`);
  else if (apply.ok) toasts.show('ok', `${what} gespeichert und übertragen.`);
  else
    toasts.show(
      'warn',
      `${what} gespeichert, aber nicht übertragen: ${apply.error}. Unter Übersicht erneut übertragen.`,
      12000
    );
}
