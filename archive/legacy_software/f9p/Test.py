'''# -*- coding: utf-8 -*-
from serial import Serial
from pyubx2 import UBXReader
from datetime import datetime
import time
import threading
import queue
import csv

# COM-Port-Konfiguration
COMBase = 'COM15'
COMRover1 = 'COM14'
COMRover2 = 'COM16'

# Serielle Schnittstellen initialisieren
streamBase = Serial(COMBase, 460800, timeout=3)
streamRover1 = Serial(COMRover1, 460800, timeout=3)
streamRover2 = Serial(COMRover2, 460800, timeout=3)

# Queues für Thread-Kommunikation
B_Message = queue.Queue()
R1_Message = queue.Queue()
R2_Message = queue.Queue()

def BaseThread():
    print("BaseThread gestartet...")
    while True:
        try:
            ubrBase = UBXReader(streamBase, validate=0)
            raw_data_Base, parsed_data_Base = ubrBase.read()
            
            if hasattr(parsed_data_Base, 'identity') and parsed_data_Base.identity == 'GNGGA':
                # Basisdaten verarbeiten
                Base_UTC = parsed_data_Base.time
                Base_lat = float(parsed_data_Base.lat)
                Base_lon = float(parsed_data_Base.lon)
                
                # Daten in Queue schreiben
                B_Message.put({
                    'UTC': Base_UTC,
                    'lat': Base_lat,
                    'lon': Base_lon
                })
        except Exception as e:
            print(f"Fehler im BaseThread: {e}")
        time.sleep(0.05)

def RoverThread(stream, rover_id):
    print(f"RoverThread {rover_id} gestartet...")
    while True:
        try:
            ubrRover = UBXReader(stream, validate=0)
            raw_data_Rover, parsed_data_Rover = ubrRover.read()
            
            data = {
                'lat': 0,
                'lon': 0,
                'time': 0,
                'heading': 0  # Das Heading für den Rover
            }
            
            if hasattr(parsed_data_Rover, 'identity') and parsed_data_Rover.identity == 'GNGGA':
                data['lat'] = float(parsed_data_Rover.lat)
                data['lon'] = float(parsed_data_Rover.lon)
                data['time'] = parsed_data_Rover.time
                
            if hasattr(parsed_data_Rover, 'identity') and parsed_data_Rover.identity == 'NAV-RELPOSNED':
                data['heading'] = parsed_data_Rover.relPosHeading  # Heading des Rovers
                
                # Daten in die entsprechende Queue schreiben
                if rover_id == 1:
                    R1_Message.put(data)
                elif rover_id == 2:
                    R2_Message.put(data)
                    
        except Exception as e:
            print(f"Fehler im RoverThread {rover_id}: {e}")
        time.sleep(0.05)

def write_to_csv():
    filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".csv"
    header = [
        "Source", "Timestamp", "Latitude", "Longitude", "Heading"
    ]
    
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file, delimiter=';')
        writer.writerow(header)
        
        while True:
            try:
                # Abruf von Base-, Rover1- und Rover2-Daten
                base_data = B_Message.get() if not B_Message.empty() else None
                r1_data = R1_Message.get() if not R1_Message.empty() else None
                r2_data = R2_Message.get() if not R2_Message.empty() else None
                
                if base_data:
                    row = ["Base", base_data["UTC"], base_data["lat"], base_data["lon"], ""]
                    writer.writerow(row)
                
                if r1_data:
                    row = ["Rover1", r1_data["time"], r1_data["lat"], r1_data["lon"], r1_data["heading"]]
                    writer.writerow(row)
                
                if r2_data:
                    row = ["Rover2", r2_data["time"], r2_data["lat"], r2_data["lon"], r2_data["heading"]]
                    writer.writerow(row)
                
            except KeyboardInterrupt:
                print("\nProgramm wurde vom Benutzer unterbrochen.")
                break
            except Exception as e:
                print(f"Fehler beim Schreiben der CSV-Datei: {e}")
                break

# Threads starten
threading.Thread(target=BaseThread, daemon=True).start()
threading.Thread(target=RoverThread, args=(streamRover1, 1), daemon=True).start()
threading.Thread(target=RoverThread, args=(streamRover2, 2), daemon=True).start()

# CSV-Schreibprozess starten
write_to_csv()
'''
# -*- coding: utf-8 -*-
from serial import Serial
from pyubx2 import UBXReader
from pyproj import Transformer
from datetime import datetime
import time
import threading
import queue

# Transformer to UTM Zone 32N (EPSG:25832)
transformer = Transformer.from_crs(4326, 25832, always_xy=True)

# Serial Ports
COMBase = 'COM15'   # Base
COMRover1 = 'COM14' # Rover 1
COMRover2 = 'COM16' # Rover 2

