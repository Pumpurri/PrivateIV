#!/bin/bash

set -euo pipefail

echo "Starting Django server with HTTPS..."
source venv/bin/activate

CERT_FILE="${HTTPS_CERT_FILE:-./.certs/localhost.pem}"
KEY_FILE="${HTTPS_KEY_FILE:-./.certs/localhost-key.pem}"

if [[ ! -f "$CERT_FILE" || ! -f "$KEY_FILE" ]]; then
  echo "Missing local HTTPS certificate files."
  echo "Expected cert: $CERT_FILE"
  echo "Expected key:  $KEY_FILE"
  echo "Generate local-only dev certs and rerun, or override with HTTPS_CERT_FILE / HTTPS_KEY_FILE."
  exit 1
fi

python3 manage.py runserver_plus --cert-file "$CERT_FILE" --key-file "$KEY_FILE"
