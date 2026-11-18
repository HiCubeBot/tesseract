/**
 * Minimaler Hash-Router ohne SvelteKit.
 * Routen sehen so aus: #/hosts, #/host-security …  ("#/" = Übersicht)
 * Links wie href="#" oder href="#abschnitt" ändern die Route nicht.
 */
function readPath(fallback = ''): string {
  const h = window.location.hash;
  if (h === '' || h === '#/') return '';
  if (h.startsWith('#/')) return decodeURIComponent(h.slice(2)).replace(/\/+$/, '');
  return fallback;
}

class Router {
  path = $state(readPath());

  constructor() {
    window.addEventListener('hashchange', () => {
      const next = readPath(this.path);
      if (next !== this.path) {
        this.path = next;
        window.scrollTo(0, 0);
      }
    });
  }

  go(path: string) {
    window.location.hash = '#/' + path.replace(/^\/+/, '');
  }
}

export const router = new Router();

/** Link-Ziel für eine Route, z. B. href('hosts') → "#/hosts" */
export const href = (path: string) => '#/' + path.replace(/^\/+/, '');
