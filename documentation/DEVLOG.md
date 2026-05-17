# DEVLOG

Detail-Log aller Änderungen am MotionPSM-System. Neueste Einträge oben.

---

## 2026-05-17 — Hardware-Erkenntnis: Base muss am Schlepper, nicht am Gestänge

**Beobachtung aus Test-Fahrt Records_F9P_20260516_171707_ausg.xls:**

Bei einer 73°-Kurvenfahrt (sichtbar im `Axis_R3_heading_deg`-Plot: 145° → 72°) blieb das Gestänge mit ~17 cm Symmetric Yaw verdreht hängen (R1 ≈ −15 cm, R2 ≈ +20 cm im Endstand). Zusätzlich schwankte `Axis_R3_length_m` während der Fahrt um 4 cm (4.97 ↔ 5.03 m) — sollte konstant sein bei festem R3.

**Ursache:** Base war auf der gezogenen Spritze selbst am Gestänge montiert. Damit:
- Base schwingt mit dem Gestänge mit
- `relPosNED` ist Rover-Position minus Base-Position → Schwingung der Base wird von der Rover-Schwingung abgezogen
- Reale Gestängebewegung wird systematisch zu klein gemessen
- Achse Base→R3 wackelt, weil Base als Bezugspunkt selbst nicht ruhig ist
- Base hat zudem schlechtere Sky-View am Gestänge → schlechtere RTK-Qualität

**Hardware-Regel ab jetzt:**
- **Base am Schlepperdach** (oder höchster fester Punkt am Schlepper), maximale Sky-View
- **R3 ebenfalls am Schlepper** (Anbaubock, vorne in Fahrtrichtung) — definiert Längsachse aus zwei schlepperfesten Punkten
- **R1, R2 am Gestänge-Ende** — die einzigen Punkte die wirklich schwingen sollen
- Damit ist die Achse Base→R3 garantiert stabil und `relPosNED` für R1/R2 misst echte Gestängebewegung 1:1

**Halterung-Tipp (Falks Eigenkonstruktion):** Antennen mit Rohrklemmen aus Kamerazubehör auf Standardrohren befestigt. Funktioniert sehr gut, vibrationsfest. Wird übernommen für alle Aufbauten.

**Folge für Daten-Validität:**
Die Test-Daten vom 16.05. (Base am Gestänge) sind als Konzept-Validierung brauchbar, aber für quantitative Aussagen nicht final — die 17 cm Restverdrehung könnte teilweise Base-Schwingungs-Artefakt sein, teilweise echte mechanische Hysterese im Gestänge. Mit Base am Schlepper (ab Dienstag 19.05.) werden die Werte sauberer.

**Test offen:**
- Dienstag 19.05.: Neuer Aufbau mit Base + R3 am Schlepper, R1/R2 am Gestänge. Vorher Tare drücken.
- Erwartung: `Axis_R3_length` stabil ±1 cm, R1/R2 longitudinal im Stand sauber bei 0, nach Schwingungsabklingen wieder ≈ 0 (außer echte mechanische Verdrehung).

---

## 2026-05-17 — Mathematik-Beweis: Variante A ist rotationsinvariant

**Frage Falks:** Wenn die Maschine Kurven fährt, verschiebt sich dann mein gemessener longitudinal-Wert durch das wechselnde Maschinen-Heading?

**Antwort:** Nein. `VarA_R1_longitudinal_cm` ist mathematisch invariant gegen Maschinen-Rotation, sofern R3 wirklich fest am Schlepper sitzt.

**Beweis (kurz):**
Sei R_θ die Rotationsmatrix der Maschine um Winkel θ. Bei reiner Rotation gilt:
```
R1_NED' = R_θ × R1_NED
R3_NED' = R_θ × R3_NED
Achsen_Einheitsvektor' = R_θ × Achsen_Einheitsvektor
longitudinal' = R1_NED' · Achsen_Einheitsvektor' = R1_NED · Achsen_Einheitsvektor = longitudinal
```
(Skalarprodukt ist rotationsinvariant.)

