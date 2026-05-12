#!/bin/bash
# ============================================================================
# MotionPSM — Autostart Wrapper-Script
# Wird vom systemd-Service motionpsm.service aufgerufen.
# Autor: Falk-Jakob Weigand (FJW Systems)
# ============================================================================

set -e

# Eigenen Pfad ermitteln (so kann das Repo überall liegen)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
SERVER_PY="$SCRIPT_DIR/server.py"
CONFIG_FILE="$REPO_DIR/system/config/config.json"
VENV_DIR="$REPO_DIR/.venv"

echo "[autostart] $(date '+%Y-%m-%d %H:%M:%S')"
echo "[autostart] Repo:   $REPO_DIR"
echo "[autostart] Server: $SERVER_PY"

# Sanity-Check: config.json muss existieren (mit echten COM-Port-IDs)
if [ ! -f "$CONFIG_FILE" ]; then
    echo "[autostart] FEHLER: $CONFIG_FILE fehlt." >&2
    echo "[autostart] Bitte einmalig anlegen:" >&2
    echo "[autostart]   cp $REPO_DIR/system/config/config.example.json $CONFIG_FILE" >&2
    echo "[autostart]   nano $CONFIG_FILE  # COM-Port-IDs eintragen" >&2
    exit 1
fi

# Optional: venv aktivieren falls vorhanden (sonst System-Python)
if [ -f "$VENV_DIR/bin/activate" ]; then
    echo "[autostart] venv aktivieren: $VENV_DIR"
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
else
    echo "[autostart] kein venv gefunden, nutze System-Python3"
fi

# Working-Dir auf pi/-Ordner setzen (für relative Imports wie geometry.py)
cd "$SCRIPT_DIR"

# exec ersetzt den Shell-Prozess durch python3 — wichtig damit systemd
# Crashes als Service-Fehler erkennt und ggf. Restart triggert.
exec python3 "$SERVER_PY"
