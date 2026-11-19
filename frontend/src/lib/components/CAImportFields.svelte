<script lang="ts" module>
  export interface CAImport {
    /** "root": Root-Zertifikat + Root-Schlüssel · "intermediate": Root + fertiges Zwischenzertifikat */
    way: 'root' | 'intermediate';
    root_cert_pem: string;
    root_key_pem: string;
    passphrase: string;
    intermediate_cert_pem: string;
    intermediate_key_pem: string;
    intermediate_passphrase: string;
  }

  export function emptyImport(): CAImport {
    return {
      way: 'root',
      root_cert_pem: '',
      root_key_pem: '',
      passphrase: '',
      intermediate_cert_pem: '',
      intermediate_key_pem: '',
      intermediate_passphrase: ''
    };
  }

  /** Nur die Felder des gewählten Wegs an die API schicken */
  export function importBody(v: CAImport): Record<string, string> {
    const body: Record<string, string> = { root_cert_pem: v.root_cert_pem };
    if (v.way === 'root') {
      body.root_key_pem = v.root_key_pem;
      body.passphrase = v.passphrase;
    } else {
      body.intermediate_cert_pem = v.intermediate_cert_pem;
      body.intermediate_key_pem = v.intermediate_key_pem;
      body.intermediate_passphrase = v.intermediate_passphrase;
    }
    return body;
  }

  export function importReady(v: CAImport): boolean {
    if (!v.root_cert_pem.trim()) return false;
    return v.way === 'root' ? !!v.root_key_pem.trim() : !!(v.intermediate_cert_pem.trim() && v.intermediate_key_pem.trim());
  }
</script>

<script lang="ts">
  interface Props {
    value: CAImport;
    /** eindeutige Namen für die Radio-Gruppe */
    id: string;
  }

  let { value = $bindable(), id }: Props = $props();

  type PemField = 'root_cert_pem' | 'root_key_pem' | 'intermediate_cert_pem' | 'intermediate_key_pem';

  async function readFile(e: Event, field: PemField) {
    const f = (e.currentTarget as HTMLInputElement).files?.[0];
    if (f) value[field] = await f.text();
  }
</script>

<div class="import">
  <fieldset class="ways">
    <legend class="label">Was liegt vor?</legend>
    <label class="check">
      <input type="radio" name={`${id}-way`} value="root" bind:group={value.way} />
      Root-Zertifikat und Root-Schlüssel – Tesseract erzeugt daraus sein Zwischenzertifikat und vergisst den Schlüssel sofort
    </label>
    <label class="check">
      <input type="radio" name={`${id}-way`} value="intermediate" bind:group={value.way} />
      Root-Zertifikat und ein fertiges Zwischenzertifikat mit Schlüssel – der Root-Schlüssel bleibt in der vorhandenen PKI
    </label>
  </fieldset>

  <label class="field col">
    <span class="label">Root-Zertifikat (PEM)</span>
    <input class="input" type="file" accept=".pem,.crt,.cer,.txt" onchange={(e) => readFile(e, 'root_cert_pem')} />
    <textarea class="input mono pem" rows="3" bind:value={value.root_cert_pem} placeholder="-----BEGIN CERTIFICATE-----"></textarea>
  </label>

  {#if value.way === 'root'}
    <label class="field col">
      <span class="label">Root-Schlüssel (PEM, ECDSA oder RSA)</span>
      <input class="input" type="file" accept=".pem,.key,.txt" onchange={(e) => readFile(e, 'root_key_pem')} />
      <textarea class="input mono pem" rows="3" bind:value={value.root_key_pem} placeholder="-----BEGIN ENCRYPTED PRIVATE KEY-----"></textarea>
    </label>
    <label class="field col">
      <span class="label">Passphrase des Root-Schlüssels (leer, wenn unverschlüsselt)</span>
      <input class="input" type="password" autocomplete="off" bind:value={value.passphrase} />
    </label>
  {:else}
    <label class="field col">
      <span class="label">Zwischenzertifikat (PEM, vom Root oben ausgestellt)</span>
      <input class="input" type="file" accept=".pem,.crt,.cer,.txt" onchange={(e) => readFile(e, 'intermediate_cert_pem')} />
      <textarea class="input mono pem" rows="3" bind:value={value.intermediate_cert_pem} placeholder="-----BEGIN CERTIFICATE-----"></textarea>
    </label>
    <label class="field col">
      <span class="label">Schlüssel des Zwischenzertifikats (PEM)</span>
      <input class="input" type="file" accept=".pem,.key,.txt" onchange={(e) => readFile(e, 'intermediate_key_pem')} />
      <textarea class="input mono pem" rows="3" bind:value={value.intermediate_key_pem} placeholder="-----BEGIN PRIVATE KEY-----"></textarea>
    </label>
    <label class="field col">
      <span class="label">Passphrase dieses Schlüssels (leer, wenn unverschlüsselt)</span>
      <input class="input" type="password" autocomplete="off" bind:value={value.intermediate_passphrase} />
    </label>
  {/if}
</div>

<style>
  .import {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .ways {
    border: 0;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .ways .check {
    align-items: flex-start;
    line-height: 1.45;
    font-size: 13px;
  }
  .col {
    flex-direction: column;
    gap: 6px;
  }
  .label {
    font-size: 13px;
    color: var(--text-muted);
  }
  .pem {
    font-size: 11px;
    resize: vertical;
  }
</style>