**Praktische Implikation:** Wenn nach einer Fahrt die R1/R2 longitudinal-Werte nicht in 0 zurückkommen, ist die Ursache:
1. Reale mechanische Verdrehung des Gestänges (Hysterese, gehemmter Pendel-Rückgang)
2. R3 hat sich physisch relativ zum Schlepper verstellt
3. Slow Phase-Drift (Ionosphäre, Antennen-PCO) — typisch nur wenige cm

**NICHT die Ursache:** das Maschinen-Heading. Die alte Sorge vor "Heading-Drift" ist mit R3 mathematisch abgedeckt.

---

## 2026-05-17 — Tare-Funktion (Set Zero / Clear)

**Was:** UI-Button "⌖ Set Zero" oben rechts (links neben Smoothed/Raw-Toggle, dezent gestaltet) speichert die aktuellen longitudinal+lateral-Werte von R1 und R2 als Nullpunkt-Referenz. Alle nachfolgenden Live-Werte und CSV-Spalten `VarA_R*_*_tared_cm` werden gegen diesen Offset berechnet. Status "Tared HH:MM:SS" zeigt aktiven Tare-Zustand mit `×`-Button zum Clear.

**Warum:**
- Rover sind nie 100% perfekt symmetrisch zur Längsachse montiert (z.B. R1 sitzt 5 cm weiter vorne als R2) → ohne Tare permanente Offsets
- Nach RTK-Re-Fix oder Halterung-Verstellung kann man auf aktuelle Position nullen ohne Code-Eingriff
- Workflow: Maschine fertig aufgebaut + still → Set Zero → Messung starten → alles relativ zur Ausgangslage

**Implementation:**
- `gps_measurement.py`: Module-Globals `TARE_R1/R2_LONG/LAT_CM` + `TARE_SET_AT`, plus `set_tare()` / `clear_tare()` Funktionen
- `server.py`: Endpoints `/zero` (POST/GET) und `/zero/clear` (POST/GET); `/data` subtrahiert Offsets vor Auslieferung
- CSV bekommt 5 zusätzliche Spalten am Ende: `VarA_R1/R2_longitudinal/lateral_tared_cm` + `Tare_set_at`
- Roh-Werte bleiben im CSV erhalten — Post-Processing-Flexibilität

**Bewusst NICHT persistent:** Tare-Werte werden nicht in eine JSON gespeichert, sondern bleiben nur pro Pi-Session. Begründung: modular auf verschiedene Spritzen — jede Spritze braucht eigenes Tare beim Aufbau.

**Test offen:** Dienstag 19.05. erste Praxis-Nutzung im Maschinen-Setup.

---

## 2026-05-17 — Filter-Iteration: Moving-Average + UI-Toggle Smoothed/Raw

**Was:**
- `config.json` neues Feld `FILTER_WINDOW_S` (Default 0.2 s = 2 Samples bei 10 Hz Sample-Rate). Höhere Werte = mehr Glättung + mehr Verzögerung.
- `gps_measurement.py`: Moving-Average-Buffer in `start_measurement()` initialisiert, im Logger berechnet. Module-Globals `R1/R2_longitudinal_filtered_cm`.
- `server.py` `/data` Endpoint: 4 neue Felder (`r1/r2_longitudinal_filtered_cm`, `symmetric/asymmetric_yaw_filtered_cm`).
- UI: Toggle "Smoothed | Raw" oben rechts. Default = Smoothed. Persistent in localStorage (Key `motionpsm_data_mode`).
- CSV bekommt **immer** beide Spaltensätze (raw + filtered), unabhängig vom UI-Toggle — für Post-Processing-Flexibilität: 6 neue Spalten (`VarA_R*_longitudinal_filtered_cm`, `Symmetric/Asymmetric_Yaw_raw/filtered_cm`).

