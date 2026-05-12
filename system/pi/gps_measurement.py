# -*- coding: utf-8 -*-
"""
MotionPSM — Mess-System für Pflanzenschutzspritzen-Gestängebewegung.

3 Rover (links / rechts / vorne) + Base.

Variante A: Mittelachsen-Projektion (R3 als Längsachsen-Referenz).
Variante B: Direkte Differenzvektoren R3 -> R1 / R2.

Refactor 2026-05-11 (Stufe 2):
- Rover-Threads konsolidiert in RoverState-Klasse (statt 3x dupliziertem Code).
- Alte init_heading / abs_heading / delta_heading Logik entfernt
  (war die Vor-R3-Mittelachsen-Hypothese, durch geometry.vehicle_axis ersetzt).
- CSV-Header schlanker: 14 Spalten pro Rover (statt 17).
- Module-globals werden direkt von den State-Objekten gepflegt;
  server.py kann unverändert weiter gegen `gps.X` lesen.
"""

from serial import Serial
from pyubx2 import UBXReader
from datetime import datetime
import time
import threading
import queue
import os
import json
import csv
from collections import deque
from math import sin, radians, degrees, cos, atan2, sqrt

import numpy as np
from geopy.distance import geodesic
from geopy.point import Point

from geometry import vehicle_axis, lateral_offset_a, diff_vector_b


# ===== Konstanten =====
MOVING_AVG_LEN = 50
LINREG_WINDOW = 20
VIBRATION_HISTORY_LEN = 100
BASE_HEADING_BUFFER_LEN = 10
BASE_HEADING_SMOOTH_LEN = 5

BAUD = 460800
SERIAL_TIMEOUT_S = 3

# Logger-Toleranzen (Einheit wie iTOW)
LOGGER_TOLERANCE_ROVER = 0.1   # max. iTOW-Spread zwischen R1/R2/R3
LOGGER_TOLERANCE_BASE = 0.5    # max. iTOW-Diff Base zu Rover-Mittel


# ===== Module-Level Live-Werte (von server.py gelesen) =====
current_vibration_rover1 = 0.0
current_vibration_rover2 = 0.0
current_vibration_rover3 = 0.0

R1_angular_velocity = 0.0
R2_angular_velocity = 0.0
R3_angular_velocity = 0.0

R1_lateral_offset_cm = 0.0
R2_lateral_offset_cm = 0.0
vehicle_axis_length_m = 0.0
vehicle_heading_via_r3 = 0.0

Base_Speed = 0.0
Base_Heading = 0.0
Base_alt = None

# Verlinkt mit den jeweiligen RoverState-Deques in start_measurement()
quality_rover1 = deque(maxlen=1)
quality_rover2 = deque(maxlen=1)
quality_rover3 = deque(maxlen=1)
vibration_history_rover1 = deque(maxlen=VIBRATION_HISTORY_LEN)
vibration_history_rover2 = deque(maxlen=VIBRATION_HISTORY_LEN)
vibration_history_rover3 = deque(maxlen=VIBRATION_HISTORY_LEN)

# Snapshots des aktuellen relPosNED jedes Rovers (für Logger)
last_relNED_r1 = (0.0, 0.0, 0.0)
last_relNED_r2 = (0.0, 0.0, 0.0)
last_relNED_r3 = (0.0, 0.0, 0.0)


# ===== Lifecycle =====
stop_event = threading.Event()
measurement_running = False
csv_data_buffer = deque()
threads = []

_rover_states = []   # gefüllt in start_measurement
_base_state = None


# ===== State-Klassen =====

