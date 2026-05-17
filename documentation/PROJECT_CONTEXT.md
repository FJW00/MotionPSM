# PROJECT_CONTEXT — MotionPSM / FJW Systems

**Diese Datei ist das Cold-Start-Briefing für jede neue Cowork-Session.**
Falk sagt zu Beginn: "Lies erst `documentation/PROJECT_CONTEXT.md`" — und du bist sofort drin.

Stand: 2026-05-11.

---

## Wer und Was

**Person:** Falk-Jakob Weigand, HSWT-Absolvent (Bachelor 2025). Gründet aktuell **FJW Systems** (Einzelunternehmen in Vorbereitung). Hauptberuf parallel: Vollzeit-Job Mo–Fr 7–16 Uhr. Codet abends + Wochenenden.

**Produkt:** **MotionPSM** — Low-Cost GNSS-basiertes Mess-System zur Erfassung der Gestängebewegungen von Pflanzenschutzspritzen. Soll Landwirten / Maschinenherstellern eine günstige Möglichkeit geben, Boom-Schwingungen quantitativ zu erfassen.

**Kontakt:**
- Email: falkweigand1304@gmail.com / info@fjw-systems.com
- Domain: fjw-systems.de, fjw-systems.com (Onepager in Vorbereitung mit carrd.co)
- Firmensitz: Steinig 1a, 97956 Werbach

---

## Hardware-Architektur

- **Base** (u-blox ZED-F9P, C099 Board): zentrale RTK-Basis. **MUSS am Schlepper / Anbaubock fest sitzen, NICHT am Gestänge** (sonst werden die Rover-Schwingungen systematisch verfälscht — Erkenntnis aus 17.05.-Test). Maximale Sky-View. Sendet RTCM-Korrekturen via UART2 an die Rover.
- **Rover 1** (ZED-F9P): **links** am Gestänge montiert (vom Fahrer aus gesehen).
- **Rover 2** (ZED-F9P): **rechts** am Gestänge.
- **Rover 3** (ZED-F9P): **vorne in Fahrtrichtung am Schlepper** (NICHT am Gestänge), definiert die Längsachse Base→R3.
- **Raspberry Pi 4**: zentrale Steuerung. Liest alle Module über USB ein (`/dev/serial/by-id/...`), läuft Flask-Server zur Live-Anzeige + CSV-Logger.
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

### CSV-Layout (81 Spalten, Stand 17.05.)
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
│   │   │   └── config.json             <- echte COM-Port-IDs (.gitignored, nur lokal/am Pi)
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

- `main` — sauberer Stand nach Reset (11.05.)
- `feature/rover3` — Rover-3-Erweiterung (Code-Erweiterung + Visualisierung)

---

## Termine + Meilensteine

| Datum | Was |
|---|---|
| 14.05. (Do) — Christi Himmelfahrt | Bench-Test Rover 3 am Schreibtisch |
| 15.05. (Fr) — Brückentag | Erste Fahrt mit Spritze |
| 16./17.05. | Feldtest + Iterationen |
| 06./07.06. | **Generalprobe-Wochenende** vor DLG (nicht-verhandelbar) |
| 15.06. (Mo) bis ca. 18.06. | **DLG-Feldtage Bernburg** — Kundenterminmust-haben |

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

- **Python 3** (Pi): Flask, pyserial, pyubx2, pyproj, numpy, geopy
- **Frontend:** Vanilla HTML + Chart.js (CDN)
- **GNSS:** u-blox ZED-F9P, Moving-Base, 10 Hz, RTCM via UART2
- **Datenformat:** CSV mit `;`-Separator und `,`-Decimal (Excel-DE-kompatibel)

---

## Offene Punkte / Ideen für später

- **Remote-Zugriff `measure1.fjw-systems.com`** (NACH 15.06.) — Falk will Frontend per Domain erreichbar machen statt nur per lokaler IP. Optionen: Cloudflare-Tunnel (braucht Nameserver-Umstellung weg von Strato) oder Pi-eigener WLAN-AP. **Falk explizit darum gebeten ihn zu erinnern.**
- **Pi-User + Hostname migrieren** (NACH 15.06.) — derzeit User `ba_weigand`, Hostname `BA_Weigand` aus der BA-Zeit. Sauberer wäre z.B. User `motionpsm` + Hostname `motionpsm-pi-01`. Aufwand mittel (Home-Verzeichnis umbenennen, SSH-Keys neu, Pfade anpassen). Falk erinnern.
- **Excel-Auto-Fill** für Prüfprotokoll (Prio 3, nach 15.06.)
- **History-Bereinigung** des alten `MotionPSM_Old`-Repos (löschen nach erfolgreichem Wochenend-Test)
- **Onepager-Website** fjw-systems.de (Prio 3 — nach 15.06.; statt carrd evtl. eigenes HTML/Tailwind über Netlify)
- **NumSV / HDOP / accHeading** im Frontend zeigen (derzeit nur Fix-Quality) — kleiner Refactor in gps_measurement.py: globale Vars ergänzen
- **Gewerbeanmeldung** + Steuerberater-Termin (Falk macht selbst)

## Hardware-Detail: udev-Regeln am Pi

Falk hat udev-Regeln eingerichtet, die die F9P-Module unter festen Kurz-Namen mappen:
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
