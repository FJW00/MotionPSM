# -*- coding: utf-8 -*-

from serial import Serial
from pyubx2 import UBXReader
from pyproj import Transformer
from datetime import datetime
import time
import threading
import queue
import os
import json
from collections import deque
import numpy as np
import csv
from math import sin, asin, radians, degrees, cos, atan2, sqrt
from geopy.distance import geodesic
from geopy.point import Point


#config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
#with open(config_path, 'r') as config_file:
 #       config = json.load(config_file)

#value_mov_avg = config.get('value_mov_avg',10)#Fallback-Wert
#lenght_mov_avg = value_mov_avg
lenght_mov_avg = 50

#-------Globale Variablen für Live-Server-----------
current_vibration_rover1 = 0
quality_rover1 = 0
R1_angular_velocity = 0

current_vibration_rover2 = 0
quality_rover2 = 0
R2_angular_velocity = 0

#-------Globale Variablen für Base und Rover--------
B_Time = queue.Queue()
B_Message = queue.Queue()
BaT_exists = False
Bmsg_Exists  = False
base_calc_heading_buffer = deque(maxlen=10)
base_heading_smooth_buffer = deque(maxlen=5)  

R_1_Message = queue.Queue()
R_1_Time = queue.Queue()
Ro_1_T_exists = False
R_1_msg_Exits = False
rover1_vibration_buffer = deque(maxlen=30)
heading_buffer_1 = deque(maxlen=2)
heading_buffer_linear_1 = deque(maxlen=20)
heading_buffer_delta_1 = deque(maxlen=2)
rel_heading_buffer_1 = deque(maxlen=lenght_mov_avg)

R_2_Message = queue.Queue()
R_2_Time = queue.Queue()
Ro_2_T_exists = False
R_2_msg_Exits = False
rover2_vibration_buffer = deque(maxlen=30)
heading_buffer_2 = deque(maxlen=2)
heading_buffer_linear_2 = deque(maxlen=20)
heading_buffer_delta_2 = deque(maxlen=2)
rel_heading_buffer_2 = deque(maxlen=lenght_mov_avg)

#-------Transform Koordinatensystem--------
transformer = Transformer.from_crs(4326, 25832)
transformer.transform(50, -80)

stop_event = threading.Event()
measurement_running = False
csv_data_buffer = [] 

#-----------------------Threads----------------------

