# PROJECT_CONTEXT — MotionPSM / FJW Systems

**Diese Datei ist das Cold-Start-Briefing für jede neue Cowork-Session.**
Falk sagt zu Beginn: "Lies erst `documentation/PROJECT_CONTEXT.md`" — und du bist sofort drin.

Stand: 2026-05-30.

---

## Wer und Was

**Person:** Falk-Jakob Weigand, HSWT-Absolvent (Bachelor 2025). Gründer **FJW Systems** (Einzelunternehmen, **angemeldet 20.05.2026** über Bayern-Serviceportal, nicht im Handelsregister eingetragen, Regelbesteuerung). Hauptberuf parallel: Vollzeit-Job Mo–Fr 7–16 Uhr. Codet abends + Wochenenden.

**Gewerbe-Tätigkeitsbeschreibung (Stand 20.05.2026):**

> Entwicklung, Herstellung, Vertrieb, Vermietung und Integration von Mess-, Sensor-, Automatisierungs- und Assistenzsystemen für die Land- und Forstwirtschaft sowie industrielle Anwendungen; Entwicklung, Vertrieb und Betrieb von GNSS-, RTK-, Telemetrie-, IoT- und datenbasierten Systemen; Erbringung von Mess-, Vermessungs-, Analyse- und Monitoringdienstleistungen mittels GNSS-, Sensor-, Drohnen- und Kameratechnologie einschließlich Luftbildauswertung, Vegetationsanalyse sowie Erstellung von Applikations- und Bewirtschaftungskarten für Düngung, Pflanzenschutz und teilflächenspezifische Landwirtschaft; Entwicklung von Hard- und Software, Embedded Systems sowie Datenverarbeitungs- und Cloudlösungen einschließlich Anwendungen im Bereich künstlicher Intelligenz, Automatisierung und Digitalisierung; technische Beratung, Schulung sowie Forschungs- und Entwicklungsdienstleistungen in den genannten Bereichen; Entwicklung, Herstellung und Nachrüstung elektronischer, mechanischer und technischer Komponenten, Sonderlösungen und Prototypen für landwirtschaftliche, kommunale und industrielle Anwendungen; Handel mit Zubehör, Ersatzteilen, elektronischen Baugruppen und technischen Komponenten.

**Produkt:** **MotionPSM** — Low-Cost GNSS-basiertes Mess-System zur Erfassung der Gestängebewegungen von Pflanzenschutzspritzen. Soll Landwirten / Maschinenherstellern eine günstige Möglichkeit geben, Boom-Schwingungen quantitativ zu erfassen.

**Kontakt:**
- Email: falkweigand1304@gmail.com / info@fjw-systems.com
- Domain: fjw-systems.de, fjw-systems.com — **Onepager LIVE seit 30.05.2026** (Impressum + Datenschutz inkl.)
- Firmensitz: Steinig 1a, 97956 Werbach

---

## Hardware-Architektur

