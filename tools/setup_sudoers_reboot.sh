#!/bin/bash
# tools/setup_sudoers_reboot.sh
# Erlaubt dem MotionPSM-User reboot ohne Passwort.
# Voraussetzung fuer den UI-Button "Pi neustarten".
#
# Einmalig ausfuehren am Pi:
#   sudo bash tools/setup_sudoers_reboot.sh
#
# Was das macht:
#   - schreibt /etc/sudoers.d/motionpsm-reboot
#   - dort steht: <user> ALL=(ALL) NOPASSWD: /sbin/reboot
#   - rechte 0440
#   - verifiziert syntaktische Korrektheit via visudo -c

set -e

if [ "$EUID" -ne 0 ]; then
    echo "Bitte mit sudo ausfuehren:"
    echo "  sudo bash $0"
    exit 1
fi

USER_NAME="${SUDO_USER:-BA_Weigand}"
FILE="/etc/sudoers.d/motionpsm-reboot"
TMP="/tmp/motionpsm-reboot.sudoers.tmp"

cat > "$TMP" <<EOF
# motionpsm-Service-User darf reboot ohne Passwort
# Geschrieben durch tools/setup_sudoers_reboot.sh
$USER_NAME ALL=(ALL) NOPASSWD: /sbin/reboot
EOF

# Syntax-Check VOR Installation - sonst sperrt man sich aus
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

# Test ob reboot ohne Passwort moeglich ist (--list zeigt erlaubte Befehle)
if sudo -n -l -U "$USER_NAME" 2>/dev/null | grep -q "/sbin/reboot"; then
    echo "VERIFIKATION: $USER_NAME darf jetzt reboot ohne Passwort."
    echo "Test: 'sudo -n /sbin/reboot --help' sollte gehen, NICHT 'sudo /sbin/reboot' jetzt!"
else
    echo "WARNUNG: Verifikation fehlgeschlagen. Pruefe manuell:"
    echo "  sudo -n -l -U $USER_NAME | grep reboot"
fi
