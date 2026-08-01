#!/usr/bin/env bash
# Trae los ocho recursos a raw/. Requiere .ft-hack.json (o FT_HACK_TOKEN).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p raw
CLI="npx -y github:LucasLeguizamo/hackathon-freeticket"

for pair in freeticket:events freeticket:artists freeticket:sales freeticket:tickets \
            boom:users boom:profile boom:tickets boom:social; do
  p="${pair%%:*}"; r="${pair##*:}"
  printf '  %s/%s ... ' "$p" "$r"
  $CLI pull "$p" "$r" --out "raw/${p}_${r}.csv" >/dev/null 2>&1 \
    && echo "$(wc -l < "raw/${p}_${r}.csv" | tr -d ' ') filas" \
    || { echo "FALLÓ"; exit 1; }
done