def BaseThread():
    global Base_alt, Base_Heading, Base_Speed
    print ("Basethread started...")
    Base_lon = 0
    Base_lat= 0
    Base_HDOP = 0
    Base_alt = 0
    Base_NumSV = 0
    Base_time = 0
    Base_Speed = 0
    B_Speed = 0
    Base_Heading = 0

    while not stop_event.is_set():
        ubr = UBXReader(streamBase, validate=0)
        raw_data, parsed_data = ubr.read()

        if parsed_data and hasattr(parsed_data, 'identity'):
            if parsed_data.identity == 'GNGGA':
                Base_alt = parsed_data.alt
                Base_NumSV = parsed_data.numSV
                Base_HDOP = parsed_data.HDOP
                if len(str(parsed_data.lat)) > 1:
                    Base_lat = float(parsed_data.lat)
                    Base_lon = float(parsed_data.lon)
                    base_calc_heading_buffer.append((Base_time, Base_lat, Base_lon))

                # Heading der Base über verktorielle Berechung Kalkulieren
                if len(base_calc_heading_buffer) >= 2:
                    # Früheste und letzte Position der Basis
                    _, lat1, lon1 = base_calc_heading_buffer[0]
                    _, lat2, lon2 = base_calc_heading_buffer[-1]

                    point1 = Point(latitude=lat1, longitude=lon1)
                    point2 = Point(latitude=lat2, longitude=lon2)

                    # Berechne die geodätische Distanz
                    movement = geodesic(point1, point2).meters

                    if movement > 0.01: # Nur sinnvoll berechnen, wenn Bewegung > 5cm
                        delta_lon_rad = radians(lon2 - lon1)
                        lat1_rad = radians(lat1)
                        lat2_rad = radians(lat2)

                        y = sin(delta_lon_rad) * cos(lat2_rad)
                        x = cos(lat1_rad) * sin(lat2_rad) - sin(lat1_rad) * cos(lat2_rad) * cos(delta_lon_rad)
                        
                        raw_heading = degrees(atan2(y, x))
                        
                        # Sicherstellen, dass raw_heading im Bereich -180 bis 180 liegt
                        raw_heading = (raw_heading + 180) % 360 - 180 
                        
                        base_heading_smooth_buffer.append(raw_heading)

                        # Gleitenden Mittelwert für Base_Heading berechnen (Kreismittelwert)
                        if len(base_heading_smooth_buffer) > 1:
                            sin_sum = sum([sin(radians(h)) for h in base_heading_smooth_buffer])
                            cos_sum = sum([cos(radians(h)) for h in base_heading_smooth_buffer])
                            Base_Heading = degrees(atan2(sin_sum, cos_sum))
                            # Normalisierung auf -180 bis 180 Grad
                            Base_Heading = (Base_Heading + 180) % 360 - 180
                        else:
                            Base_Heading = raw_heading # raw_heading ist bereits normalisiert

            elif parsed_data.identity == 'NAV-PVT':
                Base_time = parsed_data.iTOW
                B_Time.queue.clear()
                B_Time.put(Base_time) 

            elif parsed_data.identity == 'GNVTG':
                B_Speed = parsed_data.sogk 
                Base_Speed = round(B_Speed,2) 
                #Base_Heading = parsed_data.cogt
                                
                    
            B_Message.queue.clear()
            Base_outline = ";".join(map(str, [
                Base_lon, Base_lat, Base_NumSV, Base_HDOP, Base_alt, Base_time, Base_Speed, Base_Heading
            ]))

            B_Message.put(Base_outline) 
            #print('Base:',Base_outline)

