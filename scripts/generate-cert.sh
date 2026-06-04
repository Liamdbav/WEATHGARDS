#!/usr/bin/env bash
# Génère un certificat autosigné pour Weathgards
# Usage : ./scripts/generate-cert.sh [IP_LOCALE]
# Exemple : ./scripts/generate-cert.sh 192.168.1.42

set -e

IP=${1:-127.0.0.1}
mkdir -p certs

openssl req -x509 -newkey rsa:4096 -nodes \
  -keyout certs/weathgards.key \
  -out certs/weathgards.crt \
  -days 397 \
  -subj "/CN=weathgards-local" \
  -addext "subjectAltName=IP:${IP},IP:127.0.0.1,DNS:localhost"

echo "Certificat généré :"
echo "  certs/weathgards.crt  (à distribuer aux clients LLM)"
echo "  certs/weathgards.key  (clé privée, ne pas partager)"
echo ""
echo "Ajouter dans .env :"
echo "  WEATHGARDS_TLS_CERT_FILE=certs/weathgards.crt"
echo "  WEATHGARDS_TLS_KEY_FILE=certs/weathgards.key"