class RoverState:
    """
    Ein Rover-Modul (Index 1, 2 oder 3). State + Thread-Loop.

    Thread-Aufgaben:
    - GNGGA: Quality, Höhe, lon/lat
    - GNVTG: Speed
    - NAV-RELPOSNED: relPosNED, accHeading, rel_heading
      + Heading-Schwingungs-Statistik (Linear-Regression + Moving-Average)
      + Output-Message für Logger in Queue pushen
    """

    def __init__(self, idx, com_port):
        self.idx = idx
        self.com_port = com_port
        self.stream = None

        # Aktuelle Werte
        self.relNED = (0.0, 0.0, 0.0)
        self.iTOW = 0
        self.quality = 0
        self.acc_heading = 0.0
        self.lon = 0.0
        self.lat = 0.0
        self.alt = 0.0
        self.height_boom = 0.0
        self.init_height = None
        self.speed = 0.0
        self.rel_heading = 0.0

        # Heading-Schwingungs-Statistik
        self.angular_velocity = 0.0
        self.mov_avg_heading = 0.0
        self.heading_buffer_linear = deque(maxlen=LINREG_WINDOW)
        self.rel_heading_buffer = deque(maxlen=MOVING_AVG_LEN)

        # Live-Server-Deques (Module-Globals zeigen auf dieselben Objekte)
        self.quality_deque = deque(maxlen=1)
        self.vibration_history = deque(maxlen=VIBRATION_HISTORY_LEN)

        # Queues für Logger
        self.message_queue = queue.Queue()
        self.time_queue = queue.Queue()

    def open(self):
        self.stream = Serial(self.com_port, BAUD, timeout=SERIAL_TIMEOUT_S)

    def close(self):
        if self.stream and self.stream.is_open:
            self.stream.close()
            print(f"StreamRover{self.idx} geschlossen.")

    def run(self):
        print(f"Roverthread {self.idx} started...")
        ubr = UBXReader(self.stream, validate=0)
        while not stop_event.is_set():
            try:
                _, parsed = ubr.read()
            except Exception as e:
                print(f"[Rover{self.idx}] read err: {e}")
                continue
            if not parsed or not hasattr(parsed, 'identity'):
                continue
            ident = parsed.identity
            if ident == 'GNGGA':
                self._handle_gngga(parsed)
            elif ident == 'GNVTG':
                self.speed = parsed.sogk or 0.0
            elif ident == 'NAV-RELPOSNED':
                self._handle_relposned(parsed)

    def _handle_gngga(self, p):
        self.quality = p.quality or 0
        self.quality_deque.append(self.quality)
        self.alt = p.alt if p.alt is not None else 0.0
        # Höhenvariation: Differenz Base-alt zu Rover-alt, gegen initialen Offset
        if Base_alt is not None:
            if self.init_height is None:
                self.init_height = Base_alt - self.alt
            else:
                self.height_boom = self.init_height - (Base_alt - self.alt) * 100
        if len(str(p.lat)) > 1:
            self.lat = float(p.lat)
            self.lon = float(p.lon)

    def _handle_relposned(self, p):
        self.iTOW = p.iTOW or 0
        self.time_queue.queue.clear()
        self.time_queue.put(self.iTOW)
        self.acc_heading = p.accHeading or 0

        rN = (p.relPosN or 0) + (getattr(p, 'relPosHPN', 0) * 1e-2)
        rE = (p.relPosE or 0) + (getattr(p, 'relPosHPE', 0) * 1e-2)
        rD = (p.relPosD or 0) + (getattr(p, 'relPosHPD', 0) * 1e-2)
        self.relNED = (rN, rE, rD)
        _update_global_relNED(self.idx, self.relNED)

        rel = p.relPosHeading
        if rel is not None:
            rel = (rel + 180) % 360 - 180
            self.rel_heading = rel
            if rel != 0:
                self._update_angular_velocity(rel)
                self._update_mov_avg(rel)

        _update_global_rover_stats(self.idx, self.mov_avg_heading, self.angular_velocity)

        # Output-Message für Logger (14 Spalten)
        self.message_queue.queue.clear()
        msg = ";".join(map(str, [
            self.rel_heading, self.angular_velocity, self.mov_avg_heading,
            self.iTOW, self.quality,
            self.lon, self.lat, self.acc_heading,
            self.relNED[0], self.relNED[1], self.relNED[2],
            self.alt, self.height_boom, self.speed,
        ]))
        self.message_queue.put(msg)

    def _update_angular_velocity(self, rel):
        self.heading_buffer_linear.append((rel, self.iTOW))
        if len(self.heading_buffer_linear) >= LINREG_WINDOW:
            times = np.array([t / 1000 for _, t in self.heading_buffer_linear])
            angles = np.array([h for h, _ in self.heading_buffer_linear])
            A = np.vstack([times, np.ones(len(times))]).T
            m, _ = np.linalg.lstsq(A, angles, rcond=None)[0]
            self.angular_velocity = float(m)
        else:
            self.angular_velocity = 0.0

    def _update_mov_avg(self, rel):
        self.rel_heading_buffer.append(rel)
        if len(self.rel_heading_buffer) >= 10:
            angles_rad = [radians(h) for h in self.rel_heading_buffer]
            sin_sum = sum(sin(a) for a in angles_rad)
            cos_sum = sum(cos(a) for a in angles_rad)
            mean_angle = atan2(sin_sum / len(angles_rad), cos_sum / len(angles_rad))
            smoothed = degrees(mean_angle)
            diff = smoothed - rel
            self.mov_avg_heading = degrees(atan2(sin(radians(diff)), cos(radians(diff))))
            self.vibration_history.append(self.mov_avg_heading)
        else:
            self.mov_avg_heading = 0.0


