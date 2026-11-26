""".env nach einem Update auf den Stand der .env.example bringen (envmigrate.py)."""

from datetime import datetime
from pathlib import Path

from tesseract import envmigrate
from tesseract.cli import run

EXAMPLE = """# Kopf der Vorlage
# ---------- Grundlegendes ----------
TESSERACT_DOMAIN=tesseract.beispiel.de
# TESSERACT_CLOUDFLARE_TOKEN=
TESSERACT_LOG_LEVEL=info

# ---------- Neu ----------
# Erklärung zur neuen Variable
TESSERACT_NEU=standard
# TESSERACT_NEU_AUS=1
# Beispiel:
# TESSERACT_ADMIN_NETWORKS=0.0.0.0/0,::/0
# TESSERACT_ADMIN_NETWORKS=192.168.178.0/24
"""

OLD = """TESSERACT_DOMAIN=tesseract.home.example.org
TESSERACT_CLOUDFLARE_TOKEN="abc#def = ghi"
TESSERACT_ADMIN_NETWORKS=10.0.0.0/8, 192.168.0.0/16
TESSERACT_LOG_LEVEL=debug
# alter Kommentar
TESSERACT_GIBTS_NICHT_MEHR='x y # z'
EIGENE_VARIABLE=1
"""


def test_migrate_keeps_values_and_structure() -> None:
    res = envmigrate.migrate(OLD, EXAMPLE)
    text = res.text
    # Aufbau und Kommentare aus der Vorlage
    assert text.startswith("# Kopf der Vorlage\n")
    assert "# Erklärung zur neuen Variable\nTESSERACT_NEU=standard\n" in text
    # Werte exakt übernommen, auch mit Anführungszeichen, # und =
    assert "TESSERACT_DOMAIN=tesseract.home.example.org\n" in text
    assert 'TESSERACT_CLOUDFLARE_TOKEN="abc#def = ghi"\n' in text
    assert "TESSERACT_LOG_LEVEL=debug\n" in text
    # auskommentiert in der Vorlage → erste Zeile aktiviert, das Beispiel bleibt Kommentar
    assert "TESSERACT_ADMIN_NETWORKS=10.0.0.0/8, 192.168.0.0/16\n" in text
    assert "# TESSERACT_ADMIN_NETWORKS=192.168.178.0/24\n" in text
    assert "# TESSERACT_CLOUDFLARE_TOKEN=\n" not in text
    # neue Variablen bleiben wie in der Vorlage
    assert "# TESSERACT_NEU_AUS=1\n" in text
    assert res.new == ["TESSERACT_NEU", "TESSERACT_NEU_AUS"]
    # unbekannte gehen nicht verloren – eigener Abschnitt am Ende
    tail = text.split("Eigene/veraltete Einträge")[1]
    assert "TESSERACT_GIBTS_NICHT_MEHR='x y # z'\n" in tail and "EIGENE_VARIABLE=1\n" in tail
    assert res.obsolete == ["TESSERACT_GIBTS_NICHT_MEHR", "EIGENE_VARIABLE"]
    assert set(res.kept) == {"TESSERACT_DOMAIN", "TESSERACT_LOG_LEVEL"}
    assert set(res.activated) == {"TESSERACT_CLOUDFLARE_TOKEN", "TESSERACT_ADMIN_NETWORKS"}


def test_migrate_is_idempotent() -> None:
    once = envmigrate.migrate(OLD, EXAMPLE).text
    twice = envmigrate.migrate(once, EXAMPLE)
    # zweiter Lauf ändert nichts mehr (die CLI meldet dann „schon auf dem Stand“)
    assert twice.text == once


def test_report_hides_secrets() -> None:
    out = envmigrate.report(envmigrate.migrate(OLD, EXAMPLE))
    assert "abc#def" not in out and "TESSERACT_CLOUDFLARE_TOKEN=••••••" in out
    assert "TESSERACT_LOG_LEVEL=debug" in out


def test_cli_dry_run_and_backup(tmp_path: Path, capsys) -> None:
    env = tmp_path / ".env"
    ex = tmp_path / ".env.example"
    env.write_text(OLD, encoding="utf-8")
    ex.write_text(EXAMPLE, encoding="utf-8")

    try:
        run(["env", "migrate", str(env), "--example", str(ex), "--dry-run"])
    except SystemExit as e:
        assert e.code == 0
    assert env.read_text(encoding="utf-8") == OLD  # Probelauf schreibt nichts
    assert "Probelauf" in capsys.readouterr().out
    assert not list(tmp_path.glob(".env.bak-*"))

    code = envmigrate.run(str(env), str(ex), False, now=datetime(2026, 11, 26, 9, 30, 0))
    assert code == 0
    backup = tmp_path / ".env.bak-20261126-093000"
    assert backup.read_text(encoding="utf-8") == OLD
    assert "TESSERACT_NEU=standard" in env.read_text(encoding="utf-8")


def test_repo_example_is_found() -> None:
    """Im Checkout findet der Befehl die .env.example des Repos."""
    ex = envmigrate.default_example()
    assert ex is not None and ex.name == ".env.example"
    # die echte Vorlage lässt sich mit sich selbst migrieren, ohne etwas zu verlieren
    text = ex.read_text(encoding="utf-8")
    res = envmigrate.migrate(text, text)
    assert res.text == text and not res.obsolete
