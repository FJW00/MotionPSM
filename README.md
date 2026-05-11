# MotionPSM

**Mess-System zur Erfassung von Gestängebewegungen an Pflanzenschutzspritzen** auf Basis von Low-Cost GNSS-Modulen (u-blox ZED-F9P, Moving-Base-Konfiguration).

Ursprung: Bachelorarbeit Falk Weigand, Hochschule Weihenstephan-Triesdorf (2025). Weiterentwicklung im Rahmen von FJW Systems.

## Status

- BA-Endstand: Base + 2 Rover, Moving-Base, RTK-fix, Live-Server zur Visualisierung, CSV-Logger mit synchronisierter Zeitstempel-Validierung.
- Aktive Erweiterung (`feature/rover3`): Rover 3 in Fahrtrichtung als geometrische Mittelachsen-Referenz (Base→R3 = Längsachse, R1/R2 als Querauslenkung).
- Zielmeilenstein: DLG-Feldtage 15.06.2026 — System muss 4 Tage am Stück sauber laufen und loggen.

## Struktur

```
MotionPSM/
├── system/
│   ├── pi/                         # Lebender Code (läuft am Raspberry Pi)
│   │   ├── gps_measurement.py      # Threads für Base, Rover1, Rover2 + CSV-Logger
│   │   ├── server.py               # Live-Visualisierung
│   │   └── autostart_schwingung_fw.sh
│   ├── config/
│   │   ├── config.example.json     # Template (echte Datei .gitignored)
│   │   └── f9p_ucenter/            # u-center .txt-Configs für Base/Rover
│   └── analysis/
│       └── Auswertungs_Datei.xlsx  # Prüfprotokoll-Template
├── hardware/                       # STEP/SLDPRT-Modelle Antennenhalterungen, Box
├── documentation/
│   ├── DEVLOG.md                   # Change-Log aller Code-Änderungen
│   ├── 00_initial_meeting.txt      # Auftaktnotizen
│   └── 00_initial_project_vision.md
└── archive/legacy_software/        # Alte Codeversionen, Referenz
```

## Quickstart am Pi

```bash
git clone https://github.com/FJW00/MotionPSM.git
cd MotionPSM
cp system/config/config.example.json system/config/config.json
# COM-Port-IDs eintragen, die zu deiner Hardware passen:
ls /dev/serial/by-id/
# python3-Abhängigkeiten installieren
pip install pyserial pyubx2 pyproj numpy geopy
# Server starten
python3 system/pi/server.py
```

## Hauptmessgröße — Konzept

Bei der bisherigen Setup-Variante (Base + Rover1 + Rover2) wurde das Heading der Base aus deren Eigenbewegung berechnet. Im Stillstand fällt diese Referenz aus, und die Mittellinie ist verrauscht.

Mit Rover 3 vorne in Fahrtrichtung wird der Vektor Base→R3 zur **harten geometrischen Längsachse** der Maschine. Rover 1 und Rover 2 werden senkrecht auf diese Achse projiziert; Ergebnis ist die Querauslenkung des Gestänges in cm — auch im Stillstand stabil.

Details: siehe `documentation/DEVLOG.md` ab Eintrag "Rover3 Mittelachsen-Projektion".

## Verwandte Doku

- `documentation/DEVLOG.md` — alle Änderungen mit Datum + Begründung + offenen Tests
- `archive/legacy_software/` — Vor-Erweiterungs-Codestände (Heading_F9P_thread, alte PI/USB-Varianten)
