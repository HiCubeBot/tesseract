<script lang="ts">
  // Einstellungen › Integrationen: pro Domain festlegen, wie DNS-Einträge für Hosts angelegt werden
  import Button from './Button.svelte';
  import Icon from './Icon.svelte';
  import { api, formatAgo, type DnsRecord, type DnsZone } from '../api';
  import { toasts } from '../toast.svelte';

  let zones = $state<(DnsZone & { ipsText: string })[]>([]);
  let tokenSet = $state(false);
  let loaded = $state(false);
  let saving = $state(false);
  let checking = $state<string | null>(null);

  async function load() {
    try {
      const r = await api.get<{ zones: DnsZone[]; token_set: boolean }>('/settings/dns-zones');
      zones = r.zones.map((z) => ({ ...z, ipsText: z.ips.join(', ') }));
      tokenSet = r.token_set;
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e));
    } finally {
      loaded = true;
    }
  }
  load();

  // Eintrag für die Tesseract-Domain selbst – damit Nodes den Controller finden
  interface ControllerDns {
    type: 'cname' | 'address' | null;
    target: string;
    records: DnsRecord[];
    error: string | null;
    at: string | null;
    domain: string;
    zone: string | null;
    agent_api_public: boolean;
  }
  let ctl = $state<ControllerDns | null>(null);
  let ctlSaving = $state(false);
  api.get<ControllerDns>('/settings/controller-dns').then((r) => (ctl = r), () => {});

  async function saveCtl() {
    if (!ctl) return;
    ctlSaving = true;
    try {
      ctl = await api.put<ControllerDns>('/settings/controller-dns', { type: ctl.type, target: ctl.target });
      if (ctl.error) toasts.show('warn', `DNS-Eintrag für ${ctl.domain}: ${ctl.error}`, 12000);
      else toasts.show('ok', ctl.type ? `DNS-Eintrag für ${ctl.domain} steht.` : 'Kein Eintrag mehr für die Tesseract-Domain.');
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    } finally {
      ctlSaving = false;
    }
  }

  function add() {
    zones = [...zones, { zone: '', type: 'cname', cname_target: '', ip_source: 'node', ips: [], proxied: false, ipsText: '' }];
  }

  async function save() {
    saving = true;
    try {
      const body = {
        zones: zones.map(({ ipsText, ...z }) => ({ ...z, ips: ipsText.split(/[\s,;]+/).filter(Boolean) }))
      };
      const r = await api.put<{ zones: DnsZone[]; token_set: boolean }>('/settings/dns-zones', body);
      zones = r.zones.map((z) => ({ ...z, ipsText: z.ips.join(', ') }));
      toasts.show('ok', 'Gespeichert.');
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    } finally {
      saving = false;
    }
  }

  async function check(zone: string) {
    checking = zone;
    try {
      const r = await api.post<{ ok: boolean; error: string | null }>('/settings/dns-zones/check', { zone });
      if (r.ok) toasts.show('ok', `${zone}: Zone gefunden, der Token darf sie lesen.`);
      else toasts.show('bad', r.error ?? 'Fehler', 12000);
    } finally {
      checking = null;
    }
  }
</script>

