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
from math import sin, asin, radians, degrees
from scipy.signal import butter, lfilter
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import matplotlib
import csv

# Globale Variablen für Live-Server
current_vibration_rover1 = 0
current_vibration_rover2 = 0

B_Message = queue.Queue()
R_1_Message = queue.Queue()
R_2_Message = queue.Queue()
B_Time = queue.Queue()
R_1_Time = queue.Queue()
R_2_Time = queue.Queue()
BaT_exists = False
Ro_1_T_exists = False
Ro_2_T_exists = False
R_1_msg_Exits = False
R_2_msg_Exits = False
Bmsg_Exists  = False

transformer = Transformer.from_crs(4326, 25832)
transformer.transform(50, -80)

stop_event = threading.Event()

heading_buffer_1 = deque(maxlen=2)
heading_buffer_2 = deque(maxlen=2)

rover1_vibration_buffer = deque(maxlen=30)
rover2_vibration_buffer = deque(maxlen=30)

measurement_running = False
csv_data_buffer = []  # Liste aus Strings (komplette CSV-Zeilen)

#------------------Butterworth-Filter---------------------

def butter_lowpass(cutoff, fs, order):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return b, a

def butter_lowpass_filter(data, cutoff=1.0, fs=10.0, order=3): #cutoff= Grenzfrequenzen; fs= Abtastrate; order=Komplexität der Glättung
    if len(data) < order:
        return data  # Nicht genug Daten zum Filtern
    b, a = butter_lowpass(cutoff, fs, order)
    data_array = np.array(data)
    y = lfilter(b, a, data_array)
    return y

#-----------------------Threads----------------------
def BaseThread():
    Base_lon = 0
    Base_lat= 0
    Base_Quality = 0
    Base_HDOP = 0
    Base_alt = 0
    Base_time = 0
    Base_RW = 0
    Base_HW = 0
    Base_NumSV = 0

    print ("Basethread started...")
    while not stop_event.is_set():
        #print("[BaseThread] Waiting for data...")
        #if not streamBase.is_open:
        #    break
        try:
            ubrBase = UBXReader(streamBase, validate=0)
            (raw_data_Base, parsed_data_Base) = ubrBase.read()
            #print("[BaseThread] Parsed:", parsed_data_Base)
            #if (hasattr(parsed_data_Base, 'identity')== True):
             #   if (parsed_data_Base.identity == 'GNGGA'):
             # Absicherung gegen None-Rückgabe
            #if parsed_data_Base is None:
            #    continue
            #print(f"[BaseThread] Raw: {raw_data_Base}")
            if (hasattr(parsed_data_Base, 'identity')== True):
                if (parsed_data_Base.identity == 'GNGGA'):
                    #Base_UTC = parsed_data_Base.time
                    #print ("Base:" + str(Base_UTC))
                    #B_Time.queue.clear()
                    #B_Time.put(Base_UTC)
                    #print (Base_UTC)
                    if (len(str(parsed_data_Base.lat))>1):
                        Base_lat = float(parsed_data_Base.lat)
                        Base_lon = float(parsed_data_Base.lon)            
                        nc = transformer.transform(Base_lat, Base_lon)
                        Base_RW = nc[0]
                        Base_HW = nc[1]
                    #Base_Quality = parsed_data_Base.quality
                    Base_NumSV = parsed_data_Base.numSV
                    Base_HDOP = parsed_data_Base.HDOP
                    Base_alt = parsed_data_Base.alt

                elif (parsed_data_Base.identity == 'NAV-PVT'):
                    Base_time = parsed_data_Base.iTOW
                    #B_Time.queue.clear()
                    #B_Time.put(Base_time)
                    Base_Quality = parsed_data_Base.fixType
                    
                    #B_Message.queue.clear()
                    Base_outline = ";".join(map(str, [Base_time, Base_lon, Base_lat, Base_RW, Base_HW, Base_Quality, Base_NumSV, Base_HDOP, Base_alt]))
                    B_Message.put(Base_outline) 
                    print('Base:',Base_outline)
        #        pass
        #except SerialException as e:
        #    print(f"[BaseThread] SerialException: {e}")
        #    break
        #except Exception as e:
        #    if stop_event.isSet():
        #        break
        #    print(f"[BaseThread] Error: {e}")
        except Serial.SerialException:
            break
    #finally:
    #    print("BaseThread finished.")

