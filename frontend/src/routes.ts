// Echte Seiten (pages/) und die Screens aus dem Design-Canvas „Caddy Control“ (screens/).
import type { Component } from "svelte";
import Login from "./screens/Login.svelte";
import Main from "./screens/Main.svelte";
import Hosts from "./screens/Hosts.svelte";
import HostSecurity from "./screens/HostSecurity.svelte";
import HostHistory from "./screens/HostHistory.svelte";
import HostNew1 from "./screens/HostNew1.svelte";
import HostNew2 from "./screens/HostNew2.svelte";
import HostNew3 from "./screens/HostNew3.svelte";
import Users from "./screens/Users.svelte";
import Devices from "./screens/Devices.svelte";
import Access from "./screens/Access.svelte";
import Invite1 from "./screens/Invite1.svelte";
import Invite2 from "./screens/Invite2.svelte";
import Invite3 from "./screens/Invite3.svelte";
import Invite4 from "./screens/Invite4.svelte";
import Invite3m from "./screens/Invite3m.svelte";
import Invite4m from "./screens/Invite4m.svelte";
import Nodes from "./screens/Nodes.svelte";
import Stats from "./screens/Stats.svelte";
import StatsTraffic from "./screens/StatsTraffic.svelte";
import StatsUsage from "./screens/StatsUsage.svelte";
import Logs from "./screens/Logs.svelte";
import Audit from "./screens/Audit.svelte";
import Settings from "./screens/Settings.svelte";
import SettingsIntegrations from "./screens/SettingsIntegrations.svelte";
import SettingsCA from "./screens/SettingsCA.svelte";
import SettingsNotify from "./screens/SettingsNotify.svelte";
import SettingsMetrics from "./screens/SettingsMetrics.svelte";
import SettingsBackup from "./screens/SettingsBackup.svelte";
import Kit from "./screens/Kit.svelte";

import LoginPage from "./pages/Login.svelte";
import OverviewPage from "./pages/Overview.svelte";
import HostsPage from "./pages/Hosts.svelte";
import HostWizardPage from "./pages/HostWizard.svelte";
import HostEditPage from "./pages/HostEdit.svelte";
import HostHistoryPage from "./pages/HostHistory.svelte";
import SettingsPage from "./pages/Settings.svelte";
import AuditPage from "./pages/Audit.svelte";
import UsersPage from "./pages/Users.svelte";
import DevicesPage from "./pages/Devices.svelte";
import SettingsCAPage from "./pages/SettingsCA.svelte";
import AccessPage from "./pages/Access.svelte";
import HostSecurityPage from "./pages/HostSecurity.svelte";
import SettingsIntegrationsPage from "./pages/SettingsIntegrations.svelte";
import CertificatesPage from "./pages/Certificates.svelte";
import NodesPage from "./pages/Nodes.svelte";
import LogsPage from "./pages/Logs.svelte";
import StatsSecurityPage from "./pages/StatsSecurity.svelte";
import StatsTrafficPage from "./pages/StatsTraffic.svelte";
import StatsUsagePage from "./pages/StatsUsage.svelte";
import SettingsMetricsPage from "./pages/SettingsMetrics.svelte";
import SettingsNotifyPage from "./pages/SettingsNotify.svelte";
import SettingsBackupPage from "./pages/SettingsBackup.svelte";
import SettingsAuthPage from "./pages/SettingsAuth.svelte";
import SettingsLdapPage from "./pages/SettingsLdap.svelte";

export interface Page {
  /** Muster ohne "#/", Parameter mit ":" – z. B. "hosts/:id/history" */
  pattern: string;
  title: string;
  component: Component<any>;
  /** ohne Anmeldung erreichbar */
  public?: boolean;
}

