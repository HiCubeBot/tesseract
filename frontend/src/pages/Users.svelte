<script lang="ts">
  import { t } from '../lib/i18n';
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import StatusPill from '../lib/components/StatusPill.svelte';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import ConfirmDialog from '../lib/components/ConfirmDialog.svelte';
  import IssuedCertificate from '../lib/components/IssuedCertificate.svelte';
  import InviteCard from '../lib/components/InviteCard.svelte';
  import Icon from '../lib/components/Icon.svelte';
  import {
    api,
    DEVICE_STATUS,
    PLATFORMS,
    UI_ROLES,
    UI_ROLE_HINTS,
    expiresSoon,
    formatDay,
    type CAStatus,
    type Group,
    type Invite,
    type IssuedDevice,
    type Person,
    type UiRole
  } from '../lib/api';
  import { untrack } from 'svelte';
  import { router } from '../lib/router.svelte';
  import { toasts } from '../lib/toast.svelte';

  let { params = {} }: { params?: Record<string, string> } = $props();

  let persons = $state<Person[]>([]);
  let groups = $state<Group[]>([]);
  let ca = $state<CAStatus | null>(null);
  let invites = $state<Invite[]>([]);
  let inviting = $state(false);
  let error = $state('');

  const selectedId = $derived(params.id === 'new' ? null : params.id ? Number(params.id) : null);
  const creating = $derived(params.id === 'new');
  const selected = $derived(persons.find((p) => p.id === selectedId) ?? null);

  // Formular Person
  let form = $state({ name: '', note: '', max_devices: 3, disabled: false, group_ids: [] as number[], ui_role: 'none' as UiRole });
  let saving = $state(false);
  let formError = $state('');
  let confirmDelete = $state(false);

  // Gerät direkt ausstellen
  let issueOpen = $state(false);
  let issueName = $state('');
  let issuePlatform = $state('ios');
  let issueDays = $state<string>('365');
  let issuing = $state(false);
  let issued = $state<IssuedDevice | null>(null);

  // Gerät sperren
  let revokeId = $state<number | null>(null);

  // Gruppen
  let newGroup = $state('');

  async function load() {
    try {
      [persons, groups, ca, invites] = await Promise.all([
        api.get<Person[]>('/persons'),
        api.get<Group[]>('/groups'),
        api.get<CAStatus>('/ca'),
        api.get<Invite[]>('/invites')
      ]);
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  load();

  const personInvites = $derived(invites.filter((i) => i.person_id === selectedId));
  const pendingFor = (id: number) =>
    invites.filter((i) => i.person_id === id).flatMap((i) => i.enrollments).filter((e) => e.status === 'pending').length;

  // Offene Einladung angezeigt → regelmäßig nach neuen Registrierungen schauen
  $effect(() => {
    if (!personInvites.length) return;
    const timer = setInterval(async () => {
      try {
        invites = await api.get<Invite[]>('/invites');
      } catch {
        /* nächster Versuch */
      }
    }, 5000);
    return () => clearInterval(timer);
  });

  async function invite() {
    if (!selected) return;
    inviting = true;
    try {
      await api.post(`/persons/${selected.id}/invites`, { days: 7 });
      await load();
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err));
    } finally {
      inviting = false;
    }
  }

  // Formular nur beim Wechsel der Person neu füllen – nicht nach jedem Neuladen
  $effect(() => {
    void selectedId;
    void creating;
    void persons.length;
    untrack(fillForm);
  });

  let filledFor = '';
  function fillForm() {
    const key = creating ? 'new' : String(selectedId);
    const p = selected;
    if (!p && !creating) {
      filledFor = '';
      return;
    }
    if (key === filledFor) return;
    filledFor = key;
    if (p) {
      form = {
        name: p.name,
        note: p.note,
        max_devices: p.max_devices,
        disabled: p.disabled,
        group_ids: p.groups.map((g) => g.id),
        ui_role: p.ui_role ?? 'none'
      };
    } else if (creating) {
      form = { name: '', note: '', max_devices: 3, disabled: false, group_ids: [], ui_role: 'none' };
    }
    formError = '';
    confirmDelete = false;
    issueOpen = false;
    issued = null;
    revokeId = null;
  }

  async function savePerson(e: SubmitEvent) {
    e.preventDefault();
    saving = true;
    formError = '';
    try {
      const body = { ...form, max_devices: Number(form.max_devices) };
      if (creating) {
        const p = await api.post<Person>('/persons', body);
        toasts.show('ok', `${p.name} angelegt.`);
        await load();
        router.go(`users/${p.id}`);
      } else if (selected) {
        await api.put<Person>(`/persons/${selected.id}`, body);
        toasts.show('ok', t('Gespeichert.'));
        await load();
      }
    } catch (err) {
      formError = err instanceof Error ? err.message : String(err);
    } finally {
      saving = false;
    }
  }

  async function deletePerson() {
    if (!selected) return;
    const name = selected.name;
    try {
      await api.del(`/persons/${selected.id}`);
      toasts.show('ok', t('{0} gelöscht – alle Geräte haben keinen Zugriff mehr.', name));
      router.go('users');
      await load();
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err));
    }
  }

  async function issue(e: SubmitEvent) {
    e.preventDefault();
    if (!selected) return;
    issuing = true;
    try {
      issued = await api.post<IssuedDevice>(`/persons/${selected.id}/devices`, {
        name: issueName,
        platform: issuePlatform,
        days: issueDays === 'unlimited' ? null : Number(issueDays)
      });
      issueOpen = false;
      issueName = '';
      await load();
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err));
    } finally {
      issuing = false;
    }
  }

  async function revoke(reason: string) {
    if (revokeId === null) return;
    try {
      await api.post(`/devices/${revokeId}/revoke`, { reason });
      toasts.show('ok', t('Gerät gesperrt – die Freigabelisten wurden neu übertragen.'));
      revokeId = null;
      await load();
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err));
    }
  }

  async function deleteDevice(id: number, name: string) {
    if (!confirm(t('„{0}“ endgültig löschen? Das Gerät verschwindet auch aus der Liste der gesperrten Geräte.', name))) return;
    try {
      await api.del(`/devices/${id}`);
      toasts.show('ok', t('„{0}“ gelöscht.', name));
      await load();
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err));
    }
  }

  async function addGroup(e: SubmitEvent) {
    e.preventDefault();
    try {
      await api.post('/groups', { name: newGroup });
      newGroup = '';
      await load();
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err));
    }
  }

  async function deleteGroup(g: Group) {
    if (!confirm(t('Gruppe „{0}“ löschen? Freigaben über diese Gruppe entfallen.', g.name))) return;
    try {
      await api.del(`/groups/${g.id}`);
      await load();
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err));
    }
  }

  const initials = (name: string) =>
    name
      .split(/\s+/)
      .map((w) => w[0])
      .join('')
      .slice(0, 2)
      .toUpperCase();
