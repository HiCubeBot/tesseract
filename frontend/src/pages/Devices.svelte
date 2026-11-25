<script lang="ts">
  import { t } from '../lib/i18n';
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import SegmentedControl from '../lib/components/SegmentedControl.svelte';
  import StatusPill from '../lib/components/StatusPill.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import ConfirmDialog from '../lib/components/ConfirmDialog.svelte';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import Icon from '../lib/components/Icon.svelte';
  import IssuedCertificate from '../lib/components/IssuedCertificate.svelte';
  import { api, DEVICE_STATUS, PLATFORMS, expiresSoon, formatDay, type Device, type IssuedDevice } from '../lib/api';
  import { toasts } from '../lib/toast.svelte';

  let devices = $state<Device[]>([]);
  let loaded = $state(false);
  let error = $state('');
  let filter = $state(0);
  let person = $state('');
  let query = $state('');
  let revoke = $state<Device | null>(null);
  let renewing = $state<number | null>(null);
  let renewed = $state<IssuedDevice | null>(null);
  // hinterlegtes Zertifikat erneut abrufen
  let shown = $state<IssuedDevice | null>(null);

  async function showCert(d: Device) {
    try {
      const c = await api.get<{ filename: string; password: string; p12_base64: string }>(`/devices/${d.id}/certificate`);
      renewed = null;
      shown = { device: d, ...c };
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    }
  }

  async function forget() {
    const d = shown?.device;
    if (!d || !confirm(t('Hinterlegte Kopie von „{0}“ löschen? Das Zertifikat bleibt gültig, lässt sich aber nicht mehr abrufen.', d.name))) return;
    try {
      await api.del(`/devices/${d.id}/certificate`);
      shown = null;
      toasts.show('ok', t('Hinterlegte Kopie gelöscht.'));
      await load();
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e));
    }
  }

  /** Neues Zertifikat für dasselbe Gerät – Freigaben bleiben, das alte gilt nicht mehr */
  async function renew(d: Device) {
    renewing = d.id;
    try {
      renewed = await api.post<IssuedDevice>(`/devices/${d.id}/renew`, { days: d.unlimited ? null : 365 });
      await load();
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    } finally {
      renewing = null;
    }
  }

  async function load() {
    try {
      devices = await api.get<Device[]>('/devices');
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loaded = true;
    }
  }
  load();

  const persons = $derived([...new Set(devices.map((d) => d.person_name))].sort());
  const counts = $derived({
    all: devices.length,
    active: devices.filter((d) => d.status === 'active').length,
    soon: devices.filter(expiresSoon).length,
    revoked: devices.filter((d) => d.status === 'revoked').length
  });

  const visible = $derived(
    devices.filter((d) => {
      if (filter === 1 && d.status !== 'active') return false;
      if (filter === 2 && !expiresSoon(d)) return false;
      if (filter === 3 && d.status !== 'revoked') return false;
      if (person && d.person_name !== person) return false;
      const q = query.trim().toLowerCase();
      return (
        !q ||
        d.name.toLowerCase().includes(q) ||
        d.person_name.toLowerCase().includes(q) ||
        d.fingerprint.toLowerCase().replaceAll(':', '').includes(q.replaceAll(':', ''))
      );
    })
  );

  async function doRevoke() {
    if (!revoke) return;
    try {
      await api.post(`/devices/${revoke.id}/revoke`, { reason: t('vom Admin gesperrt') });
      toasts.show('ok', t('„{0}“ gesperrt.', revoke.name));
      revoke = null;
      await load();
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e));
    }
  }

  async function remove(d: Device) {
    if (!confirm(t('„{0}“ von {1} endgültig löschen?', d.name, d.person_name))) return;
    try {
      await api.del(`/devices/${d.id}`);
      toasts.show('ok', t('„{0}“ gelöscht.', d.name));
      await load();
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e));
    }
  }

  const shortFp = (fp: string) => fp.slice(0, 11) + ' … ' + fp.slice(-5);
</script>

