#!/usr/bin/env python3
"""Katalog der OWASP-CRS-Regeln erzeugen – passend zur Version im Caddy-Image.

Das Caddy-Image (docker/caddy/Dockerfile) baut coraza-caddy in einer festen Version
(ARG CORAZA_CADDY_VERSION). Welche CRS-Version darin steckt, steht in dessen go.mod
(github.com/corazawaf/coraza-coreruleset/v4). Dieses Skript liest beides und erzeugt aus den
Regel-Dateien genau dieser Version eine JSON-Liste: ID, Kategorie, Meldung, Paranoia-Level,
Schweregrad, Phase, Tags.

    python scripts/crs_catalog.py                       # Version aus docker/caddy/Dockerfile
    python scripts/crs_catalog.py --coraza-caddy v2.6.2 --out src/tesseract/data/crs_catalog.json

Läuft beim Build des Controller-Images; der erzeugte Katalog liegt außerdem im Repository,
damit Tests und Entwicklung ohne Netz gehen. Nur Standardbibliothek.
"""

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "docker" / "caddy" / "Dockerfile"
OUT = ROOT / "backend" / "src" / "tesseract" / "data" / "crs_catalog.json"
RAW = "https://raw.githubusercontent.com/corazawaf/{repo}/{ref}/{path}"
API_TREE = "https://api.github.com/repos/corazawaf/coraza-coreruleset/git/trees/{ref}?recursive=1"

# Kategorie nach Regelblock (942xxx → SQL-Injection) – wie die Statistik
CATEGORIES = {
    905: "Ausnahmen",
    911: "Methoden",
    913: "Scanner",
    920: "Protokoll",
    921: "Protokoll-Angriff",
    922: "Multipart",
    930: "LFI (lokale Dateien)",
    931: "RFI (fremde Dateien)",
    932: "RCE (Befehle)",
    933: "PHP",
    934: "Generisch (Node.js, Ruby …)",
    941: "XSS",
    942: "SQL-Injection",
    943: "Session-Fixation",
    944: "Java",
    949: "Auswertung",
    950: "Datenleck",
    951: "Datenleck (SQL)",
    952: "Datenleck (Java)",
    953: "Datenleck (PHP)",
    954: "Datenleck (IIS)",
    955: "Web-Shell",
    956: "Datenleck (Ruby)",
    959: "Auswertung",
    980: "Korrelation",
}


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "tesseract-crs-catalog"})
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 – feste https-Adressen
        return r.read().decode("utf-8")


def coraza_caddy_version(dockerfile: Path = DOCKERFILE) -> str:
    m = re.search(r"^ARG CORAZA_CADDY_VERSION=(\S+)", dockerfile.read_text(encoding="utf-8"), re.M)
    if not m:
        raise SystemExit(f"CORAZA_CADDY_VERSION fehlt in {dockerfile}")
    return m.group(1)


def crs_module_version(coraza_caddy: str) -> str:
    gomod = _get(RAW.format(repo="coraza-caddy", ref=coraza_caddy, path="go.mod"))
    m = re.search(r"github\.com/corazawaf/coraza-coreruleset/v4 (v\S+)", gomod)
    if not m:
        raise SystemExit("coraza-coreruleset nicht in go.mod von coraza-caddy gefunden")
    return m.group(1)


def _split_actions(s: str) -> list[str]:
    """Aktionen an Kommas trennen – außer innerhalb von '…'."""
    out, cur, quoted = [], "", False
    for ch in s:
        if ch == "'" and not cur.endswith("\\"):
            quoted = not quoted
        if ch == "," and not quoted:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def _unquote(v: str) -> str:
    v = v.strip()
    return v[1:-1] if len(v) >= 2 and v[0] == v[-1] == "'" else v


def parse_rules(text: str, file: str) -> list[dict]:
    """SecRule-/SecAction-Blöcke einer CRS-Datei → Regeln mit ID und Meldung."""
    # Fortsetzungszeilen zusammenfügen
    joined = re.sub(r"\\\r?\n\s*", " ", text)
    rules = []
    for line in joined.splitlines():
        line = line.strip()
        if not line.startswith(("SecRule ", "SecAction")):
            continue
        # Aktionen = letzter Block in "…"
        m = re.search(r'"((?:[^"\\]|\\.)*)"\s*$', line)
        if not m:
            continue
        actions = _split_actions(m.group(1))
        fields: dict[str, list[str]] = {}
        for a in actions:
            key, _, val = a.partition(":")
            fields.setdefault(key.strip(), []).append(_unquote(val))
        if "id" not in fields:
            continue  # verkettete Folgeregel
        msg = (fields.get("msg") or [""])[0]
        if not msg:
            continue  # interne Steuerregeln (Paranoia-Sprünge, Initialisierung)
        rid = int(fields["id"][0])
        tags = fields.get("tag", [])
        pl = next((int(t.split("/")[1]) for t in tags if t.startswith("paranoia-level/")), None)
        rules.append(
            {
                "id": rid,
                "file": file,
                "category": CATEGORIES.get(rid // 1000, "Sonstige"),
                "msg": msg,
                "paranoia": pl,
                "severity": (fields.get("severity") or [""])[0].upper() or None,
                "phase": int(fields["phase"][0]) if fields.get("phase") else None,
                "tags": [t for t in tags if not t.startswith(("paranoia-level/", "OWASP_CRS"))],
            }
        )
    return rules


def build(coraza_caddy: str) -> dict:
    crs = crs_module_version(coraza_caddy)
    tree = json.loads(_get(API_TREE.format(ref=crs)))
    files = sorted(
        p["path"]
        for p in tree["tree"]
        if p["path"].startswith("rules/@owasp_crs/") and p["path"].endswith(".conf")
    )
    rules: list[dict] = []
    for path in files:
        text = _get(RAW.format(repo="coraza-coreruleset", ref=crs, path=path))
        rules += parse_rules(text, path.rsplit("/", 1)[1])
    rules.sort(key=lambda r: r["id"])
    return {"coraza_caddy": coraza_caddy, "crs": crs.lstrip("v"), "rules": rules}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--coraza-caddy", help="Version (Standard: aus docker/caddy/Dockerfile)")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--dockerfile", default=str(DOCKERFILE), help="Dockerfile des Caddy-Images")
    args = ap.parse_args(argv)
    version = args.coraza_caddy or coraza_caddy_version(Path(args.dockerfile))
    data = build(version)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(data['rules'])} Regeln aus CRS {data['crs']} (coraza-caddy {version}) -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
