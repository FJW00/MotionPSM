import csv
import socket
import time
import json
from datetime import datetime
import threading

# Konfiguration aus JSON-Datei laden
def load_config(filename="config.json"):
    with open(filename, "r") as file:
        return json.load(file)

config = load_config()

# NTRIP-Server Einstellungen
NTRIP_HOST = config["ntrip"]["host"]
NTRIP_PORT = config["ntrip"]["port"]
MOUNTPOINT = config["ntrip"]["mountpoint"]
USERNAME = config["ntrip"]["username"]
PASSWORD = config["ntrip"]["password"]

# RTK-TCP-Server-Konfiguration
SERVER_PORT = config["rtk"]["server_port"]
CLIENTS = config["rtk"]["clients"]

# GNSS-Empfänger (Rover)
POS_MIDDLE = tuple(config["gnss"]["pos_middle"])
POS_LEFT = tuple(config["gnss"]["pos_left"])
POS_RIGHT = tuple(config["gnss"]["pos_right"])

# Timeout für die Verbindungen
TIMEOUT = config["timeout"]

# CSV-Datei vorbereiten
CSV_FILE = config["csv"]["filename"]
HEADER = ["timestamp", "lat_middle", "lon_middle", "lat_left", "lon_left", "lat_right", "lon_right"]

# Verbindung zum NTRIP-Server herstellen
def connect_ntrip():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((NTRIP_HOST, NTRIP_PORT))
    auth = f"{USERNAME}:{PASSWORD}".encode("utf-8").hex()
    headers = f"GET /{MOUNTPOINT} HTTP/1.1\r\nAuthorization: Basic {auth}\r\n\r\n"
    s.send(headers.encode())
    return s

# TCP-Server für die Verteilung der Korrekturdaten
def distribute_corrections():
    ntrip_socket = connect_ntrip()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("0.0.0.0", SERVER_PORT))
    server.listen(len(CLIENTS))
    
    clients = []
    for _ in CLIENTS:
        client, _ = server.accept()
        clients.append(client)

    while True:
        data = ntrip_socket.recv(1024)
        for client in clients:
            client.sendall(data)

# Funktion zur Verbindung mit einem Empfänger und Empfang der NMEA-Daten
def receive_gps_data(address, queue):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(TIMEOUT)
            s.connect(address)
            while True:
                data = s.recv(1024).decode("utf-8", errors="ignore")
                parsed_data = parse_nmea(data)
                if parsed_data:
                    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
                    queue.append((timestamp, parsed_data))
    except Exception as e:
        print(f"Fehler beim Abrufen der Daten von {address}: {e}")

# Funktion zur Extraktion von GGA-Daten (Latitude, Longitude) aus NMEA-Nachrichten
def parse_nmea(data):
    lines = data.split("\r\n")
    for line in lines:
        if line.startswith("$GNGGA") or line.startswith("$GPGGA"):
            parts = line.split(",")
            if len(parts) > 5:
                try:
                    lat = convert_nmea_to_decimal(parts[2], parts[3])
                    lon = convert_nmea_to_decimal(parts[4], parts[5])
                    return lat, lon
                except:
                    return None
    return None

# Funktion zur Umrechnung von NMEA-Koordinaten in Dezimalgrad
def convert_nmea_to_decimal(value, direction):
    if not value or not direction:
        return None
    degrees = float(value[:2])
    minutes = float(value[2:]) / 60
    decimal = degrees + minutes
    if direction in ['S', 'W']:
        decimal *= -1
    return decimal

# CSV-Datei initialisieren
with open(CSV_FILE, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(HEADER)

print("Starte GNSS-Datenlogging und Korrekturdatenverteilung...")

# Starte Korrekturdaten-Thread
threading.Thread(target=distribute_corrections, daemon=True).start()

# Datenwarteschlangen für Empfänger
gps_queues = {"middle": [], "left": [], "right": []}

# Threads für GPS-Empfang starten
threading.Thread(target=receive_gps_data, args=(POS_MIDDLE, gps_queues["middle"]), daemon=True).start()
threading.Thread(target=receive_gps_data, args=(POS_LEFT, gps_queues["left"]), daemon=True).start()
threading.Thread(target=receive_gps_data, args=(POS_RIGHT, gps_queues["right"]), daemon=True).start()

# Echtzeit-Datenaufzeichnung
while True:
    with open(CSV_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        while gps_queues["middle"] or gps_queues["left"] or gps_queues["right"]:
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
            pos_middle = gps_queues["middle"].pop(0)[1] if gps_queues["middle"] else ("", "")
            pos_left = gps_queues["left"].pop(0)[1] if gps_queues["left"] else ("", "")
            pos_right = gps_queues["right"].pop(0)[1] if gps_queues["right"] else ("", "")
            writer.writerow([timestamp, pos_middle[0], pos_middle[1], pos_left[0], pos_left[1], pos_right[0], pos_right[1]])
            print(f"{timestamp}: Middle={pos_middle}, Left={pos_left}, Right={pos_right}")