# Serial Streams
streamBase = Serial(COMBase, 460800, timeout=3)
streamRover1 = Serial(COMRover1, 460800, timeout=3)
streamRover2 = Serial(COMRover2, 460800, timeout=3)

# Queues
B_Time = queue.Queue()
R1_Time = queue.Queue()
R2_Time = queue.Queue()

B_Message = queue.Queue()
R1_Message = queue.Queue()
R2_Message = queue.Queue()

def parse_latlon_to_utm(lat, lon):
    if lat and lon:
        return transformer.transform(lon, lat)
    return 0, 0

def BaseThread():
    ubr = UBXReader(streamBase, validate=0)
    while True:
        _, msg = ubr.read()
        if hasattr(msg, 'identity') and msg.identity == 'GNGGA':
            if msg.lat and msg.lon:
                utm_e, utm_n = parse_latlon_to_utm(msg.lat, msg.lon)
                line = ";".join(map(str, [
                    msg.time, msg.lon, msg.lat,
                    utm_e, utm_n, msg.quality,
                    msg.numSV, msg.HDOP, msg.alt
                ]))
                B_Time.queue.clear()
                B_Time.put(msg.time)
                B_Message.queue.clear()
                B_Message.put(line)
        time.sleep(0.01)

def RoverThread(stream, time_queue, msg_queue, rover_name):
    ubr = UBXReader(stream, validate=0)
    data = {
        'heading': 0, 'valid': 0, 'acc': 0, 'length': 0,
        'date': '', 'time': '', 'sogk': 0,
        'lat': 0, 'lon': 0, 'utm_e': 0, 'utm_n': 0
    }
    while True:
        _, msg = ubr.read()
        if hasattr(msg, 'identity'):
            if msg.identity == 'NAV-RELPOSNED':
                data['heading'] = msg.relPosHeading
                data['valid'] = msg.relPosHeadingValid
                data['acc'] = msg.accHeading
                data['length'] = msg.relPosLength
            elif msg.identity == 'GNRMC':
                data['date'] = msg.date
            elif msg.identity == 'GNVTG':
                data['sogk'] = msg.sogk
            elif msg.identity == 'GNGGA' and msg.lat and msg.lon:
                data['time'] = msg.time
                data['lat'] = msg.lat
                data['lon'] = msg.lon
                data['utm_e'], data['utm_n'] = parse_latlon_to_utm(data['lat'], data['lon'])

                msg_line = ";".join(map(str, [
                    data['heading'], data['valid'], data['acc'], data['length'],
                    data['date'], data['time'], data['sogk'],
                    data['lon'], data['lat'], data['utm_e'], data['utm_n']
                ]))

                time_queue.queue.clear()
                time_queue.put(data['time'])

                msg_queue.queue.clear()
                msg_queue.put(msg_line)

                print(f"{rover_name}: {msg_line}")
        time.sleep(0.01)

# Start all threads
try:
    threading.Thread(target=BaseThread, daemon=True).start()
    threading.Thread(target=RoverThread, args=(streamRover1, R1_Time, R1_Message, 'Rover1'), daemon=True).start()
    threading.Thread(target=RoverThread, args=(streamRover2, R2_Time, R2_Message, 'Rover2'), daemon=True).start()

    print("GPS Logger Started")
    current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_name = f"GNSS_Log_{current_datetime}.txt"
    file = open(file_name, "w")

    # CSV Header
    header = (
        "R1_Heading;R1_Valid;R1_AccHeading;R1_Length;R1_Date;R1_Time;R1_SOGK;R1_Lon;R1_Lat;R1_UTM_E;R1_UTM_N;"
        "R2_Heading;R2_Valid;R2_AccHeading;R2_Length;R2_Date;R2_Time;R2_SOGK;R2_Lon;R2_Lat;R2_UTM_E;R2_UTM_N;"
        "Base_Time;Base_Lon;Base_Lat;Base_UTM_E;Base_UTM_N;Base_Quality;Base_NumSV;Base_HDOP;Base_Alt\n"
    )
    file.write(header)

    prev_time = ""
    while True:
        time.sleep(0.05)

        if not (B_Time.empty() or R1_Time.empty() or R2_Time.empty()):
            bt = B_Time.queue[-1]
            r1t = R1_Time.queue[-1]
            r2t = R2_Time.queue[-1]

            if bt == r1t == r2t and bt != prev_time:
                if not (B_Message.empty() or R1_Message.empty() or R2_Message.empty()):
                    line = f"{R1_Message.queue[-1]};{R2_Message.queue[-1]};{B_Message.queue[-1]}\n"
                    file.write(line)
                    print(f"Logged epoch @ {bt}")
                    prev_time = bt

except KeyboardInterrupt:
    print("Closing serial ports and file...")
    streamBase.close()
    streamRover1.close()
    streamRover2.close()
    file.close()