**Warum:**
- Im Stand schwanken die Rover-Werte auch bei RTK Fix um wenige cm (Multipath, Phase-Drift). Beim Lesen der Live-Anzeige war das verwirrend.
- Echte Boom-Schwingungen sind typisch 0.5–2 Hz (Periode 0.5–2 s) — diese kommen durch einen 0.2-s-Filter quasi unverändert durch.
- Der `FILTER_WINDOW_S`-Wert ist im Feld änderbar ohne Code-Eingriff.

---

## 2026-05-17 — Bug-Fix: relPosN/E/D Skalierung (Faktor 100 zu groß)

**Symptom:** `Detected Boom Width` im Frontend zeigte 40 m statt 4 m. Im CSV waren `VarA_R*_lateral_cm` 100× zu groß (z.B. 47500 statt 475).

**Ursache:** u-blox `NAV-RELPOSNED` liefert via pyubx2 die `relPosN/E/D`-Werte als **raw cm-Integers**, nicht als Meter. Der alte Code behandelte sie als Meter, dann wurden sie im Logger nochmal × 100 für cm umgerechnet → Faktor 100 zu groß.

**Fix:** in den drei Rover-Threads:
```python
Rover_N = ((parsed_data.relPosN or 0) + (getattr(parsed_data, 'relPosHPN', 0) * 1e-2)) * 1e-2
```
Erklärung: `(relPosN_cm + HPN × 0.01_cm)` ist die volle Position in cm; `× 0.01` konvertiert in Meter. Analog Rover_E, Rover_D.

**Verifiziert mit Falks CSV Records_F9P_20260515_123745.csv:**
- Rover_1_N war 475.58 cm fehlinterpretiert, jetzt 4.7558 m ✓
- Rover_2_N war −464.38 cm, jetzt −4.6416 m ✓
- Rover_3_E war 513.04 cm, jetzt 5.1304 m ✓

---

## 2026-05-17 — UI-Iteration: longitudinal als Hauptmetrik, Logo, Roboto, Englisch

**Erkenntnis von Falks erstem Frontend-Test:** Das ursprüngliche Layout zeigte `lateral_offset_cm` als Hauptmetrik. Aber lateral ist im Ruhezustand ≈ halbe Gestängebreite (≈ konstant), nicht die Schwingung. **Die echte Schwingungs-Metrik ist `longitudinal_cm`** (Vor-/Rückwärts-Komponente entlang der Fahrtrichtung).

**Umgebaut:**
- Hauptanzeige im Hero: `R1/R2 longitudinal` + `Symmetric Yaw` + `Asymmetric Yaw` + Winkel R*-Baseline
- SVG-Layout neu: Top-Down View. R1/R2-Marker wandern vertikal mit longitudinal-Wert. Soll-Position als grauer Schatten.
- Skalierung automatisch dynamisch aus den gemessenen Werten, keine manuelle Boom-Width-Eingabe mehr nötig.
- Branding: FJW-Logo (Logo_FJW_Final.png) oben links + Schriftzug "FJW Systems / MOTIONPSM". "Real Time Monitor" oben rechts in gleicher Größe.
- Komplett englisch.
- Roboto als Schriftart (passt zur Briefvorlage).
- Heading-Schwingung-Plot raus (nur Deflection-History bleibt).
- R3-Marker im SVG: transparent (45 %) und näher am Gestänge.

**GeoGebra-Referenz für Konvention:**
- Symmetric Yaw = (R2_long − R1_long) / 2 → entspricht Falks Symmetrisches-Gieren-Sketch (R1 negativ, R2 positiv bei positivem α)
- Asymmetric Yaw = (R1_long + R2_long) / 2 → reine Translation des gesamten Gestänges
- Vorzeichen: + = nach vorne in Fahrtrichtung

---

## 2026-05-17 — Autostart + Pi-Setup-Pipeline

