import { api, type NodeInfo } from './api';
import { toasts } from './toast.svelte';
import { t } from './i18n';

/** Config eines Nodes erneut übertragen und das Ergebnis melden. */
export async function applyNode(node: NodeInfo): Promise<boolean> {
  const r = await api.post<{ ok: boolean; error: string | null }>(`/nodes/${node.id}/apply`);
  if (r.ok) toasts.show('ok', t('Config an {0} übertragen.', node.name));
  else toasts.show('bad', t('Übertragen an {0} fehlgeschlagen: {1}', node.name, r.error), 10000);
  return r.ok;
}

/** Meldung nach „Speichern & übertragen“. */
export function reportApply(
  apply: { ok: boolean; error: string | null; skipped: boolean },
  what: string,
  dns?: { ok: boolean; error: string | null; skipped: boolean }
) {
  if (dns && !dns.ok) toasts.show('warn', t('DNS-Eintrag für {0}: {1}', what, dns.error), 15000);
  if (apply.skipped) toasts.show('info', `${what} gespeichert.`);
  else if (apply.ok) toasts.show('ok', t('{0} gespeichert und übertragen.', what));
  else
    toasts.show(
      'warn',
      t('{0} gespeichert, aber nicht übertragen: {1}. Unter Übersicht erneut übertragen.', what, apply.error),
      12000
    );
}
