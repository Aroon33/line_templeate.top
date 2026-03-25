#!/usr/bin/env bash
set -euo pipefail
EMAIL="${1:-info@sns-template.com}"
certbot --nginx \
  -d line.sns-template.com \
  -d api.sns-template.com \
  --agree-tos \
  -m "$EMAIL" \
  --non-interactive \
  --redirect
systemctl reload nginx
echo "[OK] SSL configured for line.sns-template.com and api.sns-template.com"