def Rover1_Thread():
    global current_vibration_rover1, R1_angular_velocity
    print("Roverthread 1 started...")
    Rover_date = '01-01-1990'
    Rover_time = 0
    Rover_lon = 0
    Rover_lat = 0
    Rover_Speed = 0
    init_height = None
    height_boom = 0
    init_heading = None
    delta_heading = 0
    init_heading_iTOW = None
    abs_heading = 0
    mov_avg_heading = 0

    while not stop_event.is_set():
        ubr = UBXReader(streamRover1, validate=0)
        raw_data, parsed_data = ubr.read()

        if parsed_data and hasattr(parsed_data, 'identity'):

            if parsed_data.identity == 'GNGGA':
                Rover_Quality = parsed_data.quality
                quality_rover1.append(Rover_Quality)
                Rover_alt = parsed_data.alt
                if len(str(parsed_data.lat)) > 1:
                    Rover_lat = float(parsed_data.lat)
                    Rover_lon = float(parsed_data.lon)

                #Calculation height varriation boom
                if Rover_alt is not None and Base_alt is not None:
                    if init_height is None:
                        init_height = Base_alt - Rover_alt
                    else:
                        height_boom = init_height - (Base_alt - Rover_alt) *100

            elif parsed_data.identity == 'GNRMC':
                Rover_date = parsed_data.date

            elif parsed_data.identity == 'GNVTG':
                Rover_Speed = parsed_data.sogk

            elif parsed_data.identity == 'NAV-RELPOSNED': 
                Rover_time = parsed_data.iTOW
                R_1_Time.queue.clear()
                R_1_Time.put(Rover_time)              
                Rover_accHeading = parsed_data.accHeading
                Rover_N = parsed_data.relPosN + (getattr(parsed_data, 'relPosHPN', 0) * 1e-2)
                Rover_E = parsed_data.relPosE + (getattr(parsed_data, 'relPosHPE', 0) * 1e-2)
                Rover_D = parsed_data.relPosD + (getattr(parsed_data, 'relPosHPD', 0) * 1e-2)
                #rel_heading = (parsed_data.relPosHeading * 1e-5)
                rel_heading = parsed_data.relPosHeading

                if rel_heading is not None:
                    rel_heading = (rel_heading + 180) % 360 - 180
            
                # Winkeländerung
                if rel_heading is not None and abs(rel_heading) > 0.0:
                    if init_heading is None:
                        if init_heading_iTOW is None:
                            init_heading_iTOW = Rover_time  # Zeitpunkt merken
                        elif Rover_time - init_heading_iTOW > 500:  # nach 500 ms initialisieren
                            init_heading = rel_heading  # einmalig setzen
                    else:
                        # Berechnung nur, wenn init_heading bereits gesetzt wurde
                        raw_delta = rel_heading - init_heading
                        #raw_delta = rel_heading - Base_Heading - 90.0 #offset 
                        abs_heading = degrees(atan2(sin(radians(raw_delta)), cos(radians(raw_delta))))
                        #current_vibration_rover1 = abs_heading
                        #vibration_history_rover1.append(abs_heading)
                    
                #Linear Regression
                if rel_heading != 0:
                    heading_buffer_linear_1.append((rel_heading, Rover_time))
                    valid_values = [(h, t) for h, t in heading_buffer_linear_1 if h != 0]
                    if len(valid_values) >= 20: #20 = 2sekunden
                        recent = valid_values[-20:]
                        angles = [h for h, _ in recent]
                        times = [t/1000 for _, t in recent]
                        x = np.array(times)
                        y = np.array(angles)
                        A = np.vstack([x, np.ones(len(x))]).T
                        m, _ = (np.linalg.lstsq(A, y, rcond=None)[0])
                        R1_angular_velocity = m
                    else:
                        R1_angular_velocity = 0 
                else:
                        R1_angular_velocity = 0
                
                #Moving Average
                if rel_heading != 0:
                    rel_heading_buffer_1.append(rel_heading)
                    if len(rel_heading_buffer_1) > lenght_mov_avg:
                        rel_heading_buffer_1.pop(0)  # Ältesten Wert entfernen

                    # Gleitender Mittelwert
                    if len(rel_heading_buffer_1) >= 10:  # Mindestanzahl für Mittelwert
                        angles_rad = [radians(h) for h in rel_heading_buffer_1]

                        # Mittelwert über Sinus und Kosinus
                        sin_sum = sum(sin(a) for a in angles_rad)
                        cos_sum = sum(cos(a) for a in angles_rad)

                        mean_angle_rad = atan2(sin_sum / len(angles_rad), cos_sum / len(angles_rad))
                        smoothed_heading = degrees(mean_angle_rad)

                        # Abweichung berechnen
                        raw_smooth_heading = smoothed_heading - rel_heading #- smoothed_heading
                        mov_avg_heading = degrees(atan2(sin(radians(raw_smooth_heading)), cos(radians(raw_smooth_heading))))
                        
                        current_vibration_rover1 = mov_avg_heading
                        vibration_history_rover1.append(mov_avg_heading)
                    else:
                        current_vibration_rover1 = 0  # Noch nicht genug Daten
                '''
                # Exponential Moving Average statt gleitender Mittelwert
                if rel_heading != 0:

                    # Initialisierung (nur beim ersten Durchlauf)
                    if 'smoothed_heading' not in locals():
                        smoothed_heading = rel_heading
                        vibration_history_rover1 = []

                    # Glättungsfaktor (klein = stärker geglättet, groß = reaktiver)
                    alpha = 0.05  # Typisch: 0.05 bis 0.2

                    # Differenz korrekt normieren auf [-180°, 180°]
                    delta = rel_heading - smoothed_heading
                    delta = degrees(atan2(sin(radians(delta)), cos(radians(delta))))

                    # EMA anwenden
                    smoothed_heading += alpha * delta

                    # Abweichung zwischen geglättetem und aktuellem Winkel berechnen
                    raw_smooth_heading = smoothed_heading - rel_heading
                    mov_avg_heading = degrees(atan2(sin(radians(raw_smooth_heading)), cos(radians(raw_smooth_heading))))

                    # Ergebnis speichern
                    current_vibration_rover1 = mov_avg_heading
                    vibration_history_rover1.append(mov_avg_heading)

                else:
                    current_vibration_rover1 = 0  # rel_heading == 0 → keine Bewegung
                '''
                #Delta Heading
                if rel_heading != 0:
                    heading_buffer_delta_1.append((rel_heading, Rover_time))
                    valid_values_heading = [(h, t) for h, t in heading_buffer_delta_1 if h != 0]
                    if len(valid_values_heading) >= 2:
                        (heading1, t1), (heading2, t2) = valid_values_heading[-2:]
                        raw_delta = heading2 - heading1
                        delta_heading = degrees(atan2(sin(radians(raw_delta)), cos(radians(raw_delta))))

        #-------------Message-----------------
                R_1_Message.queue.clear()
                Rover_1_outline = ";".join(map(str, [
                    rel_heading,abs_heading, R1_angular_velocity, delta_heading, mov_avg_heading,
                    Rover_date, Rover_time, Rover_Quality,
                    Rover_lon, Rover_lat, Rover_accHeading,
                    Rover_N, Rover_E, Rover_D, Rover_alt, height_boom, Rover_Speed
                ]))
                
                R_1_Message.put(Rover_1_outline)
                #print("Rover1:",Rover_1_outline)

