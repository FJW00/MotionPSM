#!/bin/bash
# tools/motionpsm_refresh.sh
# Wird vom UI-Button "Refresh" via /system_refresh aufgerufen.
# Ablauf:
#   1. kurze Pause (Flask-Response zurueck zum Client)
#   2. systemctl stop motionpsm    (killt server.py)
#   3. usb_reset_f9p.sh             (USB-Subsystem-Reset)
#   4. systemctl start motionpsm   (server.py kommt zurueck)
#
# Voraussetzungen:
#   - Skript wird mit sudo aufgerufen (siehe tools/setup_sudoers.sh)
#   - motionpsm.service ist eingerichtet (install_autostart.sh)
#   - tools/usb_reset_f9p.sh existiert und ist executable

set -u

# Wenn nicht als root: Selbst-Aufruf mit sudo (fallback)
if [ "$EUID" -ne 0 ]; then
    echo "Re-exec as root..."
    exec sudo -n /bin/bash "$0" "$@"
fi

# Pfade
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USB_RESET="$SCRIPT_DIR/usb_reset_f9p.sh"
LOG="/tmp/motionpsm_refresh.log"

# Logging mit Zeitstempel
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"
}

log "=== motionpsm_refresh start ==="

# 1) kurze Pause damit Flask-Response durchkommt
sleep 1.5

# 2) Service stoppen
log "systemctl stop motionpsm.service ..."
if systemctl stop motionpsm.service 2>>"$LOG"; then
    log "  service gestoppt"
else
    log "  WARN: stop fehlgeschlagen (vielleicht schon aus)"
fi
sleep 1

# 3) USB-Reset (Pi-USB-Subsystem)
log "usb_reset_f9p.sh ..."
if [ -x "$USB_RESET" ]; then
    bash "$USB_RESET" >> "$LOG" 2>&1
    rc=$?
    log "  usb_reset_f9p.sh exit=$rc"
else
    log "  WARN: $USB_RESET nicht ausfuehrbar - ueberspringe"
fi

# 4) Service starten
log "systemctl start motionpsm.service ..."
if systemctl start motionpsm.service 2>>"$LOG"; then
    log "  service gestartet"
else
    log "  FEHLER: start fehlgeschlagen!"
fi

log "=== motionpsm_refresh fertig ==="
