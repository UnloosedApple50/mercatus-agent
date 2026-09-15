#!/bin/bash
# Mercatus Agent — One-Line Installer
# curl -fsSL https://raw.githubusercontent.com/UnloosedApple50/mercatus-agent/main/install.sh | bash

set -e

REPO="UnloosedApple50/mercatus-agent"
INSTALL_DIR="${HOME}/mercatus-agent"

echo "╔══════════════════════════════════════════╗"
echo "║     Mercatus Agent — Installer           ║"
echo "╚══════════════════════════════════════════╝"

# Check prerequisites
command -v git >/dev/null 2>&1 || { echo "Error: git required"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "Error: python3 required"; exit 1; }

# Clone
if [ -d "$INSTALL_DIR" ]; then
    echo "Updating existing installation..."
    cd "$INSTALL_DIR" && git pull
else
    echo "Cloning repository..."
    git clone "https://github.com/${REPO}.git" "$INSTALL_DIR"
fi

# Setup
cd "$INSTALL_DIR"
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Create data dirs
mkdir -p data logs

echo ""
echo "Installation complete!"
echo "Start with: cd $INSTALL_DIR && source .venv/bin/activate && python -m mercatus run"
echo "Dashboard: http://localhost:8585"