</script>

<AppShell active="users">
  <PageHeader
    title={t('Nutzer')}
    subtitle={t('Rechte gehören zur Person. Jedes ihrer Geräte hat ein eigenes Zertifikat.')}
    primaryLabel={t('Person anlegen')}
    primaryHref="#/users/new"
  />

  {#if error}<Alert tone="bad" title={t('Fehler')} text={error} />{/if}
  {#if ca && !ca.configured}
    <Alert
      tone="warn"
      title={t('Noch keine Zertifizierungsstelle')}
      text={t('Ohne CA lassen sich keine Gerätezertifikate ausstellen.')}
      actionLabel={t('CA einrichten')}
      actionHref="#/settings-ca"
    />
  {/if}

  <div class="layout">
    <section class="list" aria-label={t('Personen')}>
      {#if persons.length === 0}
        <EmptyState icon="users" title={t('Noch keine Personen')} text={t('Lege Personen an und gib ihnen Geräte.')} actionLabel={t('Person anlegen')} actionHref="#/users/new" />
      {:else}
        <ul class="people">
          {#each persons as p (p.id)}
            <li>
              <a href={`#/users/${p.id}`} class="person" class:on={p.id === selectedId}>
                <span class="avatar">{initials(p.name)}</span>
                <span class="stack">
                  <span class="name">{p.name}</span>
                  <span class="muted small">
                    {t('{0} · {1} von {2} Geräten', p.groups.map((g) => g.name).join(', ') || t('keine Gruppe'), p.active_devices, p.max_devices)}
                  </span>
                </span>
                {#if p.ldap}<StatusPill tone="neutral" label={t('LDAP')} dot={false} />{/if}
                {#if p.disabled}<StatusPill tone="bad" label={t('gesperrt')} />{/if}
                {#if pendingFor(p.id)}<StatusPill tone="warn" label={t('Gerät wartet')} />{/if}
              </a>
            </li>
          {/each}
        </ul>
      {/if}

      <section class="card groups" aria-labelledby="groups-title">
        <h2 id="groups-title">{t('Gruppen')}</h2>
        <ul class="group-list">
          {#each groups as g (g.id)}
            <li>
              <span class="name">{g.name}</span>
              <span class="muted small">{t('{0} Personen{1}{2}', g.members, g.builtin ? t(' · eingebaut') : '', g.ldap ? t(' · aus LDAP') : '')}</span>
              <span class="spacer"></span>
              {#if !g.builtin}
                <button type="button" class="icon-btn" aria-label={t('Gruppe {0} löschen', g.name)} onclick={() => deleteGroup(g)}>
                  <Icon name="trash" size={15} />
                </button>
              {/if}
            </li>
          {/each}
        </ul>
        <form class="row" onsubmit={addGroup}>
          <input class="input grow" placeholder={t('Neue Gruppe, z. B. Familie')} bind:value={newGroup} required maxlength="64" aria-label={t('Name der neuen Gruppe')} />
          <Button type="submit" variant="secondary" icon="plus" label={t('Anlegen')} />
        </form>
      </section>
    </section>

    {#if selected || creating}
      <section class="card panel" aria-labelledby="person-title">
        <div class="panel-head">
          <h2 id="person-title">{creating ? t('Person anlegen') : selected?.name}</h2>
          <a href="#/users" class="close" aria-label={t('Schließen')}><Icon name="close" size={16} /></a>
        </div>

        <form class="form" onsubmit={savePerson}>
          {#if selected?.ldap && !creating}
            <p class="muted small ldap-note">
              {t('Aus LDAP{0}: Name, Sperre und LDAP-Gruppen kommen vom Abgleich und werden dort überschrieben. Geräte und Freigaben verwaltest du hier.', selected.email ? ` · ${selected.email}` : '')}
            </p>
          {/if}
          <label class="field">
            {t('Name')}
            <input class="input" required maxlength="64" bind:value={form.name} />
          </label>
          <fieldset>
            <legend>{t('Gruppen')}</legend>
            <div class="chips">
              {#each groups as g (g.id)}
                <label class="chip" class:on={form.group_ids.includes(g.id)}>
                  <input type="checkbox" value={g.id} bind:group={form.group_ids} />{g.name}
                </label>
              {/each}
            </div>
          </fieldset>
          <div class="grid2">
            <label class="field">
              {t('Höchstens Geräte')}
              <input class="input" type="number" min="1" max="20" bind:value={form.max_devices} />
            </label>
            <label class="field">
              {t('Notiz')}
              <input class="input" maxlength="255" bind:value={form.note} />
            </label>
          </div>
          <label class="field">
            {t('Zugriff auf Tesseract')}
            <select class="input" bind:value={form.ui_role}>
              {#each Object.keys(UI_ROLES) as r (r)}<option value={r}>{UI_ROLES[r as UiRole]}</option>{/each}
            </select>
            <span class="muted small">
              {UI_ROLE_HINTS[form.ui_role]}
              {#if form.ui_role !== 'none'}{t('Nur per Gerätezertifikat – kein Passwort, kein Login-Formular.')}{/if}
            </span>
          </label>
          {#if !creating}
            <label class="check"><input type="checkbox" bind:checked={form.disabled} />{t('Person sperren (alle Geräte verlieren den Zugriff)')}</label>
          {/if}
          {#if formError}<p class="field-error" role="alert">{formError}</p>{/if}
          <div class="row">
            <Button type="submit" label={saving ? t('Speichert …') : creating ? t('Anlegen') : t('Speichern')} disabled={saving} />
            {#if selected}
              <span class="spacer"></span>
              <Button variant="danger" icon="trash" label={t('Löschen')} onClick={() => (confirmDelete = true)} />
            {/if}
          </div>
        </form>

        {#if confirmDelete && selected}
          <ConfirmDialog
            title={t('Person löschen?')}
            text={t('{0} und alle {1} Geräte werden entfernt. Die Zertifikate funktionieren danach nirgends mehr.', selected.name, selected.devices.length)}
            word={selected.name}
            confirmLabel={t('Endgültig löschen')}
            onConfirm={deletePerson}
            onCancel={() => (confirmDelete = false)}
          />
        {/if}

        {#if selected}
          <div class="devices">
            <div class="row">
              <h3>{t('Geräte · {0} von {1}', selected.active_devices, selected.max_devices)}</h3>
              <span class="spacer"></span>
              {#if !personInvites.length}
                <Button
                  size="sm"
                  icon="send"
                  label={inviting ? t('Erstellt …') : t('Einladen (Link)')}
                  disabled={inviting || !ca?.configured || selected.disabled || selected.active_devices >= selected.max_devices}
                  onClick={invite}
                />
              {/if}
              {#if !issueOpen && !issued}
                <Button
                  variant="secondary"
                  size="sm"
                  icon="plus"
                  label={t('Direkt ausstellen')}
                  disabled={!ca?.configured || selected.disabled || selected.active_devices >= selected.max_devices}
                  onClick={() => (issueOpen = true)}
                />
              {/if}
            </div>
            <p class="muted small">
              {t('Per Link registriert die Person ihr Gerät selbst. „Direkt ausstellen“ ist für Geräte, die du selbst einrichtest.')}
            </p>

            {#each personInvites as inv (inv.id)}
              <InviteCard invite={inv} onChange={load} />
            {/each}

            {#if issued}
              <IssuedCertificate {issued} onClose={() => (issued = null)} />
            {/if}

            {#if issueOpen}
              <form class="card issue" onsubmit={issue}>
                <div class="grid3">
                  <label class="field">
                    {t('Gerätename')}
                    <input class="input" required maxlength="64" placeholder={t('Annas iPhone')} bind:value={issueName} />
                  </label>
                  <label class="field">
                    {t('Plattform')}
                    <select class="input" bind:value={issuePlatform}>
                      {#each Object.entries(PLATFORMS) as [k, v] (k)}<option value={k}>{v}</option>{/each}
                    </select>
                  </label>
                  <label class="field">
                    {t('Gültig')}
                    <select class="input" bind:value={issueDays}>
                      <option value="90">{t('90 Tage')}</option>
                      <option value="365">{t('1 Jahr')}</option>
                      <option value="730">{t('2 Jahre')}</option>
                      <option value="unlimited">{t('unbegrenzt (bis Zwischenzertifikat)')}</option>
                    </select>
                  </label>
                </div>
                <div class="row">
                  <Button type="submit" label={issuing ? t('Stellt aus …') : t('Zertifikat ausstellen')} disabled={issuing} />
                  <Button variant="ghost" label={t('Abbrechen')} onClick={() => (issueOpen = false)} />
                </div>
              </form>
            {/if}

            <ul class="device-list">
              {#each selected.devices as d (d.id)}
                {@const st = DEVICE_STATUS[d.status]}
                <li>
                  <span class="dev-icon"><Icon name="device" size={16} /></span>
                  <span class="stack">
                    <span class="name">{d.name}</span>
                    <span class="muted small">
                      {PLATFORMS[d.platform] ?? d.platform} ·
                      {d.status === 'revoked' ? t('gesperrt am {0}', formatDay(d.revoked_at)) : d.unlimited ? 'unbegrenzt' : `bis ${formatDay(d.not_after)}`}
                    </span>
                  </span>
                  <span class="spacer"></span>
                  {#if expiresSoon(d)}<StatusPill tone="warn" label={t('läuft bald ab')} />{:else}<StatusPill tone={st.tone} label={st.label} />{/if}
                  {#if d.status === 'active'}
                    <Button variant="ghost" size="sm" label={t('Sperren')} onClick={() => (revokeId = d.id)} />
                  {:else}
                    <Button variant="ghost" size="sm" label={t('Löschen')} onClick={() => deleteDevice(d.id, d.name)} />
                  {/if}
                </li>
                {#if revokeId === d.id}
                  <li class="confirm">
                    <ConfirmDialog
                      title={t('„{0}“ sperren?', d.name)}
                      text={t('Das Zertifikat wird sofort aus allen Freigaben entfernt. Unter Geräte › Gesperrt lässt es sich wieder entsperren.')}
                      word="sperren"
                      confirmLabel={t('Gerät sperren')}
                      onConfirm={() => revoke(t('vom Admin gesperrt'))}
                      onCancel={() => (revokeId = null)}
                    />
                  </li>
                {/if}
              {:else}
                <li class="muted">{t('Noch keine Geräte.')}</li>
              {/each}
            </ul>
          </div>
        {/if}
      </section>
    {/if}
  </div>
</AppShell>

<style>
  .layout {
    display: flex;
    flex-wrap: wrap;
    gap: 18px;
    align-items: flex-start;
  }
  .list {
    flex: 1 1 340px;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 18px;
  }
  .panel {
    flex: 999 1 460px;
    border-color: var(--accent-border);
  }
  .people,
  .group-list,
  .device-list {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
  }
  .people {
    gap: 6px;
  }
  .person {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 14px;
    border-radius: var(--radius-md);
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    text-decoration: none;
  }
  .person:hover {
    border-color: var(--border-input);
  }
  .person.on {
    border-color: var(--accent);
    background: rgba(139, 124, 246, 0.08);
  }
  .avatar {
    width: 34px;
    height: 34px;
    flex-shrink: 0;
    border-radius: 50%;
    background: var(--surface-active);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 600;
  }
  .stack {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .name {
    font-weight: 600;
  }
  .small {
    font-size: 12px;
  }
  h2 {
    margin: 0;
    font-size: 16px;
  }
  h3 {
    margin: 0;
    font-size: 14px;
  }
  .group-list li,
  .device-list li {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 0;
    border-top: 1px solid var(--border);
    flex-wrap: wrap;
  }
  .device-list li.confirm {
    display: block;
    border-top: none;
    padding-top: 0;
  }
  .grow {
    flex: 1 1 160px;
  }
  .icon-btn {
    width: 34px;
    height: 34px;
    border-radius: var(--radius);
    border: 1px solid var(--border-input);
    background: transparent;
    color: var(--text-muted);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }
  .panel-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .close {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
  }
  .form {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  fieldset {
    margin: 0;
    padding: 0;
    border: none;
  }
  legend {
    padding: 0;
    margin-bottom: 8px;
    font-size: 13px;
    color: var(--text-muted);
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 36px;
    padding: 0 12px;
    border-radius: var(--radius-pill);
    background: var(--surface-raised);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
  }
  .chip.on {
    background: var(--accent-soft);
    color: var(--accent-text);
  }
  .chip input {
    margin: 0;
    accent-color: var(--accent);
  }
  .grid2 {
    display: grid;
    grid-template-columns: 140px minmax(0, 1fr);
    gap: 12px;
  }
  .grid3 {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
  }
  .devices {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding-top: 14px;
    border-top: 1px solid var(--border);
  }
  .devices p {
    margin: 0;
  }
  .issue {
    background: var(--bg);
  }
  .dev-icon {
    width: 32px;
    height: 32px;
    border-radius: var(--radius);
    background: var(--surface-raised);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-soft);
  }
</style>
