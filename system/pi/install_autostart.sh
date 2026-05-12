#!/bin/bash
# ============================================================================
# MotionPSM — Einmaliger Installer für den systemd-Autostart.
#
# Was passiert hier:
#   1. Aktuellen User + Repo-Pfad ermitteln
#   2. motionpsm.service aus dem Template generieren (Pfade einsetzen)
#   3. Service nach /etc/systemd/system/ kopieren (sudo)
#   4. systemd reload + Service "enable" (startet beim Boot automatisch)
#
# Nach Installation:
#   sudo systemctl start motionpsm      # manueller Start (zum Testen)
#   sudo systemctl status motionpsm     # läuft?
#   sudo journalctl -u motionpsm -f     # Live-Logs anschauen
#   sudo systemctl stop motionpsm       # stoppen
#   sudo systemctl disable motionpsm    # Autostart aus
#
# Autor: Falk-Jakob Weigand (FJW Systems)
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

USER_NAME="$(whoami)"
TEMPLATE="$SCRIPT_DIR/motionpsm.service.template"
DEST="/etc/systemd/system/motionpsm.service"

echo "============================================="
echo "MotionPSM Autostart Installer"
echo "============================================="
echo "User:      $USER_NAME"
echo "Repo:      $REPO_DIR"
echo "Service:   $DEST"
echo "============================================="

if [ ! -f "$TEMPLATE" ]; then
    echo "FEHLER: Template $TEMPLATE nicht gefunden." >&2
    exit 1
fi

if [ ! -f "$REPO_DIR/system/config/config.json" ]; then
    echo ""
    echo "WARNUNG: $REPO_DIR/system/config/config.json existiert noch nicht."
    echo "Bevor der Autostart sinnvoll läuft, musst du das machen:"
    echo "  cp $REPO_DIR/system/config/config.example.json $REPO_DIR/system/config/config.json"
    echo "  nano $REPO_DIR/system/config/config.json   # COM-Port-IDs eintragen"
    echo ""
    read -p "Trotzdem fortfahren? [y/N] " ANSWER
    if [ "$ANSWER" != "y" ] && [ "$ANSWER" != "Y" ]; then
        echo "Abgebrochen."
        exit 0
    fi
fi

# autostart-Script ausführbar machen
chmod +x "$SCRIPT_DIR/autostart_schwingung_fw.sh"

# Template rendern (USER und REPO_DIR einsetzen)
TMP_SERVICE=$(mktemp)
sed -e "s|{{USER}}|$USER_NAME|g" \
    -e "s|{{REPO_DIR}}|$REPO_DIR|g" \
    "$TEMPLATE" > "$TMP_SERVICE"

echo ""
echo "Generierter Service:"
echo "-----"
cat "$TMP_SERVICE"
echo "-----"
echo ""

# Nach /etc/systemd/system/ kopieren (sudo)
echo "Installation (sudo wird abgefragt)..."
sudo cp "$TMP_SERVICE" "$DEST"
sudo systemctl daemon-reload
sudo systemctl enable motionpsm.service
rm "$TMP_SERVICE"

echo ""
echo "============================================="
echo "Installation OK."
echo "============================================="
echo "Service wird beim nächsten Boot automatisch starten."
echo ""
echo "Manueller Start jetzt:    sudo systemctl start motionpsm"
echo "Status prüfen:            sudo systemctl status motionpsm"
echo "Logs verfolgen:           sudo journalctl -u motionpsm -f"
echo "Autostart deaktivieren:   sudo systemctl disable motionpsm"
echo ""