<AppShell active="devices">
  <PageHeader
    title={t('Geräte')}
    subtitle={t('Ein Gerät = ein Client-Zertifikat. Es gehört immer zu genau einer Person.')}
    secondaryLabel={t('Gesperrte exportieren (CSV)')}
    secondaryHref="/api/devices/revoked.csv"
  />

  {#if error}<Alert tone="bad" title={t('Fehler')} text={error} />{/if}

  <div class="row">
    <SegmentedControl
      groupLabel={t('Gerätestatus')}
      options={[t('Alle · {0}', counts.all), t('Aktiv · {0}', counts.active), t('Läuft bald ab · {0}', counts.soon), t('Gesperrt · {0}', counts.revoked)]}
      bind:selected={filter}
    />
    <label class="search">
      <Icon name="search" size={16} strokeWidth={2} />
      <span class="visually-hidden">{t('Geräte durchsuchen')}</span>
      <input type="search" placeholder={t('Gerät, Person oder Fingerabdruck')} bind:value={query} />
    </label>
    <label class="field inline">
      {t('Person')}
      <select class="input" bind:value={person}>
        <option value="">{t('Alle Personen')}</option>
        {#each persons as p (p)}<option value={p}>{p}</option>{/each}
      </select>
    </label>
  </div>

  {#if renewed}<IssuedCertificate issued={renewed} onClose={() => (renewed = null)} />{/if}
  {#if shown}<IssuedCertificate issued={shown} again onClose={() => (shown = null)} onForget={forget} />{/if}

  {#if revoke}
    <ConfirmDialog
      title={t('„{0}“ von {1} sperren?', revoke.name, revoke.person_name)}
      text={t('Das Zertifikat wird sofort aus allen Freigaben entfernt. Das lässt sich nicht rückgängig machen.')}
      word="sperren"
      confirmLabel={t('Gerät sperren')}
      onConfirm={doRevoke}
      onCancel={() => (revoke = null)}
    />
  {/if}

  {#if loaded && devices.length === 0}
    <EmptyState icon="devices" title={t('Noch keine Geräte')} text={t('Geräte bekommen Personen per Einladung oder direkt unter Nutzer.')} actionLabel={t('Zu den Nutzern')} actionHref="#/users" />
  {:else}
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th scope="col">{t('Gerät')}</th>
            <th scope="col">{t('Person')}</th>
            <th scope="col">{t('Fingerabdruck')}</th>
            <th scope="col">{t('Gültig bis')}</th>
            <th scope="col">{t('Status')}</th>
            <th scope="col"><span class="visually-hidden">{t('Aktionen')}</span></th>
          </tr>
        </thead>
        <tbody>
          {#each visible as d (d.id)}
            {@const st = DEVICE_STATUS[d.status]}
            <tr>
              <td>
                <span class="strong">{d.name}</span>
                <span class="muted small block">{PLATFORMS[d.platform] ?? d.platform}</span>
              </td>
              <td><a href={`#/users/${d.person_id}`}>{d.person_name}</a></td>
              <td class="mono small muted" title={d.fingerprint}>{shortFp(d.fingerprint)}</td>
              <td class="nowrap">{d.unlimited ? 'unbegrenzt' : formatDay(d.not_after)}</td>
              <td>
                {#if expiresSoon(d)}<StatusPill tone="warn" label={t('läuft bald ab')} />{:else}<StatusPill tone={st.tone} label={st.label} />{/if}
              </td>
              <td class="right">
                {#if d.p12_stored && d.status !== 'revoked'}
                  <Button variant="ghost" size="sm" label={t('Zertifikat')} onClick={() => showCert(d)} />
                {/if}
                {#if d.status === 'active' || d.status === 'expired'}
                  <Button variant="ghost" size="sm" label={renewing === d.id ? t('Verlängert …') : t('Verlängern')} disabled={renewing !== null} onClick={() => renew(d)} />
                {/if}
                {#if d.status === 'active'}
                  <Button variant="ghost" size="sm" label={t('Sperren')} onClick={() => (revoke = d)} />
                {:else}
                  <Button variant="ghost" size="sm" label={t('Löschen')} onClick={() => remove(d)} />
                {/if}
              </td>
            </tr>
          {:else}
            <tr><td colspan="6" class="muted">{t('Keine Treffer.')}</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</AppShell>

<style>
  .search {
    flex: 1 1 240px;
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 44px;
    padding: 0 12px;
    border-radius: var(--radius);
    background: var(--surface);
    border: 1px solid var(--border-input);
    color: var(--text-muted);
  }
  .search input {
    flex: 1;
    min-width: 0;
    border: none;
    outline: none;
    background: transparent;
    color: var(--text);
    font: inherit;
  }
  .inline {
    flex-direction: row;
    align-items: center;
    gap: 8px;
  }
  .strong {
    font-weight: 600;
  }
  .block {
    display: block;
  }
  .small {
    font-size: 12px;
  }
  .nowrap {
    white-space: nowrap;
  }
  .right {
    text-align: right;
  }
</style>
