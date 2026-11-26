"""`.env` auf den Stand der aktuellen `.env.example` bringen – ohne eigene Werte zu verlieren.

Grundlage ist die Vorlage (Aufbau, Reihenfolge, Kommentare):
- Jede in der alten `.env` gesetzte Variable wird mit ihrem Wert übernommen – exakt, auch mit
  Anführungszeichen, `#`, `=` oder Leerzeichen. Steht sie in der Vorlage nur auskommentiert
  (`# TESSERACT_…=`), wird dort die erste solche Zeile aktiviert.
- Neue Variablen der Vorlage bleiben, wie sie dort stehen (Standardwert bzw. auskommentiert).
- Variablen der alten `.env`, die die Vorlage nicht kennt, landen in einem eigenen Abschnitt am
  Ende – nichts geht verloren.
- Vorher wird die alte Datei gesichert (`.env.bak-JJJJMMTT-HHMMSS`); `--dry-run` zeigt nur,
  was sich ändern würde. Geheimnisse erscheinen in der Ausgabe nie im Klartext.

Aufruf: `tesseract env migrate .env [--example .env.example] [--dry-run]`
"""

import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# KEY=wert, optional mit „export “ davor
_ASSIGN = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
# auskommentierte Zuweisung in der Vorlage: „# KEY=wert“
_COMMENTED = re.compile(r"^\s*#\s*([A-Z_][A-Z0-9_]*)=(.*)$")
_SECRET = re.compile(r"PASSWORD|PASSPHRASE|TOKEN|SECRET|_KEY\b|_KEY_|APIKEY|CREDENTIAL", re.I)

OBSOLETE_HEADER = (
    "# ---------- Eigene/veraltete Einträge ----------\n"
    "# Diese Variablen stehen nicht (mehr) in der .env.example. Sie wurden bei der Migration\n"
    "# unverändert übernommen – prüfen und bei Bedarf entfernen.\n"
)


@dataclass
class Result:
    text: str
    kept: list[str] = field(default_factory=list)  # Wert aus der alten .env übernommen
    activated: list[str] = field(default_factory=list)  # in der Vorlage auskommentiert, jetzt aktiv
    new: list[str] = field(default_factory=list)  # nur in der Vorlage (Standard)
    obsolete: list[str] = field(default_factory=list)  # nur in der alten .env
    values: dict[str, str] = field(default_factory=dict)  # alte Werte (für die Anzeige)

    @property
    def changed(self) -> bool:
        return bool(self.new or self.obsolete or self.activated)


def parse_values(text: str) -> dict[str, str]:
    """Gesetzte Variablen einer .env: Name → Rohwert (alles nach dem ersten „=“, unverändert).
    Kommt ein Name mehrfach vor, gilt wie bei Docker Compose die letzte Zuweisung."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        m = _ASSIGN.match(line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def migrate(old_text: str, example_text: str) -> Result:
    old = parse_values(old_text)
    res = Result(text="", values=old)
    seen: set[str] = set()
    lines_out: list[str] = []
    # Variablen, die die Vorlage aktiv setzt – auskommentierte Zeilen dafür nicht aktivieren
    active_in_example = set(parse_values(example_text))

    for line in example_text.splitlines():
        m = _ASSIGN.match(line) if not line.lstrip().startswith("#") else None
        if m:
            name = m.group(1)
            if name in seen:
                # doppelte aktive Zeile in der Vorlage: nur die erste trägt den Wert
                lines_out.append(f"# {line}")
                continue
            seen.add(name)
            if name in old:
                lines_out.append(f"{name}={old[name]}")
                res.kept.append(name)
            else:
                lines_out.append(line)
                res.new.append(name)
            continue
        c = _COMMENTED.match(line)
        if c:
            name = c.group(1)
            if name in old and name not in seen and name not in active_in_example:
                seen.add(name)
                lines_out.append(f"{name}={old[name]}")
                res.activated.append(name)
                continue
            if (
                name not in old
                and name not in seen
                and name not in active_in_example
                and name not in res.new
            ):
                res.new.append(name)
        lines_out.append(line)

    obsolete = [n for n in old if n not in seen]
    if obsolete:
        while lines_out and not lines_out[-1].strip():
            lines_out.pop()
        lines_out += ["", OBSOLETE_HEADER.rstrip("\n")]
        lines_out += [f"{n}={old[n]}" for n in obsolete]
        res.obsolete = obsolete
    res.text = "\n".join(lines_out) + "\n"
    return res


def mask(name: str, value: str) -> str:
    """Wert für die Ausgabe – Geheimnisse nie im Klartext."""
    if not value.strip():
        return "(leer)"
    if _SECRET.search(name):
        return "••••••"
    return value if len(value) <= 60 else value[:57] + "…"


def report(res: Result) -> str:
    rows: list[str] = []
    for title, names, show in (
        ("übernommen", res.kept, True),
        ("aktiviert (war in der Vorlage auskommentiert)", res.activated, True),
        ("neu aus der Vorlage", res.new, False),
        ("eigene/veraltete (bleiben am Ende erhalten)", res.obsolete, True),
    ):
        if not names:
            continue
        rows.append(f"{title}: {len(names)}")
        for n in names:
            rows.append(f"  {n}={mask(n, res.values[n])}" if show else f"  {n}")
    return "\n".join(rows) if rows else "nichts zu tun"


def default_example() -> Path | None:
    """Vorlage suchen: TESSERACT_ENV_EXAMPLE, im Image /app/.env.example, im Checkout das Repo."""
    here = Path(__file__).resolve()
    candidates = [
        os.environ.get("TESSERACT_ENV_EXAMPLE", ""),
        "/app/.env.example",
        # Checkout: backend/src/tesseract/envmigrate.py → Repo-Wurzel
        str(here.parents[3] / ".env.example") if len(here.parents) > 3 else "",
    ]
    for c in candidates:
        if c and Path(c).is_file():
            return Path(c)
    return None


def run(env_path: str, example: str | None, dry_run: bool, now: datetime | None = None) -> int:
    env = Path(env_path)
    ex = Path(example) if example else default_example()
    if ex is None or not ex.is_file():
        print("Keine .env.example gefunden – mit --example angeben.")
        return 2
    if not env.is_file():
        print(f"{env} gibt es nicht – einfach die Vorlage kopieren: cp {ex} {env}")
        return 2
    old_text = env.read_text(encoding="utf-8")
    res = migrate(old_text, ex.read_text(encoding="utf-8"))
    print(f"Vorlage: {ex}")
    print(report(res))
    if res.text == old_text:
        print("\n.env ist schon auf dem Stand der Vorlage.")
        return 0
    if dry_run:
        print("\nProbelauf – nichts geschrieben.")
        return 0
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    backup = env.with_name(f"{env.name}.bak-{stamp}")
    shutil.copy2(env, backup)
    env.write_text(res.text, encoding="utf-8", newline="\n")
    print(f"\nGeschrieben: {env} (Sicherung: {backup})")
    return 0
