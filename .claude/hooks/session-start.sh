#!/bin/bash
# Installe les dépendances du projet vidéo (motion/) au démarrage d'une session cloud,
# pour que Remotion soit prêt à prévisualiser et rendre sans étape manuelle.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR/motion"
if [ ! -d node_modules ] || [ package-lock.json -nt node_modules ]; then
  npm ci --no-audit --no-fund
fi
