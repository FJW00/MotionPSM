# DEVLOG

Detail-Log aller Änderungen am MotionPSM-System. Neueste Einträge oben.

---

## 2026-05-11 — Autostart: systemd-Service + neues Wrapper-Script

**Was:**

Drei Files in `system/pi/`:
- `autostart_schwingung_fw.sh` — überarbeitetes Wrapper-Script.
  - Erkennt seinen eigenen Pfad und davon ausgehend Repo-Pfad automatisch (egal wo das Repo geclont ist).
  - Prüft, ob `config.json` existiert — wenn nicht, klare Fehlermeldung.
  - Aktiviert venv falls vorhanden (`<repo>/.venv/`), sonst System-Python3.
  - `exec python3` ersetzt den Shell-Prozess, damit systemd Crashes erkennt.
- `motionpsm.service.template` — systemd-Service-Template mit Platzhaltern `{{USER}}` und `{{REPO_DIR}}`.
  - 10 Sek `ExecStartPre=/bin/sleep` damit USB-Hardware Zeit hat sich zu enumerieren.
  - `Restart=on-failure` mit `StartLimitBurst=10` in 300 Sek — bei Crashes Restart-Loop, aber kein endloses Re-Loopen.
  - Logging über journalctl (`SyslogIdentifier=motionpsm`).
- `install_autostart.sh` — Einmal-Installer.
  - Erkennt aktuellen User + Repo-Pfad automatisch.
  - Rendert das Template mit den korrekten Werten.
  - Kopiert generierte Service-Datei nach `/etc/systemd/system/` (sudo).
  - `systemctl enable` damit Service beim Boot startet.

**Warum:**

- Altes `autostart_schwingung_fw.sh` hatte hardcoded Pfade aus dem Pre-Refactor-Stand (`/home/ba_weigand/software/final/PI/server.py`) — funktioniert nach Repo-Restrukturierung nicht mehr.
- Shebang stand auf Zeile 4 statt Zeile 1 — wurde so nicht als Bash-Script erkannt.
- Es gab keinen systemd-Service. Ein `.sh` allein startet nicht beim Boot.
- Neue Lösung ist portabel (Repo kann überall liegen), user-agnostisch (Installer erkennt User), und resistent (Restart-on-failure).

**Test offen:**

Am Pi einmalig:
```bash
cd ~/MotionPSM   # oder wo immer geclont
git fetch
git checkout feature/rover3       # oder refactor/cleanup
cp system/config/config.example.json system/config/config.json
nano system/config/config.json    # COM-Port-IDs eintragen
bash system/pi/install_autostart.sh
sudo systemctl start motionpsm
sudo systemctl status motionpsm
sudo journalctl -u motionpsm -f
```

Erwartete Sanity-Checks:
- `systemctl status motionpsm` zeigt `active (running)`
- `journalctl` zeigt "Roverthread 1/2/3 started", "Basethread started", "[Logger] Thread gestartet"
- `http://<pi-ip>:5000` liefert das Frontend

**Risiko:**

- `ExecStartPre=/bin/sleep 10` reicht evtl. nicht wenn USB-Hardware langsam enumeriert. Notfalls in der Service-Datei auf 20 oder 30 erhöhen.
- venv-Detection: wenn der User vorher ein venv angelegt hat, das aber unter einem anderen Pfad als `<repo>/.venv/` liegt, wird es ignoriert. Falls nötig: VENV_DIR im autostart-Script anpassen.
- Logs landen in journalctl, nicht in einer Datei. Falls eine eigene Log-Datei gewünscht: `StandardOutput=append:/var/log/motionpsm.log` ergänzen.

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
