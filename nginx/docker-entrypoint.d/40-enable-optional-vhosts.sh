#!/bin/sh
set -eu

# ------------------------------------------------------------
# Enable optional vhosts only when their dependencies exist.
#
# This is "production-grade graceful boot":
# - nginx can start even if certs are not yet provisioned
# - certbot can run over HTTP (port 80)
# - once cert exists, we just reload nginx and HTTPS vhost appears
# ------------------------------------------------------------

STAGING_CERT="/etc/letsencrypt/live/staging.secretroom.kirillwynn.com/fullchain.pem"
STAGING_KEY="/etc/letsencrypt/live/staging.secretroom.kirillwynn.com/privkey.pem"

OPTIONAL_DIR="/etc/nginx/optional"
CONF_DIR="/etc/nginx/conf.d"

# Defensive: ensure dirs exist
mkdir -p "$OPTIONAL_DIR" "$CONF_DIR"

if [ -f "$STAGING_CERT" ] && [ -f "$STAGING_KEY" ]; then
  if [ -f "$OPTIONAL_DIR/staging.secretroom.https.conf" ]; then
    echo "[entrypoint] Enabling staging HTTPS vhost (cert present)"
    cp -f "$OPTIONAL_DIR/staging.secretroom.https.conf" "$CONF_DIR/staging.secretroom.https.conf"
  else
    echo "[entrypoint] Optional staging HTTPS config missing: $OPTIONAL_DIR/staging.secretroom.https.conf"
  fi
else
  echo "[entrypoint] Staging cert not found yet; leaving HTTPS vhost disabled"
  rm -f "$CONF_DIR/staging.secretroom.https.conf" || true
fi
