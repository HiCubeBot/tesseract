<!--
  Komponenten · Übersicht
  Aus dem Design-Canvas „Caddy Control“ übernommen (Kit.dc.html).
  Die Logik steckt noch in der Klasse Component (renderVals) – siehe src/lib/dc.svelte.ts.
-->
<script>
  import { DCLogic, useDC } from '../lib/dc.svelte';
  import AccessChip from '../lib/components/AccessChip.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import Button from '../lib/components/Button.svelte';
  import ConfirmDialog from '../lib/components/ConfirmDialog.svelte';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import EventItem from '../lib/components/EventItem.svelte';
  import NodeCard from '../lib/components/NodeCard.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import SegmentedControl from '../lib/components/SegmentedControl.svelte';
  import SelectField from '../lib/components/SelectField.svelte';
  import StatCard from '../lib/components/StatCard.svelte';
  import StatusPill from '../lib/components/StatusPill.svelte';
  import TextField from '../lib/components/TextField.svelte';
  import Toggle from '../lib/components/Toggle.svelte';

  let props = $props();

  class Component extends DCLogic {
    renderVals() {
      return {};
    }
  }

  const dc = useDC(Component, () => props);
  const dcv = $derived(dc.vals);
</script>

<main style="box-sizing: border-box; min-height: 100vh; background: #0E1014; color: #E7E9EE; font-family: Inter, system-ui, sans-serif; font-size: 14px; padding: 32px;">
<div style="max-width: 1240px; margin: 0 auto; display: flex; flex-direction: column; gap: 28px;">

<header style="display: flex; flex-direction: column; gap: 6px;">
<span style="font-size: 12px; font-weight: 600; color: #A0A7B4; text-transform: uppercase; letter-spacing: 0.06em;">Tesseract · Bausteine</span>
<h1 style="margin: 0; font-size: 30px; font-weight: 700; letter-spacing: -0.02em;">Komponenten</h1>
<p style="margin: 0; max-width: 720px; color: #A0A7B4; line-height: 1.5;">Jeder Baustein liegt als eigenes Artboard rechts daneben und wird in Screens per Import eingebunden. Änderungen am Baustein wirken überall.</p>
</header>

<section style="display: flex; flex-direction: column; gap: 12px; padding: 20px; border-radius: 12px; background: #12151B; border: 1px solid #232833;">
<h2 style="margin: 0; font-size: 15px; font-weight: 600;">Buttons</h2>
<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 12px;">
<Button variant="primary" icon="plus" label="Host anlegen" />
<Button variant="secondary" icon="none" label="Person einladen" />
<Button variant="secondary" icon="send" label="Speichern &amp; übertragen" />
<Button variant="ghost" icon="refresh" label="Erneut prüfen" />
<Button variant="danger" icon="trash" label="Gerät sperren" />
<Button variant="primary" icon="check" label="Übernehmen" disabled={true} />
<Button variant="secondary" size="sm" icon="download" label="Export CSV" />
</div>
</section>

<section style="display: flex; flex-direction: column; gap: 12px; padding: 20px; border-radius: 12px; background: #12151B; border: 1px solid #232833;">
<h2 style="margin: 0; font-size: 15px; font-weight: 600;">Status &amp; Zugriff</h2>
<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 10px;">
<StatusPill tone="ok" label="online" />
<StatusPill tone="ok" label="synchron" dot={false} />
<StatusPill tone="warn" label="lokal geändert" />
<StatusPill tone="bad" label="offline · 14 Min." />
<StatusPill tone="mtls" label="Nur mit Zertifikat" />
<StatusPill tone="neutral" label="gesperrt" />
</div>
<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 8px;">
<AccessChip kind="group" label="Gruppe Familie" />
<AccessChip kind="person" label="Ben" />
<AccessChip kind="device" label="Pixel 8 von Ben" />
<AccessChip kind="person" label="Anna" removable={false} />
</div>
</section>

<section style="display: flex; flex-direction: column; gap: 14px; padding: 20px; border-radius: 12px; background: #12151B; border: 1px solid #232833;">
<h2 style="margin: 0; font-size: 15px; font-weight: 600;">Formular</h2>
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; align-items: start;">
<TextField label="Domain" value="fotos.beispiel.de" placeholder="sub.beispiel.de" hint="" />
<TextField label="Ziel (Upstream)" value="10.0.1.20:2342" placeholder="IP:Port oder Hostname" hint="Wird vom Node aus erreicht, nicht vom Controller." />
<TextField label="Ziel (Upstream)" value="10.0.1.20" error="Port fehlt – z. B. 10.0.1.20:2342" placeholder="IP:Port oder Hostname" hint="Wird vom Node aus erreicht, nicht vom Controller." />
<SelectField label="Node" options="home-nas, edge-fra, pi-eltern, vps-hel" value="home-nas" />
<SelectField label="Ohne passendes Zertifikat" options="Verbindung ablehnen, Hinweisseite „Kein Zugang“ anzeigen" value="home-nas" />
<div style="display: flex; flex-direction: column; gap: 6px;">
<span style="font-size: 13px; color: #A0A7B4;">Filter</span>
<SegmentedControl options="Alle · 18, Öffentlich · 11, mTLS · 7" selected={0} groupLabel="Zugriffsart filtern" />
</div>
</div>
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 12px;">
<Toggle label="Coraza-WAF aktiv" description="OWASP Core Rule Set, Paranoia-Level 1" checked={true} />
<Toggle label="Authelia vorschalten" description="Zusätzliche Anmeldung per SSO vor dem Host" checked={false} />
</div>
</section>