def Rover1_Thread():
    global current_vibration_rover1
    print("Roverthread 1 started...")
    Rover_1_date = '01-01-1990'
    Rover_1_time = 0
    Rover_1_lon = 0
    Rover_1_lat = 0

    while not stop_event.is_set():
        ubr = UBXReader(streamRover1, validate=0)
        raw_data, parsed_data = ubr.read()

        if parsed_data and hasattr(parsed_data, 'identity'):
            if parsed_data.identity == 'GNGGA':
                #Rover_1_time = parsed_data.time
                #R_1_Time.queue.clear()
                #if parsed_data.quality != '0':  # 0 = kein Fix
                    #R_1_Time.put(Rover_1_time)
                    #print("Rover1:",Rover_1_time)
                if len(str(parsed_data.lat)) > 1:
                    Rover_1_lat = float(parsed_data.lat)
                    Rover_1_lon = float(parsed_data.lon)

            elif parsed_data.identity == 'GNRMC':
                Rover_1_date = parsed_data.date

            elif parsed_data.identity == 'NAV-RELPOSNED':
                Rover_1_time = parsed_data.iTOW
                R_1_Time.queue.clear()
                R_1_Time.put(Rover_1_time)
                Rover_1_N = parsed_data.relPosN
                Rover_1_E = parsed_data.relPosE
                Rover_1_D = parsed_data.relPosD
                rel_heading = parsed_data.relPosHeading
                Rover_1_accHeading = parsed_data.accHeading
                heading_buffer_1.append((rel_heading, time.time()))
                if len(heading_buffer_1) == 2:
                    (h1, t1), (h2, t2) = heading_buffer_1
                    delta_heading = h2 - h1
                    delta_time = t2 - t1
                    raw_vibration = delta_heading / delta_time if delta_time != 0 else 0
                    fixed_vibration = degrees(asin(sin(radians(raw_vibration))))
                    rover1_vibration_buffer.append(fixed_vibration)

                    filtered_vibration = (
                        butter_lowpass_filter(list(rover1_vibration_buffer))[-1]
                        if len(rover1_vibration_buffer) >= 4 else fixed_vibration
                    )

                    current_vibration_rover1 = filtered_vibration
                    vibration_history_rover1.append(filtered_vibration)

                    R_1_Message.queue.clear()
                    Rover_1_outline = ";".join(map(str, [
                        filtered_vibration, fixed_vibration, raw_vibration, rel_heading,
                        Rover_1_date, Rover_1_time, Rover_1_lon, Rover_1_lat, Rover_1_accHeading,
                        Rover_1_N, Rover_1_E, Rover_1_D
                    ]))
                    
                    R_1_Message.put(Rover_1_outline)
                    #print("Rover1:",Rover_1_outline)