**Was:** Drei neue Files in `system/pi/`:
- `setup_pi.sh`: Einmaliger Pi-Setup. apt-Pakete (python3-venv, git, pip), venv unter `<repo>/.venv/`, pip install -r requirements.txt, config.json aus Template.
- `requirements.txt`: flask, pyserial, pyubx2, pyproj, numpy, geopy
- `autostart_schwingung_fw.sh` + `motionpsm.service.template` + `install_autostart.sh`: systemd-Service mit Pfad-Auto-Detection, USB-Wait (10 s), Restart-on-failure, journalctl-Logging.

`documentation/PI_SETUP.md`: Schritt-für-Schritt-Anleitung von frischem Pi-OS bis "Service läuft beim Boot", inkl. Trouble-Shooting-Tabelle und Update-Workflow.

**Warum:** Alter Autostart hatte hardcoded BA-Pfade (`/home/ba_weigand/software/final/...`) und war nicht systemd-basiert. Neue Lösung ist portabel (Repo kann überall liegen), user-agnostisch (Installer erkennt User), und resistent (Restart-on-failure).

**Status (17.05.):** Falk nutzt vorerst manuellen Start ohne Autostart. Autostart wird aktiviert, sobald das System ein Wochenende ohne Eingriff durchgelaufen ist.

---

## 2026-05-11 — Visualisierung neu: Gestänge-Hero + alle 3 Rover + Längsachse

**Was:**

`system/pi/server.py` komplett neu strukturiert. UI-Fokus von Heading-Charts auf **Gestänge-Auslenkung in cm** verschoben.

Layout (von oben nach unten):
1. **Hero "Aktuelle Gestänge-Auslenkung"**:
   - Eingabefeld Gestängebreite (cm), Default 1500
   - Schematisches SVG: horizontale Linie mit R1-Marker (links, blau), R2-Marker (rechts, rot), R3-Marker oben (grün, "Fahrtrichtung"), Mittelachse als gestrichelte Linie. Die Marker bewegen sich live mit `lateral_offset_cm`.
   - Drei Wert-Boxen: R1-Auslenkung (cm, signed), Gesamt-Differenz R1−R2 (cm), R2-Auslenkung (cm, signed)
2. **Quality-Grid + Achse-Info nebeneinander**:
   - Quality-Tabelle pro Rover (Fix-Type-Badge, Angular Velocity, Schwingung in °)
   - Längsachse Base→R3: Länge in m, Heading in °, plus Fahrgeschwindigkeit
3. **Zwei Live-Charts (kleiner)**:
   - Verlauf lateral_offset R1/R2/Differenz (cm)
   - Heading-Schwingung R1/R2/R3 (° mov_avg)

`/data` Endpoint erweitert auf 16 Felder (neue: r1/r2_lateral_cm, gestaenge_total_cm, axis_length_m, axis_heading_deg, r3_quality, r3_angular_velocity, r3_vibration). Alle returnen JSON-safe (`round` für Floats, Fallback 0 für None).

CSS responsive (Grid bricht auf 1-Spalte um bei <800px). Polling-Intervall 200 ms.

**Warum:**

- Alte UI zeigte nur ° (Heading) — für den User schwer interpretierbar im Feld. Cm-Auslenkung der Boom-Ausleger ist direkt und intuitiv.
- Gestängebreite-Input ist Live-konfigurierbar (vom User vor Ort einstellbar), wirkt nur auf die SVG-Skalierung — Daten selbst bleiben unverändert.
- Rover 3 ist jetzt erstklassig sichtbar (Quality-Reihe + Achsen-Info). Längsachse Base→R3 wird live als Länge + Heading angezeigt — direkter Sanity-Check: Länge sollte stabil sein (≈ physische Distanz Base zu R3, z.B. 2-3 m), Heading sollte mit Fahrtrichtung übereinstimmen.

**Test offen:**

- Frontend in Chrome / Safari / Firefox am Tablet/Smartphone testen (responsive Layout).
- SVG-Marker-Bewegung bei extremen Werten (>> Gestängebreite/2): Marker rutschen außerhalb der SVG-Box. Aktuell wird ohne Clipping gerendert — bewusst, damit Anomalien sichtbar bleiben.
- Performance bei längerer Messung: Charts haben CHART_MAX_POINTS = 80 Sliding-Window — sollte fluffig bleiben.

