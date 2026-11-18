"""Kommandozeile: `tesseract-agent join | run | status`."""

import argparse
import logging
import os
import signal
import sys

from tesseract_agent import __version__
from tesseract_agent.agent import Agent, AgentError, format_fp
from tesseract_agent.config import Settings

log = logging.getLogger("tesseract_agent")


def _print_fingerprint(agent: Agent) -> None:
    print(
        f"\nBeitrittsanfrage für Node „{agent.state.name}“ gestellt.\n"
        "Im Controller unter Nodes bestätigen – vorher den Schlüssel vergleichen:\n\n"
        f"  {format_fp(agent.state.key_fingerprint)}\n",
        flush=True,
    )


def ensure_joined(agent: Agent, controller: str, token: str, hostname: str = "") -> None:
    """Tritt bei bzw. wartet auf eine schon gestellte Anfrage."""
    if agent.state.joined:
        return
    if not agent.state.join_secret:
        if not token:
            raise AgentError(
                "Noch nicht beigetreten: Beitritts-Token fehlt "
                "(--token oder TESSERACT_AGENT_JOIN_TOKEN)"
            )
        agent.join(controller, token, hostname)
    _print_fingerprint(agent)
    print("Warte auf die Bestätigung im Controller …", flush=True)
    agent.wait_for_approval()


def main(argv: list[str] | None = None) -> int:
    settings = Settings.from_env()
    p = argparse.ArgumentParser(prog="tesseract-agent", description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--data-dir", default=None, help="Datenverzeichnis (Schlüssel, Zustand)")
    p.add_argument("--log-level", default=os.environ.get("TESSERACT_AGENT_LOG_LEVEL", "info"))
    sub = p.add_subparsers(dest="cmd")

    j = sub.add_parser("join", help="Beim Controller anmelden und auf Bestätigung warten")
    j.add_argument("--controller", default=settings.controller, help="https://tesseract.…")
    j.add_argument("--token", default=settings.join_token)
    j.add_argument("--hostname", default="")
    j.add_argument("--run", action="store_true", help="danach direkt weiterlaufen")

    r = sub.add_parser("run", help="Verbunden bleiben (tritt bei Bedarf vorher bei)")
    r.add_argument("--controller", default=settings.controller)
    r.add_argument("--token", default=settings.join_token)

    sub.add_parser("status", help="Zustand anzeigen")

    args = p.parse_args(argv)
    logging.basicConfig(
        level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(message)s"
    )
    # Jede einzelne Anfrage (Long-Polling!) wäre zu viel fürs Log
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if args.data_dir:
        from pathlib import Path

        settings.data_dir = Path(args.data_dir)
    # Docker stoppt mit SIGTERM – sauber beenden
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    agent = Agent(settings)
    try:
        if args.cmd == "join":
            if agent.state.joined:
                print(f"Schon beigetreten als Node „{agent.state.name}“.")
            else:
                ensure_joined(agent, args.controller, args.token, args.hostname)
            if args.run:
                agent.run()
        elif args.cmd == "status":
            s = agent.state
            if s.joined:
                print(f"Node „{s.name}“ (#{s.node_id}) · Controller {s.controller}")
                print(f"Geladene Config: {s.loaded_hash[:12] or '–'}")
            elif s.join_secret:
                print(f"Beitritt wartet auf Bestätigung · Node „{s.name}“")
                print(f"Schlüssel: {format_fp(s.key_fingerprint)}")
            else:
                print("Nicht beigetreten.")
        else:  # run (Standard)
            controller = getattr(args, "controller", "") or settings.controller
            token = getattr(args, "token", "") or settings.join_token
            ensure_joined(agent, controller, token)
            agent.run()
    except AgentError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
