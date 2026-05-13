# MotionPSM — Pi-Setup

Schritt-für-Schritt-Anleitung zum Einrichten von MotionPSM auf einem Raspberry Pi (frischer Zustand).

Annahme: Raspberry Pi mit aktuellem Pi-OS (Bookworm oder neuer), Internet-Verbindung, SSH oder direkter Login.

---

## 0. Vorbereitung

Du brauchst:
- Raspberry Pi 4 (oder neuer) mit aktuellem Pi-OS
- Internet-Verbindung
- Alle 4 F9P-Module per USB angesteckt (Base + R1 + R2 + R3)
- Basis-Konfiguration via u-center am PC einmal aufgespielt (Configs in `system/config/f9p_ucenter/`)

---

## 1. Repository klonen

```bash
cd ~
git clone https://github.com/FJW00/MotionPSM.git
cd MotionPSM
git checkout feature/rover3      # oder refactor/cleanup für Stufe-2-Variante
```

---

## 2. Setup ausführen

```bash
bash system/pi/setup_pi.sh
```

Was passiert dabei:
- System-Pakete prüfen (python3-venv, git, pip) und falls nötig installieren — `sudo` wird abgefragt
- venv anlegen unter `~/MotionPSM/.venv/`
- Python-Abhängigkeiten aus `requirements.txt` installieren (flask, pyserial, pyubx2, pyproj, numpy, geopy)
- `system/config/config.json` aus Template kopieren (falls noch nicht da)

Dauert ca. 2-5 Minuten je nach Pi-Leistung und Internet.

---

## 3. COM-Port-IDs eintragen

Stelle sicher, dass **alle vier F9P-Module per USB gesteckt** sind, dann:

```bash
ls /dev/serial/by-id/
```

Beispiel-Output:
```
usb-u-blox_AG_C099__ZED-F9P_DBTFR0K9-if00-port0
usb-u-blox_AG_C099__ZED-F9P_DBTIHI5H-if00-port0
usb-u-blox_AG_C099__ZED-F9P_DBTLN7UC-if00-port0
usb-u-blox_AG_C099__ZED-F9P_<NEUE-R3-ID>-if00-port0
```

Die letzten 8 Zeichen vor `-if00-port0` sind die ID jedes Moduls. **Beschrifte deine Module physisch** (Sticker am Gehäuse), damit du weißt: welche ID ist Base, R1, R2, R3?

Dann editieren:

```bash
nano ~/MotionPSM/system/config/config.json
```

Eintragen:
```json
{
  "BASE_COM_PORT":   "/dev/serial/by-id/usb-u-blox_AG_C099__ZED-F9P_DBTFR0K9-if00-port0",
  "ROVER1_COM_PORT": "/dev/serial/by-id/usb-u-blox_AG_C099__ZED-F9P_DBTIHI5H-if00-port0",
  "ROVER2_COM_PORT": "/dev/serial/by-id/usb-u-blox_AG_C099__ZED-F9P_DBTLN7UC-if00-port0",
  "ROVER3_COM_PORT": "/dev/serial/by-id/usb-u-blox_AG_C099__ZED-F9P_<R3-ID>-if00-port0",
  "LIVE_PLOT": true
}
```

**Wichtig:**
- R1 = **links** am Gestänge montiert
- R2 = **rechts** am Gestänge
- R3 = **vorne** in Fahrtrichtung

Falls du dir bei R1/R2 unsicher bist: ein Probelauf, dann in der Live-Visualisierung schauen. Wenn die R1-Auslenkung beim Linkslenken negativ statt positiv ist, IDs in der config einfach tauschen.

---

## 4. Erster Test (manuell)

Vor dem Autostart erstmal manuell prüfen:

```bash
cd ~/MotionPSM
source .venv/bin/activate
python3 system/pi/server.py
```

Im Browser auf einem anderen Gerät (Handy/Tablet/Laptop im selben WLAN):

```
http://<pi-ip>:5000
```

Pi-IP findest du mit `hostname -I`.

**Was du sehen solltest:**
- Hauptseite mit Button "Messung starten"
- Nach Klick: Hero-Layout mit SVG-Gestänge, Quality-Boxen
- Wenn alle 4 Module RTK Fix haben (grün), bewegen sich die Werte realistisch (im Stand: lateral_cm sollte stabil bleiben, axis_length sollte der physischen Distanz Base→R3 entsprechen, z.B. 2-3m)

Strg+C zum Stoppen.

---

## 5. Autostart einrichten

```bash
bash system/pi/install_autostart.sh
```

Was passiert:
- Service-Template wird mit deinem User + Repo-Pfad gerendert
- Nach `/etc/systemd/system/motionpsm.service` kopiert (sudo)
- `systemctl enable` damit beim Boot startet

Sofort starten zum Testen:

```bash
sudo systemctl start motionpsm
sudo systemctl status motionpsm
```

Logs verfolgen:

```bash
sudo journalctl -u motionpsm -f
```

---

## 6. Nach Reboot prüfen

```bash
sudo reboot
```

Nach Neustart ssh-back rein und prüfen:

```bash
sudo systemctl status motionpsm
```

Sollte `active (running)` zeigen. Wenn nicht: `journalctl` lesen, sehr wahrscheinlich falsche COM-Port-ID in config.json oder einer der Module nicht gesteckt.

---

## Häufige Probleme

| Symptom | Ursache | Lösung |
|---|---|---|
| `FEHLER: config.json fehlt` | Schritt 3 übersprungen | `cp config.example.json config.json` |
| `Could not open port /dev/...` | COM-Port-ID falsch oder Modul nicht gesteckt | `ls /dev/serial/by-id/` prüfen, IDs vergleichen |
| Service startet aber crashed | venv-Probleme oder fehlende Deps | `journalctl -u motionpsm -n 100` lesen |
| Keine Daten im Frontend, Charts leer | Module noch beim Initialisieren / kein RTK-Fix | 1-2 Min warten, Quality-Badge prüfen |
| `RuntimeError: Fehlende Config-Felder` | ROVER3_COM_PORT vergessen | config.json prüfen |
| Pi reagiert langsam | Logger-Thread spammt CSV | `sudo systemctl restart motionpsm`, CSVs in `/tmp/` aufräumen |

---

## Update auf neuere Code-Version

Wenn neue Commits gepusht werden:

```bash
cd ~/MotionPSM
sudo systemctl stop motionpsm
git pull
# Falls requirements.txt sich geändert hat:
source .venv/bin/activate
pip install -r system/pi/requirements.txt
deactivate
sudo systemctl start motionpsm
```

Branch wechseln (z.B. von `feature/rover3` zu `refactor/cleanup`):

```bash
sudo systemctl stop motionpsm
git fetch
git checkout refactor/cleanup
sudo systemctl start motionpsm
```

---

## Backup

Wichtige Datei: `system/config/config.json` (deine echten COM-Port-IDs).
Sicherheitskopie irgendwo ablegen, falls Pi-SD-Karte mal ausfällt.

CSVs landen in `/tmp/` — sind beim Reboot weg! Direkt nach jeder Aufnahme über das Frontend `CSV exportieren` drücken und sicher ablegen.