/** Fertig angebundene Seiten (Phase 1). Sie haben Vorrang vor den Prototyp-Screens. */
export const pages: Page[] = [
  { pattern: "login", title: "Anmelden", component: LoginPage, public: true },
  { pattern: "", title: "Übersicht", component: OverviewPage },
  { pattern: "hosts", title: "Proxy-Hosts", component: HostsPage },
  { pattern: "hosts/new", title: "Host anlegen", component: HostWizardPage },
  { pattern: "certificates", title: "Zertifikate", component: CertificatesPage },
  { pattern: "nodes", title: "Nodes", component: NodesPage },
  { pattern: "logs", title: "Logs", component: LogsPage },
  { pattern: "stats", title: "Statistik · Sicherheit", component: StatsSecurityPage },
  { pattern: "stats-traffic", title: "Statistik · Traffic & Leistung", component: StatsTrafficPage },
  { pattern: "stats-usage", title: "Statistik · Nutzung", component: StatsUsagePage },
  { pattern: "settings-metrics", title: "Einstellungen · Metriken", component: SettingsMetricsPage },
  { pattern: "settings-notify", title: "Einstellungen · Benachrichtigungen", component: SettingsNotifyPage },
  { pattern: "settings-backup", title: "Einstellungen · Backup", component: SettingsBackupPage },
  { pattern: "settings-auth", title: "Einstellungen · Anmeldung", component: SettingsAuthPage },
  { pattern: "settings-ldap", title: "Einstellungen · LDAP", component: SettingsLdapPage },
  { pattern: "hosts/:id", title: "Host bearbeiten", component: HostEditPage },
  { pattern: "hosts/:id/access", title: "Host · Zugriff", component: HostEditPage },
  { pattern: "hosts/:id/history", title: "Host · Verlauf", component: HostHistoryPage },
  { pattern: "hosts/:id/security", title: "Host · Sicherheit", component: HostSecurityPage },
  { pattern: "settings-integrations", title: "Einstellungen · Integrationen", component: SettingsIntegrationsPage },
  { pattern: "settings", title: "Einstellungen", component: SettingsPage },
  { pattern: "audit", title: "Audit-Log", component: AuditPage },
  { pattern: "users", title: "Nutzer", component: UsersPage },
  { pattern: "users/:id", title: "Nutzer", component: UsersPage },
  { pattern: "devices", title: "Geräte", component: DevicesPage },
  { pattern: "access", title: "Zugriffsmatrix", component: AccessPage },
  { pattern: "settings-ca", title: "Einstellungen · Zertifizierungsstelle", component: SettingsCAPage },
];

export function matchPage(path: string): { page: Page; params: Record<string, string> } | null {
  const parts = path.split("/").filter(Boolean);
  for (const page of pages) {
    const pp = page.pattern.split("/").filter(Boolean);
    if (pp.length !== parts.length) continue;
    const params: Record<string, string> = {};
    if (pp.every((seg, i) => (seg.startsWith(":") ? ((params[seg.slice(1)] = parts[i]), true) : seg === parts[i]))) {
      return { page, params };
    }
  }
  return null;
}

export interface Route {
  /** Hash-Pfad ohne "#/" – leer = Übersicht */
  path: string;
  title: string;
  component: Component<any>;
}

/** Prototyp-Screens aus dem Design – auch unter #/design/<pfad> erreichbar. */
export const routes: Route[] = [
  { path: "login", title: "Login", component: Login },
  { path: "", title: "Übersicht", component: Main },
  { path: "hosts", title: "Proxy-Hosts", component: Hosts },
  { path: "host-security", title: "Host · Sicherheit (IP-Filter, Coraza, Authelia)", component: HostSecurity },
  { path: "host-history", title: "Host · Verlauf & Zurücksetzen", component: HostHistory },
  { path: "host-new-1", title: "Host anlegen 1 · Domain & Ziel", component: HostNew1 },
  { path: "host-new-2", title: "Host anlegen 2 · Zugriff", component: HostNew2 },
  { path: "host-new-3", title: "Host anlegen 3 · Prüfen & übertragen", component: HostNew3 },
  { path: "users", title: "Nutzer", component: Users },
  { path: "devices", title: "Geräte", component: Devices },
  { path: "access", title: "Zugriffsmatrix", component: Access },
  { path: "invite-1", title: "Einladung 1 · Admin: Person anlegen", component: Invite1 },
  { path: "invite-2", title: "Einladung 2 · Admin: Link teilen", component: Invite2 },
  { path: "invite-3", title: "Einladung 3 · Gast: Gerät registrieren", component: Invite3 },
  { path: "invite-4", title: "Einladung 4 · Gast: Zertifikat installieren", component: Invite4 },
  { path: "invite-3m", title: "Einladung 3 · Handy", component: Invite3m },
  { path: "invite-4m", title: "Einladung 4 · Handy", component: Invite4m },
  { path: "nodes", title: "Nodes", component: Nodes },
  { path: "stats", title: "Statistik · Sicherheit", component: Stats },
  { path: "stats-traffic", title: "Statistik · Traffic & Leistung", component: StatsTraffic },
  { path: "stats-usage", title: "Statistik · Nutzung", component: StatsUsage },
  { path: "logs", title: "Statistik · Logs", component: Logs },
  { path: "audit", title: "Audit-Log", component: Audit },
  { path: "settings", title: "Einstellungen · Allgemein", component: Settings },
  { path: "settings-integrations", title: "Einstellungen · Integrationen", component: SettingsIntegrations },
  { path: "settings-ca", title: "Einstellungen · Zertifizierungsstelle", component: SettingsCA },
  { path: "settings-notify", title: "Einstellungen · Benachrichtigungen", component: SettingsNotify },
  { path: "settings-metrics", title: "Einstellungen · Metriken (Prometheus)", component: SettingsMetrics },
  { path: "settings-backup", title: "Einstellungen · Backup", component: SettingsBackup },
  { path: "kit", title: "Komponenten · Übersicht", component: Kit },
];

/** Alternative Pfade */
export const aliases: Record<string, string> = {
  main: "",
  uebersicht: "",
  "host-new-1": "hosts/new",
  "host-new-2": "hosts/new",
  "host-new-3": "hosts/new",
};
