#!/bin/bash
# tools/setup_sudoers.sh
# Erlaubt dem MotionPSM-User reboot UND das refresh-Skript ohne Passwort.
# Voraussetzung fuer die UI-Buttons "Reboot" und "Refresh".
#
# Einmalig am Pi ausfuehren:
#   sudo bash tools/setup_sudoers.sh
#
# Was das macht:
#   - schreibt /etc/sudoers.d/motionpsm mit NOPASSWD fuer:
#     * /sbin/reboot
#     * /bin/bash <repo>/tools/motionpsm_refresh.sh
#   - rechte 0440
#   - prueft Syntax mit visudo -c VOR Installation

set -e

if [ "$EUID" -ne 0 ]; then
    echo "Bitte mit sudo ausfuehren:"
    echo "  sudo bash $0"
    exit 1
fi

USER_NAME="${SUDO_USER:-BA_Weigand}"

# Absoluter Pfad zum refresh-Skript (muss mit dem in server.py uebereinstimmen)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REFRESH_SCRIPT="$SCRIPT_DIR/motionpsm_refresh.sh"

if [ ! -x "$REFRESH_SCRIPT" ]; then
    echo "FEHLER: $REFRESH_SCRIPT existiert nicht oder ist nicht ausfuehrbar."
    echo "Erst git pull machen damit es da ist."
    exit 1
fi

FILE="/etc/sudoers.d/motionpsm"
TMP="/tmp/motionpsm.sudoers.tmp"

cat > "$TMP" <<EOF
# motionpsm-Service-User darf folgende Befehle ohne Passwort:
#   /sbin/reboot                              -> UI-Button "Reboot"
#   /bin/bash $REFRESH_SCRIPT                 -> UI-Button "Refresh"
#
# Geschrieben durch tools/setup_sudoers.sh am $(date '+%Y-%m-%d %H:%M')
$USER_NAME ALL=(ALL) NOPASSWD: /sbin/reboot, /bin/bash $REFRESH_SCRIPT
EOF

# Syntax-Check VOR Installation - sonst kann man sich aussperren
if ! visudo -c -f "$TMP" >/dev/null 2>&1; then
    echo "FEHLER: sudoers-Eintrag waere syntaktisch ungueltig. Abbruch."
    rm -f "$TMP"
    exit 1
fi

mv "$TMP" "$FILE"
chmod 0440 "$FILE"

echo "Sudoers-Eintrag fuer User '$USER_NAME' geschrieben:"
echo "  $FILE"
echo ""
echo "Inhalt:"
cat "$FILE"
echo ""

# Verifikation
echo "=== Verifikation: was darf $USER_NAME ohne Passwort? ==="
sudo -n -l -U "$USER_NAME" 2>/dev/null | grep -E "reboot|motionpsm" || echo "(nichts gefunden - bitte manuell pruefen)"

echo ""
echo "OK. UI-Buttons 'Reboot' und 'Refresh' funktionieren jetzt."