- **Base** (u-blox ZED-F9P, C099 Board): zentrale RTK-Basis. **MUSS auf einem starren Rahmen sitzen, NICHT am Gestänge** (sonst werden Rover-Schwingungen systematisch verfälscht — Erkenntnis aus 17.05.-Test). Geeignet: Schlepperdach/Kabine ODER Spritzen-Chassis (sofern lang genug für ~3 m Baseline Base→R3 — Falk's Spritze hat das, getestet 22.05./30.05.). Maximale Sky-View. Sendet RTCM-Korrekturen via UART2 an die Rover.
- **Rover 1** (ZED-F9P): **links** am Gestänge montiert (vom Fahrer aus gesehen).
- **Rover 2** (ZED-F9P): **rechts** am Gestänge.
- **Rover 3** (ZED-F9P): **vorne in Fahrtrichtung am Schlepper** (NICHT am Gestänge), definiert die Längsachse Base→R3.
- **Raspberry Pi 5 (8 GB)**: zentrale Steuerung (seit Ende 2025 von Pi 4 upgegradet). Liest alle Module über USB ein (`/dev/serial/by-id/...`), läuft Flask-Server zur Live-Anzeige + CSV-Logger.
  - **Active Cooler** (GeeekPi Armor Lite V5) seit 30.05.: max. 50°C bei 32°C Außentemperatur + Sonne — Throttling-Problem (87.8°C in alter Box) gelöst.
  - **Neue ASA-Box** mit Belüftungsschlitzen + Heatsink-Aussparung.
- **Antennenhalter**: STEP-Files in `hardware/f9p/`. Falks Eigenkonstruktion mit Kamera-Rohrklemmen — vibrationsfest, wird übernommen für alle Aufbauten.

**RTK-Modus:** Moving-Base. Jeder Rover bekommt RTCM von der Base und liefert `relPosNED` (Position relativ zur Base) mit RTK-Genauigkeit (~cm).

**COM-Port-IDs (echte Werte sind in `system/config/config.json` lokal am Pi, .gitignored):**
- Base: `DBTFR0K9`
- Rover 1: `DBTIHI5H`
- Rover 2: `DBTLN7UC`
- Rover 3: noch nicht festgehalten — beim ersten Anstecken aus `ls /dev/serial/by-id/` ablesen

---

## Mess-Konzept

### Bisher (vor Rover 3)
- Heading der Base aus Eigenbewegung berechnet → verrauscht + nicht stillstandsfähig.
- Moving-Average als Notbehelf für Mittellinien-Stabilisierung.

### Neu mit Rover 3
- Vektor Base→R3 **ist** die geometrische Längsachse der Maschine (auch im Stillstand stabil).
- Zwei parallele Auswertungsvarianten:
  - **Variante A (Hauptmetrik):** R1, R2 senkrecht auf Achse projiziert → `lateral_offset_cm` (signed). Konvention: **links = positiv**, rechts = negativ.
  - **Variante B (Vergleich):** Differenzvektoren R3→R1 und R3→R2 → Distanz + Heading, direkt aus relPosNED-Diff.
- Beides wird ins CSV geloggt (`VarA_*` und `VarB_*` Spalten am Ende).

### CSV-Layout (81 Spalten, Stand 17.05. — unverändert seit Tare/Filter-Iteration)
1. R1 (17 Spalten) — Heading-Stats, Position, Quality
2. R2 (17)
3. R3 (17)
4. Base (8) — Position, Heading, Speed
5. Berechnungen Variante A + B + Achsen-Info + Total (11)
6. Filtered Spalten (6) — Moving-Average longitudinal + Symmetric/Asymmetric Yaw raw+filtered (siehe config.json `FILTER_WINDOW_S`, default 0.2 s)
7. Tare-bereinigte Spalten (5) — VarA_R*_longitudinal/lateral_tared_cm + Tare_set_at

### Hauptmetriken
- **`longitudinal_cm`** = Vor-/Rück-Auslenkung von R1/R2 entlang Fahrtrichtung. + = vorne, − = hinten. **Das ist die Schwingungs-Metrik.**
- **`lateral_cm`** = Seitlicher Abstand zur Längsachse. ≈ Gestängehalbe, fast konstant.
- **`Symmetric Yaw`** = (R2_long − R1_long) / 2. Rotation des Gestänges um die Mittelachse.
- **`Asymmetric Yaw`** = (R1_long + R2_long) / 2. Translation des Gestänges (vor/zurück).
- Mathematik ist **rotationsinvariant gegen Maschinen-Heading** (Beweis im DEVLOG 17.05.).

### UI-Funktionen
- **Tare-Button "⌖ Set Zero"** oben rechts (links neben Toggle): speichert aktuelle Werte als Nullpunkt. CSV bekommt zusätzliche `*_tared_cm`-Spalten. Tare-Status mit Clear-`×` daneben.
- **Toggle "Smoothed | Raw"** oben rechts: schaltet Anzeige zwischen gefilterten und rohen Werten. CSV bekommt immer beides. Persistent in localStorage.
- **Set Zero VOR jeder Messung drücken** (nach Aufbau, Maschine still) → Schwingungs-Auswertung relativ zur Ausgangslage.

---

## Repository-Struktur

```
FJW_Schwingung/                         <- lokaler Master-Ordner
├── MotionPSM_repo/                     <- Git-Repo (github.com/FJW00/MotionPSM)
│   ├── system/
│   │   ├── pi/                         <- Lebender Code
│   │   │   ├── gps_measurement.py      <- Threads, Logger, CSV
│   │   │   ├── geometry.py             <- Mittelachsen-Projektion (Var A) + Diff-Vektoren (Var B)
│   │   │   ├── server.py               <- Flask + HTML-Frontend
│   │   │   └── autostart_schwingung_fw.sh
│   │   ├── config/
│   │   │   ├── config.example.json     <- Template (im Repo)
│   │   │   ├── config.json             <- echte COM-Port-IDs (.gitignored, nur lokal/am Pi)
│   │   │   └── f9p_ucenter/usb_only_v2_2026-05-30/   <- Aktive u-blox Configs (USB-only Outputs, 10 Hz)
│   │   └── analysis/
│   │       └── Auswertungs_Datei.xlsx  <- Excel-Template Prüfprotokoll
│   ├── hardware/                       <- STEP/SLDPRT-Modelle Halter, Box
│   ├── documentation/
│   │   ├── DEVLOG.md                   <- Detail-Log aller Änderungen
│   │   ├── PROJECT_CONTEXT.md          <- DIESE Datei
│   │   ├── 00_initial_meeting.txt
│   │   └── 00_initial_project_vision.md
│   └── archive/legacy_software/        <- alte Code-Stände (Heading_F9P_thread, alte PI/USB-Varianten)
│
├── business/                           <- LOKAL, nie Git
│   ├── branding/                       (Logos)
│   ├── gruendung/{exist,hswt,gewerbeanmeldung}/
│   ├── finanzen/{kalkulationen,rechnungen,steuer}/
│   ├── recht/{ndas,eigentumserklärung}/
│   ├── kunden/feldtage_2026/
│   ├── vorlagen/                       <- Brief/Word-Templates (für Dokumente nutzen)
│   └── website/
│
├── data/                               <- LOKAL, große Files
│   ├── ba_messungen/                   (alte CSVs, Auswertungen)
│   ├── validierung_2025-12/            (Seilzug- und Kamera-Validierung)
│   └── literatur/                      (u-blox-Docs + Fremdliteratur PDFs)
│
├── BA_Abgabe/                          <- Bachelorarbeit, eingefroren read-only
│
└── archive/
    ├── 2026-05-11_full_backup/         (1:1 Backup vor Repo-Reset)
    └── _legacy_empty/                  (leere Original-Ordner, macOS rmdir blockt)
```

---

## Branches

- `main` — **Production-Stand** (54d1dd4): USB-only Configs v2 + Sleep-Fix + alle DEVLOG-Einträge.
- `refactor/logger-itow-dict` — **in Test** (a0fb3f3): Refactor C — iTOW-Dict-Logger statt 4 unsync'd Queues. Behebt die 38%-Sample-Drop-Race in der alten Architektur. Bench-Test am Pi am 31.05.2026, bei Erfolg Merge nach main.
- `refactor/cleanup` — historischer Branch (Stufe-2-Refactor), unverändert seit Mai
- `feature/rover3` — gelöscht (komplett in main gemerged, 30.05.)

---

## Termine + Meilensteine — laufender Fortschritt

| Datum | Was | Status |
|---|---|---|
| 14.05. | Bench-Test Rover 3 | ✅ |
| 15.–17.05. | Feldtest + Iterationen, UI-Refactor, Filter, Tare | ✅ |
| 19.05. | Steuerberater-Termin | ✅ |
| 20.05. | **Gewerbeanmeldung** Bayern-Serviceportal | ✅ Gründungstag |
| 22.05. | Testfahrt mit Tare: 10 cm Stand-Auslenkung exakt gemessen | ✅ (Geometrie + Tare validiert) |
| 22.05. | Pi-Thermal-Problem entdeckt (87.8°C → Sample-Lücken) | ✅ diagnostiziert |
| 23.05. | Active Cooler bestellt (GeeekPi Armor Lite V5) | ✅ |
| 24./25.05. | Generalprobe-Wochenende mit neuer Box + Cooler (50°C bei 32°C/Sonne) | ✅ |
| 25.05. | 5-Hz-Problem entdeckt (CFG-RATE OK aber NMEA-Multicast drosselt F9P) | ✅ diagnostiziert |
| 26.05. | USB-only Configs v1 — fehlerhaft (off-by-one Item-IDs) | ✅ verworfen |
| 30.05. | USB-only Configs v2 mit pyubx2-DB → 10 Hz auf allen Modulen | ✅ commit 54d1dd4 |
| 30.05. | Hof-Test: 10/20 cm Tare-Auslenkung exakt gemessen | ✅ Geometrie 2× validiert |
| 30.05. | Logger-Refactor C (iTOW-Dict) implementiert | ✅ commit a0fb3f3 (Branch) |
| 30.05. | Grundplatten Base + R3 bestellt | ✅ |
| 30.05. | feature/rover3 → main gemerged, Repo aufgeräumt | ✅ |
| 30.05. | **fjw-systems.de LIVE** (Impressum + Datenschutz) | ✅ 🎉 |
| **31.05. 09:00** | **Bench-Test Refactor C am Pi** | 📅 scheduled |
| Anfang Juni | Echte Testfahrt mit Refactor + USB-only + Hardware-Updates | ⏳ |
| Anfang Juni | ZTE-WLAN-Port-Forwarding fixen (Tablet↔Pi externer Zugang) | ⏳ |
| Anfang Juni | Autostart am Pi aktivieren (`install_autostart.sh`) | ⏳ |
| 06./07.06. | Reserve-WE für letzte Fahrtests + Bug-Fix | herabgestuft |
| Vor 15.06. | Geschäftskonto eröffnet | ⏳ (nicht zwingend) |
| **15.–18.06.** | **DLG-Feldtage Bernburg** — erste öffentliche Demo | Hauptevent |
| Juli 2026 | GitHub-PAT von Classic auf Fine-grained rotieren (läuft August aus) | 📅 |
| Nach 15.06. | RTCM-Löten, Cloudflare-Tunnel (`measure1.fjw-systems.com`), Pi-User/Hostname-Migration | später |

---

## Konventionen / Falk's Präferenzen

- **Sprache:** Deutsch.
- **Tonalität:** pragmatisch, direkt, keine Floskeln.
- **Vor destruktiven Änderungen fragen** ("wenn du änderungen machst frage mich").
- **DEVLOG parallel führen** — jeder Code-Change kriegt einen Eintrag mit Was/Warum/Test offen/Risiko.
- **Vertrauliche Daten niemals ins Repo:** echte HW-IDs, NDAs, Kalkulationen, Förderanträge gehören in `business/` oder werden sanitisiert.
- **Calendar:** noch nicht freigeschaltet. Steuerberater (Freund) kümmert sich Falk selbst.

---

## Tech-Stack

- **Python 3** (Pi 5, venv): Flask, pyserial, pyubx2, pyproj, numpy, geopy
- **Frontend:** Vanilla HTML + Chart.js (CDN)
- **GNSS:** u-blox ZED-F9P, Moving-Base, **10 Hz** (effektiv erreicht nach USB-only Configs v2 + Refactor C). Baudrate 460800 auf USB.
- **LTE-Konnektivität:** ZTE-WLAN-Stick + Thingsmobile IoT-SIM in der Box (für DLG-Stand-WLAN; Port-Forwarding für externen Zugriff noch zu fixen)
- **Datenformat:** CSV mit `;`-Separator und `,`-Decimal (Excel-DE-kompatibel)

---

## Offene Punkte / Ideen für später

**Vor DLG (15.06.):**
- **Bench-Test Refactor C** (31.05. 09:00 scheduled): wenn >95% iTOW-Lücken bei 100 ms → Merge nach main
- **ZTE-WLAN-Port-Forwarding**: WLAN-Verbindung Tablet↔Pi funktioniert, aber externer Port (Remote-Zugriff aufs Frontend) klemmt. ZTE-Admin-Interface checken.
- **Autostart am Pi aktivieren** (`bash system/pi/install_autostart.sh`) — Code liegt schon, war für "nach Generalprobe" geplant, jetzt der richtige Moment
- **Echte Testfahrt** mit allen Updates zusammen (Refactor C + USB-only + Box + Cooler)

**Nach DLG:**
- **Remote-Zugriff `measure1.fjw-systems.com`** — Cloudflare-Tunnel (braucht Nameserver-Umstellung weg von Strato) ODER Pi-eigener WLAN-AP als Fallback
- **Pi-User + Hostname migrieren** — derzeit User `ba_weigand`, Hostname `BA_Weigand` aus der BA-Zeit. Sauberer wäre `motionpsm` + `motionpsm-pi-01`
- **Base-Config mit USBonly_v2 nachflashen** — war beim 5-Hz-Fix nicht zwingend (Base war nicht der Engpass), nur für Konsistenz
- **NumSV / HDOP / accHeading** im Frontend zeigen
- **GitHub-PAT** von Classic auf Fine-grained umstellen (Sicherheit)
- **Mail-/Kalender-MCP** (Google Workspace) — Cowork-Connector

## Hardware-Detail: udev-Regeln am Pi

Falk hat udev-Regeln eingerichtet, die die F9P-Module unter festen Kurz-Namen mappen (Pi-User noch `ba_weigand` aus BA-Zeit, Migration post-DLG geplant):
- `/dev/serial/by-id/usb-B_B-if00` (Base)
- `/dev/serial/by-id/usb-R_1-if00` (Rover 1, links)
- `/dev/serial/by-id/usb-R_2-if00` (Rover 2, rechts)
- `/dev/serial/by-id/usb-R_3-if00` (Rover 3, vorne)

Diese Namen kommen in seine echte `system/config/config.json` (.gitignored). Die `config.example.json` im Repo hat die langen Standard-IDs als Platzhalter.

---

## Wie ich (Claude) helfe

- Code-Änderungen: erst Diff zeigen, dann committen, dann pushen.
- Bei langen Tasks: TodoList + Backup vor destruktiven Schritten.
- Push erfolgt via PAT (im August 2026 auslaufend); Token bei Bedarf erneuern.
- Branches: pro Feature ein eigener Branch, Push auf GitHub, Merge per Falk-Entscheidung.
- Bei neuer Session: bitte dieses File lesen, dann letzten DEVLOG-Eintrag, dann `git log --oneline -10` für aktuellen Repo-Stand.
