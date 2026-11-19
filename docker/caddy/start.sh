#!/bin/sh
# Startet Caddy. --resume: nach einem Neustart gilt die zuletzt vom Controller geladene
# Config (liegt in /config); nur beim allerersten Start gilt eine der Caddyfiles.
set -e
config=/etc/caddy/Caddyfile
if [ -n "$TESSERACT_CLOUDFLARE_TOKEN" ]; then
	config=/etc/caddy/Caddyfile.cloudflare
fi
exec caddy run --config "$config" --adapter caddyfile --resume