**Risiko:**

- Bei R3-Ausfall (RTK lost) sind `lateral_offset_cm` Werte = 0 (Fallback in gps_measurement.py). Die UI würde dann "R1=0, R2=0" anzeigen — verwechselbar mit "Gestänge gerade". Mitigation: Quality-Badge zeigt rot/grau bei R3 → User erkennt sofort, dass Daten nicht trauenswürdig.
- `boom_total = lateral_r1 − lateral_r2` ist als rohe Differenz definiert. Bei symmetrischer Aufhängung sollte das im Stand ≈ 0 sein. Falls Falks Setup asymmetrisch ist (z.B. R1 weiter draußen als R2), ist `boom_total` permanent verschoben — nicht falsch, aber interpretationsbedürftig.

**Vor erstem Lauf am Pi:**

Pi braucht Flask + die anderen Python-Deps. Sollte schon installiert sein vom alten Stand. Falls nicht:
```bash
pip install flask pyserial pyubx2 pyproj numpy geopy
```

---

## 2026-05-11 — PROJECT_CONTEXT.md angelegt

**Was:** `documentation/PROJECT_CONTEXT.md` mit Cold-Start-Briefing für neue Cowork-Sessions: Wer/Was, Hardware, Mess-Konzept, Repo-Struktur, Termine, Konventionen, Tech-Stack.

**Warum:** Cowork hat keine "Projects"-Feature wie claude.ai. Mit einem zentralen Kontext-File startet jede neue Session sofort produktiv — Falk muss nur "lies PROJECT_CONTEXT.md" sagen.

---

## 2026-05-11 — Rover3-Erweiterung: Längsachse + Mittelachsen-Projektion

**Was:**

Neuer Branch `feature/rover3`. Rover 3 sitzt vorne in Fahrtrichtung am Schlepper. Der Vektor Base→R3 definiert die geometrische Längsachse der Maschine — sauberer und im Stillstand stabiler als das bisherige Verfahren (Base-Heading aus Eigenbewegung).

Neue Files:
- `system/pi/geometry.py` — Helper-Modul mit:
  - `vehicle_axis(relNED_r3)` → Achsenlänge, Einheitsvektor (aN_hat, aE_hat), Heading
  - `lateral_offset_a(relNED_rover, aN_hat, aE_hat)` → Variante A: Querauslenkung
  - `diff_vector_b(relNED_target, relNED_reference)` → Variante B: Differenzvektor
  - Konvention: lateral_m > 0 → Rover links der Mittelachse (Fahrer-Perspektive)
  - MIN_AXIS_LENGTH_M = 0.05 (5 cm Mindestlänge der Achse, sonst None)

Geändert: `system/pi/gps_measurement.py`
- Imports: `from geometry import vehicle_axis, lateral_offset_a, diff_vector_b`
- Neue globale Variablen: `current_vibration_rover3`, `quality_rover3`, `R3_angular_velocity`
- Live-Server-Variablen: `R1_lateral_offset_cm`, `R2_lateral_offset_cm`, `vehicle_axis_length_m`, `vehicle_heading_via_r3`
- Rover3-Buffers analog R1/R2 (vibration_buffer, heading_buffers, rel_heading_buffer, etc.)
- `last_relNED_r1/r2/r3` — Snapshots der jeweils letzten relPosNED (Tuple), vom Rover-Thread gesetzt, vom Logger gelesen. Python-GIL macht atomare Tuple-Assignment thread-safe.
- Rover1_Thread + Rover2_Thread: ein-Zeile-Patch, Snapshot in `last_relNED_rN` setzen
- `Rover3_Thread()` neu, voll spiegelbildlich zu Rover2_Thread (für CSV-Konsistenz; alle Werte loggable)
- `csv_logger_thread_buffered()` komplett neu:
  - 3-Wege-Sync: alle drei Rover-iTOWs müssen innerhalb `tolerance_rover = 0.1` liegen, Base innerhalb `tolerance_base = 0.5` vom Rover-Mittel
  - Var. A: Projektion R1/R2 auf Längsachse → lateral_cm, longitudinal_cm
  - Var. B: Direkte Differenzvektoren R3→R1 und R3→R2 → distance_cm, heading_deg
  - Gestängebewegungs-Indikator: `lat_r1 - lat_r2` (≈ Querbewegung des gesamten Gestänges)
  - Fallback: bei zu kurzer R3-Achse alle Var. A Werte = None (CSV: leere Zelle)
