# -*- coding: utf-8 -*-

from serial import Serial, SerialException
from pyubx2 import UBXReader
from pyproj import Transformer
from datetime import datetime
import time
import threading
import queue
import os
import json
from collections import deque
from math import sin, radians, degrees, cos, atan2
import numpy as np
import csv

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

R_1_Message = queue.Queue()
R_1_Time = queue.Queue()
Ro_1_T_exists = False
R_1_msg_Exits = False
rover1_vibration_buffer = deque(maxlen=30)
heading_buffer_1 = deque(maxlen=2)
heading_buffer_linear_1 = deque(maxlen=20)
heading_buffer_1_test = deque(maxlen=2) #Test Angular without filte

R_2_Message = queue.Queue()
R_2_Time = queue.Queue()
Ro_2_T_exists = False
R_2_msg_Exits = False
rover2_vibration_buffer = deque(maxlen=30)
heading_buffer_2 = deque(maxlen=2)
heading_buffer_linear_2 = deque(maxlen=20)
heading_buffer_2_test = deque(maxlen=2) #Test Angular without filter

#-------Transform Koordinatensystem--------
transformer = Transformer.from_crs(4326, 25832)
transformer.transform(50, -80)

stop_event = threading.Event()
measurement_running = False
csv_data_buffer = [] 

