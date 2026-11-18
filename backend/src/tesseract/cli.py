"""Kommandozeile.

tesseract                    Controller starten (wie `tesseract serve`)
tesseract admin reset        neues Zufallspasswort setzen, alle Sessions beenden
tesseract admin mtls off     Oberfläche wieder ohne Admin-Zertifikat erreichbar machen
tesseract db upgrade         Migrationen ausführen
tesseract backup create      Sicherung anlegen (Passphrase aus den Einstellungen oder
                             TESSERACT_BACKUP_PASSPHRASE)
tesseract backup restore F   Sicherung zurückspielen – nur bei gestopptem Controller
"""

import argparse

import uvicorn
from sqlalchemy import select

from tesseract import audit
from tesseract.config import get_settings


def serve() -> None:
    settings = get_settings()
    uvicorn.run(
        "tesseract.app:app_factory",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level,
        proxy_headers=True,
        forwarded_allow_ips=settings.forwarded_allow_ips,
    )


def admin_reset(username: str) -> None:
    from tesseract.auth import generate_password, hash_password, set_password
    from tesseract.bootstrap import init_database
    from tesseract.db.models import Admin

    database = init_database(get_settings())
    with database.sessionmaker() as db:
        admin = db.scalar(select(Admin).where(Admin.username == username))
        password = generate_password()
        if admin is None:
            admin = Admin(username=username, password_hash=hash_password(password))
            db.add(admin)
            db.flush()
        else:
            set_password(db, admin, password)
        audit.record(db, actor="system", action="password_reset", target=username)
        db.commit()
    print(f"Neues Passwort für '{username}': {password}")


def admin_mtls_off() -> None:
    """Notausgang, falls das Admin-Gerät verloren ist."""
    from tesseract.bootstrap import init_database
    from tesseract.services import apply_all, set_general

    settings = get_settings()
    database = init_database(settings)
    with database.sessionmaker() as db:
        set_general(db, {"admin_mtls": False})
        audit.record(db, actor="system", action="admin_mtls_off", target="Oberfläche (CLI)")
        db.commit()
        errors = apply_all(db, settings)
        db.commit()
    print("Admin-Zertifikat für die Oberfläche ist abgeschaltet.")
    if errors:
        print("Achtung – Config nicht übertragen:", "; ".join(errors))


def db_upgrade() -> None:
    from tesseract.db import make_engine, run_migrations

    run_migrations(make_engine(get_settings()))
    print("Datenbank ist aktuell.")


def _passphrase(confirm: bool = False) -> str:
    import getpass
    import os

    phrase = os.environ.get("TESSERACT_BACKUP_PASSPHRASE", "")
    if phrase:
        return phrase
    phrase = getpass.getpass("Passphrase der Sicherung: ")
    if confirm and getpass.getpass("Wiederholen: ") != phrase:
        raise SystemExit("Passphrasen stimmen nicht überein")
    return phrase


def backup_create(out: str | None) -> None:
    from pathlib import Path

    from tesseract import backup as b
    from tesseract.bootstrap import init_database
    from tesseract.secretbox import load_secretbox

    settings = get_settings()
    database = init_database(settings)
    with database.sessionmaker() as db:
        cfg = b.get_config(db)
        try:
            phrase = b.passphrase(cfg, load_secretbox(settings))
        except b.BackupError:
            phrase = _passphrase(confirm=True)
    database.engine.dispose()
    name, data = b.create(settings, phrase, bool(cfg.get("include_logs")))
    path = Path(out) if out else b.local_dir(settings) / name
    if path.is_dir():
        path = path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print(f"Sicherung geschrieben: {path} ({len(data) // 1024} KB)")


def backup_restore(file: str) -> None:
    from pathlib import Path

    from tesseract import backup as b
    from tesseract.db import make_engine, run_migrations

    settings = get_settings()
    try:
        item = b.inspect(Path(file).read_bytes(), _passphrase())
        b.restore_files(settings, item)
    except (b.BackupError, OSError) as e:
        raise SystemExit(f"Wiederherstellen fehlgeschlagen: {e}") from e
    run_migrations(make_engine(settings))
    m = item.manifest
    print(f"Stand vom {m.get('created')} (Version {m.get('version')}) zurückgespielt.")
    print("Beim nächsten Start überträgt der Controller die Config an alle Nodes.")


def run(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="tesseract", description="Tesseract Controller")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("serve", help="Controller starten")

    admin = sub.add_parser("admin", help="Admin-Zugang verwalten")
    admin_sub = admin.add_subparsers(dest="admin_cmd", required=True)
    reset = admin_sub.add_parser("reset", help="Passwort zurücksetzen (nur lokal)")
    reset.add_argument("--username", default="admin")
    mtls = admin_sub.add_parser("mtls", help="Admin-Zertifikat für die Oberfläche")
    mtls.add_argument("state", choices=["off"])

    db = sub.add_parser("db", help="Datenbank")
    db_sub = db.add_subparsers(dest="db_cmd", required=True)
    db_sub.add_parser("upgrade", help="Migrationen ausführen")

    bk = sub.add_parser("backup", help="Sicherungen")
    bk_sub = bk.add_subparsers(dest="backup_cmd", required=True)
    create = bk_sub.add_parser("create", help="Sicherung anlegen")
    create.add_argument("--out", help="Datei oder Ordner (Standard: Sicherungsordner)")
    restore = bk_sub.add_parser("restore", help="Sicherung zurückspielen (Controller gestoppt!)")
    restore.add_argument("file")

    args = parser.parse_args(argv)
    if args.cmd == "admin" and args.admin_cmd == "mtls":
        admin_mtls_off()
    elif args.cmd == "admin":
        admin_reset(args.username)
    elif args.cmd == "db":
        db_upgrade()
    elif args.cmd == "backup" and args.backup_cmd == "create":
        backup_create(args.out)
    elif args.cmd == "backup":
        backup_restore(args.file)
    else:
        serve()
