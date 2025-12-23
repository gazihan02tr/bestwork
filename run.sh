#!/bin/bash

# BestWork Application Run Script
# Kurulum olmadan direkt başlat (venv gerekli)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if venv exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment bulunamadı!"
    echo "Lütfen önce kurulum yapın: python3 setup.py"
    exit 1
fi

# Activate venv
source .venv/bin/activate

# Run the app
python app.py