def _update_global_relNED(idx, ned):
    """Atomare Tuple-Assignment ist thread-safe via Python-GIL."""
    global last_relNED_r1, last_relNED_r2, last_relNED_r3
    if idx == 1:   last_relNED_r1 = ned
    elif idx == 2: last_relNED_r2 = ned
    elif idx == 3: last_relNED_r3 = ned


def _update_global_rover_stats(idx, vibration, ang_vel):
    global current_vibration_rover1, current_vibration_rover2, current_vibration_rover3
    global R1_angular_velocity, R2_angular_velocity, R3_angular_velocity
    if idx == 1:
        current_vibration_rover1 = vibration
        R1_angular_velocity = ang_vel
    elif idx == 2:
        current_vibration_rover2 = vibration
        R2_angular_velocity = ang_vel
    elif idx == 3:
        current_vibration_rover3 = vibration
        R3_angular_velocity = ang_vel


class BaseState:
    """
    Base-Thread. Berechnet Heading aus Eigenbewegung (vektoriell aus
    aufeinanderfolgenden lat/lon-Positionen). Wird im CSV als
    `Base_Heading_via_motion` geloggt — als Vergleichswert zur
    R3-basierten axis_heading.
    """

    def __init__(self, com_port):
        self.com_port = com_port
        self.stream = None

        self.iTOW = 0
        self.lon = 0.0
        self.lat = 0.0
        self.alt = 0.0
        self.numSV = 0
        self.HDOP = 0.0
        self.speed = 0.0
        self.heading = 0.0

        self.calc_buffer = deque(maxlen=BASE_HEADING_BUFFER_LEN)
        self.smooth_buffer = deque(maxlen=BASE_HEADING_SMOOTH_LEN)

        self.message_queue = queue.Queue()
        self.time_queue = queue.Queue()

    def open(self):
        self.stream = Serial(self.com_port, BAUD, timeout=SERIAL_TIMEOUT_S)

    def close(self):
        if self.stream and self.stream.is_open:
            self.stream.close()
            print("StreamBase geschlossen.")

    def run(self):
        global Base_alt, Base_Speed
        print("Basethread started...")
        ubr = UBXReader(self.stream, validate=0)
        while not stop_event.is_set():
            try:
                _, parsed = ubr.read()
            except Exception as e:
                print(f"[Base] read err: {e}")
                continue
            if not parsed or not hasattr(parsed, 'identity'):
                continue
            ident = parsed.identity
            if ident == 'GNGGA':
                self.alt = parsed.alt if parsed.alt is not None else 0
                Base_alt = self.alt
                self.numSV = parsed.numSV or 0
                self.HDOP = parsed.HDOP or 0
                if len(str(parsed.lat)) > 1:
                    self.lat = float(parsed.lat)
                    self.lon = float(parsed.lon)
                    self.calc_buffer.append((self.iTOW, self.lat, self.lon))
                self._update_heading_from_motion()
            elif ident == 'NAV-PVT':
                self.iTOW = parsed.iTOW or 0
                self.time_queue.queue.clear()
                self.time_queue.put(self.iTOW)
            elif ident == 'GNVTG':
                self.speed = round(parsed.sogk or 0, 2)
                Base_Speed = self.speed

            # Output-Message für Logger (8 Spalten)
            self.message_queue.queue.clear()
            msg = ";".join(map(str, [
                self.lon, self.lat, self.numSV, self.HDOP,
                self.alt, self.iTOW, self.speed, self.heading,
            ]))
            self.message_queue.put(msg)

    def _update_heading_from_motion(self):
        global Base_Heading
        if len(self.calc_buffer) < 2:
            return
        _, lat1, lon1 = self.calc_buffer[0]
        _, lat2, lon2 = self.calc_buffer[-1]
        movement = geodesic(Point(lat1, lon1), Point(lat2, lon2)).meters
        if movement <= 0.01:
            return
        delta_lon = radians(lon2 - lon1)
        lat1r = radians(lat1)
        lat2r = radians(lat2)
        y = sin(delta_lon) * cos(lat2r)
        x = cos(lat1r) * sin(lat2r) - sin(lat1r) * cos(lat2r) * cos(delta_lon)
        raw = degrees(atan2(y, x))
        raw = (raw + 180) % 360 - 180
        self.smooth_buffer.append(raw)
        if len(self.smooth_buffer) > 1:
            sin_sum = sum(sin(radians(h)) for h in self.smooth_buffer)
            cos_sum = sum(cos(radians(h)) for h in self.smooth_buffer)
            self.heading = degrees(atan2(sin_sum, cos_sum))
            self.heading = (self.heading + 180) % 360 - 180
        else:
            self.heading = raw
        Base_Heading = self.heading


