# DEVLOG

Detail-Log aller Änderungen am MotionPSM-System. Neueste Einträge oben.

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