def Rover2_Thread():
    global current_vibration_rover2, R2_angular_velocity
    print("Roverthread 2 started...")
    Rover_date = '01-01-1990'
    Rover_time = 0
    Rover_lon = 0
    Rover_lat = 0
    Rover_Speed = 0
    init_height = None
    height_boom = 0
    init_heading = None
    delta_heading = 0
    init_heading_iTOW = None
    abs_heading = 0
    mov_avg_heading = 0

    while not stop_event.is_set():
        ubr = UBXReader(streamRover2, validate=0)
        raw_data, parsed_data = ubr.read()

        if parsed_data and hasattr(parsed_data, 'identity'):

            if parsed_data.identity == 'GNGGA':
                Rover_Quality = parsed_data.quality
                quality_rover2.append(Rover_Quality)
                Rover_alt = parsed_data.alt
                if len(str(parsed_data.lat)) > 1:
                    Rover_lat = float(parsed_data.lat)
                    Rover_lon = float(parsed_data.lon)

                #Calculation height varriation boom
                if Rover_alt is not None and Base_alt is not None:
                    if init_height is None:
                        init_height = Base_alt - Rover_alt
                    else:
                        height_boom = init_height - (Base_alt - Rover_alt) *100

            elif parsed_data.identity == 'GNRMC':
                Rover_date = parsed_data.date
            
            elif parsed_data.identity == 'GNVTG':
                Rover_Speed = parsed_data.sogk

            elif parsed_data.identity == 'NAV-RELPOSNED':
                Rover_time = parsed_data.iTOW
                R_2_Time.queue.clear()
                R_2_Time.put(Rover_time)
                Rover_accHeading = parsed_data.accHeading
                Rover_N = parsed_data.relPosN + (getattr(parsed_data, 'relPosHPN', 0) * 1e-2)
                Rover_E = parsed_data.relPosE + (getattr(parsed_data, 'relPosHPE', 0) * 1e-2)
                Rover_D = parsed_data.relPosD + (getattr(parsed_data, 'relPosHPD', 0) * 1e-2)
                #rel_heading = (parsed_data.relPosHeading * 1e-5)
                rel_heading = parsed_data.relPosHeading

                if rel_heading is not None:
                    rel_heading = (rel_heading + 180) % 360 - 180

                # Winkeländerung
                if rel_heading is not None and abs(rel_heading) > 0.0:
                    if init_heading is None:
                        if init_heading_iTOW is None:
                            init_heading_iTOW = Rover_time  # Zeitpunkt merken
                        elif Rover_time - init_heading_iTOW > 500:  # nach 500 ms initialisieren
                            init_heading = rel_heading  # einmalig setzen
                    else:
                        # Berechnung nur, wenn init_heading bereits gesetzt wurde
                        raw_delta = rel_heading - init_heading
                        #raw_delta = rel_heading - Base_Heading + 90.0
                        abs_heading = degrees(atan2(sin(radians(raw_delta)), cos(radians(raw_delta))))
                        #current_vibration_rover2 = abs_heading
                        #vibration_history_rover2.append(abs_heading)

                #Linear Regression
                if rel_heading != 0:
                    heading_buffer_linear_2.append((rel_heading, Rover_time))
                    valid_values = [(h, t) for h, t in heading_buffer_linear_2 if h != 0]
                    if len(valid_values) >= 20:
                        recent = valid_values[-20:]
                        angles = [h for h, _ in recent]
                        times = [t/1000 for _, t in recent]
                        x = np.array(times)
                        y = np.array(angles)
                        A = np.vstack([x, np.ones(len(x))]).T
                        m, _ = (np.linalg.lstsq(A, y, rcond=None)[0])
                        R2_angular_velocity = m
                    else:
                        R2_angular_velocity = 0 
                else:
                        R2_angular_velocity = 0
                
                #Moving Average
                if rel_heading != 0:
                    rel_heading_buffer_2.append(rel_heading)
                    if len(rel_heading_buffer_2) > lenght_mov_avg:
                        rel_heading_buffer_2.pop(0)  # Ältesten Wert entfernen

                    # Gleitender Mittelwert
                    if len(rel_heading_buffer_2) >= 10:  # Mindestanzahl für Mittelwert
                        angles_rad = [radians(h) for h in rel_heading_buffer_2]

                        # Mittelwert über Sinus und Kosinus
                        sin_sum = sum(sin(a) for a in angles_rad)
                        cos_sum = sum(cos(a) for a in angles_rad)

                        mean_angle_rad = atan2(sin_sum / len(angles_rad), cos_sum / len(angles_rad))
                        smoothed_heading = degrees(mean_angle_rad)

                        # Abweichung berechnen
                        raw_smooth_heading = smoothed_heading - rel_heading #- smoothed_heading
                        mov_avg_heading = degrees(atan2(sin(radians(raw_smooth_heading)), cos(radians(raw_smooth_heading))))

                        current_vibration_rover2 = mov_avg_heading
                        vibration_history_rover2.append(mov_avg_heading)
                    else:
                        current_vibration_rover2 = 0  # Noch nicht genug Daten


                #Delta Heading
                if rel_heading != 0:
                    heading_buffer_delta_2.append((rel_heading, Rover_time))
                    valid_values_heading = [(h, t) for h, t in heading_buffer_delta_2 if h != 0]
                    if len(valid_values_heading) >= 2:
                        (heading1, t1), (heading2, t2) = valid_values_heading[-2:]
                        raw_delta = heading2 - heading1
                        delta_heading = degrees(atan2(sin(radians(raw_delta)), cos(radians(raw_delta))))

        #-------------Message-----------------
                R_2_Message.queue.clear()
                Rover_2_outline = ";".join(map(str, [
                    rel_heading, abs_heading, R2_angular_velocity, delta_heading, mov_avg_heading, 
                    Rover_date, Rover_time, Rover_Quality,
                    Rover_lon, Rover_lat, Rover_accHeading,
                    Rover_N, Rover_E, Rover_D, Rover_alt, height_boom, Rover_Speed 
                    
                ]))
                R_2_Message.put(Rover_2_outline)
                #print("rover2:",Rover_2_outline)

