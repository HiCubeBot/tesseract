/**
 * Kleine Brücke für die aus dem Design übernommenen Screens.
 *
 * Die Screens im Design-Canvas haben ihre Logik als Klasse mit renderVals()
 * (React-artig: this.props, this.state, this.setState). Damit sie 1:1 laufen,
 * bleibt die Klasse erhalten und diese Funktion macht sie reaktiv.
 *
 * Beim Ausbau einer Seite kann man die Klasse nach und nach durch normales
 * Svelte ersetzen ($state, $derived) – die Komponenten unter lib/components
 * sind bereits so geschrieben.
 */
export class DCLogic<P extends Record<string, any> = Record<string, any>, S = any> {
  props: P = {} as P;
  state: S | null = null;
  _bump?: () => void;

  setState(patch: Partial<S> | ((s: S | null, p: P) => Partial<S>)) {
    const p = typeof patch === 'function' ? patch(this.state, this.props) : patch;
    this.state = { ...((this.state ?? {}) as S), ...p } as S;
    this._bump?.();
  }

  forceUpdate() {
    this._bump?.();
  }

  renderVals(): Record<string, any> {
    return {};
  }
}

export function useDC<T extends DCLogic>(Ctor: new () => T, getProps: () => Record<string, any> = () => ({})) {
  const inst = new Ctor();
  let tick = $state(0);
  inst._bump = () => {
    tick++;
  };
  return {
    get vals(): Record<string, any> {
      void tick;
      inst.props = getProps() ?? {};
      return inst.renderVals();
    }
  };
}
