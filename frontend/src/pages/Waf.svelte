<script lang="ts">
  // WAF-Regeln (OWASP CRS) nachschlagen, Treffer sehen und Ausnahmen zentral pflegen.
  // Links: #/waf?rule=942100 öffnet eine Regel, #/waf?tab=exceptions&new=1&host_id=…&rule=…
  // &target=…&path=… das Formular für eine (gezielte) Ausnahme, z. B. aus einem Log-Eintrag.
  import { locale, t, tApi } from '../lib/i18n';
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import Button from '../lib/components/Button.svelte';
  import SegmentedControl from '../lib/components/SegmentedControl.svelte';
  import StatusPill from '../lib/components/StatusPill.svelte';
  import {
    api,
    formatDate,
    wafRuleHref,
    type Host,
    type WafCatalog,
    type WafException,
    type WafRule,
    type WafRuleDetail
  } from '../lib/api';
  import { toasts } from '../lib/toast.svelte';

  const params = () => new URLSearchParams(location.hash.split('?')[1] ?? '');
  const TARGET_EXAMPLE = ['ARGS:content', 'REQUEST_HEADERS:User-Agent', 'REQUEST_COOKIES:sid'].join(' · ');

  let catalog = $state<WafCatalog | null>(null);
  let exceptions = $state<WafException[]>([]);
  let hosts = $state<Host[]>([]);
  let error = $state('');
  let tab = $state(params().get('tab') === 'exceptions' ? 1 : 0);

  // Filter der Regelliste
  let query = $state('');
  let category = $state('');
  let paranoia = $state(0);
  let onlyHits = $state(false);

  let detail = $state<WafRuleDetail | null>(null);

  async function load() {
    try {
      [catalog, exceptions, hosts] = await Promise.all([
        api.get<WafCatalog>('/waf/rules'),
        api.get<WafException[]>('/waf/exceptions'),
        api.get<Host[]>('/hosts')
      ]);
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }

  async function openRule(id: number) {
    try {
      detail = await api.get<WafRuleDetail>(`/waf/rules/${id}`);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e));
    }
  }

  function fromHash() {
    const p = params();
    const rule = Number(p.get('rule'));
    if (rule) {
      tab = 0;
      openRule(rule);
    }
    if (p.get('tab') === 'exceptions') tab = 1;
    if (p.get('new')) {
      tab = 1;
      startNew({
        host_id: Number(p.get('host_id')) || 0,
        rule_id: Number(p.get('rule_id') ?? p.get('rule')) || 0,
        target: p.get('target') ?? '',
        path: p.get('path') ?? ''
      });
    }
  }

  load().then(fromHash);
  $effect(() => {
    const onHash = () => fromHash();
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  });

  const categories = $derived([...new Set((catalog?.rules ?? []).map((r) => r.category))].sort());
  const shown = $derived(
    (catalog?.rules ?? []).filter((r) => {
      const q = query.trim().toLowerCase();
      if (q && !String(r.id).includes(q) && !r.msg.toLowerCase().includes(q) && !r.tags.some((x) => x.includes(q))) return false;
      if (category && r.category !== category) return false;
      if (paranoia && r.paranoia !== paranoia) return false;
      if (onlyHits && !r.hits['30d']) return false;
      return true;
    })
  );
  const fmt = (n: number) => n.toLocaleString(locale);

  // ---------- Ausnahmen ----------

  interface Form {
    id: number | null;
    host_id: number;
    rule_id: number;
    target: string;
    path: string;
    comment: string;
    expires: string;
  }
  let form = $state<Form | null>(null);
  let saving = $state(false);

  function startNew(init: Partial<Form> = {}) {
    form = { id: null, host_id: 0, rule_id: 0, target: '', path: '', comment: '', expires: '', ...init };
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function startEdit(x: WafException) {
    form = {
      id: x.id,
      host_id: x.host_id,
      rule_id: x.rule_id,
      target: x.target,
      path: x.path,
      comment: x.comment,
      expires: x.expires_at ? x.expires_at.slice(0, 10) : ''
    };
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // Ablauf: Ende des gewählten Tages (lokale Zeit)
  const expiresIso = (d: string) => (d ? new Date(`${d}T23:59:59`).toISOString() : null);

  async function save(e: SubmitEvent) {
    e.preventDefault();
    if (!form) return;
    saving = true;
    try {
      if (form.id !== null) {
        await api.put(`/waf/exceptions/${form.id}`, { comment: form.comment, expires_at: expiresIso(form.expires) });
        toasts.show('ok', t('Ausnahme gespeichert.'));
      } else {
        const r = await api.post<{ exception: WafException; error: string | null }>('/waf/exceptions', {
          host_id: Number(form.host_id),
          rule_id: Number(form.rule_id),
          target: form.target,
          path: form.path,
          comment: form.comment,
          expires_at: expiresIso(form.expires)
        });
        if (r.error) toasts.show('warn', t('Gespeichert, aber nicht übertragen: {0}', r.error), 10000);
        else toasts.show('ok', t('Ausnahme angelegt und übertragen.'));
      }
      form = null;
      await load();
      if (detail) await openRule(detail.rule.id);
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err), 10000);
    } finally {
      saving = false;
    }
  }

  async function remove(x: WafException) {
    if (!confirm(t('Ausnahme für Regel {0} auf {1} entfernen? Die Regel greift dort danach wieder.', x.rule_id, x.host))) return;
    try {
      const r = await api.del<{ ok: boolean; error: string | null }>(
        x.id !== null ? `/waf/exceptions/${x.id}` : `/waf/hosts/${x.host_id}/exclusions/${x.rule_id}`
      );
      if (r.error) toasts.show('warn', t('Entfernt, aber nicht übertragen: {0}', r.error), 10000);
      else toasts.show('ok', t('Ausnahme entfernt.'));
      await load();
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err));
    }
  }

  function scope(x: WafException): string {
    if (x.area) return t('Bereich {0} · ganze Regel', x.area);
    if (x.target && x.path) return t('{0} unter {1}', x.target, x.path);
    if (x.target) return x.target;
    if (x.path) return t('ganze Regel unter {0}', x.path);
    return t('ganze Regel');
  }
  const formRule = $derived(form && catalog ? catalog.rules.find((r) => r.id === Number(form?.rule_id)) : undefined);