- `export_to_csv()` Header: 28 neue Spalten (17 R3 + 11 Calc), insgesamt jetzt 70 Spalten
- `start_measurement()`: ROVER3_COM_PORT einlesen, streamRover3 öffnen, Rover3_Thread starten
- `stop_measurement()`: streamRover3.close() ergänzt
- `start_measurement()` Config-Pfad korrigiert: `'..', 'config.json'` → `'..', 'config', 'config.json'` (neue Ordnerstruktur nach Reset)

`system/config/config.example.json`:
- Neues Feld `ROVER3_COM_PORT` als Template

**Warum:**

- Bisheriges Verfahren: Base-Heading aus Eigenbewegung (`base_calc_heading_buffer`) ist verrauscht und fällt im Stillstand komplett aus → bisher Notfall-Glättung über Moving-Average.
- Neues Verfahren: Vektor Base→R3 ist eine harte geometrische Achse, **auch im Stillstand stabil**. R1/R2 werden senkrecht darauf projiziert → echte Querauslenkung in Metern. Der Moving-Average bleibt als Glättung, ist aber nicht mehr für die Mittellinien-Stabilisierung nötig.
- Variante A (Projektion) ist die Hauptmetrik; Variante B (Differenzvektoren) wird parallel mitgeloggt zur Validierung und für ggf. spätere Auswertungen.

**Test offen:**

- Bench-Test am Schreibtisch mit angeschlossenen F9P-Modulen: Lassen sich alle 3 Rover öffnen, schreibt der Logger CSV-Zeilen mit 70 Spalten, sind die Werte plausibel (R1 lateral ≈ Gestängearm-Länge mit gewünschtem Vorzeichen, longitudinal ≈ 0)?
- Konvention prüfen: ist R1 in deinem Setup wirklich links (positiv) und R2 rechts (negativ)? Falls vertauscht: COM-Port-IDs in config.json tauschen.
- Hardware-Verkabelung Rover 3 mit Base (Moving-Base UART-Brücke / RTCM): erhält Rover 3 RTCM-Korrekturen wie R1/R2?
- Feldtest am Wochenende 14.-17.05.: Erste Fahrt → CSV inspizieren → Auslenkungs-Werte gegen optische / Seilzug-Referenz vergleichen.

**Risiko:**

- Vorzeichen-Konvention links/rechts: getestet in geometry.py mit 4 Test-Szenarien (heading 0°, 90°, 45°, zu-kurze-Achse). Bei Test stimmt links=positiv, rechts=negativ. **Wichtig**: bei der Montage muss R1 wirklich an die linke Auslegerseite, R2 an die rechte, R3 nach vorne in Fahrtrichtung. Bei Vertauschung sind die Vorzeichen falsch herum.
- Logger 3-Wege-Sync: falls einer der Rover länger als ~100 ms hängt, fallen Samples raus. Bei 10 Hz Sampling ist das aber ok; nur bei massiven RTK-Drops könnte Datenrate sinken.
- Globale relNED-Snapshots: bei sehr seltenen Race-Conditions könnte der Logger eine "alte" R1-Position mit einer "neuen" R3-Achse mischen. Praktisch unbedeutend bei 10 Hz, aber technisch nicht 100% race-frei. Falls Bedarf später: durch Queue mit (iTOW, relNED) ersetzen und im Logger nach passendem iTOW suchen.

---

