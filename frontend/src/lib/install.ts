/** Plattform erkennen und Installationsanleitungen für das Geräte-Zertifikat. */

import { t } from './i18n';
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
    other: t('Gerät')
  };
  return `${first}s ${device[p]}`;
}

export const INSTALL_STEPS: Record<Platform, { title: string; steps: string[]; browser?: string }> = {
  ios: {
    title: t('iPhone / iPad'),
    steps: [
      t('Zertifikat herunterladen – Safari fragt „Profil laden?“ → Erlauben.'),
      t('Einstellungen öffnen → oben „Profil geladen“ antippen (oder Allgemein › VPN & Geräteverwaltung).'),
      t('„Installieren“ antippen, Gerätecode eingeben und das Passwort von dieser Seite eintragen.'),
      t('Fertig. Beim ersten Aufruf eines Dienstes fragt Safari, welches Zertifikat es verwenden soll – deins wählen.')
    ],
    browser: t('Bitte Safari verwenden – andere Browser auf iOS können das Zertifikat nicht installieren.')
  },
  android: {
    title: t('Android'),
    steps: [
      t('Zertifikat herunterladen.'),
      t('Einstellungen › Sicherheit › Weitere Sicherheitseinstellungen › Verschlüsselung & Anmeldedaten › Zertifikat installieren.'),
      t('„VPN- und App-Nutzerzertifikat“ wählen, die heruntergeladene .p12-Datei auswählen und das Passwort eintragen.'),
      t('Beim ersten Aufruf eines Dienstes fragt Chrome nach dem Zertifikat – deins wählen und „Zulassen“.')
    ],
    browser: t('Die Menünamen unterscheiden sich je nach Hersteller leicht – in den Einstellungen nach „Zertifikat“ suchen hilft.')
  },
  macos: {
    title: t('Mac'),
    steps: [
      t('Zertifikat herunterladen und die .p12-Datei doppelklicken.'),
      t('Die Schlüsselbundverwaltung öffnet sich: Schlüsselbund „Anmeldung“ wählen und das Passwort eintragen.'),
      t('Safari und Chrome verwenden das Zertifikat automatisch und fragen beim ersten Mal nach.')
    ],
    browser: t('Firefox hat einen eigenen Speicher: Einstellungen › Datenschutz & Sicherheit › Zertifikate anzeigen › Ihre Zertifikate › Importieren.')
  },
  windows: {
    title: t('Windows'),
    steps: [
      t('Zertifikat herunterladen und die .p12-Datei doppelklicken.'),
      t('Im Zertifikatimport-Assistenten „Aktueller Benutzer“ wählen, Passwort eintragen, Speicherort automatisch wählen lassen.'),
      t('Edge und Chrome verwenden das Zertifikat automatisch und fragen beim ersten Mal nach.')
    ],
    browser: t('Firefox hat einen eigenen Speicher: Einstellungen › Datenschutz & Sicherheit › Zertifikate anzeigen › Ihre Zertifikate › Importieren.')
  },
  linux: {
    title: t('Linux'),
    steps: [
      t('Zertifikat herunterladen.'),
      t('Firefox: Einstellungen › Datenschutz & Sicherheit › Zertifikate anzeigen › Ihre Zertifikate › Importieren.'),
      t('Chrome/Chromium: chrome://settings/certificates › Ihre Zertifikate › Importieren.')
    ]
  },
  other: {
    title: t('Anderes Gerät'),
    steps: [
      t('Zertifikat herunterladen.'),
      t('Die .p12-Datei im Zertifikatsspeicher des Systems oder Browsers importieren und das Passwort eintragen.')
    ]
  }
};