def Rover2_Thread():
    global current_vibration_rover2
    print("Roverthread 2 started...")
    Rover_2_date = '01-01-1990'
    Rover_2_time = 0
    Rover_2_lon = 0
    Rover_2_lat = 0

    while not stop_event.is_set():
        ubr = UBXReader(streamRover2, validate=0)
        raw_data, parsed_data = ubr.read()

        if parsed_data and hasattr(parsed_data, 'identity'):
            if parsed_data.identity == 'GNGGA':
                #Rover_2_time = parsed_data.time
                #R_2_Time.queue.clear()
                #if parsed_data.quality != '0':  # 0 = kein Fix
                 #   R_2_Time.put(Rover_2_time)
                    #print("Rover2:",Rover_2_time)
                if len(str(parsed_data.lat)) > 1:
                    Rover_2_lat = float(parsed_data.lat)
                    Rover_2_lon = float(parsed_data.lon)
                    

            elif parsed_data.identity == 'GNRMC':
                Rover_2_date = parsed_data.date

            elif parsed_data.identity == 'NAV-RELPOSNED':
                Rover_2_time = parsed_data.iTOW
                R_2_Time.queue.clear()
                R_2_Time.put(Rover_2_time)
                Rover_2_N = parsed_data.relPosN
                Rover_2_E = parsed_data.relPosE
                Rover_2_D = parsed_data.relPosD
                rel_heading = parsed_data.relPosHeading
                Rover_2_accHeading = parsed_data.accHeading
                heading_buffer_2.append((rel_heading, time.time()))
                if len(heading_buffer_2) == 2:
                    (h1, t1), (h2, t2) = heading_buffer_2
                    delta_heading = h2 - h1
                    delta_time = t2 - t1
                    raw_vibration = delta_heading / delta_time if delta_time != 0 else 0
                    fixed_vibration = degrees(asin(sin(radians(raw_vibration))))
                    rover2_vibration_buffer.append(fixed_vibration)

                    filtered_vibration = (
                        butter_lowpass_filter(list(rover2_vibration_buffer))[-1]
                        if len(rover2_vibration_buffer) >= 4 else fixed_vibration
                    )

                    current_vibration_rover2 = filtered_vibration
                    vibration_history_rover2.append(filtered_vibration)

                    R_2_Message.queue.clear()
                    Rover_2_outline = ";".join(map(str, [
                        filtered_vibration, fixed_vibration, raw_vibration, rel_heading,
                        Rover_2_date, Rover_2_time, Rover_2_lon, Rover_2_lat, Rover_2_accHeading,
                        Rover_2_N, Rover_2_E, Rover_2_D
                    ]))
                    
                    R_2_Message.put(Rover_2_outline)
                    #print("rover2:",Rover_2_outline)

csv_data_buffer = deque()

def csv_logger_thread_buffered():
    print("[Logger] Thread gestartet")
    while not stop_event.is_set():
        time.sleep(0.1)

        try:
            if R_1_Time.empty() or R_2_Time.empty() or B_Time.empty() or R_1_Message.empty() or R_2_Message.empty() or B_Message.empty():
            #if R_1_Time.empty() or R_2_Time.empty() or R_1_Message.empty() or R_2_Message.empty():
               continue

            Ro_1_T = R_1_Time.get()
            Ro_2_T = R_2_Time.get()
            R_1_msg = R_1_Message.get()
            R_2_msg = R_2_Message.get()

            Ba_T = B_Time.get()
            Bmsg = B_Message.get()

            print("[Logger] Rover-Zeiten:", Ro_1_T, Ro_2_T, Ba_T)

            if Ro_1_T == Ro_2_T == Ba_T:
                line = f"{R_1_msg.replace('.', ',')};{R_2_msg.replace('.', ',')};{Bmsg.replace('.', ',')}"
                #print("[Logger] Neue Zeile:", line)
                csv_data_buffer.append(line.split(";"))
                #print("[Logger] Gespeichert:", line)

            #if Ro_1_T == Ro_2_T:
            #    line = f"{R_1_msg.replace('.', ',')};{R_2_msg.replace('.', ',')}"
            #    #print("[Logger] Neue Zeile:", line)
            #    csv_data_buffer.append(line.split(";"))
            #    #print("[Logger] Gespeichert:", line)

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
            # Header schreiben
            
            writer.writerow([
                "Rover_1_Filtered", "Rover_1_norm_vibration", "Rover_1_vibration",
                "R1_Heading", "R1_Rover_date", "R1_Rover_time",
                "R1_Rover_lon", "R1_Rover_lat","Rover_1_accHeading",
                "Rover_1_N", "Rover_1_E", "Rover_1_D",
                "Rover_2_Filtered", "Rover_2_norm_vibration", "Rover_2_vibration",
                "R2_Heading", "R2_Rover_date", "R2_Rover_time",
                "R2_Rover_lon", "R2_Rover_lat", "Rover_2_accHeading",
                "Rover_2_N", "Rover_2_E", "Rover_2_D",
                "Base_UTC", "Base_lon", "Base_lat",
                "Base_RW", "Base_HW", "Base_Quality", "Base_NumSV", "Base_HDOP", "Base_alt"
            ])
            # Daten schreiben
            for row in csv_data_buffer:
                writer.writerow(row)

        print(f"[CSV Export] Gespeichert: {path}")
        csv_data_buffer.clear()
        return path

    except Exception as e:
        print(f"[CSV Export] Fehler: {e}")
        return None
     