<section style="display: flex; flex-direction: column; gap: 12px; padding: 20px; border-radius: 12px; background: #12151B; border: 1px solid #232833;">
<h2 style="margin: 0; font-size: 15px; font-weight: 600;">Kennzahlen</h2>
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px;">
<StatCard label="Nodes online" value="3 / 4" sub="vps-hel antwortet seit 14 Min. nicht" tone="ok" subTone="bad" />
<StatCard label="Hosts" value="11 + 7" sub="öffentlich + nur mit Zertifikat (mTLS)" tone="mtls" subTone="muted" />
<StatCard label="Personen" value="6" sub="1 Einladung offen" tone="mtls" subTone="muted" />
<StatCard label="Geräte" value="6 aktiv" sub="2 Zertifikate laufen bald ab" tone="warn" subTone="warn" />
</div>
</section>

<section style="display: flex; flex-direction: column; gap: 12px; padding: 20px; border-radius: 12px; background: #12151B; border: 1px solid #232833;">
<h2 style="margin: 0; font-size: 15px; font-weight: 600;">Hinweise</h2>
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 12px;">
<Alert tone="info" title="Neue Caddy-Version verfügbar" text="2.10.2 läuft auf 3 von 4 Nodes. pi-eltern nutzt noch 2.9.1." actionLabel="Nodes ansehen" actionHref="#/nodes" />
<Alert tone="ok" title="Konfiguration übertragen" text="home-nas hat 3 Änderungen übernommen und neu geladen." actionLabel="" actionHref="#/nodes" />
<Alert tone="warn" title="pi-eltern wurde lokal geändert" text="Die laufende Caddy-Config weicht von der gespeicherten ab. Übernehmen oder mit dem Controller-Stand überschreiben?" actionLabel="Abweichung ansehen" actionHref="#/nodes" />
<Alert tone="bad" title="Zertifikat-Erneuerung fehlgeschlagen" text="wiki.beispiel.de läuft in 9 Tagen ab. Der Node vps-hel ist offline." actionLabel="Host öffnen" actionHref="#/host-security" />
</div>
</section>

<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 18px; align-items: start;">
<section style="display: flex; flex-direction: column; gap: 12px; padding: 20px; border-radius: 12px; background: #12151B; border: 1px solid #232833;">
<h2 style="margin: 0; font-size: 15px; font-weight: 600;">Nodes</h2>
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px;">
<NodeCard nodeName="edge-fra" location="VPS · Frankfurt" caddy="2.10.2" hosts="9" seen="gerade eben" status="online" />
<NodeCard nodeName="pi-eltern" location="Elternhaus" caddy="2.9.1" hosts="2" seen="vor 8 s" status="drift" />
</div>
</section>
<section style="display: flex; flex-direction: column; gap: 4px; padding: 20px; border-radius: 12px; background: #12151B; border: 1px solid #232833;">
<h2 style="margin: 0 0 6px; font-size: 15px; font-weight: 600;">Ereignisse</h2>
<EventItem time="10:42" title="Zugriff verweigert" detail="Unbekanntes Gerät an fotos.beispiel.de (home-nas)" tone="bad" />
<EventItem time="10:20" title="Einladung geöffnet" detail="Dana hat den Einladungslink aufgerufen" tone="mtls" />
<EventItem time="10:15" title="Konfiguration übertragen" detail="home-nas · 3 Änderungen" tone="ok" />
<EventItem time="gestern" title="Abweichung erkannt" detail="pi-eltern wurde lokal geändert" tone="warn" />
</section>
</div>

<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 18px; align-items: start;">
<section style="display: flex; flex-direction: column; gap: 12px; padding: 20px; border-radius: 12px; background: #12151B; border: 1px solid #232833;">
<h2 style="margin: 0; font-size: 15px; font-weight: 600;">Leerer Zustand</h2>
<EmptyState icon="devices" title="Noch keine Geräte" text="Lade eine Person ein – sie registriert ihr Gerät dann selbst über den Einladungslink und bekommt ein eigenes Zertifikat." actionLabel="Person einladen" actionHref="#/invite-1" />
</section>
<section style="display: flex; flex-direction: column; gap: 12px; padding: 20px; border-radius: 12px; background: #12151B; border: 1px solid #232833;">
<h2 style="margin: 0; font-size: 15px; font-weight: 600;">Bestätigungsdialog</h2>
<ConfirmDialog title="Gerät sperren?" text="Das Zertifikat von „iPhone von Anna“ wird sofort widerrufen und von allen Nodes entfernt. Annas andere Geräte behalten ihren Zugriff." word="sperren" confirmLabel="Gerät sperren" tone="danger" />
</section>
</div>

<section style="display: flex; flex-direction: column; gap: 12px; padding: 20px; border-radius: 12px; background: #12151B; border: 1px solid #232833;">
<h2 style="margin: 0; font-size: 15px; font-weight: 600;">Seitenkopf</h2>
<PageHeader title="Proxy-Hosts" subtitle="Öffentlich mit Let’s Encrypt – oder nur für freigegebene Geräte (mTLS)." secondaryLabel="" primaryLabel="Host anlegen" primaryHref="#/host-new-1" primaryIcon="plus" secondaryHref="#/invite-1" />
<PageHeader crumb="Proxy-Hosts" crumbHref="#/hosts" title="fotos.beispiel.de" subtitle="home-nas · nur mit Zertifikat" secondaryLabel="Verlauf" secondaryHref="#/host-history" primaryLabel="Speichern &amp; übertragen" primaryIcon="send" primaryHref="" />
</section>

</div>
</main>
