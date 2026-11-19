<script lang="ts">
  import Button from './Button.svelte';
  import StatusPill from './StatusPill.svelte';
  import { api, ENROLLMENT_STATUS, PLATFORMS, formatAgo, formatDate, type Invite } from '../api';
  import { toasts } from '../toast.svelte';

  interface Props {
    invite: Invite;
    onChange: () => void;
  }

  let { invite, onChange }: Props = $props();

  let copied = $state(false);
  let busy = $state(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(invite.url);
      copied = true;
      setTimeout(() => (copied = false), 2000);
    } catch {
      /* Link steht ja da */
    }
  }

  async function act(path: string, ok: string) {
    busy = true;
    try {
      await api.post(path);
      toasts.show('ok', ok);
      onChange();
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e));
    } finally {
      busy = false;
    }
  }
</script>

<section class="card invite" aria-label={`Einladung für ${invite.person_name}`}>
  <div class="row">
    <h3>Einladung für {invite.person_name}</h3>
    <span class="spacer"></span>
    {#if invite.state === 'open'}
      <StatusPill tone="ok" label={`gültig bis ${formatDate(invite.expires_at)}`} />
    {:else}
      <StatusPill tone="bad" label={invite.state === 'expired' ? 'abgelaufen' : 'widerrufen'} />
    {/if}
  </div>

  <div class="share">
    <img src={`/api/invites/${invite.id}/qr.svg`} alt="QR-Code für den Einladungslink" width="148" height="148" />
    <div class="stack">
      <label class="field">
        Link
        <span class="link-row">
          <input class="input mono" readonly value={invite.url} onfocus={(e) => e.currentTarget.select()} />
          <Button variant="secondary" size="sm" label={copied ? 'Kopiert' : 'Kopieren'} onClick={copy} />
        </span>
      </label>
      <div class="field">
        Bestätigungscode – separat mitteilen
        <span class="code mono">{invite.code}</span>
      </div>
      <p class="muted small">
        Am besten mündlich oder per Anruf. Wer nur den Link abfängt, kann damit kein Gerät registrieren.
        Noch {invite.slots_left} Gerät(e) möglich.
      </p>
    </div>
  </div>

  {#if invite.enrollments.length}
    <ul class="requests">
      {#each invite.enrollments as e (e.id)}
        {@const st = ENROLLMENT_STATUS[e.status]}
        <li>
          <span class="stack">
            <strong>„{e.device_name}“</strong>
            <span class="muted small">
              {PLATFORMS[e.platform] ?? (e.platform || 'unbekannt')} · {formatAgo(e.created_at)}{e.ip ? ` · ${e.ip}` : ''}
            </span>
          </span>
          <span class="spacer"></span>
          {#if e.status === 'pending'}
            <Button size="sm" label="Gerät freigeben" disabled={busy} onClick={() => act(`/enrollments/${e.id}/approve`, `„${e.device_name}“ freigegeben.`)} />
            <Button variant="ghost" size="sm" label="Ablehnen" disabled={busy} onClick={() => act(`/enrollments/${e.id}/reject`, 'Abgelehnt.')} />
          {:else}
            <StatusPill tone={st.tone} label={st.label} />
          {/if}
        </li>
      {/each}
    </ul>
  {:else if invite.state === 'open'}
    <p class="muted small">Noch keine Registrierung. Diese Ansicht aktualisiert sich automatisch.</p>
  {/if}

  {#if invite.state === 'open'}
    <div class="row">
      <span class="spacer"></span>
      <Button variant="ghost" size="sm" label="Einladung widerrufen" disabled={busy} onClick={() => act(`/invites/${invite.id}/revoke`, 'Einladung widerrufen.')} />
    </div>
  {/if}
</section>

<style>
  .invite {
    background: var(--bg);
    border-color: var(--accent-border);
  }
  h3 {
    margin: 0;
    font-size: 14px;
  }
  .share {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    align-items: flex-start;
  }
  img {
    border-radius: var(--radius);
    background: #fff;
    flex-shrink: 0;
  }
  .stack {
    flex: 1 1 220px;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .link-row {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .code {
    font-size: 22px;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: var(--text);
  }
  .small {
    font-size: 12px;
    margin: 0;
    line-height: 1.5;
  }
  .requests {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .requests li {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    padding: 10px 0;
    border-top: 1px solid var(--border);
  }
  .requests .stack {
    gap: 2px;
  }
</style>