Format pro Eintrag:
- **Datum** + Kurz-Subject
- **Was:** Konkrete Änderung mit Pfaden
- **Warum:** Begründung / Hintergrund
- **Test offen:** Was muss am System verifiziert werden
- **Risiko:** Potenzielle Probleme

---

## 2026-05-11 — Repository neu strukturiert, sauberer Schnitt

**Was:**
- Altes Repo `FJW00/MotionPSM` umbenannt zu `FJW00/MotionPSM_Old` (auf GitHub) — bleibt als Referenz erhalten.
- Neues leeres `FJW00/MotionPSM` als Zielrepo angelegt.
- Lokaler Projekt-Ordner `FJW_Schwingung` komplett reorganisiert.
- Vorher (alter Stand): software/, hardware/, documentation/, Validierung/, AS_Digi/, Abgabe/, Kalkulationen/, exist Gründungsförderung/, NDA-PDFs, alle gemischt im Repo.
- Nachher: Strikte Trennung Code+Hardware (im neuen Repo) vs. Business+Daten+BA-Doku (nur lokal+NAS, niemals Git).

**Warum:**
- Alter Repo-Stand mischte technisches Material mit NDA, Preiskalkulation, Förderanträgen und der BA-Endabgabe. Bei einer späteren Einladung von Co-Foundern / Mitarbeitern / Reviewern wäre das problematisch.
- Saubere Trennung von Anfang an erspart spätere History-Bereinigung mit `git filter-repo` (sensible Daten bleiben nach `git rm` in der History und sind über alte Commit-Hashes wieder zugänglich).
- Repo wird durch CSV-Exclusion deutlich kleiner und schneller zu klonen.

**Neue Ordnerstruktur lokal (`FJW_Schwingung/`):**
- `MotionPSM_repo/` — Git-Repo (Klon von github.com/FJW00/MotionPSM)
  - `system/` — Lebender Code, Configs, Analysis-Templates
  - `hardware/` — STEP/SLDPRT-Modelle
  - `documentation/` — DEVLOG + Auftaktnotizen
  - `archive/legacy_software/` — alte Code-Varianten als Referenz
- `business/` — Branding, Gründung, Finanzen, Recht, Kunden, Vorlagen, Website (vertraulich)
- `data/` — Messdaten-CSVs, Validierungs-Excels, Literatur-PDFs (zu groß für Repo)
- `BA_Abgabe/` — Bachelorarbeit-Endstand, eingefroren read-only
- `archive/2026-05-11_full_backup/` — 1:1 Backup des Zustands vor der Umstrukturierung
- `archive/_legacy_empty/` — geparkte, jetzt leere Original-Ordner (macOS-Sandbox erlaubt kein `rmdir`)

**Lebende Code-Variante:**
- Quelle war `software/final/BA_Weigand_Software/`
- Ziel ist jetzt `MotionPSM_repo/system/pi/`
- Files: `gps_measurement.py`, `server.py`, `autostart_schwingung_fw.sh`
- `config.json` (mit echten COM-Port-IDs) liegt unter `system/config/config.json` und ist via `.gitignore` ausgeschlossen.
- Template ohne sensible Daten: `system/config/config.example.json`

**Test offen:**
- Verifikation, dass `git clone` auf dem Raspberry Pi den Repo-Stand vom 11.05. korrekt zieht.
- Am Pi muss `config.json` aus `config.example.json` neu erstellt und mit den lokalen COM-Port-IDs befüllt werden.
- Erster `python3 system/pi/server.py`-Lauf am Pi nach dem Pull.

**Risiko:**
- Keine direkten Code-Risiken — Code-Inhalt ist 1:1 erhalten, nur Pfade haben sich geändert.
- Operativ: COM-Port-IDs in `config.json` müssen am Pi neu eingetragen werden (waren bewusst nicht im Repo).
- Falls Pfad-Hardcodes im Code stecken (z.B. relative Pfade zu Logging-Verzeichnissen), könnten die nach der Reorganisation brechen — beim ersten Pi-Lauf überprüfen.

---