# ===== Logger =====

def _csv_format(v):
    """None -> '', Float mit 4 Nachkommastellen, sonst str()."""
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def csv_logger_thread():
    """
    Synchronisiert iTOW über alle drei Rover + Base.
    Berechnet Mittelachsen-Auswertung (Var. A + B).
    Appendet eine CSV-Zeile zum csv_data_buffer pro synchronen Sample.
    """
    global R1_lateral_offset_cm, R2_lateral_offset_cm
    global vehicle_axis_length_m, vehicle_heading_via_r3

    print("[Logger] Thread gestartet (3 Rover + Base)")

    while not stop_event.is_set():
        time.sleep(0.1)
        try:
            r1, r2, r3 = _rover_states[0], _rover_states[1], _rover_states[2]
            b = _base_state
            if (r1.time_queue.empty() or r2.time_queue.empty() or r3.time_queue.empty()
                or b.time_queue.empty()
                or r1.message_queue.empty() or r2.message_queue.empty() or r3.message_queue.empty()
                or b.message_queue.empty()):
                continue

            t1 = r1.time_queue.get();  m1 = r1.message_queue.get()
            t2 = r2.time_queue.get();  m2 = r2.message_queue.get()
            t3 = r3.time_queue.get();  m3 = r3.message_queue.get()
            tb = b.time_queue.get();   mb = b.message_queue.get()

            if max(t1, t2, t3) - min(t1, t2, t3) > LOGGER_TOLERANCE_ROVER:
                continue
            if abs(tb - (t1 + t2 + t3) / 3.0) > LOGGER_TOLERANCE_BASE:
                continue

            # Mittelachsen-Auswertung
            ned1, ned2, ned3 = r1.relNED, r2.relNED, r3.relNED
            a_len, aN, aE, axis_head = vehicle_axis(ned3)
            if aN is not None:
                lat1_m, lon1_m = lateral_offset_a(ned1, aN, aE)
                lat2_m, lon2_m = lateral_offset_a(ned2, aN, aE)
                lat1_cm = lat1_m * 100 if lat1_m is not None else None
                lat2_cm = lat2_m * 100 if lat2_m is not None else None
                lon1_cm = lon1_m * 100 if lon1_m is not None else None
                lon2_cm = lon2_m * 100 if lon2_m is not None else None
            else:
                lat1_cm = lat2_cm = lon1_cm = lon2_cm = None

            _, _, dist1_m, head1_deg = diff_vector_b(ned1, ned3)
            _, _, dist2_m, head2_deg = diff_vector_b(ned2, ned3)

            total = (lat1_cm - lat2_cm) if (lat1_cm is not None and lat2_cm is not None) else None

            # Live-Server Werte aktualisieren
            R1_lateral_offset_cm  = lat1_cm if lat1_cm is not None else 0
            R2_lateral_offset_cm  = lat2_cm if lat2_cm is not None else 0
            vehicle_axis_length_m = a_len if a_len is not None else 0
            vehicle_heading_via_r3 = axis_head if axis_head is not None else 0

            calc = ";".join(_csv_format(v) for v in [
                lat1_cm, lat2_cm, lon1_cm, lon2_cm,
                a_len, axis_head,
                dist1_m * 100 if dist1_m is not None else None, head1_deg,
                dist2_m * 100 if dist2_m is not None else None, head2_deg,
                total,
            ])

            line = (
                f"{m1.replace('.', ',')};"
                f"{m2.replace('.', ',')};"
                f"{m3.replace('.', ',')};"
                f"{mb.replace('.', ',')};"
                f"{calc.replace('.', ',')}"
            )
            csv_data_buffer.append(line.split(";"))
        except Exception as e:
            print(f"[Logger] Fehler: {e}")


# ===== CSV-Export =====

