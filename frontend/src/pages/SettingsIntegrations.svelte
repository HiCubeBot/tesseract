<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import SettingsTabs from '../lib/components/SettingsTabs.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import { api, WAF_MODES, type GeneralSettings, type WafMode } from '../lib/api';
  import { toasts } from '../lib/toast.svelte';

  let general = $state<GeneralSettings | null>(null);
  let error = $state('');
  let saving = $state(false);

  async function load() {
    try {
      general = await api.get<GeneralSettings>('/settings/general');
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  load();

  async function save(e: SubmitEvent) {
    e.preventDefault();
    if (!general) return;
    saving = true;
    try {
      general = await api.put<GeneralSettings>('/settings/general', {
        acme_email: general.acme_email || null,
        public_ips: general.public_ips,
        waf_default_mode: general.waf_default_mode,
        waf_default_paranoia: Number(general.waf_default_paranoia),
        controller_waf_mode: general.controller_waf_mode
      });
      toasts.show('ok', 'Gespeichert.');
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    } finally {
      saving = false;
    }
  }

  const modes = Object.entries(WAF_MODES) as [WafMode, string][];
</script>

<AppShell active="settings">
  <PageHeader title="Einstellungen" subtitle="Externe Dienste und Caddy-Module, die Hosts nutzen können." />
  <SettingsTabs current="#/settings-integrations" />

  {#if error}<Alert tone="bad" title="Fehler" text={error} />{/if}

  {#if general}
    <form class="card" onsubmit={save} aria-labelledby="waf-title">
      <h2 id="waf-title">Coraza WAF · Standards</h2>
      <div class="grid">
        <label class="field">
          Modus für neue Hosts
          <select class="input" bind:value={general.waf_default_mode}>
            {#each modes as [k, v] (k)}<option value={k}>{v}</option>{/each}
          </select>
        </label>
        <label class="field">
          Paranoia-Level für neue Hosts
          <select class="input" bind:value={general.waf_default_paranoia}>
            {#each [1, 2, 3, 4] as l (l)}<option value={l}>{l}</option>{/each}
          </select>
        </label>
        <label class="field">
          WAF für die Tesseract-Oberfläche
          <select class="input" bind:value={general.controller_waf_mode}>
            {#each modes as [k, v] (k)}<option value={k}>{v}</option>{/each}
          </select>
        </label>
      </div>
      <p class="muted small">
        Bestehende Hosts behalten ihre Einstellung – die änderst du pro Host unter „Sicherheit“.
        Empfehlung: neue Dienste erst „nur protokollieren“, nach ein paar Tagen ohne Fehlalarme auf „Blockieren“.
      </p>
      <div class="row"><Button type="submit" label={saving ? 'Speichert …' : 'Speichern'} disabled={saving} /></div>
    </form>

    <section class="card muted-card">
      <h2>IP-Listen, vertrauenswürdige Proxys, Authelia</h2>
      <p class="muted small">Folgen in den nächsten Schritten von Phase 3. Vorschau: <a href="#/design/settings-integrations">Design</a>.</p>
    </section>
  {/if}
</AppShell>

<style>
  h2 {
    margin: 0;
    font-size: 16px;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 12px;
  }
  .small {
    font-size: 12px;
    margin: 0;
    line-height: 1.5;
  }
  .muted-card {
    opacity: 0.75;
  }
</style>
