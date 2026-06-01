#!/bin/bash
# tools/usb_reset_f9p.sh — USB-Reset der 4 F9P-Module ohne Pi-Reboot
#
# Hintergrund: Bei wiederholten Server-Starts akkumuliert sich State
# im Pi-USB-Subsystem -> CSV-iTOW-Quote degeneriert mit der Zeit
# (gemessen 2026-06-01: 140 ms direkt nach Pi-Reboot -> 200-250 ms
# nach 2-3 Server-Restarts). Dieses Skript bindet die USB-Devices
# ab und wieder an — Alternative zum Pi-Reboot zwischen Tests.
#
# Voraussetzungen:
#   - sudo (USB-sysfs-Schreibrechte)
#   - server.py NICHT laufend (Ports muessen frei sein)
#
# Verwendung:
#   # Server vorher stoppen
#   sudo systemctl stop motionpsm   # falls Autostart-Service
#   # oder Strg+C im Server-Terminal
#
#   sudo bash tools/usb_reset_f9p.sh
#
#   # Danach Server wieder starten
#
# Sicherheit: Skript fasst NUR die 4 udev-Symlinks an, die zu MotionPSM
# gehoeren (usb-B_B-if00 + usb-R_1/2/3-if00). Andere USB-Devices bleiben
# unbeeinflusst.

set -u  # unbound vars sind Fehler — set -e weglassen, wir wollen
        # auch bei einzelnen Modul-Fehlern weitermachen

USB_PORTS=(
    "/dev/serial/by-id/usb-B_B-if00"
    "/dev/serial/by-id/usb-R_1-if00"
    "/dev/serial/by-id/usb-R_2-if00"
    "/dev/serial/by-id/usb-R_3-if00"
)

if [ "$EUID" -ne 0 ]; then
    echo "Fehler: bitte mit sudo ausfuehren:"
    echo "  sudo bash $0"
    exit 1
fi

# Server-Prozess pruefen
if pgrep -f "python3 .*server\.py" > /dev/null 2>&1; then
    echo "FEHLER: server.py laeuft noch."
    echo "  Erst stoppen:"
    echo "    sudo systemctl stop motionpsm   # falls Autostart"
    echo "    oder Strg+C im Server-Terminal"
    exit 1
fi

echo "=== F9P USB-Reset ==="
echo ""

reset_one_port() {
    local symlink="$1"
    local name
    name="$(basename "$symlink")"

    if [ ! -e "$symlink" ]; then
        echo "  ! $name: Symlink fehlt, ueberspringe"
        return 1
    fi

    local tty_dev
    tty_dev="$(readlink -f "$symlink" 2>/dev/null || true)"
    if [ -z "$tty_dev" ] || [ ! -e "$tty_dev" ]; then
        echo "  ! $name: Symlink loest nicht auf, ueberspringe"
        return 1
    fi

    # USB-Device-ID aus udevadm attribute-walk extrahieren.
    # Eintrag wie: KERNEL=="1-1.2"
    local usb_id
    usb_id="$(udevadm info --attribute-walk -n "$tty_dev" 2>/dev/null \
        | grep -oE 'KERNEL=="[0-9]+-[0-9.]+"' \
        | head -1 \
        | sed 's/KERNEL=="\(.*\)"/\1/')"

    if [ -z "$usb_id" ]; then
        echo "  ! $name ($tty_dev): USB-Bus-ID nicht ermittelbar"
        return 1
    fi

    echo "  $name: $tty_dev  ->  USB $usb_id"
    echo "    unbind..."
    if echo "$usb_id" > /sys/bus/usb/drivers/usb/unbind 2>/dev/null; then
        echo "    unbind OK"
    else
        echo "    unbind fehlgeschlagen (vielleicht schon ab)"
    fi
    sleep 1.5
    echo "    bind..."
    if echo "$usb_id" > /sys/bus/usb/drivers/usb/bind 2>/dev/null; then
        echo "    bind OK"
    else
        echo "    bind fehlgeschlagen"
        return 1
    fi
    sleep 0.5
    return 0
}

ok=0
fail=0
for symlink in "${USB_PORTS[@]}"; do
    if reset_one_port "$symlink"; then
        ok=$((ok+1))
    else
        fail=$((fail+1))
    fi
    echo ""
done

echo "Warte 3s bis Module neu erkannt sind..."
sleep 3
echo ""

echo "=== Verifikation: udev-Symlinks vorhanden? ==="
all_back=1
for symlink in "${USB_PORTS[@]}"; do
    name="$(basename "$symlink")"
    if [ -e "$symlink" ]; then
        tty="$(readlink -f "$symlink" 2>/dev/null || echo "?")"
        echo "  ok   $name  ->  $tty"
    else
        echo "  MISS $name  FEHLT!"
        all_back=0
    fi
done

echo ""
echo "Zusammenfassung: $ok erfolgreich, $fail Fehler"
if [ "$all_back" = "1" ] && [ "$fail" = "0" ]; then
    echo "Alle Module wieder verfuegbar. Server kann neu gestartet werden."
    exit 0
else
    echo "WARNUNG: nicht alles ist sauber. Pi-Reboot empfohlen wenn Module fehlen."
    exit 1
fi
