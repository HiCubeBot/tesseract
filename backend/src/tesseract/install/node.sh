#!/bin/sh
# Tesseract-Node installieren: Caddy + Agent per Docker Compose.
# Erzeugt vom Controller __CONTROLLER__ (Version __VERSION__).
#
#   curl -fsSL __CONTROLLER__/install/node.sh | sudo sh -s -- --token <Beitritts-Token>
#
# Optionen:
#   --token T            Beitritts-Token aus dem Controller (Nodes › Node hinzufügen)
#   --dir PFAD           Installationsordner (Standard: /opt/tesseract-node)
#   --install-docker     Docker installieren, falls es fehlt (offizielles Skript get.docker.com)
#   --registry-token T   Zugang zur Image-Registry, falls die Images nicht öffentlich sind
#   --registry-user U    Benutzer dazu (Standard: tesseract)
#   --update             vorhandene Installation auf diese Version aktualisieren
#   --uninstall --yes    alles entfernen (Container, Volumes, Ordner)
#
# Ohne Internet: Images vorher per „docker load“ einspielen – das Skript nutzt sie dann.
set -eu

CONTROLLER="__CONTROLLER__"
VERSION="__VERSION__"
REGISTRY="ghcr.io"
DIR="/opt/tesseract-node"
TOKEN=""
REG_TOKEN=""
REG_USER="tesseract"
INSTALL_DOCKER=0
ACTION="install"
YES=0

say() { printf '\033[1m%s\033[0m\n' "$*"; }
fail() { printf '\033[31mFehler:\033[0m %s\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --token) TOKEN="${2:-}"; shift 2 ;;
    --dir) DIR="${2:-}"; shift 2 ;;
    --install-docker) INSTALL_DOCKER=1; shift ;;
    --registry-token) REG_TOKEN="${2:-}"; shift 2 ;;
    --registry-user) REG_USER="${2:-}"; shift 2 ;;
    --update) ACTION="update"; shift ;;
    --uninstall) ACTION="uninstall"; shift ;;
    --yes) YES=1; shift ;;
    -h|--help) sed -n '2,16p' "$0" 2>/dev/null || true; exit 0 ;;
    *) fail "Unbekannte Option: $1 (--help zeigt alle)" ;;
  esac
done

[ "$(id -u)" -eq 0 ] || fail "Bitte als root ausführen (… | sudo sh -s -- …)"

# ---------- Docker ----------
if ! command -v docker >/dev/null 2>&1; then
  if [ "$INSTALL_DOCKER" -eq 1 ]; then
    say "Docker fehlt – installiere es über get.docker.com …"
    command -v curl >/dev/null 2>&1 || fail "curl fehlt"
    curl -fsSL https://get.docker.com | sh
  else
    fail "Docker fehlt. Installieren (https://docs.docker.com/engine/install/) oder mit --install-docker erneut aufrufen."
  fi
fi
docker compose version >/dev/null 2>&1 || fail "Docker Compose (Plugin) fehlt – Paket docker-compose-plugin installieren"

compose() { docker compose --project-directory "$DIR" "$@"; }

# ---------- Entfernen ----------
if [ "$ACTION" = "uninstall" ]; then
  [ "$YES" -eq 1 ] || fail "Entfernt Caddy, Agent, Zertifikate und Daten in $DIR – mit --yes bestätigen"
  [ -f "$DIR/compose.yaml" ] && compose down -v || true
  rm -rf "$DIR"
  say "Tesseract-Node entfernt. Im Controller den Node unter Nodes löschen."
  exit 0
fi

if [ -f "$DIR/.env" ] && [ "$ACTION" = "install" ] && [ -z "$TOKEN" ]; then
  ACTION="update"
fi
if [ "$ACTION" = "install" ] && [ -z "$TOKEN" ]; then
  fail "Beitritts-Token fehlt (--token …) – im Controller unter Nodes › Node hinzufügen erzeugen"
fi

# ---------- Dateien ----------
mkdir -p "$DIR"
umask 077
say "Schreibe $DIR/compose.yaml …"
cat > "$DIR/compose.yaml" <<'TESSERACT_COMPOSE'
__COMPOSE__
TESSERACT_COMPOSE

CA_PEM='__CA_PEM__'
if [ -n "$CA_PEM" ]; then
  # Interne Controller-Domain: dem Zertifikat des Controllers über diese CA vertrauen
  printf '%s\n' "$CA_PEM" > "$DIR/controller-ca.pem"
  chmod 644 "$DIR/controller-ca.pem"
  cat > "$DIR/compose.override.yaml" <<'TESSERACT_OVERRIDE'
services:
  agent:
    environment:
      TESSERACT_AGENT_CONTROLLER_CA: /ca/controller.pem
    volumes:
      - ./controller-ca.pem:/ca/controller.pem:ro
TESSERACT_OVERRIDE
fi

if [ "$ACTION" = "install" ]; then
  {
    echo "TESSERACT_CONTROLLER=$CONTROLLER"
    echo "TESSERACT_JOIN_TOKEN=$TOKEN"
    echo "TESSERACT_VERSION=$VERSION"
  } > "$DIR/.env"
else
  # Update: Version anheben, Rest behalten
  if grep -q '^TESSERACT_VERSION=' "$DIR/.env"; then
    sed -i "s/^TESSERACT_VERSION=.*/TESSERACT_VERSION=$VERSION/" "$DIR/.env"
  else
    echo "TESSERACT_VERSION=$VERSION" >> "$DIR/.env"
  fi
fi
chmod 600 "$DIR/.env"

# ---------- Images ----------
if [ -n "$REG_TOKEN" ]; then
  say "Anmeldung bei $REGISTRY …"
  printf '%s' "$REG_TOKEN" | docker login "$REGISTRY" -u "$REG_USER" --password-stdin >/dev/null
fi
say "Lade Images (Version $VERSION) …"
if ! compose pull; then
  # Ohne Registry (z. B. Server ohne Internet): vorher per „docker load“ eingespielte Images nutzen
  missing=0
  for img in $(compose config --images); do
    docker image inspect "$img" >/dev/null 2>&1 || { echo "  fehlt: $img"; missing=1; }
  done
  if [ "$missing" -eq 1 ]; then
    fail "Images nicht ladbar. Sind sie öffentlich? Sonst mit --registry-token <Token mit read:packages> erneut aufrufen."
  fi
  say "Registry nicht erreichbar – nutze die lokal vorhandenen Images."
fi
compose up -d --remove-orphans

if [ "$ACTION" = "update" ]; then
  say "Aktualisiert auf $VERSION."
  exit 0
fi

# ---------- Fingerabdruck ----------
say "Warte auf die Beitrittsanfrage des Agents …"
i=0
FP=""
while [ $i -lt 60 ]; do
  FP=$(compose logs agent 2>/dev/null | grep -Eo '([0-9A-F]{2}:){31}[0-9A-F]{2}' | tail -n 1 || true)
  [ -n "$FP" ] && break
  i=$((i + 1))
  sleep 2
done
if [ -z "$FP" ]; then
  echo "Keine Antwort vom Agent. Log ansehen: docker compose --project-directory $DIR logs agent"
  exit 1
fi
echo
say "Fast fertig – jetzt im Controller bestätigen:"
echo "  $CONTROLLER  →  Nodes  →  Anfrage bestätigen"
echo
echo "  Schlüssel-Fingerabdruck (muss übereinstimmen):"
echo "  $FP"
echo
echo "Installiert in $DIR. Aktualisieren: dasselbe curl-Kommando mit --update statt --token."