</script>

<AppShell active="waf">
  <PageHeader
    title={t('WAF-Regeln')}
    subtitle={catalog ? t('OWASP Core Rule Set {0} – Regeln nachschlagen, Treffer sehen, Ausnahmen pflegen.', catalog.crs) : ''}
    primaryLabel={t('Ausnahme anlegen')}
    onPrimary={() => startNew()}
  />

  {#if error}<Alert tone="bad" title={t('Fehler')} text={error} />{/if}

  {#if form}
    <form class="card form" onsubmit={save} aria-labelledby="form-title">
      <h2 id="form-title">{form.id !== null ? t('Ausnahme bearbeiten') : t('Neue Ausnahme')}</h2>
      <div class="grid3">
        <label class="field">
          {t('Host')}
          <select class="input" bind:value={form.host_id} disabled={form.id !== null} required>
            <option value={0} disabled>{t('Host wählen …')}</option>
            {#each hosts as h (h.id)}<option value={h.id}>{h.domain}</option>{/each}
          </select>
        </label>
        <label class="field">
          {t('Regel-ID')}
          <input class="input mono" type="number" min="1" bind:value={form.rule_id} disabled={form.id !== null} required />
          {#if formRule}<span class="muted small">{tApi(formRule.category)} · {formRule.msg}</span>{/if}
        </label>
        <label class="field">
          {t('Ablauf (optional)')}
          <input class="input" type="date" bind:value={form.expires} />
          <span class="muted small">{t('Danach greift die Regel wieder – mit Eintrag im Audit-Log.')}</span>
        </label>
        <label class="field">
          {t('Nur dieses Feld (optional)')}
          <input class="input mono" bind:value={form.target} disabled={form.id !== null} placeholder={TARGET_EXAMPLE} />
        </label>
        <label class="field">
          {t('Nur unter diesem Pfad (optional)')}
          <input class="input mono" bind:value={form.path} disabled={form.id !== null} placeholder="/api/upload" />
        </label>
        <label class="field">
          {t('Kommentar')}
          <input class="input" maxlength="255" bind:value={form.comment} placeholder={t('z. B. Fehlalarm im Wiki-Editor')} />
        </label>
      </div>
      <p class="muted small">
        {t('Ohne Feld und Pfad wird die Regel auf dem Host ganz abgeschaltet. Besser gezielt: nur das Feld (z. B. ARGS:content) und/oder nur den Pfad, an dem der Fehlalarm auftritt – überall sonst schützt die Regel weiter.')}
      </p>
      <div class="row">
        <Button type="submit" label={saving ? t('Speichert …') : t('Speichern & übertragen')} disabled={saving} />
        <Button variant="secondary" label={t('Abbrechen')} onClick={() => (form = null)} />
      </div>
    </form>
  {/if}

  {#if detail}
    {@const r = detail.rule}
    <section class="card" aria-labelledby="rule-title">
      <div class="head">
        <h2 id="rule-title"><span class="mono">{r.id}</span> · {r.msg || t('Regel nicht im Katalog')}</h2>
        <Button variant="ghost" size="sm" label={t('Schließen')} onClick={() => (detail = null)} />
      </div>
      <dl class="meta">
        <dt>{t('Kategorie')}</dt><dd>{tApi(r.category)}</dd>
        {#if r.paranoia}<dt>{t('Paranoia-Level')}</dt><dd>{r.paranoia}</dd>{/if}
        {#if r.severity}<dt>{t('Schweregrad')}</dt><dd>{r.severity}</dd>{/if}
        {#if r.file}<dt>{t('Datei')}</dt><dd class="mono small">{r.file}</dd>{/if}
        {#if r.tags.length}<dt>{t('Tags')}</dt><dd class="small">{r.tags.join(', ')}</dd>{/if}
        <dt>{t('Treffer')}</dt>
        <dd>
          {t('{0} in 24 h · {1} in 7 Tagen · {2} in 30 Tagen', fmt(detail.hits['24h']), fmt(detail.hits['7d']), fmt(detail.hits['30d']))}
          {#if detail.last_hit} · {t('zuletzt {0}', formatDate(detail.last_hit))}{/if}
        </dd>
      </dl>
      <div class="cols">
        <div>
          <h3>{t('Hosts')}</h3>
          {#each detail.hosts as h (h.host)}
            <p class="small"><a href={`#/logs?q=${encodeURIComponent(`rule:${r.id} host:${h.host}`)}`} class="mono">{h.host}</a> · {fmt(h.count)}</p>
          {:else}<p class="muted small">{t('Keine Treffer in 30 Tagen.')}</p>{/each}
        </div>
        <div>
          <h3>{t('Pfade')}</h3>
          {#each detail.paths as p (p.host + p.path)}
            <p class="small"><span class="mono">{p.host}{p.path}</span> · {fmt(p.count)}</p>
          {:else}<p class="muted small">–</p>{/each}
        </div>
        <div>
          <h3>{t('Betroffene Felder')}</h3>
          {#each detail.targets as x (x.target)}
            <p class="small"><span class="mono">{x.target}</span> · {fmt(x.count)}</p>
          {:else}<p class="muted small">–</p>{/each}
        </div>
      </div>
      <h3>{t('Ausnahmen')}</h3>
      {#each detail.exceptions as x (`${x.id}-${x.host_id}-${x.area}-${x.target}-${x.path}`)}
        <p class="small"><span class="mono">{x.host}</span> · {scope(x)}{#if x.comment} · {x.comment}{/if}</p>
      {:else}<p class="muted small">{t('Keine.')}</p>{/each}
      <div class="row">
        <Button
          variant="secondary"
          size="sm"
          label={t('Ausnahme für diese Regel anlegen')}
          onClick={() => startNew({ rule_id: r.id, target: detail?.targets[0]?.target ?? '' })}
        />
      </div>
    </section>
  {/if}

  <SegmentedControl groupLabel={t('Ansicht')} options={[t('Regeln'), t('Ausnahmen · {0}', exceptions.length)]} bind:selected={tab} />

  {#if tab === 0}
    <div class="row filters">
      <input class="input" type="search" bind:value={query} placeholder={t('ID, Meldung oder Tag')} aria-label={t('Regeln durchsuchen')} />
      <select class="input" bind:value={category} aria-label={t('Kategorie')}>
        <option value="">{t('Alle Kategorien')}</option>
        {#each categories as c (c)}<option value={c}>{tApi(c)}</option>{/each}
      </select>
      <select class="input" bind:value={paranoia} aria-label={t('Paranoia-Level')}>
        <option value={0}>{t('Alle Level')}</option>
        {#each [1, 2, 3, 4] as l (l)}<option value={l}>{t('Paranoia-Level {0}', l)}</option>{/each}
      </select>
      <label class="check"><input type="checkbox" bind:checked={onlyHits} />{t('nur mit Treffern (30 Tage)')}</label>
    </div>
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th scope="col">{t('ID')}</th>
            <th scope="col">{t('Kategorie')}</th>
            <th scope="col">{t('Meldung')}</th>
            <th scope="col" class="num">{t('PL')}</th>
            <th scope="col" class="num">24 h</th>
            <th scope="col" class="num">{t('7 Tage')}</th>
            <th scope="col" class="num">{t('30 Tage')}</th>
            <th scope="col" class="num">{t('Ausnahmen')}</th>
          </tr>
        </thead>
        <tbody>
          {#each shown as r (r.id)}
            <tr>
              <td><a class="mono" href={wafRuleHref(r.id)} onclick={(e) => { e.preventDefault(); openRule(r.id); }}>{r.id}</a></td>
              <td class="small nowrap">{tApi(r.category)}</td>
              <td class="small">{r.msg || '–'}</td>
              <td class="num">{r.paranoia ?? '–'}</td>
              <td class="num">{r.hits['24h'] ? fmt(r.hits['24h']) : ''}</td>
              <td class="num">{r.hits['7d'] ? fmt(r.hits['7d']) : ''}</td>
              <td class="num">{r.hits['30d'] ? fmt(r.hits['30d']) : ''}</td>
              <td class="num">{r.exceptions || ''}</td>
            </tr>
          {:else}
            <tr><td colspan="8" class="muted">{t('Keine Treffer.')}</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
    {#if catalog}<p class="muted small">{t('Katalog aus coraza-caddy {0} (OWASP CRS {1}) – passend zum Caddy-Image.', catalog.coraza_caddy, catalog.crs)}</p>{/if}
  {:else}
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th scope="col">{t('Host')}</th>
            <th scope="col">{t('Regel')}</th>
            <th scope="col">{t('Umfang')}</th>
            <th scope="col">{t('Kommentar')}</th>
            <th scope="col">{t('Angelegt')}</th>
            <th scope="col">{t('Ablauf')}</th>
            <th scope="col" class="num">{t('Treffer seit Anlage')}</th>
            <th scope="col"><span class="visually-hidden">{t('Aktionen')}</span></th>
          </tr>
        </thead>
        <tbody>
          {#each exceptions as x (`${x.id}-${x.host_id}-${x.area}-${x.rule_id}-${x.target}-${x.path}`)}
            <tr>
              <td class="mono small">{x.host}</td>
              <td><a class="mono" href={wafRuleHref(x.rule_id)}>{x.rule_id}</a></td>
              <td class="small">{scope(x)}</td>
              <td class="small">{x.comment || '–'}</td>
              <td class="small nowrap">{x.created_at ? `${formatDate(x.created_at)} · ${x.created_by}` : t('direkt am Host')}</td>
              <td class="small nowrap">
                {#if x.expires_at}<StatusPill tone="warn" label={formatDate(x.expires_at)} />{:else}–{/if}
              </td>
              <td class="num" title={x.hits_since === null ? t('Ganze Regel aus – Coraza protokolliert sie auf dem Host nicht mehr') : ''}>
                {x.hits_since === null ? '–' : fmt(x.hits_since)}
              </td>
              <td class="right nowrap">
                {#if x.area}
                  <a class="small" href={`#/hosts/${x.host_id}/security`}>{t('am Host')}</a>
                {:else if x.id !== null}
                  <Button variant="ghost" size="sm" label={t('Bearbeiten')} onClick={() => startEdit(x)} />
                  <Button variant="ghost" size="sm" label={t('Entfernen')} onClick={() => remove(x)} />
                {:else}
                  <Button variant="ghost" size="sm" label={t('Kommentar ergänzen')} onClick={() => startNew({ host_id: x.host_id, rule_id: x.rule_id })} />
                  <Button variant="ghost" size="sm" label={t('Entfernen')} onClick={() => remove(x)} />
                {/if}
              </td>
            </tr>
          {:else}
            <tr><td colspan="8" class="muted">{t('Noch keine Ausnahmen.')}</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
    <p class="muted small">
      {t('Bei ganzen Ausnahmen protokolliert Coraza die Regel auf dem Host nicht mehr – Treffer seit Anlage gibt es nur bei gezielten. Ausnahmen in Bereichen pflegst du am Host unter Sicherheit.')}
    </p>
  {/if}
</AppShell>

<style>
  h2 {
    margin: 0;
    font-size: 16px;
  }
  h3 {
    margin: 12px 0 4px;
    font-size: 13px;
  }
  .small {
    font-size: 12px;
    margin: 0;
    line-height: 1.5;
  }
  .form {
    display: grid;
    gap: 12px;
  }
  .grid3 {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 12px;
  }
  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }
  .meta {
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: 6px 16px;
    margin: 12px 0 0;
  }
  .meta dt {
    color: var(--text-muted);
  }
  .meta dd {
    margin: 0;
  }
  .cols {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 12px;
  }
  .filters {
    flex-wrap: wrap;
  }
  .filters .input {
    width: auto;
    min-width: 180px;
  }
  .num {
    text-align: right;
  }
  .right {
    text-align: right;
  }
  .nowrap {
    white-space: nowrap;
  }
</style>
