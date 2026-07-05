#!/usr/bin/env bash
# Installe (si nécessaire) et lance Annote_pdf.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Création de l'environnement virtuel..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

echo "Installation des dépendances..."
pip install --quiet --upgrade pip
pip install --quiet -e .

echo "Lancement d'Annote_pdf..."
annote-pdf "$@"
