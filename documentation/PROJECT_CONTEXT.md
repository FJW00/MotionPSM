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

- **Base** (u-blox ZED-F9P, C099 Board): zentrale RTK-Basis, sitzt mittig auf dem Schlepper / Traktor. Sendet RTCM-Korrekturen via UART2 an die Rover.
- **Rover 1** (ZED-F9P): **links** am Gestänge montiert (vom Fahrer aus gesehen).
- **Rover 2** (ZED-F9P): **rechts** am Gestänge.
- **Rover 3** (ZED-F9P): **vorne in Fahrtrichtung**, definiert die Längsachse Base→R3. *Neu hinzugefügt im Mai 2026.*
- **Raspberry Pi 4**: zentrale Steuerung. Liest alle Module über USB ein (`/dev/serial/by-id/...`), läuft Flask-Server zur Live-Anzeige + CSV-Logger.
- **Antennenhalter**: STEP-Files in `hardware/f9p/`.

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

### CSV-Layout (70 Spalten)
1. R1 (17 Spalten) — Heading-Stats, Position, Quality
2. R2 (17)
3. R3 (17)
4. Base (8) — Position, Heading, Speed
5. Berechnungen (11) — Variante A + B + Achsen-Info + Gestängebewegungs-Total

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

- **Excel-Auto-Fill** für Prüfprotokoll (Prio 3, nach 15.06.)
- **History-Bereinigung** des alten `MotionPSM_Old`-Repos (löschen nach erfolgreichem Wochenend-Test)
- **Onepager-Website** fjw-systems.de (Prio 3 — nach 15.06.; statt carrd evtl. eigenes HTML/Tailwind über Netlify)
- **NumSV / HDOP / accHeading** im Frontend zeigen (derzeit nur Fix-Quality) — kleiner Refactor in gps_measurement.py: globale Vars ergänzen
- **Gewerbeanmeldung** + Steuerberater-Termin (Falk macht selbst)

---

## Wie ich (Claude) helfe

- Code-Änderungen: erst Diff zeigen, dann committen, dann pushen.
- Bei langen Tasks: TodoList + Backup vor destruktiven Schritten.
- Push erfolgt via PAT (im August 2026 auslaufend); Token bei Bedarf erneuern.
- Branches: pro Feature ein eigener Branch, Push auf GitHub, Merge per Falk-Entscheidung.
- Bei neuer Session: bitte dieses File lesen, dann letzten DEVLOG-Eintrag, dann `git log --oneline -10` für aktuellen Repo-Stand.
