#!/bin/bash
# ============================================================================
# MotionPSM — Einmaliger Pi-Setup.
#
# Was passiert hier:
#   1. System-Pakete: python3-venv, git, pip (falls fehlen)
#   2. venv anlegen unter <repo>/.venv/
#   3. Abhängigkeiten aus requirements.txt installieren
#   4. config.json aus Template erstellen (falls noch nicht vorhanden)
#
# Aufruf am Pi:
#   cd ~/MotionPSM
#   bash system/pi/setup_pi.sh
#
# Danach:
#   nano system/config/config.json   # COM-Port-IDs eintragen
#   bash system/pi/install_autostart.sh
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_DIR="$REPO_DIR/.venv"

echo "=============================================="
echo "MotionPSM Pi-Setup"
echo "=============================================="
echo "Repo: $REPO_DIR"
echo "venv: $VENV_DIR"
echo "Python: $(python3 --version)"
echo "=============================================="

# 1. System-Pakete (falls fehlen)
echo ""
echo "[1/4] System-Pakete prüfen (sudo nötig)..."
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git

# 2. venv anlegen
echo ""
echo "[2/4] venv anlegen..."
if [ -d "$VENV_DIR" ]; then
    echo "  venv existiert bereits: $VENV_DIR"
    read -p "  neu anlegen? [y/N] " ANSWER
    if [ "$ANSWER" = "y" ] || [ "$ANSWER" = "Y" ]; then
        rm -rf "$VENV_DIR"
        python3 -m venv "$VENV_DIR"
        echo "  venv neu angelegt."
    fi
else
    python3 -m venv "$VENV_DIR"
    echo "  venv angelegt."
fi

# 3. Abhängigkeiten installieren
echo ""
echo "[3/4] pip install -r requirements.txt..."
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install --upgrade pip --quiet
pip install -r "$SCRIPT_DIR/requirements.txt"
deactivate

# 4. config.json (falls fehlt)
echo ""
echo "[4/4] config.json prüfen..."
CONFIG_JSON="$REPO_DIR/system/config/config.json"
CONFIG_TEMPLATE="$REPO_DIR/system/config/config.example.json"
if [ -f "$CONFIG_JSON" ]; then
    echo "  config.json existiert bereits — wird nicht überschrieben."
else
    cp "$CONFIG_TEMPLATE" "$CONFIG_JSON"
    echo "  config.json aus Template erstellt."
    echo "  WICHTIG: jetzt COM-Port-IDs eintragen:"
    echo "    nano $CONFIG_JSON"
    echo "    ls /dev/serial/by-id/    # zeigt die echten IDs der gesteckten Module"
fi

echo ""
echo "=============================================="
echo "Setup OK."
echo "=============================================="
echo ""
echo "Nächste Schritte:"
echo "  1. nano $CONFIG_JSON   (falls noch nicht editiert)"
echo "  2. Test ob Server startet:"
echo "       source $VENV_DIR/bin/activate"
echo "       python3 $SCRIPT_DIR/server.py"
echo "       (Strg+C zum Beenden)"
echo "  3. Autostart einrichten:"
echo "       bash $SCRIPT_DIR/install_autostart.sh"
echo ""
