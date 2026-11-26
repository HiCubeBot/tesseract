# Caddy mit den Modulen, die Tesseract nutzt:
#  - Coraza WAF (OWASP Core Rule Set)
#  - DNS-01 über Cloudflare (für Wildcards / Hosts ohne offenen Port 80)
ARG CADDY_VERSION=2.11
# Fest, damit der Regel-Katalog des Controllers (backend/scripts/crs_catalog.py) zur CRS-Version
# passt – beim Anheben den Katalog neu erzeugen
ARG CORAZA_CADDY_VERSION=v2.6.2
FROM caddy:${CADDY_VERSION}-builder AS builder
ARG CORAZA_CADDY_VERSION
RUN xcaddy build \
    --with github.com/corazawaf/coraza-caddy/v2@${CORAZA_CADDY_VERSION} \
    --with github.com/caddy-dns/cloudflare

FROM caddy:${CADDY_VERSION}
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
COPY Caddyfile Caddyfile.cloudflare /etc/caddy/
COPY --chmod=755 start.sh /usr/local/bin/tesseract-caddy
CMD ["tesseract-caddy"]
