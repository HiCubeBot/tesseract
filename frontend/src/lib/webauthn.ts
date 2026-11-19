/**
 * WebAuthn (Passkeys) im Browser: Optionen vom Server (JSON, Base64url) in die Form bringen,
 * die navigator.credentials erwartet, und die Antwort wieder als JSON zurück.
 * Eigene Umrechnung statt parseCreationOptionsFromJSON – läuft so auch in älteren Browsern.
 */

type Json = Record<string, any>;

function fromB64url(s: string): ArrayBuffer {
  const b64 = s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4);
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out.buffer;
}

function toB64url(buf: ArrayBuffer | null): string {
  if (!buf) return '';
  const bytes = new Uint8Array(buf);
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export function supported(): boolean {
  return typeof window !== 'undefined' && !!window.PublicKeyCredential && window.isSecureContext;
}

/** Passkey anlegen. */
export async function create(options: Json): Promise<Json> {
  const publicKey: PublicKeyCredentialCreationOptions = {
    ...(options as PublicKeyCredentialCreationOptions),
    challenge: fromB64url(options.challenge),
    user: { ...options.user, id: fromB64url(options.user.id) },
    excludeCredentials: (options.excludeCredentials ?? []).map((c: Json) => ({ ...c, id: fromB64url(c.id) }))
  };
  const cred = (await navigator.credentials.create({ publicKey })) as PublicKeyCredential | null;
  if (!cred) throw new Error('Abgebrochen');
  const r = cred.response as AuthenticatorAttestationResponse;
  return {
    id: cred.id,
    rawId: toB64url(cred.rawId),
    type: cred.type,
    response: {
      clientDataJSON: toB64url(r.clientDataJSON),
      attestationObject: toB64url(r.attestationObject),
      transports: typeof r.getTransports === 'function' ? r.getTransports() : []
    },
    clientExtensionResults: cred.getClientExtensionResults()
  };
}

/** Mit Passkey anmelden (auffindbare Passkeys – kein Name nötig). */
export async function get(options: Json): Promise<Json> {
  const publicKey: PublicKeyCredentialRequestOptions = {
    ...(options as PublicKeyCredentialRequestOptions),
    challenge: fromB64url(options.challenge),
    allowCredentials: (options.allowCredentials ?? []).map((c: Json) => ({ ...c, id: fromB64url(c.id) }))
  };
  const cred = (await navigator.credentials.get({ publicKey })) as PublicKeyCredential | null;
  if (!cred) throw new Error('Abgebrochen');
  const r = cred.response as AuthenticatorAssertionResponse;
  return {
    id: cred.id,
    rawId: toB64url(cred.rawId),
    type: cred.type,
    response: {
      clientDataJSON: toB64url(r.clientDataJSON),
      authenticatorData: toB64url(r.authenticatorData),
      signature: toB64url(r.signature),
      userHandle: toB64url(r.userHandle)
    },
    clientExtensionResults: cred.getClientExtensionResults()
  };
}

/** Verständliche Meldung für typische Browser-Fehler. */
export function explain(e: unknown): string {
  if (e instanceof DOMException) {
    if (e.name === 'NotAllowedError') return 'Abgebrochen oder keine Zustimmung am Gerät.';
    if (e.name === 'InvalidStateError') return 'Dieser Passkey ist auf dem Gerät schon eingetragen.';
    if (e.name === 'SecurityError') return 'Passkeys gehen nur über HTTPS und mit der richtigen Domain.';
  }
  return e instanceof Error ? e.message : String(e);
}
