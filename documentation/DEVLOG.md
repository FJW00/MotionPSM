# DEVLOG

Detail-Log aller Änderungen am MotionPSM-System. Neueste Einträge oben.

---

## 2026-08-15 — Live-Degradation: Kandidat 2 (Thermik) ausgeschlossen, nächster Test vorbereitet

**Kandidat 2 (thermische Pi-Drosselung) ausgeschlossen — Falks Gegenargument:** War nicht heiß am 14.08., und wichtiger: ein CFG-RST-Reset am F9P-Modul kann die Pi-CPU-Temperatur/-Drosselung gar nicht beeinflussen. Dass der Reset zuverlässig sofort wieder 10Hz bringt, beweist, dass die Ursache am F9P/USB-Pfad hängt, nicht an allgemeiner Pi-Rechenlast/Hitze. Sauberer Ausschluss, nicht nur Bauchgefühl.

**Falk hat außerdem die USB-Strom-Drosselung am Pi (Throttling bei zu hoher Stromaufnahme über die USB-Ports) deaktiviert.** Für später als Idee notiert, aber nicht akut: F9P-Module ggf. direkt über eigene 5V-Versorgung statt über Pi-USB-Strom versorgen, falls Strom weiterhin ein Thema wird.

**Verbleibende Kandidaten für die Live-Degradation während einer laufenden Messung** (Sammlung aus Falks und meinen Ideen):
- GIL-Kontention Flask vs. Producer-Threads mit sich aufschaukelndem Rückstau (Puffer/Backlog wächst statt sich einzupendeln)
- Pi drosselt USB-Geschwindigkeit unter Last (unabhängig von der jetzt deaktivierten Strom-Drosselung — ggf. Bandbreiten-/Scheduling-Ebene)
- F9P-interner Sende-Puffer läuft voll, wenn Host nicht schnell genug abholt (Falk hält das für unwahrscheinlich)
- Moving-Base fürs Senden an 1 Rover ausgelegt, jetzt an 3 gleichzeitig — vermutlich kein Faktor, da RTCM-Output vermutlich als Broadcast auf UART2 läuft (ein Sendevorgang, mehrere passive Hörer), nicht pro Rover einzeln dupliziert — müsste aber verifiziert werden, nicht nur angenommen.
- USB-Verbindung/Controller am Pi generell (Hub-Bandbreite, Scheduling)

**Nächster Test (vorbereitet, noch nicht ausgeführt):** 4 Module **gleichzeitig, aber komplett unabhängig von `gps_measurement.py`/Flask** auslesen — 4 separate Python-Prozesse parallel für 60s (kein gemeinsamer GIL, kein Flask-Polling), Wall-Clock-Zeit + iTOW pro Sample in JSON loggen. Soll trennen zwischen:
- Degradation tritt AUCH hier auf → Ursache liegt auf USB/Hardware-Ebene (Pi-Controller, F9P-Verhalten unter 4-fach-Last), unabhängig vom Python-Code.
- Bleibt sauber bei 10Hz → Ursache ist spezifisch an der `gps_measurement.py`/Flask-Architektur festzumachen (GIL/Threading).

Skript-Vorlage liegt im Chat-Verlauf bereit (4 parallele `python3 -c`-Hintergrundprozesse, einer pro Modul, `wait` am Ende, JSON-Output nach `/tmp/hz_parallel_test/`).

**Test offen:** Hoftest-Aufbau + paralleler Test stehen noch aus (Falk ist heute an was anderem dran, macht das, sobald der Hoftest wieder steht).

---

## 2026-08-14 (Fortsetzung 3) — CFG-RST-Reset auf alle 4 Module + End-to-End-Test: weiterhin NEGATIV

**Was:** UBX-CFG-RST (Hardware-Reset, Hot-Start) auf alle 4 Module (Base, R1, R2, R3) angewendet, einzeln verifiziert (siehe unten), danach `systemctl start motionpsm` und echte Messung über die Web-UI (Set Zero → Start → ~60s → Stop → Export). 2 CSVs unter `~/Documents/FJW_Schwingung/Records/CSV/20260814/`.

**Einzel-Verifikation der Rover nach Reset (vor der eigentlichen Messung):** R1/R2/R3 lagen vor dem Reset alle bei ~4.6-4.7 Hz (200ms-Boden, festgefahren aus den vielen Tests/Start-Stops des Tages). Nach CFG-RST-Reset + Wartezeit: wenn Daten kamen, ~9.9 Hz (82×100ms + 12×200ms) — deutliche Verbesserung, nicht perfekt. Vereinzelt 0 Samples in den ersten Verifikationsversuchen direkt nach Reset (`Port wieder offen` aber 0 NAV-RELPOSNED in 10s) — plausibel durch RTK-Ambiguitäts-Neuaufbau nach Hardware-Reset, der laenger dauert als der reine Port-Reconnect; begleitet von "Unknown protocol header"-Meldungen (Frame-Muell waehrend des Modul-Neustarts, erwartbar, kein eigenstaendiger Bug).

**End-to-End-Ergebnis trotzdem negativ:**

| Datei | Dauer | Median dt | ≤100ms | eff. Rate | Sync-Mismatches |
|---|---|---|---|---|---|
| 194005 | 61s | 200ms | 0.0% | 4.22 Hz | 0 |
| 194233 | 60s | 200ms | 19.5% | 3.31 Hz | 0 |

Sync weiterhin perfekt (0 Mismatches R1/R2/R3/Base) — bestätigt erneut, dass der Logger nicht die Ursache ist.

**Korrektur nach genauerem Blick auf den zeitlichen Verlauf (nicht nur die aggregierte Verteilung) — Falk hat zu Recht nachgehakt:**

- **194005** (mit mehr Zwischenschritten zwischen Reset und Start): von Sample 0 an nie 100ms, durchgehend 200/500ms im Wechsel.
- **194233** (laut Falk: direkt nach Restart, ohne Pause, sofort UI → Start): **die ersten 8 Samples laufen exakt bei 100ms** — sauberer 10-Hz-Start, bestätigt dass ein wirklich unmittelbarer Reset→Start-Übergang funktioniert. Danach kippt es aber **progressiv während der laufenden Messung**: ab ca. Sample 60 (~10-12s Messdauer) dominiert 200ms, ab Sample ~140 kommen zunehmend große Aussetzer (500-2200ms) dazu.

**Das heißt: zwei unterschiedliche, sich überlagernde Mechanismen, nicht einer:**
1. **Vor-Start-Degradation** (bereits bekannt): Zwischenschritte/Verzögerung zwischen Reset und Messstart verschlechtern die Startqualität (194005 vs. 194233).
2. **NEU — Live-Degradation während der Messung selbst:** Selbst mit sauberem 100ms-Start baut sich die Rate innerhalb der 60s-Messung progressiv ab. Das konnten die bisherigen Isolationstests nie zeigen, weil die immer nur 10s mit einem einzelnen Thread liefen, nie 60s mit dem vollen System (4 Threads + Flask-Polling durch den Browser alle 100ms). Das deutet wieder Richtung der alten GIL/Flask-Polling-Konkurrenz-Theorie aus dem Juni 2026 — zusätzlich zur F9P-internen Akkumulation, die heute isoliert nachgewiesen wurde.

**Schlussfolgerung für heute:** Ein einmaliger Reset zu Sessionbeginn reicht nicht — weder gegen die Vor-Start-Degradation (braucht Reset unmittelbar vor jedem Start) noch gegen die Live-Degradation während der Messung (das ist ein anderes, noch ungeklärtes Thema, vermutlich GIL/Threading-bezogen, nicht F9P-Hardware).

**Nicht heute umgesetzt** (Falk wollte für heute Schluss machen) — Code-Änderungen erst nach Rücksprache, siehe Standing Rule #4 (Approval vor größeren Änderungen).

**Test offen (zwei getrennte Baustellen für nächstes Mal):**
1. **Vor-Start-Degradation:** CFG-RST-Reset direkt in `start_measurement()` integrieren (eigener Branch, nicht auf `fix/reader-once-per-thread`), mit Wartezeit auf RTK-Fix statt fixem Sleep.
2. **Live-Degradation während der Messung:** eigene Diagnose nötig — z.B. dt-Verlauf über die Zeit in einer 60s-Messung mit `top`/CPU-Last parallel beobachten, ob GIL-Kontention (Flask-Polling vs. Producer-Threads) zeitlich mit dem Abfall korreliert. Nicht mit Schritt 1 verwechseln, vermutlich unabhängige Ursache.
3. Branch `fix/reader-once-per-thread` bleibt weiterhin ungemergt, `main` weiterhin auf `v1.0-dlg`.

---

## 2026-08-14 (Fortsetzung 2) — Akkumulation lokalisiert: F9P-intern, nicht Pi/Kernel/Python