<section class="card" aria-labelledby="dnsz-title">
  <h2 id="dnsz-title">DNS-Einträge</h2>
  <p class="muted small">
    Beim Anlegen eines Hosts kann Tesseract den DNS-Eintrag bei Cloudflare gleich mit anlegen – und ändert oder löscht ihn mit dem
    Host. Pro Domain legst du fest, wie: als <strong>CNAME</strong> auf einen Namen (z. B. deinen DDNS-Namen) oder als
    <strong>A/AAAA</strong> auf IP-Adressen. Beim Host lässt sich beides ändern. Einträge, die Tesseract nicht selbst angelegt hat, bleiben
    unangetastet.
  </p>
  {#if loaded && !tokenSet}
    <p class="muted small">Braucht den Cloudflare-Token (oben, Rechte „Zone · Zone · Lesen“ und „Zone · DNS · Bearbeiten“).</p>
  {:else if loaded}
    {#each zones as z, i (i)}
      <div class="zone">
        <div class="grid">
          <label class="field"
            >Domain<input class="input mono" bind:value={z.zone} placeholder="beispiel.de" spellcheck="false" autocomplete="off" /></label
          >
          <label class="field"
            >Standard für neue Hosts
            <select class="input" bind:value={z.type}>
              <option value="cname">CNAME</option>
              <option value="address">A / AAAA (IP-Adressen)</option>
            </select>
          </label>
          {#if z.type === 'cname'}
            <label class="field"
              >CNAME-Ziel<input
                class="input mono"
                bind:value={z.cname_target}
                placeholder="home.beispiel.de"
                spellcheck="false"
                autocomplete="off"
              /></label
            >
          {:else}
            <label class="field"
              >IP-Adressen
              <select class="input" bind:value={z.ip_source}>
                <option value="node">öffentliche IPs des Nodes</option>
                <option value="custom">eigene</option>
              </select>
            </label>
            {#if z.ip_source === 'custom'}
              <label class="field"
                >IPs<input class="input mono" bind:value={z.ipsText} placeholder="203.0.113.7, 2001:db8::7" spellcheck="false" /></label
              >
            {/if}
          {/if}
        </div>
        <div class="row">
          <label class="check"><input type="checkbox" bind:checked={z.proxied} />Über den Cloudflare-Proxy (Standard)</label>
          <span class="spacer"></span>
          <Button
            variant="ghost"
            size="sm"
            label={checking === z.zone ? 'Prüft …' : 'Zugriff prüfen'}
            disabled={!z.zone || checking !== null}
            onClick={() => check(z.zone)}
          />
          <button type="button" class="remove" aria-label={`${z.zone || 'Domain'} entfernen`} onclick={() => (zones = zones.filter((_, j) => j !== i))}>
            <Icon name="trash" size={16} />
          </button>
        </div>
      </div>
    {/each}
    <div class="row">
      <Button variant="secondary" size="sm" icon="plus" label="Domain hinzufügen" onClick={add} />
      <Button label={saving ? 'Speichert …' : 'Speichern'} disabled={saving} onClick={save} />
    </div>

    {#if ctl}
      <div class="zone">
        <h3>Tesseract-Domain für die Nodes</h3>
        <p class="muted small">
          Nodes außerhalb deines Netzes finden den Controller nur, wenn <span class="mono">{ctl.domain || 'TESSERACT_DOMAIN'}</span> öffentlich auflöst.
          Tesseract kann den Eintrag dafür anlegen – nie über den Cloudflare-Proxy, weil sich die Nodes mit eigenem Zertifikat anmelden.
          {#if ctl.agent_api_public}Ist die Oberfläche auf bestimmte Netze beschränkt, bleibt die Schnittstelle für die Nodes trotzdem erreichbar.{/if}
        </p>
        {#if !ctl.domain}
          <p class="field-error">TESSERACT_DOMAIN ist nicht gesetzt.</p>
        {:else if !ctl.zone}
          <p class="muted small">Für {ctl.domain} ist oben noch keine Domain eingetragen.</p>
        {:else}
          <div class="grid">
            <label class="field"
              >Eintrag
              <select class="input" bind:value={ctl.type}>
                <option value={null}>keiner (selbst verwalten)</option>
                <option value="cname">CNAME</option>
                <option value="address">A / AAAA</option>
              </select>
            </label>
            {#if ctl.type}
              <label class="field"
                >{ctl.type === 'cname' ? 'Ziel' : 'IP-Adressen'}
                <input
                  class="input mono"
                  bind:value={ctl.target}
                  placeholder={ctl.type === 'cname' ? 'leer = Standard der Domain' : 'leer = öffentliche IPs des lokalen Nodes'}
                  spellcheck="false"
                  autocomplete="off"
                />
              </label>
            {/if}
          </div>
          <div class="row">
            <Button size="sm" label={ctlSaving ? 'Überträgt …' : 'Übernehmen'} disabled={ctlSaving} onClick={saveCtl} />
            {#if ctl.records.length}
              <span class="mono small">{ctl.records.map((r) => `${r.type} → ${r.content}`).join(' · ')}</span>
            {/if}
            {#if ctl.at}<span class="muted small">geprüft {formatAgo(ctl.at)}</span>{/if}
          </div>
          {#if ctl.error}<p class="field-error">{ctl.error}</p>{/if}
        {/if}
      </div>
    {/if}
  {/if}
</section>

<style>
  .small {
    font-size: 13px;
    margin: 0;
  }
  .zone {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px 14px;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
  }
  h3 {
    margin: 0;
    font-size: 14px;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 12px;
  }
  .remove {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--border-input);
    border-radius: var(--radius);
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
  }
  .remove:hover {
    color: var(--bad-text);
  }
</style>
