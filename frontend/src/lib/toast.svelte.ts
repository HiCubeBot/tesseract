/** Kurze Rückmeldungen („Gespeichert & übertragen“) unten rechts. */

export interface Toast {
  id: number;
  tone: 'ok' | 'warn' | 'bad' | 'info';
  text: string;
}

class Toasts {
  items = $state<Toast[]>([]);
  #next = 1;

  show(tone: Toast['tone'], text: string, ms = 5000) {
    const id = this.#next++;
    this.items.push({ id, tone, text });
    if (ms > 0) setTimeout(() => this.dismiss(id), ms);
  }

  dismiss(id: number) {
    this.items = this.items.filter((t) => t.id !== id);
  }
}

export const toasts = new Toasts();