csv_data_buffer = deque()

def csv_logger_thread_buffered():
    print("[Logger] Thread gestartet")
    
    tolerance_r1_r2 = 0.1   # 100 ms zwischen R1 und R2
    tolerance_base  = 0.5   # 500 ms zur Base

    while not stop_event.is_set():
        time.sleep(0.1)

        try:
            if R_1_Time.empty() or R_2_Time.empty() or B_Time.empty() or \
               R_1_Message.empty() or R_2_Message.empty() or B_Message.empty():
                continue

            Ro_1_T = R_1_Time.get()
            R_1_msg = R_1_Message.get()

            Ro_2_T = R_2_Time.get()
            R_2_msg = R_2_Message.get()

            Ba_T = B_Time.get()
            Bmsg = B_Message.get()

            # Bedingung 1: R1 und R2 müssen eng beieinander liegen
            if abs(Ro_1_T - Ro_2_T) <= tolerance_r1_r2:
                # Mittelwert der Rover-Zeiten
                mean_rover_time = (Ro_1_T + Ro_2_T) / 2

                # Bedingung 2: Base darf bis zu 0.5s davon abweichen
                if abs(Ba_T - mean_rover_time) <= tolerance_base:
                    line = f"{R_1_msg.replace('.', ',')};{R_2_msg.replace('.', ',')};{Bmsg.replace('.', ',')}"
                    csv_data_buffer.append(line.split(";"))
                    # Optional: print("[Logger] Gespeichert:", line)

        except Exception as e:
            print("[Logger Thread] Fehler:", e)