*(Datums-Korrektur: dieser und die beiden folgenden Einträge waren ursprünglich fälschlich auf 05.08. datiert — Standing Rule #1 nicht befolgt, Datum nicht neu geprüft nach Session-Sprung. Tatsächliches Datum laut Systemzeit + CSV-Timestamps: 14.08.2026. Zwischen dem Hoftest vom 05.08. und dieser Diagnose-Session lagen also 9 Tage.)*

**Testreihe (Falk, isolierter Base-Test, mehrere aufeinanderfolgende `python3 -c`-Prozesse):**

| Schritt | Aktion | Ergebnis |
|---|---|---|
| 1 | frischer Zustand | 9.8 Hz (94×100ms, 3×200ms) |
| 2 | nochmal derselbe Test, kein UI-Kontakt | 8.4 Hz |
| 3 | nochmal | 6.9 Hz |
| 4 | nochmal | 7.0 Hz |
| 5 | `usb_reset_f9p.sh` (Kernel-Unbind/Bind aller 4 Module, Strom bleibt an) | 7.4 Hz — **kaum Besserung** |
| 6 | Base **physisch aus- und wieder eingesteckt** (echter Stromausfall am Modul) | **10.1 Hz — sauber zurückgesetzt** |

**Zentrale Deduktion:** Jeder Testlauf ist ein komplett unabhängiger, frisch gestarteter `python3 -c`-Prozess — es kann also kein Python-interner State zwischen den Läufen überleben. Die Akkumulation liegt damit nachweislich außerhalb von `gps_measurement.py` und außerhalb von Python generell. Dass selbst das Kernel-seitige USB-Unbind/Bind (Schritt 5 — das Gerät wird aus Sicht des Linux-Treibers vollständig ab- und neu angemeldet) keine Wirkung zeigt, aber das echte Stromtrennen (Schritt 6) sofort resettet, lokalisiert die Ursache **im F9P-Modul selbst** — vermutlich ein interner USB-Peripherie-/Puffer-Zustand in der Empfänger-Firmware, der mit jeder neuen Host-Verbindung (Serial-Open) ohne echten Power-Cycle etwas degradiert.

**Bedeutung für die bisherige Diagnose-Kette:** Widerlegt die Milestone-B-Grundannahme ("Subprocess-Architektur löst Akkumulations-Bug, da sauberer Prozess-Kill") — ein neuer OS-Prozess ändert nichts, weil der Zustand nicht auf OS/Python-Ebene sitzt. NMEA-Multicast-Fix (30.05./14.08.) und RTCM3-Fix (14.08.) waren beide berechtigt und wirksam für den Ruhezustand (sauber 10 Hz vor jeder Nutzung) — lösen aber nicht die Degradation durch wiederholtes Öffnen/Schließen der Verbindung.

**Praktische Konsequenz:** Physisches Kabel-Ziehen zwischen jeder Messung ist im Feld nicht praktikabel. Nächster Test: **UBX-CFG-RST (Hardware-Reset, Hot-Start, `navBbrMask=0`)** per Software an die Base senden — simuliert intern einen Chip-Reset ähnlich dem Stromausfall, ohne Kabel anzufassen. Falls das denselben Reset-Effekt hat wie Schritt 6: Kandidat, um direkt in `start_measurement()` eingebaut zu werden (Reset senden, kurz auf Fix warten, dann erst Messung starten) — würde das Problem für jede Feldsession automatisch lösen.

**Test offen:** UBX-CFG-RST-Test von Falk ausstehend. Falls das NICHT reicht: Fallback wäre eine steuerbare USB-Hub-Stromversorgung (z.B. `uhubctl`, falls der verwendete Hub Port-Power-Switching unterstützt) um den physischen Power-Cycle zu automatisieren.

---

## 2026-08-14 (Fortsetzung) — RTCM3-Multicast-Fix bestätigt + Akkumulations-Bug lebt noch

**RTCM3-Fund (Falk, per u-center direkt an Base):** Auf der Base waren mehrere RTCM3-Messages zusätzlich zu UART2 (Sollzustand laut Architektur: RTCM nur UART2 Base→Rover) noch auf **USB und UART1** aktiv. Rausgenommen. Gleiches Muster wie der NMEA-Multicast-Fund vom 30.05. — nur bei den Korrektur-Messages statt bei NMEA/GGA/RMC/VTG, zusätzliche Output-Operationen pro Zyklus.

**Bestätigt: Fix wirkt.** Isolierter 10s-dt-Test auf Base direkt nach dem RTCM3-Fix, **vor** jedem Start einer Messung über die Web-UI: N=100, dt-Verteilung 97× 100ms + 2× 200ms → **10.0 Hz effektiv, sauber.**

**Neuer, wichtigerer Fund direkt danach:** Web-UI aufgerufen, **eine** Messung gestartet und wieder gestoppt (Service danach wieder gestoppt für den nächsten Isolationstest) — direkt danach derselbe 10s-dt-Test auf Base: N=77, dt = 52× 100ms + 24× 200ms → **7.7 Hz.** Keine Config wurde dazwischen verändert. Einziger Unterschied: `gps_measurement.py` hat einmal den Base-Port geöffnet und wieder geschlossen.

**Einordnung:** Das ist mit hoher Wahrscheinlichkeit der alte **"Akkumulations-Bug"**, dokumentiert am 22.05., 30.05. und 01.06.2026 ("2.-N. Messung (nur Server-Restart): 200-247ms iTOW-Mittel... Nur Pi-Reboot setzt vollständig zurück"). Der wurde damals nie ursächlich gelöst, nur mit `/tmp`-Cleanup + `usb_reset_f9p.sh` pragmatisch für die DLG umschifft, und die systematische Lösung auf Milestone B (Subprocess-Architektur) vertagt. Sieht so aus, als sei er nie weg gewesen — er wurde von der viel dominanteren NMEA/RTCM-Multicast-Drosselung überdeckt, die jetzt gefixt ist.

**Konsequenz für die bisherige Diagnose-Kette:** Die 200ms/5Hz-Werte im Hoftest-CSV vom 05.08. (siehe Eintrag oben) waren vermutlich eine Überlagerung aus zwei unabhängigen Bugs: Base-Multicast (jetzt gefixt) + Start/Stop-Akkumulation (weiterhin offen). Reine F9P-Config-Fixes reichen also nicht für einen im Feld nutzbaren Zustand — nach jedem Start/Stop-Zyklus einer Messung würde man wieder degradieren.

**Test offen (bestätigender Test, von Falk angekündigt):**
1. Pi-Reboot, ohne Website/Messung: Base-Test → erwartet wieder sauber 10 Hz (Baseline-Reset-Verhalten wie in den alten Einträgen beschrieben).
2. Eine Messung starten/stoppen, danach Test → erwartet erneuter Rückgang (Reproduzierbarkeit).
3. Zweites Start/Stop ohne Reboot dazwischen → alte Einträge deuten auf **progressive** Verschlechterung mit jedem weiteren Zyklus hin, nicht nur einen einmaligen Sprung.

**Falls bestätigt:** nächster Fokus verschiebt sich von F9P-Config zurück zu `stop_measurement()`/`start_measurement()` in `gps_measurement.py` — was genau beim Schließen/Wiederöffnen des Serial-Streams einen sauberen Neustart verhindert.

---

## 2026-08-05 — Hoftest UBXReader-Fix: NEGATIV. Root-Cause liegt nicht im Logger.

**Was:** Verifikations-Hoftest für `fix/reader-once-per-thread` (Commit `8b0c6c5`) durchgeführt (Falk, 20:38–20:50 Uhr), 7 Messläufe à 60 s im Hof. CSVs abgelegt unter `data/Records/Reader-once-per-thread/`.

**Ergebnis: Fix hat NICHT gewirkt.** dt-Analyse über alle 7 CSVs (`R1_Rover_time`-iTOW-Diffs):

| Kennzahl | Erwartung | Tatsächlich |
|---|---|---|
| Median dt | ~100 ms | **200 ms** (alle 7 Läufe) |
| Anteil dt ≤100 ms | ≥95 % | 0.1 % |
| Effektive Rate | ≥9.5 Hz | 3.2–5.0 Hz |

RTK-Quality durchgehend 4 (Fix) in allen Läufen — kein GNSS/RTK-Problem.

**Entscheidender Zusatzbefund — Logger-Sync ist NICHT die Ursache:** `R1_Rover_time`, `R2_Rover_time`, `R3_Rover_time` und `Base_Time` sind in **allen 7 Dateien zu 100 % identisch pro Zeile** (0 Mismatches über 1830 Zeilen). Falk hat den Hoftest zusätzlich live per `journalctl -u motionpsm -f` verfolgt — keine einzige "[Logger] dropped X iTOWs"-Meldung. Das heißt: `csv_logger_thread_buffered` (iTOW-Dict, Refactor C) funktioniert exakt wie designed und verliert nichts. Alle vier Threads (Base + R1 + R2 + R3) liefern neue iTOWs bereits **quellseitig nur alle 200 ms im Gleichschritt** — das ist kein Race/Sync-Problem im Python-Code, sondern eine Rate-Begrenzung vor dem Logger.

**Damit sind widerlegt:** Milestone-A-Hypothese (Queue-Konsum vor Toleranz-Prüfung, 17.07.) UND die UBXReader-Neuinstanziierungs-Hypothese (26.07.) als alleinige/hinreichende Ursache — beide sind Logger-/Reader-interne Fixes, aber das Problem sitzt eine Ebene tiefer.

**Neue Hypothese:** Rate-Ceiling auf F9P-Hardware-Ebene, vermutlich analog zum bereits einmal gelösten Fall vom 30.05.2026 ("NMEA-Multicast drosselt intern auf 5 Hz", siehe Eintrag weiter unten) — nur diesmal vermutlich am **Base-Modul**, das laut CLAUDE.md-Stand nie auf `Base_USBonly_v2` geflasht wurde ("Kleinigkeit, 5 Min am Modul" — offener Punkt seit 30.05., nie erledigt). Passt zum Bild: Base_Time läuft im exakten Gleichschritt mit allen 3 Rovern — in Moving-Base-RTK hängt die Rover-RELPOSNED-Rate an den RTCM-Korrekturepochen der Base. Wenn Base intern (NMEA auf allen 5 Ports weiterhin aktiv, nicht USB-only) auf 5 Hz gedrosselt ist, geht das über die RTCM-Kopplung 1:1 auf alle 3 Rover durch — unabhängig vom UBXReader-Fix im Python-Code.

**Sekundärbefund:** in 6 von 7 Läufen zusätzlich 7–21 % der Übergänge bei ~500 ms statt 200 ms (Lauf 1, 20:38 Uhr, war sauber — nur 2×400 ms). Fällt zeitlich mit den geplanten Hand-Auslenkungen an R1/R2 zusammen, vermutlich kurze RTK-Fix-Aussetzer durch Antennen-Anfassen, separates Thema von der 200-ms-Rate-Deckelung.

**Test offen (nächster Schritt, VOR weiterem Code):**
1. CFG-RATE-MEAS auf allen 4 Modulen direkt prüfen (u-center oder `pyubx2 UBX-CFG-VALGET`) — insbesondere ob das am 30.05. verifizierte 100-ms-Setting noch steht, speziell auf der Base.
2. Base-Konfiguration gegen `system/config/f9p_ucenter/usb_only_v2_2026-05-30/` prüfen — Base wurde damals bewusst NICHT geflasht ("war nicht der Bottleneck" laut damaliger NAV-PVT-Messung). Zu klären: ob das unter vollem Moving-Base-RTK-Betrieb im Feld (statt Schreibtisch-Bench-Test ohne RTK-Last) noch stimmt.
3. Falls Base der Flaschenhals ist: `Base_USBonly_v2.txt` flashen (liegt vermutlich schon vor, siehe `f9p_ucenter`-Ordner) und Hoftest wiederholen.

**Risiko:** Kein Blocker für die bereits versendeten DLG-Kurzberichte (Nyquist bei 5 Hz für 0.5–2 Hz Boom-Schwingung weiterhin erfüllt). Blockiert aber weiterhin Milestone B und jede Frequenz-Spektrum-Analyse als Angebot. `fix/reader-once-per-thread` bleibt unangetastet, main bleibt auf `v1.0-dlg` — **kein Merge, kein Tag `v1.1-post-dlg`.**

### Update selber Tag — CFG-Check + Base-USB-only + Einzel-Hz-Test (Falk, ZBook direkt an Modulen)

**CFG-Werte auf Base verifiziert:** `RATE-MEAS=100ms`, `RATE-NAV=1` → angeforderte Rate korrekt 10 Hz (100×1). `RATE-TIMEREF=1 (GPS)` unauffällig. Diese Werte allein beweisen aber nichts über die *tatsächlich erreichte* Rate — dieselbe Lücke gab es schon am 30.05. (Config sagte 10 Hz, Chip lieferte real 5 Hz durch Output-Overload).

**Base MSGOUT auf USB-only umgestellt:** NMEA-GGA/RMC/VTG liefen auf Base noch auf UART/I2C zusätzlich zu USB (Rover waren das seit 30.05. nicht mehr, Base wurde damals bewusst ausgenommen). Auf USB-only gestellt, persistent gespeichert (BBR+Flash, laut Falk bestätigt).

**Isolierter Hz-Test auf Base (Service gestoppt, Antennen dran, Fix erreicht):**
- 5s-Test: 6.2 Hz
- 10s-Test mit dt-Verteilung: **N=67, dt = 33× 100ms + 33× 200ms exakt alternierend, 6.7 Hz effektiv**

**Wichtiger Deutungs-Shift:** Ein reines Rate-Ceiling (Chip berechnet nur alle 200ms eine neue Lösung) könnte niemals 100ms-Abstände produzieren. Dass hier exakt die Hälfte der Übergänge bei 100ms liegt, beweist: **die Base liefert intern tatsächlich 10 Hz**, aber ca. jede zweite NAV-PVT-Message geht zwischen Empfänger und Python-Zählskript verloren — randomisiert, nicht deterministisch. Strukturell dasselbe Symptom wie der UBXReader-Bug vom 26.07., obwohl der Reader in diesem Diagnose-Skript bereits korrekt einmal instanziiert wird (entspricht dem gefixten Pattern). Die Base-USB-only-Änderung hat leicht geholfen (5.0 → 6.2–6.7 Hz), aber nicht das Kernproblem gelöst.

**Neue Arbeitshypothese:** NMEA-Frames (GGA/RMC/VTG laufen weiter auf USB, nur nicht mehr auf UART/I2C) im selben USB-Byte-Stream interleaved mit UBX-Binärframes stören das Parsing/Timing und kosten dabei gelegentlich ein UBX-Frame — eine andere Variante des ursprünglichen "verlorene Bytes im Stream-Puffer"-Mechanismus, diesmal nicht durch Reader-Neuinstanziierung, sondern durch Message-Type-Mischung im Stream.

**Test offen (nächster Schritt):** NMEA auf Base-USB testweise komplett auf 0 (nur RAM/"Send", nicht "Store" — reversibel per Reboot), gleicher 10s-dt-Test wiederholen.
- Wenn dann sauber 100ms ohne Wechsel → NMEA-Interleaving bestätigt als (Teil-)Ursache → dauerhafte Lösung: GGA/VTG auf einen anderen Port (z.B. UART1) verlegen statt USB, damit `gps_measurement.py` (braucht Base_alt/Base_Speed aus GGA/VTG) weiter versorgt wird, ohne den NAV-PVT-Hauptstream zu stören.
- Wenn weiterhin alterniert → kein NMEA-Thema, dann tiefer auf Pi/USB-Treiber-Ebene schauen (`dmesg`, roher Byte-Count wie am 30.05.).

**Noch nicht getestet:** volle 4-Modul-Kette (Rover-Seite) nach der Base-Änderung — der Hoftest mit CSV-Export steht noch aus, ergibt aber erst nach dieser Isolierung Sinn.

---

## 2026-07-28 — Nachtrag: DEVLOG-Lücke Juni/Juli geschlossen

**Was:** Standing Rule #3 (CLAUDE.md) verlangt "wichtige Zwischenstände sofort ins DEVLOG" — das war für den Zeitraum 03.06. bis 26.07.2026 nicht passiert. Die folgenden 5 Einträge (17.07. bis 15.06.) sind rückwirkend rekonstruiert aus Commit-Historie (`git log`) und `data/Feldtage/02_Analyse_Docs/SESSION_LOG_Auswertung.md` (lokal, außerhalb Repo).

**Offener Punkt beim Rekonstruieren entdeckt:** SESSION_LOG_Auswertung.md behauptet für den 17.07. einen Code-Commit `9755749` ("iTOW-Bucket-Dict-Version", Branch `feat/subprocess-refactor`) inkl. Hinweis, der zugehörige DEVLOG-Text sei "lokal geändert (staged)" gewesen, aber wegen eines Sandbox-`index.lock`-Problems nie committed worden — mit der Anweisung, Falk solle das vom Mac aus nachholen. Verifiziert: **Commit `9755749` existiert nicht im Repo** (`git log --all`, `git fsck` — nicht auffindbar, auch nicht unreachable). `origin/feat/subprocess-refactor` steht exakt auf `5a322fe` (DLG-Lock), keinen Commit weiter. Der aktuelle Logger in `system/pi/gps_measurement.py` (`csv_logger_thread_buffered`, Zeile ~544) läuft bereits im iTOW-Dict-Modus — das ist aber Refactor C vom 30.05.2026, nicht die am 17.07. behauptete Änderung. **Der Milestone-A-Commit vom 17.07. ist vermutlich nie über den Sandbox-Lock hinausgekommen und komplett verlorengegangen**, nicht nur der DEVLOG-Text dazu.

**Einordnung:** Praktisch folgenlos — der tatsächliche 5-Hz-Root-Cause war ohnehin ein anderer (UBXReader-Neuinstanziierung, siehe Eintrag 26.07.), der Milestone-A-Fix vom 17.07. war laut SESSION_LOG selbst nur eine Hypothese-basierte Korrektur am alten Queue-Sync-Pattern. Trotzdem: falls in `data/Feldtage/.../PLAN_Phase2-1_2026-07-10.md` (Milestone B / Subprocess-Refactor) auf Details aus dem verlorenen Commit `9755749` aufgebaut werden soll, ist der Code weg und müsste aus dem SESSION_LOG-Text neu geschrieben werden.

**Test offen:** Keiner (reine Dokumentation). Falk ggf. fragen ob `feat/subprocess-refactor` als Branch noch gebraucht wird oder gelöscht werden kann, da er nichts Eigenes mehr enthält.

---

## 2026-07-26 — 5-Hz-Root-Cause gefunden und gefixt: UBXReader pro Thread neu instanziiert

**Branch:** `fix/reader-once-per-thread` (von `main`/`v1.0-dlg`), Commit `8b0c6c5`.

**Was:** In `BaseThread` + `Rover1/2/3_Thread` wurde `UBXReader(stream, validate=0)` bei **jeder** while-Iteration neu erzeugt statt einmal pro Thread. `pyubx2` hält einen internen Byte-Puffer, der beim Neu-Erzeugen verworfen wird — Partial-UBX-Frames aus dem Stream-Puffer gehen dabei verloren. Effekt: jede zweite NAV-PVT/NAV-RELPOSNED-Message wurde verpasst → effektive Rate 5 Hz statt 10 Hz. Fix: Reader wird beim Thread-Start einmal instanziert, danach nur noch `.read()` in der Schleife aufgerufen.

**Warum jetzt erst gefunden:** Der Fix existierte bereits als Experiment `a56b95f` (31.05.2026, Branch `experiment/ubxreader-cleanup`), wurde damals aber nie nach `main` gemerged — genau der Fall, den Standing Rule #2 in CLAUDE.md referenziert ("3 Wochen an einem Bug debuggt der schon längst gefixt war").

**Test offen:** Verifikations-Hoftest am Mittwoch 29.07.2026 abends (Falk), Testplan unter `data/Feldtage/02_Analyse_Docs/TESTPLAN_2026-07-29.md`. Erwartung: Median-dt springt von ~200 ms auf ~100 ms, ≥95 % der Samples ≤100 ms. Bei Erfolg: Merge nach `main`, Tag `v1.1-post-dlg`, danach Milestone B (Subprocess-Architektur) starten.

**Risiko:** Nur `gps_measurement.py` geändert (14+/4−), Reader-Threads sonst unverändert. Kein Risiko für die bereits versendeten DLG-Kurzberichte — deren Std-Abw-Kennzahlen bleiben bei 5 Hz gültig (Nyquist für Boom-Schwingung 0.5–2 Hz erfüllt), nur Frequenz-Spektrum-Analysen (Angebot in den Kurzberichten) brauchen die 10 Hz.

---

## 2026-07-17 — Sample-Rate-Diagnose Phase 2.1: Bug isoliert (Hypothese, siehe Nachtrag oben)

**Was:** Hz-Test am Pi (Falk) zeigt Base + alle 3 Rover feuern einzeln bei 10 Hz — F9P-Konfiguration damit als Ursache ausgeschlossen. Als Kandidat identifiziert: `.get()`-Aufrufe auf den Sync-Queues konsumierten Samples, bevor die iTOW-Toleranz-Prüfung lief — bei Mismatch wurden Samples verworfen statt zurückgelegt, Race zwischen asynchron befüllenden Reader-Threads. Offline-Simulator-Test (Worst-Case-Reordering) zeigte 0/200 vs. 200/200 emittierte Samples zwischen alt/neu.

**Siehe Nachtrag 2026-07-28 oben:** der zugehörige Commit `9755749` ist nicht im Repo auffindbar — dieser Eintrag dokumentiert die Diagnose, nicht einen verifizierten Merge-Stand.

**Test offen (damals geplant, nicht mehr relevant):** Feld-Test im Hof — wurde vermutlich nie durchgeführt, da der Root-Cause sich am 26.07. als ein anderer herausstellte (siehe oben).

---

## 2026-07-10 — Sample-Rate-Diagnose Phase 1: 5 Hz bei allen 6 DLG-Messläufen bestätigt

**Was:** dt-Analyse über alle 6 DLG-CSVs (5 Hersteller, HORSCH mit 2 Läufen): Sample-Rate konstant 5.0 Hz bei **0 %** der Samples auf 10 Hz. Rate ist stabil, kein Drift.

**Ausgeschlossen durch Korrelationsanalyse:** Multipath auf der Spritze (|r| < 0.15 zwischen dt und Speed/Heading-Rate), Akkumulations-Bug (dt in 1./3. Messdrittel identisch), Antennen-Setup.

**Damalige Hypothese:** Base-Modul hat die USB-only-v2-Config nie erhalten (nur auf Rovern geflasht) → Base intern auf 5 Hz gedrosselt → Sync-Logger zieht alles auf 5 Hz. Bestätigt durch Hz-Test am 10.07. (Base UND Rover liefen tatsächlich alle bei 10 Hz einzeln — die Hypothese "Base gedrosselt" war damit widerlegt, der eigentliche Bug lag im Logger/Reader, siehe Einträge 17.07. und 26.07.).

**Auswirkung auf die bereits versendeten Kurzberichte:** Std-Abw-Werte bleiben belastbar (Nyquist erfüllt für 0.5–2 Hz Boom-Schwingung). Frequenz-Spektrum-Analysen (im Angebotsteil aller 5 Kurzberichte enthalten) brauchen für eine bezahlte Folgemessung aber echte 10 Hz.

**Erzeugte Dateien:** `data/Feldtage/02_Analyse_Docs/SampleRate_Diagnose_2026-07-10.docx` + `.xlsx`.

---

## 2026-07-02 — DLG-Auswertung fertiggestellt, 5 Kurzberichte an Hersteller versendet

**Was:** Auswertung der DLG-Feldtage-Messungen (15.–18.06.2026 Bernburg) für 5 Hersteller-Spritzen (AGRIO, HORSCH, AGRIFAC, AMAZONE, KUHN; HORSCH mit 2 Messläufen, Lauf 1 verworfen). Kern-KPI: Std-Abw. R1/R2 in cm + % der Boom-Länge, Toleranz-Verteilung (±0.1/0.3/0.5 %).

**Methodik-Wechsel auf "Option D"** (Falks Entscheidung, angewendet auf alle 5 Berichte einheitlich): Heading-Rate-Schwelle 3°/s → 2°/s, Speed-Cutoff 3 → 5 km/h, Ausreißer-Cap ±3σ, Median-Zentrierung R1+R2 (Zero-Offset raus). Alle vier Änderungen sind ISO-2631-Standardpraxis, kein Zahlen-Schönen. Größter Effekt: KUHN R2 (±0.5 %-Anteil springt 28 % → 94 %) — lag an einem Tare-Zero-Offset, nicht an der eigentlichen Schwingung.

**KUHN-Caveat:** Antennen mussten aus Montage-Gründen bei 30 m statt am echten 36 m-Boom-Ende sitzen — im Kurzbericht als kursiver Hinweis vermerkt, im internen Vergleich als Klassen-Sonderfall markiert.

**Baseline-Backup** vor der Option-D-Umstellung unter `data/Feldtage/_archiv/backup_baseline_2026-07-02/`.

**Versendet:** 15.06. abends alle 5 `MotionPSM_Kurzbericht_<Hersteller>.docx`. Jeweils 1-seitig: Std-R1/R2-KPI-Kacheln, Toleranz-Tabelle, Angebots-Kasten (Frequenz-Spektrum, R&D-Messungen, Asymmetrie, Fahrgeschwindigkeit) für bezahlte Folgemessung. Kein Hersteller-Vergleich in den Berichten (Vertraulichkeit).

**Danach priorisiert (Falks Ansage 02.07.):** stabile 10 Hz Sample-Rate zuerst, vor Auto-Auswertungs-Pipeline — "sonst automatisieren wir im Zweifel schlechte Daten." Daraus resultierten die Diagnose-Einträge 10.07./17.07./26.07. oben.

**Test offen:** Follow-up mit den 5 Herstellern auf Reaktion/Interesse an Folgemessung — Stand 28.07. noch offen.

---

## 2026-06-15 bis 18 — DLG-Feldtage Bernburg: Live-Messungen bei 6 Hersteller-Vorführungen

**Was:** Vor-Ort-Einsatz des MotionPSM-Systems (`v1.0-dlg`-Stand, Tag `v1.0-dlg` auf `5a322fe`) bei den DLG-Feldtagen. Boom-Schwingungsmessungen an Feldspritzen von AGRIO und HORSCH (30 m-Klasse) sowie AGRIFAC, AMAZONE und KUHN (36 m-Klasse) — HORSCH mit 2 Messläufen (Lauf 1 später verworfen, Lauf 2 als Marken-Repräsentant genutzt), macht 6 Messläufe über 5 Hersteller.

**Warum:** Erster Praxiseinsatz nach dem DLG-Lock (Merge `feature/ui-system-restart` → `main`, 02.06.2026). Ziel: belastbare Vergleichsdaten für Kunden-Kurzberichte und Grundlage für Folgemessungs-Angebote.

**Test offen (Stand 15.06.):** keiner mehr offen — Rohdaten wurden erfolgreich erfasst, Roh-Excels unter `data/Feldtage/6× 20260630_*.xlsx` liegen als Basis für die Auswertung ab 30.06. (siehe Eintrag 02.07. oben).

**Risiko:** Rückblickend erkannt (siehe Eintrag 10.07.): alle 6 Messläufe liefen faktisch mit 5 Hz statt der angenommenen 10 Hz. Kein Blocker für Std-Abw.-KPIs (Nyquist erfüllt), aber relevant für zukünftige Frequenz-Spektrum-Angebote.

---

## 2026-06-02 spaet abends — UI-Politur (Branch feature/ui-system-restart)

Iteration auf dem Reboot/Refresh-Branch nach Falks Feedback:

1. **Filter-Default 0.2 → 0.5 s** (Moving-Average 5 Samples statt 2). Setzt sich in `gps_measurement.py` Default UND `config.example.json`. Falks lokales `config.json` muss zusaetzlich aktualisiert werden. Hintergrund: RTK-Rauschen so klein, dass Smoothed/Raw kaum unterscheidbar war — mit 500 ms-Fenster sichtbarere Glaettung.
2. **Header-Text:** "Real Time Monitor" → "MotionPSM" (oben rechts).
3. **Layout-Restructure:** alle 4 Buttons in eine eigene `action-bar`-Zeile UNTER dem Brand-Header. Reboot/Refresh links, Set Zero + Smoothed/Raw rechts (`justify-content: space-between`). Brand-Header bleibt zweizeilig (Logo + Name).
4. **Logo:** `logo_fjw.png` → `logo_brand.svg`. Das offizielle Firmenlogo aus `business/website/assets/` ist jetzt im Repo unter `system/pi/static/logo_brand.svg`. SVG skaliert sauber bei Tablet-Zoom.

Neue CSS-Klassen: `.action-bar`, `.action-bar-group`, `.sys-btn`, `.sys-btn-reboot`, `.sys-btn-refresh`. Hover-States fuer Reboot/Refresh.

---

## 2026-06-02 abends — UI-Buttons "Reboot" + "Refresh" (Branch feature/ui-system-restart)

**Ziel:** Für DLG zwei UI-Buttons im Brand-Header, mit denen Falk vom Tablet aus den Pi neu starten ODER nur den Service+USB-Reset auslösen kann — ohne SSH am Stand.

**Branch:** `feature/ui-system-restart` (von main da3cda1)

**Aenderungen `server.py`:**
1. Neuer Endpoint `POST /system_restart`:
   - Stoppt laufende Messung sauber
   - `subprocess.Popen(['sudo', '-n', '/sbin/reboot'])` (detached)
2. Neuer Endpoint `POST /system_refresh`:
   - Stoppt laufende Messung sauber
   - `subprocess.Popen(['sudo', '-n', '/bin/bash', tools/motionpsm_refresh.sh])` (detached)
3. HTML im Brand-Header: roter Button **Reboot** + oranger Button **Refresh** rechts neben "Real Time Monitor"
4. JS `systemRestart()` und `systemRefresh()` mit `window.confirm()` Dialog + Alert

**Neue Helper-Skripte:**
- `tools/motionpsm_refresh.sh` — laeuft als root via sudo:
  1. `sleep 1.5` (Flask-Response zurueck zum Client)
  2. `systemctl stop motionpsm.service` (toetet server.py)
  3. `tools/usb_reset_f9p.sh` (USB-unbind+bind)
  4. `systemctl start motionpsm.service` (Server kommt zurueck)
  Loggt nach `/tmp/motionpsm_refresh.log`
- `tools/setup_sudoers.sh` — schreibt `/etc/sudoers.d/motionpsm`:
  ```
  $USER ALL=(ALL) NOPASSWD: /sbin/reboot, /bin/bash <repo>/tools/motionpsm_refresh.sh
  ```
  Selbst-Pruefung via `visudo -c` VOR Installation (kein lockout-Risiko).

**Sicherheit:** sudoers erlaubt EXAKT `/sbin/reboot` und den vollen Pfad zu `motionpsm_refresh.sh`. Wenn jemand das Skript modifiziert um beliebigen Code auszufuehren — der User hat eh die Rechte das Skript zu modifizieren, also kein Privilegien-Eskalation.

**Test-Plan (auf Branch, vor merge nach main):**
1. `git pull && git checkout feature/ui-system-restart`
2. `sudo bash tools/setup_sudoers.sh` (einmalig)
3. `sudo -n /sbin/reboot --help` → muss ohne Passwort gehen
4. UI im Browser - beide Buttons sichtbar
5. **Refresh** klicken → ~15 s warten → F5 → UI wieder da, gleiche Pi-Session
6. **Reboot** klicken → ~60 s warten → F5 → UI wieder da, neue Pi-Session

**Bei Erfolg:** merge `feature/ui-system-restart` → `main`, Tag v1.0-dlg force-move.

---

## 2026-06-02 — Frontend-Polling 1000ms → 100ms (validiert, in v1.0-dlg)

**Befund 02.06. abends, 4-Run-Hof-Test mit Desktop deaktiviert:**
- Pi-OS-Desktop deaktiviert (raspi-config Console Autologin) — `ps aux` zeigt keine Xorg/Wayland mehr, RAM 305 MB used von 7.9 GB
- 4 aufeinanderfolgende 30s-Messungen:
  - Reboot 1 → 118 ms iTOW-Mittel (8.5 Hz)
  - Server-Restart → 158 ms (6.3 Hz)
  - Reboot 2 → 150 ms (6.7 Hz)
  - Server-Restart → 138 ms (7.2 Hz)
- **Akkumulations-Bug ist deutlich abgeschwächt!** Run 4 (Restart) ist sogar besser als Run 3 (nach Reboot). Desktop-Deaktivierung war der relevante Hebel.

**Change:** `setInterval(fetchData, 1000)` → `setInterval(fetchData, 100)` in server.py.

**Warum 100ms statt 1000ms:** Über mehrere Tests am 01./02.06. zeigte sich: 100ms-Polling ergibt bessere CSV-Quote als 1000ms (paradox). Hypothese: bei 100ms ist der Polling-Rhythmus exakt synchron zur 10Hz-Sample-Rate — Flask-Calls fallen in Sample-Lücken, blockieren Producer-Threads weniger. Bei 1000ms passieren die Calls zu sporadisch und treffen oft auf Sample-Ankunft.

**Tag v1.0-dlg force-moved** auf neuen HEAD nach diesem Commit. archive/pre-dlg-2026-06-01 bleibt unverändert als Sicherung.

---

## 2026-06-01 abends — DLG-Lock: /tmp-Cleanup + USB-Reset-Skript

**Befund Akkumulations-Bug (klar bestätigt):**
- Direkt nach Pi-Reboot + F9P-Reboot: iTOW-Mittel **140-155 ms** (≈ 6.5-7 Hz)
- 2.-N. Messung (nur Server-Restart): iTOW-Mittel **200-247 ms** (≈ 4-5 Hz)
- Reproduziert mit beiden Base-Configs (Original und USBonly_v2). Modul ist NICHT die Ursache.
- Frontend-Polling-Reduktion (1000ms) brachte _nichts_ — paradoxerweise zeigte 100ms-Polling die beste Quote.
  Heißt: GIL-Polling allein erklärt den Bug nicht.

**Hypothese:** Pi-USB-Subsystem oder Python-State akkumuliert zwischen Server-Restarts. Nur Pi-Reboot setzt vollständig zurück. Saubere Lösung wäre Subprocess-Architektur (gps_measurement als eigener Python-Prozess, getötet beim Stop) — aber zu viel Refactor 13 Tage vor DLG.

**Zwei pragmatische Quick-Hacks für DLG:**

### 1. `/tmp`-Cleanup nach erfolgreichem CSV-Download
`server.py` `/export`-Endpoint: nach `send_file` über `after_this_request`-Hook alle `/tmp/Records_F9P_*.csv` älter als 30s löschen (gerade gesendete Datei sicher ausgenommen). Nur wenn Response-Status 200/206.

**Warum:** Pi's `/tmp` ist tmpfs (RAM). Bei vielen Test-Runs ohne Cleanup wächst es. Reduziert RAM-Druck.

**Sicherheit:** Cleanup läuft erst NACH erfolgreichem Download — kein Datenverlust möglich.

### 2. `tools/usb_reset_f9p.sh` — F9P USB-Reset ohne Pi-Reboot
Bindet die 4 F9P-USB-Devices über `/sys/bus/usb/drivers/usb/{unbind,bind}` ab und wieder an. Setzt USB-Subsystem-State zurück ohne Reboot (~5s Dauer statt ~60s).

**Verwendung:**
```
# Server vorher stoppen:
sudo systemctl stop motionpsm    # falls Autostart
# oder Strg+C im Server-Terminal

sudo bash tools/usb_reset_f9p.sh

# danach Server wieder starten
```

**Test-Plan:** morgen am Pi testen — wenn nach Reset wieder ~140ms-Mittelwert → Workaround validiert für DLG.

### Was NICHT gefixt ist
- Eigentliche Akkumulations-Ursache (Subprocess-Refactor post-DLG)
- 100ms-Quote im Frontend-Live-View (Live-View ist nicht der CSV-Logger; Visualisierung ist OK)

**Risiko-Abwägung:** kein Code-Risiko (nur additive Maßnahmen). Cleanup im Export ist defensiv (after_this_request-Hook fängt Exceptions, dropt sie still). USB-Reset-Skript wird manuell aufgerufen.

---

## 2026-06-01 — Frontend-Polling 200ms → 1000ms (DLG-Lock-Kandidat)

**Befund:** Hof-Test 21:00 mit lean-producer + stop-cleanup + break→continue zeigte trotz allem **200ms-Pattern in CSV mit 42× "3 Rover gleichzeitig" Drop-Pattern**. Im Log-Output: Browser pollt `GET /data` alle 200ms = 5×/s.

Flask läuft im gleichen Python-Prozess wie Producer-Threads. Pro `/data`-Response: ~30-50ms CPU (math, jsonify, _g für 25 Variablen). Python's GIL → Producer-Threads sind während Flask-Response BLOCKIERT → verpassen NAV-RELPOSNED-Verarbeitung → unvollständige iTOW-Slots → CSV jede 200ms statt 100ms.

**Fix:** Frontend `setInterval(fetchData, 200)` → `setInterval(fetchData, 1000)`. 1 UI-Update pro Sekunde statt 5. Tablet zeigt Boom-Schwingung weiterhin flüssig (Schwingung ist 0.5-2 Hz, Update-Rate 1 Hz reicht für visuelle Demo).

**Erwartung:** Producer-Threads bekommen GIL zurück → 100ms-Quote sollte deutlich steigen.

**Wenn DLG-tauglich:** lean-producer → main merge. DLG-Lock.

---

## 2026-06-01 — Logger: break → continue (letzter Code-Test vor DLG-Lock)

**Hypothese:** Aktuell stoppt der Logger beim ersten jungen unvollständigen iTOW. Komplette spätere iTOWs müssen auf nächsten Cycle warten (max 20ms). Bei kontinuierlichem Stream mit gelegentlichen unvollständigen iTOWs könnte das die Output-Rate begrenzen.

**Change:** `break` → `continue`. Logger iteriert nun durch ALLE iTOWs in samples_by_itow:
- Komplette → schreiben + del
- Zu alte (>SAMPLE_MAX_AGE_MS) ohne komplett → drop + del
- Junge unvollständige → continue (im Dict lassen für nächsten Cycle)

**Erwartung:** wenn ein junger iTOW (z.B. 50ms alt) inkomplett ist, aber der nächste iTOW (10ms alt) komplett — wird der jüngere KOMPLETTE jetzt direkt geschrieben. Vorher blockierte der ältere unvollständige.

**Trade-off:** CSV-Zeilen-Reihenfolge nicht mehr strikt aufsteigend nach iTOW (kann aber via Spalte sortiert werden — keine echte Einschränkung).

**Risiko:** sehr gering. Wenn keine Verbesserung → Bottleneck liegt woanders (vermutlich Producer-Thread-Latency / Multi-Port-USB).

**Test offen:** Bench-Test refactor/lean-producer. Wenn deutlich besser → DLG-Version. Wenn nicht → akzeptieren dass 5-7 Hz mit aktuellem Stand der finale ist.

---

## 2026-06-01 — Stop-Cleanup-Fix: Thread + Stream Lifecycle sauber

**Befund:** Falk hat bemerkt — frischer Server-Start liefert deutlich bessere CSV-Daten als nach mehreren Start/Stop-Zyklen. Drop-Log bestätigt:
- `logger fresh after start`: 32 Drop-Lines, fast keine "3 Rover gleichzeitig"
- `logger ubx` (nach vorherigem Run): 128 Drop-Lines, 82× "3 Rover gleichzeitig"

**Ursache:** Im alten `stop_measurement()`:
- `t.join(timeout=2)` aber Producer-Threads sind in `ubr.read()` mit Serial-Timeout 3s blocking → Join gibt nach 2s auf
- Daemon-Threads laufen im Hintergrund weiter
- Beim nächsten `start_measurement()`: neue Threads + alte = mehr Threads → mehr GIL-Druck → mehr Drops
- `samples_by_itow.clear()` passierte nur in start, nicht in stop → Race möglich

**Fix:**
1. Streams ZUERST schließen → Producer-`ubr.read()` kriegt SerialException → Thread durchläuft Catch-Block → kann stop_event prüfen → endet
2. Join-Timeout auf 4s erhöht
3. `samples_by_itow.clear()` + `csv_data_buffer.clear()` in stop_measurement
4. start_measurement: defensiv prüfen ob alte Messung noch läuft + alte Threads noch leben

**Test offen:** Mehrere start/stop-Zyklen am Pi — sollte konsistent gleich gute Daten liefern wie frischer Start.

---

## 2026-06-01 — Lean Producer Threads: schwere Berechnungen raus, GIL entlastet

**Befund 31.05. (Hof-Tests, alle Browser-Tabs zu):**
Drop-Debug-Output zeigt klares Pattern: in 80.5% der Drops fehlen ALLE 3 ROVER gleichzeitig, Base ist da. 9.8% alle 4 fehlen, 7.3% nur Base. Browser-Polling-Hypothese damit ausgeschlossen.

**Diagnose:** Python GIL erlaubt nur 1 Thread Bytecode auf einmal. Die 3 Rover-Threads machen pro NAV-RELPOSNED:
- `np.linalg.lstsq` für angular_velocity (Linear Regression über 20 Punkte)
- Moving-Average mit sin/cos-Schleife über buffer
- init_heading + abs_heading Logik
- height_boom (Base_alt - Rover_alt)

Bei 30 NAV-RELPOSNED/s (3 Rover × 10 Hz) kämpfen die Threads um den GIL → werden gleichzeitig blockiert → Samples gehen verloren.

**Falks Entscheidung (01.06.):** Viele dieser Berechnungen sind Legacy aus der BA-Zeit und nicht mehr DLG-relevant. Behalten werden pro Rover nur: Heading, delta_Heading, Date, Time, Quality, Lon, Lat, accHeading, N, E, D, alt, Speed. Variante A/B + Filter + Tare bleiben im Logger unverändert (nutzen nur N/E/D).

**Änderungen:**

- BaseThread: `geodesic()` + `Point()` + sin/cos-Heading-Mittelwert raus. Base_Heading bleibt 0 (kommt aus Vektor Base→R3 im Logger).
- Rover1/2/3_Thread: `np.linalg.lstsq` (angular_velocity), `mov_avg_heading` mit sin/cos, `init_heading`/`abs_heading`, `current_vibration_*`, `height_boom` aus Base_alt-Diff — alle RAUS.
- Behalten in jedem Rover: `rel_heading` (direkt aus NAV-RELPOSNED), `delta_heading` (einfache Differenz über letzte 2 Werte).
- CSV-Schema unverändert: alle ehemaligen Berechnungs-Spalten bleiben im Header, Werte sind 0 statt berechnet. Rückwärtskompatibel für Excel-Auswertungen.

**Erwartung:** Producer-Threads sind ca. 5-10× weniger CPU-intensiv pro Message. GIL-Last drastisch reduziert. 100ms-Quote sollte deutlich steigen.

**Nachtrag 01.06.:** `height_boom` doch behalten — aus `-Rover_D * 100` (cm, positiv wenn Rover über Base). Eine Zeile pro Rover-Thread, keine Last-Relevanz.

**Test offen:** Hof-Bench-Test auf `refactor/lean-producer`. Drop-Debug-Output zeigt ob "alle 3 Rover gleichzeitig fehlen"-Pattern verschwindet.

**Risiko:** sehr gering. Wenn keine Verbesserung, einfach zurück auf refactor/logger-itow-dict. Geometrie/Mess-Pipeline (Var A/B, Tare) unverändert.

---

## 2026-05-31 — Rollback: SAMPLE_MAX_AGE_MS 500 → 300

**Befund vom Hof-Test 14:00:** Mit MAX=500 lieferte die CSV durchgängig 200ms-Steps (= 5 Hz effektiv), während die Module per pyubx2-Hz-Test sauber 10 Hz produzieren. Vormittag-Stand (MAX=300) hatte 60.8% bei 100ms erreicht — deutlich besser.

**Rollback:** SAMPLE_MAX_AGE_MS zurück auf 300. Architektur (break-Statement) bleibt unverändert. Stand entspricht commit a0fb3f3 (vor dem 500ms-Experiment).

**Test offen:** erneuter Hof-Bench-Test sollte ~60% bei 100ms reproduzieren. Ist das die Baseline, von der wir auf separatem Branch `experiment/ubxreader-cleanup` weiter optimieren.

---

## 2026-05-31 — SAMPLE_MAX_AGE_MS 300 → 500 ms

**Hintergrund:** Bench-Test 31.05. Hof mit Refactor C zeigte saubere iTOW-Sync
(alle 4 Module pro CSV-Zeile identisch ✓), aber 39% der erwarteten Slots
fehlten (100ms-Quote 60.8%, 200ms-Drops 34.3%). Erklärung: die Module
liefern zwar 10 Hz im Bench-Test, aber im Real-World-Setup skipt jedes Modul
sporadisch mal 1 Sample (USB-Latency, F9P-Bursts). Bei 4 Modulen × 90%
Liefer-Quote = 0.9^4 ≈ 65% komplette Slots — passt zu beobachteten 60.8%.

**Fix:** SAMPLE_MAX_AGE_MS von 300 auf 500 ms erhöhen. Logger wartet
länger auf späte Samples. Wenn nur 1 Modul 200ms verspätet liefert, wird
der Slot trotzdem komplett.

**Risiko:** sehr gering. Bei 10Hz Production = max ~5 Samples gleichzeitig
im Dict statt 3, also ~10 KB statt 6 KB. Pi 5 mit 8 GB RAM ignoriert das.
Lock-Contention bleibt minimal (Sort über max ~10 Keys).

**Test offen:** erneuter Hof-Bench-Test nach Base-USBonly-Flash. Erwartung
>90% bei 100 ms.

---

## 2026-05-30 — Logger-Refactor C: iTOW-Dict statt 4 unsync'd Queues

**Befund:** Auch nach dem USB-only-Configs-Fix (54d1dd4) zeigen die CSV-iTOW-Differenzen nur 62.4% bei 100 ms, 25.1% bei 200 ms, der Rest auch grösser. Effektive Rate: 5.29 Hz statt 10 Hz. Die Module liefern jetzt definitiv 10 Hz (per pyubx2-Hz-Test verifiziert), aber der Logger dropt 38% der Samples.

**Ursache (in der alten Architektur):**

- 4 Producer-Threads (Base, Rover1, Rover2, Rover3) schrieben in 8 separate `queue.Queue`-Instanzen mit `queue.clear() + put()` Pattern (jede Queue maximal 1 Sample tief).
- 1 Consumer-Thread (`csv_logger_thread_buffered`) pollte mit `time.sleep(0.02)`, holte aus jeder Queue mit `.get()`, und prüfte iTOW-Sync per Toleranz (100 ms Rover, 500 ms Base).
- Bei Phase-Versatz der Module: Beispiel — Rover 1 schreibt bei iTOW=200, Rover 2 hat noch iTOW=100 weil USB-Latency 5 ms später. Logger zieht: R1=200, R2=100, R3=200, B=200. Spread 100 ms → an Toleranzgrenze, oft `continue`. Sample weg, Lücke im CSV.
- Plus: die Queues haben kein Verständnis von "wer hat geliefert" — sie liefern einfach den letzten Wert. Wenn die Producer leicht unterschiedlich oft `clear()+put()` machen, kann der Consumer „alte" R1-Werte mit „neuen" R3-Werten mischen. Sync-Logik fängt das nur teilweise ab.

**Lösung (Refactor C):**

Zentrale Sample-Sammlung, gruppiert nach iTOW:

```python
samples_lock = threading.Lock()
samples_by_itow = {}  # iTOW (int ms) → {"r1": {...}, "r2": {...}, "r3": {...}, "base": {...}}
SAMPLE_MAX_AGE_MS = 300

def add_sample(itow, source, payload):
    with samples_lock:
        bucket = samples_by_itow.setdefault(int(itow), {})
        bucket[source] = payload
```

**Producer-Threads:**

Jeder Thread ruft beim NAV-RELPOSNED-Empfang (Rover) bzw. NAV-PVT-Empfang (Base) `add_sample(itow, source, {"outline": ..., "relNED": (N,E,D)})` auf. Outline wird aus dem aktuellen Thread-State (akkumulierte NMEA-Daten) gebaut. Die alten `queue.clear()+put()` Pattern sind komplett raus.

**Consumer (csv_logger_thread_buffered v2):**

```python
while not stop_event.is_set():
    time.sleep(0.02)
    with samples_lock:
        itows_sorted = sorted(samples_by_itow.keys())
        newest = itows_sorted[-1] if itows_sorted else 0
        complete_samples = []
        for itow in itows_sorted:
            sample = samples_by_itow[itow]
            if len(sample) == 4 and all(k in sample for k in ("r1","r2","r3","base")):
                complete_samples.append((itow, sample))
                del samples_by_itow[itow]
            elif newest - itow > SAMPLE_MAX_AGE_MS:
                del samples_by_itow[itow]  # zu alt, drop
            else:
                break  # noch jung, warten
    # CSV-Schreiben außerhalb des Locks (vermeidet Lock-Contention bei langen Operationen)
    for itow, sample in complete_samples:
        ... build CSV line from sample[r1/r2/r3/base].outline + relNED ...
```

**Erwarteter Effekt:**

- 100ms-Lücken-Quote sollte > 95% steigen (von 62.4%)
- 200ms-Drops verschwinden weil keine Race-Condition mehr möglich ist (Samples werden NACH iTOW gruppiert, nicht nach Queue-Eintrag-Reihenfolge)
- Spikes > 500 ms bleiben evtl. drin — die kommen vermutlich von echten USB-Stalls oder Pi-Scheduler-Hängern, das löst dieser Refactor nicht

**Architektur-Vorteile zusätzlich:**

- Lock nur kurz beim Pull aus Dict, CSV-Bau außerhalb → kein Lock-Contention mit Producern
- Memory-bounded durch SAMPLE_MAX_AGE_MS Cleanup (Dict wächst nicht unbegrenzt)
- Easy Debug: `samples_by_itow` ist inspizierbar, vs alte Queues waren opak

**Files geändert:**

- `system/pi/gps_measurement.py`:
  - Globale Queue-Decls (B_Time, B_Message, R_X_Time/Message) → samples_by_itow + samples_lock
  - `add_sample()` Helper hinzugefügt
  - BaseThread, Rover1/2/3_Thread: queue.clear+put → add_sample bei NAV-PVT/RELPOSNED
  - csv_logger_thread_buffered komplett neu (Dict-Konsumption)
  - start_measurement(): Queue-Globals aus globals raus, samples_by_itow.clear() bei Start

**Test offen:**

- Bench-Test am Pi: `git checkout refactor/logger-itow-dict`, `git pull`, Server starten, 30s messen, CSV-iTOW-Verteilung analysieren. Erwartung: > 95% bei 100 ms.
- Falls bestätigt → merge nach main
- Wenn problematisch (z.B. Memory-Leak oder Lock-Contention): zurück auf main, weiter analysieren

**Risiko:**

- Mittel. Architektur-Umbau betrifft kritischen Datenpfad. Aber: durch Branch isoliert, jederzeit zurückrollbar mit `git checkout main`.
- Edge Case: wenn ein Modul länger als 300 ms ausfällt, droppen wir frühe Samples. Bei DLG-Anwendungsfall (RTK-Fix-Verlust) ist das aber gewünscht — kein Müll-Sample mit Mixed-Time-Daten.

---

## 2026-05-30 — 5-Hz-Problem auf USB gelöst: NMEA-Multicast war die Ursache

**Befund:** Trotz CFG-RATE-MEAS = 100 ms (= 10 Hz) auf allen Modulen lieferte der CSV-Logger nur 5 Hz effektive Sample-Rate (Lücken bei 200 ms statt 100 ms). Der Sleep-Fix vom 22.05. (time.sleep 0.1 -> 0.02) hatte keinen Effekt — er war notwendig aber nicht ausreichend.

**Diagnose:**

Per `cat /dev/serial/by-id/usb-R_N-if00 | wc -c` über 5 Sekunden gemessen, mit Antennen + RTK:
- Base: ca. 82 KB / 5s
- Rover 1/2/3: je ca. 44 KB / 5s (= halb so viel wie Base)

Genau-Hz-Test mit pyubx2 zeigte: alle Rover bei NAV-RELPOSNED nur 5 Hz, Base bei NAV-PVT 10 Hz. CFG-RATE war aber bei allen Modulen korrekt auf 100 ms gesetzt — verifiziert in u-center.

Tiefe Konfig-Analyse via UBX_CONFIG_DATABASE (pyubx2): die u-blox Configs hatten **NMEA-GGA, NMEA-RMC, NMEA-VTG auf ALLEN 5 Ports aktiviert** (I2C + UART1 + UART2 + USB + SPI). Plus NAV-RELPOSNED auf 3 Ports (UART2 + USB + SPI). Das sind 18 Output-Operationen pro Mess-Zyklus pro Rover. Bei 10 Hz Mess-Rate intern hat der ZED-F9P sich **auf 5 Hz NAV-RELPOSNED-Output gedrosselt**, weil er die 180 Output-Operationen pro Sekunde plus die normale Mess-Verarbeitung nicht parallel schaffte.

Die Base war NICHT betroffen: sie sendet NAV-PVT statt NAV-RELPOSNED (kleinere Message) und hat ihren UART2-RTCM-Output (Moving-Base-Korrektur zu Rovern) der nicht mit NMEA-Multicast konkurriert.

**Fehlversuch v1 (Configs `usb_only_2026-05-25/`, NICHT im Repo gelandet):**

Erstes Skript hatte geschätzte Item-IDs für die CFG-MSGOUT-Keys verwendet. Annahme war: I2C, UART1, UART2, USB, SPI laufen sequentiell bei 0xXX, 0xXX+1, +2, +3, +4. Für die meisten Messages stimmt das (NMEA-GGA: I2C=BA, UART1=BB, UART2=BC, USB=BD, SPI=BE) — aber **NAV-RELPOSNED beginnt bei 0x8D statt 0x8C**:
- NAV-RELPOSNED I2C = 0x8D, UART1 = 0x8E, UART2 = **0x8F**, USB = **0x90**, SPI = 0x91

Mein Off-by-one-Skript identifizierte 0x8F als USB (= war UART2) und 0x90 als SPI (= war USB). Effekt nach Flash auf Rover 1/2/3: USB-Output abgeschaltet, UART2-Output aktiv geblieben — Pi konnte kein NAV-RELPOSNED mehr lesen. Falk hat das in u-center selbst entdeckt ("USB = 0, UART2 = 1, ist das richtig?").

**Lösung v2 (`usb_only_v2_2026-05-30/`, dieser Commit):**

Neues Skript nutzt direkt `pyubx2.UBX_CONFIG_DATABASE` als autoritative u-blox-Doku-Quelle (1268 Config-Keys). Pro Key kann der Port aus dem Namen extrahiert werden, Item-IDs sind exakt. Pro Original-Config: nur USB-Variants behalten = 1, alle anderen UBX/NMEA-Ports auf 0. RTCM-Keys (high byte != 0) bleiben unangetastet — kritisch fuer Base-UART2-RTCM-Output.

Vier Configs erzeugt:
- `Falk_weigand_config_Base_USBonly_v2.txt`
- `Falk_weigand_config_Rover1_USBonly_v2.txt`
- `Falk_weigand_config_Rover2_USBonly_v2.txt`
- `Falk_weigand_config_Rover3_USBonly_v2.txt`

Falk hat R1/R2/R3 in u-center geflasht + persistent in BBR/Flash gespeichert (Base blieb auf Original-Stand — sie war nicht der Bottleneck).

**Verifikation:**

pyubx2-Hz-Test direkt auf Pi (alle Module ohne Antennen, am Schreibtisch):
- Base: NAV-PVT 10.0 Hz, NMEA-GGA/RMC/VTG je 10.0 Hz
- Rover 1: NAV-RELPOSNED **10.0 Hz**, NMEA je 10.0 Hz
- Rover 2: NAV-RELPOSNED **10.0 Hz**, NMEA je 10.0 Hz
- Rover 3: NAV-RELPOSNED **10.0 Hz**, NMEA je 10.0 Hz

Anschliessend Hof-Test mit Antennen + RTK + Tare-Sequenz (CSV `Records_F9P_20260530_131028.csv`):
- 10 cm physisch ausgelenkt -> -10 cm gemessen in `VarA_R2_longitudinal_tared_cm` (Zeilen 150-175)
- 20 cm physisch ausgelenkt -> -20 cm gemessen (Zeilen 180-200)
- Zuruck auf Stand -> 0 cm +/- 1.5 cm Rauschen

Geometrie + Tare-Logik damit zum 2. Mal validiert (nach 22.05. mit 10 cm). Mess-Konzept ist solid fuer DLG.

**Test offen:**

CSV-Auswertung der iTOW-Differenzen zeigt: **62.4% der Zeilen-Uebergaenge bei 100 ms** (= Soll), aber 25.1% bei 200 ms, 7.5% bei 300-500 ms, 5% Spikes bis 2600 ms. Effektive mittlere Rate: 5.29 Hz. **Die Module liefern jetzt sauber 10 Hz, aber der CSV-Logger droppt 38% der Samples** wegen Race-Conditions in der 3-Wege-Sync-Logik. Das ist die alte Logger-Architektur mit 4 separaten `queue.clear() + put()` pro Producer — bei Phase-Versatz der Module misst die Sync-Toleranz fail.

Naechster Schritt (separater Branch `refactor/logger-itow-dict`): Logger umbauen auf zentralen iTOW-keyed dict statt 4 unsync'd Queues. Erwartung: > 95% bei 100 ms.

**Risiko des aktuellen Stands:**

Fuer DLG-Boom-Schwingungsmessung (0.5-2 Hz Frequenzinhalt) ist 5 Hz Nyquist-konform, also funktional ausreichend. Aber 38% Sample-Drops sehen in einer Live-Demo unprofessionell aus, und die Spikes bis 2.6 s reissen wirklich Loecher in die Auswertung. Refactor sollte vor 15.06. fertig sein.

**Konfig-Hinweis fuer zukuenftige UBX-Modifikationen:**

NIEMALS Item-IDs schaetzen oder aus Beobachtungen abloeschen. Immer `from pyubx2 import UBX_CONFIG_DATABASE` und das Reverse-Lookup nutzen. 1268 Keys decken praktisch alle ZED-F9P-Settings ab und stammen direkt aus der u-blox Interface Description.

---

## 2026-05-22 — Logger-Sleep-Fix: 10 Hz statt 5 Hz effektive Sample-Rate

**Beobachtung aus Testfahrt 22.05.2026 (Spritze, Base+R3 am Spritzen-Chassis, R1/R2 an Gestängeenden):**

Stillstands-Messung sauber (10 cm Auslenkung gemessen = 10 cm angezeigt — Geometrie + Tare + Variante A validiert).

Aber während der Fahrt zeigte das CSV **iTOW-Abstände von dauerhaft ca. 200 ms** (= effektiv 5 Hz statt eingestellter 10 Hz), plus 2-3 Spitzen bei ca. 1800 ms.

**Ursache:**

In `system/pi/gps_measurement.py` Zeile 724 (im `csv_logger_thread_buffered`):

```python
while not stop_event.is_set():
    time.sleep(0.1)        # 100 ms Pause vor jedem Sync-Check
    ...
    # 4 queue.get(), Sync-Check, 81-Spalten _fmt(), Disk-Write (~50 ms)
```

Logger-Zyklus = 100 ms Sleep + ~50 ms Verarbeitung ≈ **150 – 200 ms** → effektiv 5 – 7 Hz, egal wie schnell die Module liefern.

**Verifiziert:** Die u-blox-Configs (`f9p_ucenter/Falk_weigand_config_Base/Rover1/2/3.txt`) sind alle korrekt auf 100 ms = 10 Hz konfiguriert. NICHT die Ursache war:
- RTK-Qualität (immer Fix=4 auf allen Rovern während Test)
- NumSV (stabil 12 für Base)
- Module-Konfiguration (alle 4 Configs zeigen 10 Hz)
- Pi-Thermal (jetzt mit offener Box bei 54 °C, kein Throttling)

**Fix:**

```python
time.sleep(0.1) -> time.sleep(0.02)  # 50 Hz Logger-Poll-Zyklus
```

Logger wacht jetzt 5x pro 100-ms-Sample-Periode auf. Sync-Checks gelingen sofort, Queues bleiben praktisch leer. CPU-Last marginal höher (Pi 5 mit 8 GB lacht darüber).

**Bewusst NICHT geändert:**

Die Sync-Logik selbst (4 separate Queues, `if empty(): continue` Pattern) hat einen latent vorhandenen Architektur-Bug: bei Race-Conditions (z.B. wenn ein Modul kurz lag und die Queues unbalanced füllt) können Samples falsch zugeordnet werden. Strukturell sauberer wäre ein **iTOW-Dictionary** als zentraler Sammelpunkt. **Aber das ist ein 50-Zeilen-Refactor und kommt POST-DLG** (Ansatz C in der Architektur-Diskussion vom 22.05.).

Ein zwischenzeitlich angedachter Fix mit `get_nowait()` wurde verworfen, weil er ein Daten-Verlust-Risiko mitbrächte: wenn ein Modul gerade nichts in der Queue hat, würde der erste erfolgreiche `get_nowait()` das Sample der vorherigen Module konsumieren, dann werfen — Samples wären verloren. Die original `if .empty(): continue`-Variante schützt davor.

**Test offen:**

- Bench-Test am Pi: Logger 60 s laufen lassen, neue CSV inspizieren. Erwartung: iTOW-Lücken durchgehend bei 100 ms +/- 20 ms (also tatsächliche 10 Hz).
- Testfahrt nach Active-Cooler-Einbau + neue Box (siehe TODO.md Hardware): Verifikation unter realistischer Last + Vibration.
- Die 1800-ms-Spitzen sind vermutlich USB-/Vibrations-bedingte Module-Stalls — werden vom Sleep-Fix moeglicherweise nicht vollstaendig adressiert. Beobachten und ggf. mit Architektur-Refactor (Ansatz C) post-DLG fixen.

**Risiko:**

Sehr gering. Eine Zeichen-Änderung, leicht rückgängig zu machen. Falls aus unerklärlichen Gründen unter sehr hoher Last (z.B. SD-Karte fast voll, anderer Prozess belegt CPU) der Logger doch CPU-bound wird, könnte die System-Reaktion träger werden — aber Pi 5 hat dafür mehr als genug Reserven.

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
