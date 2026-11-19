/** Anmeldestatus des Admins. */
import { api, onUnauthorized, type Me } from './api';
import { router } from './router.svelte';

class SessionState {
  user = $state<Me | null>(null);
  checked = $state(false);

  constructor() {
    onUnauthorized(() => {
      this.user = null;
      if (router.path !== 'login') router.go('login');
    });
  }

  async check() {
    try {
      this.user = await api.get<Me>('/auth/me');
    } catch {
      this.user = null;
    } finally {
      this.checked = true;
    }
  }

  async login(username: string, password: string, remember: boolean) {
    this.user = await api.post<Me>('/auth/login', { username, password, remember });
  }

  /** Nach Passkey-/SSO-Anmeldung: Benutzer übernehmen */
  set(user: Me) {
    this.user = user;
  }

  async logout() {
    try {
      await api.post('/auth/logout');
    } finally {
      this.user = null;
      router.go('login');
    }
  }
}

export const session = new SessionState();