CSV_HEADER = [
    # Rover 1 (14)
    "R1_Heading", "R1_Ang_velo", "R1_mov_avg_Heading",
    "R1_iTOW", "R1_Quality", "R1_lon", "R1_lat", "R1_accHeading",
    "R1_N", "R1_E", "R1_D", "R1_alt", "R1_height_var", "R1_Speed",
    # Rover 2 (14)
    "R2_Heading", "R2_Ang_velo", "R2_mov_avg_Heading",
    "R2_iTOW", "R2_Quality", "R2_lon", "R2_lat", "R2_accHeading",
    "R2_N", "R2_E", "R2_D", "R2_alt", "R2_height_var", "R2_Speed",
    # Rover 3 (14) — definiert Längsachse
    "R3_Heading", "R3_Ang_velo", "R3_mov_avg_Heading",
    "R3_iTOW", "R3_Quality", "R3_lon", "R3_lat", "R3_accHeading",
    "R3_N", "R3_E", "R3_D", "R3_alt", "R3_height_var", "R3_Speed",
    # Base (8)
    "Base_lon", "Base_lat", "Base_NumSV", "Base_HDOP",
    "Base_alt", "Base_iTOW", "Base_Speed", "Base_Heading_via_motion",
    # Mittelachsen-Auswertung (11)
    "VarA_R1_lateral_cm", "VarA_R2_lateral_cm",
    "VarA_R1_longitudinal_cm", "VarA_R2_longitudinal_cm",
    "Axis_R3_length_m", "Axis_R3_heading_deg",
    "VarB_R3R1_distance_cm", "VarB_R3R1_heading_deg",
    "VarB_R3R2_distance_cm", "VarB_R3R2_heading_deg",
    "VarA_Gestaenge_total_cm",
]


def export_to_csv():
    if not csv_data_buffer:
        print("Keine Daten verfügbar")
        return None
    filename = f"Records_F9P_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    path = os.path.join("/tmp", filename)
    try:
        with open(path, "w", newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(CSV_HEADER)
            for row in csv_data_buffer:
                clean = ['' if (x is None or str(x).lower() in ('nan', 'none')) else x for x in row]
                writer.writerow(clean)
        print(f"[CSV Export] {path}")
        csv_data_buffer.clear()
        return path
    except Exception as e:
        print(f"[CSV Export] Fehler: {e}")
        return None


# ===== Lifecycle =====

def _load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.json')
    with open(config_path, 'r') as f:
        return json.load(f)


def start_measurement():
    global measurement_running, stop_event, threads
    global _rover_states, _base_state
    global quality_rover1, quality_rover2, quality_rover3
    global vibration_history_rover1, vibration_history_rover2, vibration_history_rover3

    if measurement_running:
        print("Messung läuft bereits.")
        return

    threads = []
    stop_event = threading.Event()
    csv_data_buffer.clear()
    print(">>> start_measurement()")

    cfg = _load_config()
    required = ['BASE_COM_PORT', 'ROVER1_COM_PORT', 'ROVER2_COM_PORT', 'ROVER3_COM_PORT']
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        raise RuntimeError(f"Fehlende Config-Felder: {missing} (siehe config.example.json)")

    _base_state = BaseState(cfg['BASE_COM_PORT'])
    _rover_states = [
        RoverState(1, cfg['ROVER1_COM_PORT']),
        RoverState(2, cfg['ROVER2_COM_PORT']),
        RoverState(3, cfg['ROVER3_COM_PORT']),
    ]

    # Module-Globals an die State-Deques verbinden — server.py liest hier
    quality_rover1 = _rover_states[0].quality_deque
    quality_rover2 = _rover_states[1].quality_deque
    quality_rover3 = _rover_states[2].quality_deque
    vibration_history_rover1 = _rover_states[0].vibration_history
    vibration_history_rover2 = _rover_states[1].vibration_history
    vibration_history_rover3 = _rover_states[2].vibration_history

    _base_state.open()
    for r in _rover_states:
        r.open()

    t_base = threading.Thread(target=_base_state.run, daemon=True, name="BaseThread")
    t_rovers = [threading.Thread(target=r.run, daemon=True, name=f"Rover{r.idx}Thread")
                for r in _rover_states]
    t_logger = threading.Thread(target=csv_logger_thread, daemon=True, name="LoggerThread")
    threads = [t_base, *t_rovers, t_logger]
    measurement_running = True

    for t in threads:
        print(f"Starte {t.name}")
        t.start()


def stop_measurement():
    global measurement_running
    stop_event.set()
    for t in threads:
        print(f"Stoppe {t.name}...")
        t.join(timeout=2)
        if t.is_alive():
            print(f"  Thread {t.name} hat nicht sauber beendet.")
    if _base_state:
        _base_state.close()
    for r in _rover_states:
        r.close()
    measurement_running = False


if __name__ == "__main__":
    try:
        start_measurement()
        while measurement_running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Messung abgebrochen")
    finally:
        stop_measurement()