'''
def csv_logger_thread_buffered():
    print("[Logger] Thread gestartet")
    while not stop_event.is_set():
        time.sleep(0.1)

        try:
            if R_1_Time.empty() or R_2_Time.empty() or B_Time.empty() or R_1_Message.empty() or R_2_Message.empty() or B_Message.empty():
               continue

            Ro_1_T = R_1_Time.get()
            R_1_msg = R_1_Message.get()

            Ro_2_T = R_2_Time.get()
            R_2_msg = R_2_Message.get()

            Ba_T = B_Time.get()
            Bmsg = B_Message.get()

            #print("[Logger] Rover-Zeiten:", Ro_1_T, Ro_2_T, Ba_T)

            if Ro_1_T == Ro_2_T == Ba_T:
                line = f"{R_1_msg.replace('.', ',')};{R_2_msg.replace('.', ',')};{Bmsg.replace('.', ',')}"
                #print("[Logger] Neue Zeile:", line)
                csv_data_buffer.append(line.split(";"))
                #print("[Logger] Gespeichert:", line)

        except Exception as e:
            print("[Logger Thread] Fehler:", e)
'''

def export_to_csv():
    if not csv_data_buffer:
        print("no Data available")
        return None

    filename = f"Records_F9P_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    path = os.path.join("/tmp", filename)

    try:
        with open(path, "w", newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';')

            #------Header schreiben-------
            writer.writerow([
                "R1_Heading", "R1_absolute_Heading", "Rover_1_Ang_velo","R1_delta_Heading", "R1_mov_avg_Heading",
                "R1_Rover_date", "R1_Rover_time","Rover_1_Quality",
                "R1_Rover_lon", "R1_Rover_lat","Rover_1_accHeading",
                "Rover_1_N", "Rover_1_E", "Rover_1_D","Rover_1_alt", "Rover_1_height_varriation","Rover_1_Speed", 
                "R2_Heading", "R2_absolute_Heading", "Rover_2_Ang_velo","R2_delta_Heading","R2_mov_avg_Heading",
                "R2_Rover_date", "R2_Rover_time","Rover_2_Quality",
                "R2_Rover_lon", "R2_Rover_lat", "Rover_2_accHeading",
                "Rover_2_N", "Rover_2_E", "Rover_2_D","Rover_2_alt", "Rover_2_height_varriation","Rover_2_Speed",
                "Base_lon", "Base_lat",
                "Base_NumSV", "Base_HDOP", "Base_alt", "Base_Time", "Base_Speed", "Base_Heading"
            ])
            #------Daten schreiben--------
            for row in csv_data_buffer:
                clean_row = [
                    '' if (elem is None or str(elem).lower() == 'nan' or str(elem).lower() == 'none') else elem
                    for elem in row
                ]
                writer.writerow(clean_row)

        print(f"[CSV Export] Gespeichert: {path}")
        csv_data_buffer.clear()
        return path

    except Exception as e:
        print(f"[CSV Export] Fehler: {e}")
        return None
    