#-----------------------Threads----------------------
'''
def BaseThread():
    global Base_alt
    Base_lon = 0
    Base_lat= 0
    Base_HDOP = 0
    Base_alt = 0
    Base_NumSV = 0
    Base_time = 0

    print ("Basethread started...")
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

            elif parsed_data.identity == 'NAV-PVT':
                Base_time = parsed_data.iTOW
                B_Time.queue.clear()
                B_Time.put(Base_time)                   
                    
            B_Message.queue.clear()
            Base_outline = ";".join(map(str, [
                Base_lon, Base_lat, Base_NumSV, Base_HDOP, Base_alt, Base_time
            ]))

            B_Message.put(Base_outline) 
            print('Base:',Base_outline)
'''
def Rover1_Thread():
    global current_vibration_rover1, R1_angular_velocity
    print("Roverthread 1 started...")
    Rover_date = '01-01-1990'
    Rover_time = 0
    Rover_lon = 0
    Rover_lat = 0
    raw_vibration = 0
    fixed_vibration = 0
    filtered_vibration = 0
    delta_heading = 0
    init_height = None

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
                if Rover_alt is not None:
                    if init_height is None:
                        init_height = Rover_alt
                height_boom = (Rover_alt - init_height) * 100

                #height_boom = (Rover_alt - Base_alt) * 100 #meter in centimeter

            elif parsed_data.identity == 'GNRMC':
                Rover_date = parsed_data.date

            elif parsed_data.identity == 'NAV-PVT':
                Rover_time = parsed_data.iTOW
                R_1_Time.queue.clear()
                R_1_Time.put(Rover_time)

            elif parsed_data.identity == 'NAV-RELPOSNED':               
                Rover_accHeading = parsed_data.accHeading
                Rover_N = parsed_data.relPosN
                Rover_E = parsed_data.relPosE
                Rover_D = parsed_data.relPosD
                rel_heading = (parsed_data.relPosHeading * 1e-5)
                
                #Heading Filtered
                heading_buffer_1.append((rel_heading, Rover_time))
                if len(heading_buffer_1) == 2:
                    (h1, t1), (h2, t2) = heading_buffer_1
                    d_heading = h2 - h1
                    d_time =(t2- t1)/1000 #ms
                    raw_vibration = d_heading / d_time if d_time != 0 else 0
                    #fixed_vibration = degrees(asin(sin(radians(raw_vibration))))
                    fixed_vibration = degrees(atan2(sin(radians(raw_vibration)), cos(radians(raw_vibration))))#Test                    
                    rover1_vibration_buffer.append(fixed_vibration)
                    filtered_vibration = (
                        butter_lowpass_filter(list(rover1_vibration_buffer))[-1]
                        if len(rover1_vibration_buffer) >= 4 else fixed_vibration
                        )
                    current_vibration_rover1 = filtered_vibration
                    vibration_history_rover1.append(filtered_vibration)
                
                #Delta Heading
                if rel_heading != 0:
                    heading_buffer_1_test.append((rel_heading, Rover_time))
                    valid_values_heading = [(h, t) for h, t in heading_buffer_1_test if h != 0]
                    if len(valid_values_heading) >= 2:
                        (heading1, t1), (heading2, t2) = valid_values_heading[-2:]
                        raw_delta = heading2 - heading1
                        delta_heading = degrees(atan2(sin(radians(raw_delta)), cos(radians(raw_delta))))
                        
                #Linear Regression
                if rel_heading != 0:
                    heading_buffer_linear_1.append((rel_heading, Rover_time))
                    valid_values = [(h, t) for h, t in heading_buffer_linear_1 if h != 0]
                    if len(valid_values) >= 5:
                        recent = valid_values[-5:]
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

                R_1_Message.queue.clear()
                Rover_1_outline = ";".join(map(str, [
                    filtered_vibration, delta_heading, rel_heading,
                    Rover_date, Rover_time, Rover_Quality,
                    Rover_lon, Rover_lat, Rover_accHeading,
                    Rover_N, Rover_E, Rover_D, Rover_alt, height_boom,  R1_angular_velocity
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
    raw_vibration = 0
    fixed_vibration = 0
    filtered_vibration = 0
    delta_heading = 0
    init_height = None

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
                if Rover_alt is not None:
                    if init_height is None:
                        init_height = Rover_alt
                height_boom = (Rover_alt - init_height) * 100 #meter in centimeter
                #height_boom = (Rover_alt - Base_alt) * 100

            elif parsed_data.identity == 'GNRMC':
                Rover_date = parsed_data.date

            elif parsed_data.identity == 'NAV-PVT':
                Rover_time = parsed_data.iTOW
                R_2_Time.queue.clear()
                R_2_Time.put(Rover_time)

            elif parsed_data.identity == 'NAV-RELPOSNED':
                Rover_accHeading = parsed_data.accHeading
                Rover_N = parsed_data.relPosN
                Rover_E = parsed_data.relPosE
                Rover_D = parsed_data.relPosD
                rel_heading = (parsed_data.relPosHeading * 1e-5)
                
                #Heading Filtered
                heading_buffer_2.append((rel_heading, Rover_time))
                if len(heading_buffer_2) == 2:
                    (h1, t1), (h2, t2) = heading_buffer_2
                    d_heading = h2 - h1
                    d_time =(t2- t1)/1000 #ms
                    raw_vibration = d_heading / d_time if d_time != 0 else 0
                    #fixed_vibration = degrees(asin(sin(radians(raw_vibration))))
                    fixed_vibration = degrees(atan2(sin(radians(raw_vibration)), cos(radians(raw_vibration))))#Test
                    rover2_vibration_buffer.append(fixed_vibration)
                    filtered_vibration = (
                        butter_lowpass_filter(list(rover2_vibration_buffer))[-1]
                        if len(rover2_vibration_buffer) >= 4 else fixed_vibration
                        )
                    current_vibration_rover2 = filtered_vibration
                    vibration_history_rover2.append(filtered_vibration)
                
                #Delta Heading
                if rel_heading != 0:
                    heading_buffer_2_test.append((rel_heading, Rover_time))
                    valid_values_heading = [(h, t) for h, t in heading_buffer_2_test if h != 0]
                    if len(valid_values_heading) >= 2:
                        (heading1, t1), (heading2, t2) = valid_values_heading[-2:]
                        raw_delta = heading2 - heading1
                        delta_heading = degrees(atan2(sin(radians(raw_delta)), cos(radians(raw_delta))))
                    #current_vibration_rover2 = delta_heading #Ändern Zahl

                #Linear Regression
                if rel_heading != 0:
                    heading_buffer_linear_2.append((rel_heading, Rover_time))
                    valid_values = [(h, t) for h, t in heading_buffer_linear_2 if h != 0]
                    if len(valid_values) >= 5:
                        recent = valid_values[-5:]
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

                R_2_Message.queue.clear()
                Rover_2_outline = ";".join(map(str, [
                    filtered_vibration, delta_heading, rel_heading,
                    Rover_date, Rover_time, Rover_Quality,
                    Rover_lon, Rover_lat, Rover_accHeading,
                    Rover_N, Rover_E, Rover_D, Rover_alt, height_boom,  R2_angular_velocity
                ]))
                R_2_Message.put(Rover_2_outline)
                print("rover2:",Rover_2_outline)

csv_data_buffer = deque()

def csv_logger_thread_buffered():
    print("[Logger] Thread gestartet")
    while not stop_event.is_set():
        time.sleep(0.1)

        try:
            #if R_1_Time.empty() or R_2_Time.empty() or B_Time.empty() or R_1_Message.empty() or R_2_Message.empty() or B_Message.empty():
            if R_1_Time.empty() or R_2_Time.empty() or R_1_Message.empty() or R_2_Message.empty():
               continue

            Ro_1_T = R_1_Time.get()
            R_1_msg = R_1_Message.get()

            Ro_2_T = R_2_Time.get()
            R_2_msg = R_2_Message.get()

            #Ba_T = B_Time.get()
            #Bmsg = B_Message.get()

            #print("[Logger] Rover-Zeiten:", Ro_1_T, Ro_2_T, Ba_T)

           #if Ro_1_T == Ro_2_T == Ba_T:
           #    line = f"{R_1_msg.replace('.', ',')};{R_2_msg.replace('.', ',')};{Bmsg.replace('.', ',')}"
           #    #print("[Logger] Neue Zeile:", line)
           #    csv_data_buffer.append(line.split(";"))
           #    #print("[Logger] Gespeichert:", line)

            if Ro_1_T == Ro_2_T:
                line = f"{R_1_msg.replace('.', ',')};{R_2_msg.replace('.', ',')}"
                #print("[Logger] Neue Zeile:", line)
                csv_data_buffer.append(line.split(";"))
                #print("[Logger] Gespeichert:", line)

        except Exception as e:
            print("[Logger Thread] Fehler:", e)

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
                "Rover_1_Filtered", "R1_delta_Heading", "R1_Heading",
                "R1_Rover_date", "R1_Rover_time","Rover_1_Quality",
                "R1_Rover_lon", "R1_Rover_lat","Rover_1_accHeading",
                "Rover_1_N", "Rover_1_E", "Rover_1_D","Rover_1_alt", "Rover_1_height_varriation", "Rover_1_Ang_velo",
                "Rover_2_Filtered",  "R2_delta_Heading", "R2_Heading",
                "R2_Rover_date", "R2_Rover_time","Rover_2_Quality",
                "R2_Rover_lon", "R2_Rover_lat", "Rover_2_accHeading",
                "Rover_2_N", "Rover_2_E", "Rover_2_D","Rover_2_alt", "Rover_2_height_varriation",  "Rover_2_Ang_velo",
                #"Base_lon", "Base_lat",
                #"Base_NumSV", "Base_HDOP", "Base_alt", "Base_Time"
            ])
            #------Daten schreiben--------
            for row in csv_data_buffer:
                writer.writerow(row)

        print(f"[CSV Export] Gespeichert: {path}")
        csv_data_buffer.clear()
        return path

    except Exception as e:
        print(f"[CSV Export] Fehler: {e}")
        return None
    
def start_measurement():
    #global streamBase
    #global B_Message, B_Time
    global streamRover1, R_1_Message, R_1_Time, vibration_history_rover1, heading_buffer_1,heading_buffer_linear_1 , heading_buffer_1_test, quality_rover1, R1_angular_velocity
    global streamRover2,R_2_Message, R_2_Time, vibration_history_rover2, heading_buffer_2,heading_buffer_linear_2 , heading_buffer_2_test, quality_rover2, R2_angular_velocity 
    global threads, stop_event
    global measurement_running

    threads = []
    stop_event = threading.Event()
    csv_data_buffer.clear()

    print(">>> start_measurement() wurde aufgerufen")
    
    #-----Konfigurationsdatei lesen------
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    with open(config_path, 'r') as config_file:
        config = json.load(config_file)

    #BASE_COM_PORT = config.get('BASE_COM_PORT')
    ROVER1_COM_PORT = config.get('ROVER1_COM_PORT')
    ROVER2_COM_PORT = config.get('ROVER2_COM_PORT')

    #streamBase = Serial(BASE_COM_PORT, 460800, timeout=3)
    streamRover1 = Serial(ROVER1_COM_PORT, 460800, timeout=3)
    streamRover2 = Serial(ROVER2_COM_PORT, 460800, timeout=3)

    heading_buffer_1 = deque(maxlen=2)
    heading_buffer_linear_1 = deque(maxlen=20)
    heading_buffer_1_test = deque(maxlen=2)
    vibration_history_rover1 = deque(maxlen=1200)
    quality_rover1 = deque(maxlen=1)
    t1 = threading.Thread(target=Rover1_Thread, daemon=True)

    heading_buffer_2 = deque(maxlen=2)
    heading_buffer_linear_2 = deque(maxlen=20)
    heading_buffer_2_test = deque(maxlen=2)
    vibration_history_rover2 = deque(maxlen=1200)
    quality_rover2 = deque(maxlen=1)
    t2 = threading.Thread(target=Rover2_Thread, daemon=True)

    #t0 = threading.Thread(target=BaseThread)
    t_logger = threading.Thread(target=csv_logger_thread_buffered, daemon=True)
    
    #threads.append(t0)
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

    #if streamBase.is_open:
        #streamBase.close()
        #print("StreamBase geschlossen.")

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