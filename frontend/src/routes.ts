// Alle Screens aus dem Design-Canvas „Caddy Control“ – Reihenfolge wie auf dem Canvas.
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

export interface Route {
  /** Hash-Pfad ohne "#/" – leer = Übersicht */
  path: string;
  title: string;
  component: Component<any>;
}

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
export const aliases: Record<string, string> = { main: "", uebersicht: "" };
