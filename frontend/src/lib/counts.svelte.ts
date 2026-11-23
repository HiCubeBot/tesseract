// Zahlen für die Seitenleiste (Hosts, Personen, Geräte, Nodes).
import { api } from './api';

export interface Counts {
  hosts: number;
  persons: number;
  devices: number;
  nodes: number;
}

class CountStore {
  value = $state<Counts | null>(null);
  #busy = false;

  /** Neu laden – bei jedem Seitenwechsel, Fehler bleiben still (die Zahlen sind nur Beiwerk). */
  async refresh(): Promise<void> {
    if (this.#busy) return;
    this.#busy = true;
    try {
      this.value = await api.get<Counts>('/counts');
    } catch {
      // nicht angemeldet o. Ä. – alte Zahlen behalten
    } finally {
      this.#busy = false;
    }
  }
}

export const counts = new CountStore();