# Nur starten, wenn explizit aufgerufen wird
def start_measurement():
    global streamRover1, streamRover2, streamBase
    global heading_buffer_1, heading_buffer_2
    global threads, stop_event
    global R_1_Message,R_2_Message, B_Message
    global R_1_Time, R_2_Time, B_Time
    global vibration_history_rover1, vibration_history_rover2
    global measurement_running
    global threads
    threads = []
    stop_event = threading.Event()
    csv_data_buffer.clear()

    print(">>> start_measurement() wurde aufgerufen")
    
    # Konfigurationsdatei lesen
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r') as config_file:
        config = json.load(config_file)

    #BASE_COM_PORT = config.get('BASE_COM_PORT', '/dev/ttyUSB0')
    #ROVER1_COM_PORT = config.get('ROVER1_COM_PORT', '/dev/ttyUSB1')
    #ROVER2_COM_PORT = config.get('ROVER2_COM_PORT', '/dev/ttyUSB2')

    BASE_COM_PORT = config.get('BASE_COM_PORT')
    ROVER1_COM_PORT = config.get('ROVER1_COM_PORT')
    ROVER2_COM_PORT = config.get('ROVER2_COM_PORT')


    streamBase = Serial(BASE_COM_PORT, 460800, timeout=3)
    streamRover1 = Serial(ROVER1_COM_PORT, 460800, timeout=3)
    streamRover2 = Serial(ROVER2_COM_PORT, 460800, timeout=3)

    heading_buffer_1 = deque(maxlen=2)
    heading_buffer_2 = deque(maxlen=2)
    vibration_history_rover1 = deque(maxlen=1200)
    vibration_history_rover2 = deque(maxlen=1200)
    
    t0 = threading.Thread(target=BaseThread)
    t1 = threading.Thread(target=Rover1_Thread, daemon=True)
    t2 = threading.Thread(target=Rover2_Thread, daemon=True)
    t_logger = threading.Thread(target=csv_logger_thread_buffered, daemon=True)
    #t_logger = threading.Thread(target=csv_logger_thread, args=(full_path,), daemon=True)

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

    # Starte Live-Plot-Thread
    #if config.get("LIVE_PLOT", True):
    #    plot_thread = threading.Thread(target=start_live_plot)
    #    plot_thread.daemon = True
    #    plot_thread.start()


def stop_measurement():
    global stop_event
    global measurement_running

    stop_event.set()
    for t in threads:
        print(f"Stoppe Thread: {t.name}...")
        t.join(timeout=2) #Max 2 Sekunden warten
        if t.is_alive():
            print(f"⚠️ Thread {t.name} hat nicht sauber beendet.")
        else:
            print(f"✅ Thread {t.name} beendet.")

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

# Für Live-Plot-Daten
plot_data_length = 100  # Anzahl der Punkte im Plot
time_series = deque(maxlen=plot_data_length)
vib_rover1_series = deque(maxlen=plot_data_length)
vib_rover2_series = deque(maxlen=plot_data_length)

def update_plot(frame):
    global current_vibration_rover1, current_vibration_rover2
    now = time.time()
    time_series.append(now - start_time_plot)
    vib_rover1_series.append(current_vibration_rover1)
    vib_rover2_series.append(current_vibration_rover2)

    plt.cla()
    plt.title("Live Vibration Plot")
    plt.xlabel("Time (s)")
    plt.ylabel("Vibration Δheading/s")
    plt.grid(True)
    plt.plot(time_series, vib_rover1_series, label="Rover 1", color="blue")
    plt.plot(time_series, vib_rover2_series, label="Rover 2", color="red")
    plt.legend(loc="upper right")

def start_live_plot():
    try:
        matplotlib.use('TkAgg')  # oder 'Qt5Agg', je nach System
        global start_time_plot
        start_time_plot = time.time()
        fig = plt.figure()
        ani = FuncAnimation(fig, update_plot, interval=500)
        plt.show()
    except Exception as e:
        print(f"Live-Plot konnte nicht gestartet werden: {e}")



if __name__ == "__main__":
    try:
        start_measurement()
    except KeyboardInterrupt:
        print("Messung abgebrochen")
    finally:
        stop_measurement()