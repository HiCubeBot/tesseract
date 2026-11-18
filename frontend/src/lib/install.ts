/** Plattform erkennen und Installationsanleitungen für das Geräte-Zertifikat. */

export type Platform = 'ios' | 'android' | 'macos' | 'windows' | 'linux' | 'other';

export function detectPlatform(ua = navigator.userAgent): Platform {
  if (/iPhone|iPad|iPod/i.test(ua)) return 'ios';
  // iPadOS meldet sich als Mac – mit Touch
  if (/Macintosh/i.test(ua) && navigator.maxTouchPoints > 1) return 'ios';
  if (/Android/i.test(ua)) return 'android';
  if (/Mac OS X|Macintosh/i.test(ua)) return 'macos';
  if (/Windows/i.test(ua)) return 'windows';
  if (/Linux|X11/i.test(ua)) return 'linux';
  return 'other';
}

export function suggestedName(p: Platform, person: string): string {
  const first = person.split(/\s+/)[0];
  const device: Record<Platform, string> = {
    ios: /iPad/i.test(navigator.userAgent) ? 'iPad' : 'iPhone',
    android: 'Android-Handy',
    macos: 'Mac',
    windows: 'Windows-PC',
    linux: 'Linux-PC',
    other: 'Gerät'
  };
  return `${first}s ${device[p]}`;
}

export const INSTALL_STEPS: Record<Platform, { title: string; steps: string[]; browser?: string }> = {
  ios: {
    title: 'iPhone / iPad',
    steps: [
      'Zertifikat herunterladen – Safari fragt „Profil laden?“ → Erlauben.',
      'Einstellungen öffnen → oben „Profil geladen“ antippen (oder Allgemein › VPN & Geräteverwaltung).',
      '„Installieren“ antippen, Gerätecode eingeben und das Passwort von dieser Seite eintragen.',
      'Fertig. Beim ersten Aufruf eines Dienstes fragt Safari, welches Zertifikat es verwenden soll – deins wählen.'
    ],
    browser: 'Bitte Safari verwenden – andere Browser auf iOS können das Zertifikat nicht installieren.'
  },
  android: {
    title: 'Android',
    steps: [
      'Zertifikat herunterladen.',
      'Einstellungen › Sicherheit › Weitere Sicherheitseinstellungen › Verschlüsselung & Anmeldedaten › Zertifikat installieren.',
      '„VPN- und App-Nutzerzertifikat“ wählen, die heruntergeladene .p12-Datei auswählen und das Passwort eintragen.',
      'Beim ersten Aufruf eines Dienstes fragt Chrome nach dem Zertifikat – deins wählen und „Zulassen“.'
    ],
    browser: 'Die Menünamen unterscheiden sich je nach Hersteller leicht – in den Einstellungen nach „Zertifikat“ suchen hilft.'
  },
  macos: {
    title: 'Mac',
    steps: [
      'Zertifikat herunterladen und die .p12-Datei doppelklicken.',
      'Die Schlüsselbundverwaltung öffnet sich: Schlüsselbund „Anmeldung“ wählen und das Passwort eintragen.',
      'Safari und Chrome verwenden das Zertifikat automatisch und fragen beim ersten Mal nach.'
    ],
    browser: 'Firefox hat einen eigenen Speicher: Einstellungen › Datenschutz & Sicherheit › Zertifikate anzeigen › Ihre Zertifikate › Importieren.'
  },
  windows: {
    title: 'Windows',
    steps: [
      'Zertifikat herunterladen und die .p12-Datei doppelklicken.',
      'Im Zertifikatimport-Assistenten „Aktueller Benutzer“ wählen, Passwort eintragen, Speicherort automatisch wählen lassen.',
      'Edge und Chrome verwenden das Zertifikat automatisch und fragen beim ersten Mal nach.'
    ],
    browser: 'Firefox hat einen eigenen Speicher: Einstellungen › Datenschutz & Sicherheit › Zertifikate anzeigen › Ihre Zertifikate › Importieren.'
  },
  linux: {
    title: 'Linux',
    steps: [
      'Zertifikat herunterladen.',
      'Firefox: Einstellungen › Datenschutz & Sicherheit › Zertifikate anzeigen › Ihre Zertifikate › Importieren.',
      'Chrome/Chromium: chrome://settings/certificates › Ihre Zertifikate › Importieren.'
    ]
  },
  other: {
    title: 'Anderes Gerät',
    steps: [
      'Zertifikat herunterladen.',
      'Die .p12-Datei im Zertifikatsspeicher des Systems oder Browsers importieren und das Passwort eintragen.'
    ]
  }
};