def start_measurement():
    global streamBase
    global B_Message, B_Time, Base_Speed
    global streamRover1, R_1_Message, R_1_Time, vibration_history_rover1, heading_buffer_1, heading_buffer_linear_1 , quality_rover1, R1_angular_velocity
    global streamRover2,R_2_Message, R_2_Time, vibration_history_rover2, heading_buffer_2, heading_buffer_linear_2 , quality_rover2, R2_angular_velocity 
    global threads, stop_event
    global measurement_running
    global lenght_mov_avg

    threads = []
    stop_event = threading.Event()
    csv_data_buffer.clear()

    print(">>> start_measurement() wurde aufgerufen")
    
    #-----Konfigurationsdatei lesen------
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    with open(config_path, 'r') as config_file:
        config = json.load(config_file)

    BASE_COM_PORT = config.get('BASE_COM_PORT')
    ROVER1_COM_PORT = config.get('ROVER1_COM_PORT')
    ROVER2_COM_PORT = config.get('ROVER2_COM_PORT')

    streamBase = Serial(BASE_COM_PORT, 460800, timeout=3)
    streamRover1 = Serial(ROVER1_COM_PORT, 460800, timeout=3)
    streamRover2 = Serial(ROVER2_COM_PORT, 460800, timeout=3)

    vibration_history_rover1 = deque(maxlen=100)
    quality_rover1 = deque(maxlen=1)
    t1 = threading.Thread(target=Rover1_Thread, daemon=True)

    vibration_history_rover2 = deque(maxlen=100)
    quality_rover2 = deque(maxlen=1)
    t2 = threading.Thread(target=Rover2_Thread, daemon=True)

    t0 = threading.Thread(target=BaseThread)
    t_logger = threading.Thread(target=csv_logger_thread_buffered, daemon=True)
    
    threads.append(t0)
    threads.append(t1)
    threads.append(t2)
    threads.append(t_logger)

    if measurement_running:
        print("Messung läuft bereits.")
        return
    measurement_running = True
    

    for t in threads:
        print("Starte Threads:", threads)
        print(f"Starte Thread: {t.name}")
        t.start()

def stop_measurement():
    global stop_event
    global measurement_running

    stop_event.set()
    for t in threads:
        print(f"Stoppe Thread: {t.name}...")
        t.join(timeout=2) #Max 2 Sekunden warten
        if t.is_alive():
            print(f"Thread {t.name} hat nicht sauber beendet.")
        else:
            print(f"Thread {t.name} beendet.")

    if streamBase.is_open:
        streamBase.close()
        print("StreamBase geschlossen.")

    if streamRover1.is_open:
        streamRover1.close()
        print("StreamRover1 geschlossen.")

    if streamRover2.is_open:
        streamRover2.close()
        print("StreamRover2 geschlossen.")

    measurement_running = False

#-------Running and Key Interrupt-----------
if __name__ == "__main__":
    try:
        start_measurement()
    except KeyboardInterrupt:
        print("Messung abgebrochen")
    finally:
        stop_measurement()