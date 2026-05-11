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

# Konfigurationsdatei lesen
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as config_file:
    config = json.load(config_file)

BASE_COM_PORT = config.get('BASE_COM_PORT', 'COM15')
ROVER1_COM_PORT = config.get('ROVER1_COM_PORT', 'COM14')
ROVER2_COM_PORT = config.get('ROVER2_COM_PORT', 'COM16')

#Savepoint
folder = os.path.join(os.path.dirname(__file__), "CSV_Data")
os.makedirs(folder, exist_ok=True)
str_current_datetime = datetime.now().strftime("%Y%m%d_%H%M%S")
file_name = str_current_datetime+"F9P"+".csv"
full_path = os.path.join(folder, file_name)

streamBase = Serial(BASE_COM_PORT, 460800, timeout=3)
streamRover1 = Serial(ROVER1_COM_PORT, 460800, timeout=3)
streamRover2 = Serial(ROVER2_COM_PORT, 460800, timeout=3)

#Coordinate transdormation (WGS85 -> ETRS89/UTM Zone 32N)
transformer = Transformer.from_crs(4326, 25832)
transformer.transform(50, -80)

stop_event = threading.Event()


def BaseThread():
    Base_lon = 0
    Base_lat= 0
    Base_RW= 0
    Base_HW= 0
    Base_UTC = 0
    Base_Quality = 0
    Base_NumSV = 0
    Base_HDOP = 0
    Base_alt = 0 
    Rover_1_time = 0
    Rover_2_time = 0
    Base_UTC = 0
    
    
    print ("Basethread started...")
    while not stop_event.is_set():
        try:

            ubrBase = UBXReader(streamBase, validate=0)
            (raw_data_Base, parsed_data_Base) = ubrBase.read()
            # if (hasattr(parsed_data_Base, 'identity')== True):
            #     if (parsed_data_Base.identity == 'GNGGA'):
            #         Base_UTC = parsed_data_Base.time
            #         B_Time.queue.clear()
            #         B_Time.put(Base_UTC)
            #         #print ("BASE:" + str(Base_UTC))
            
            if (hasattr(parsed_data_Base, 'identity')== True):
                if (parsed_data_Base.identity == 'GNGGA'):
                    
                    Base_UTC = parsed_data_Base.time
                    #print ("Base:" + str(Base_UTC))
                    B_Time.queue.clear()
                    B_Time.put(Base_UTC)
                    #print (Base_UTC)
                    if (len(str(parsed_data_Base.lat))>1):
                        Base_lat = float(parsed_data_Base.lat)
                        Base_lon = float(parsed_data_Base.lon)            
                        nc = transformer.transform(Base_lat, Base_lon)
                        Base_RW = nc[0]
                        Base_HW = nc[1]
                        
                        #print ("BASE:" + str(Base_UTC))
                        Base_Quality = parsed_data_Base.quality
                        Base_NumSV = parsed_data_Base.numSV
                        Base_HDOP = parsed_data_Base.HDOP
                        Base_alt = parsed_data_Base.alt
                        
                        Base_outline = ";".join(map(str,[Base_UTC,Base_lon,Base_lat,Base_RW,Base_HW, Base_Quality,Base_NumSV,Base_HDOP, Base_alt]))
                        #time.sleep (0.05)
                        #print('BASE:')
                        #print (Base_outline)
                        #B_Message.queue.clear()       
                        B_Message.put(Base_outline) 
                    
                    #print (Base_UTC)
                    #print('BASErelPosHeading;relPosHeadingValid;accHeading;relPosLength;date;time;sogk;lon;lat;RW;HW')
                    #print(Base_time,sogk,lon,lat,RW,HW)
                    
            #time.sleep(.05)
        except Serial.SerialException:
            break

                
def Rover1_Thread():
    
    print ("Roverthread 1 started...")
    relPosHeading_1 = 0
    relPosHeadingValid_1= 0
    accHeading_1= 0
    relPosLength_1= 0
    Rover_1_date= '01-01-1990'
    Rover_1_time = 0
    Rover_1_sogk= 0
    Rover_1_lon = 0
    Rover_1_lat= 0
    Rover_1_RW= 0
    Rover_1_HW= 0
    while not stop_event.is_set():
        try:
            ubrRover_1 = UBXReader(streamRover1, validate=0)
            (raw_data, parsed_data) = ubrRover_1.read()
            # if (hasattr(parsed_data, 'identity')== True):       
            #     if (parsed_data.identity == 'GNGGA'):     
            #         Rover_time = parsed_data.time
            #         R_Time.queue.clear()
            #         R_Time.put(Rover_time)
            #         R_Message.queue.clear()
            #         R_Message.put(str(parsed_data.lat) + ";" + str(parsed_data.lon))
            #         #print ("ROVER_1:" + str(Rover_time))
            #time.sleep(.2)
            if (hasattr(parsed_data, 'identity')== True):
                if (parsed_data.identity == 'NAV-RELPOSNED'):
                    relPosHeading_1 = parsed_data.relPosHeading
                    relPosHeadingValid_1 = parsed_data.relPosHeadingValid
                    accHeading_1 = parsed_data.accHeading
                    relPosLength_1 = parsed_data.relPosLength
                    #print (relPosLength)
                if (parsed_data.identity == 'GNRMC'):
                    Rover_1_date = parsed_data.date
                if (parsed_data.identity == 'GNVTG'):
                    Rover_1_sogk = parsed_data.sogk
                if (parsed_data.identity == 'GNGGA'):
                    Rover_1_time = parsed_data.time
                    #print ("Rover1:" + str(Rover_1_time))
                    R_1_Time.queue.clear()
                    R_1_Time.put(Rover_1_time)
                    if (len(str(parsed_data.lat))>1):
                            Rover_1_lat = float(parsed_data.lat)
                            Rover_1_lon = float(parsed_data.lon)            
                            nc = transformer.transform(Rover_1_lat, Rover_1_lon)
                            Rover_1_RW = nc[0]
                            Rover_1_HW = nc[1]
                            R_1_Message.queue.clear()       
                            Rover_1_outline = ";".join(map(str,[relPosHeading_1,relPosHeadingValid_1,accHeading_1,relPosLength_1,Rover_1_date,Rover_1_time,Rover_1_sogk,Rover_1_lon,Rover_1_lat,Rover_1_RW,Rover_1_HW]))
                            Header = "R1_Heading;R1_HeadValid;R1_AccHeading;R1_BaseLength;R1_Rover_date;R1_Rover_time;R1_Rover_sogk;R1_Rover_lon;R1_Rover_lat;R1_Rover_RW;R1_Rover_HW"
                            #print ("ROVER1:")
                            #print (Rover_1_outline)
                            R_1_Message.put(Rover_1_outline)
                            
            #time.sleep(0.05)
        except Serial.SerialException:
            break      
            
            
def Rover2_Thread():
    
    print ("Roverthread 2 started...")
    relPosHeading_2 = 0
    relPosHeadingValid_2= 0
    accHeading_2= 0
    relPosLength_2= 0
    Rover_2_date= '01-01-1990'
    Rover_2_time = 0
    Rover_2_sogk= 0
    Rover_2_lon = 0
    Rover_2_lat= 0
    Rover_2_RW= 0
    Rover_2_HW= 0
    while not stop_event.is_set():
        try:
            ubrRover_2 = UBXReader(streamRover2, validate=0)
            (raw_data, parsed_data) = ubrRover_2.read()
            # if (hasattr(parsed_data, 'identity')== True):       
            #     if (parsed_data.identity == 'GNGGA'):     
            #         Rover_time = parsed_data.time
            #         R_Time.queue.clear()
            #         R_Time.put(Rover_time)
            #         R_Message.queue.clear()
            #         R_Message.put(str(parsed_data.lat) + ";" + str(parsed_data.lon))
            #         #print ("ROVER:" + str(Rover_time))
            #time.sleep(.2)
            if (hasattr(parsed_data, 'identity')== True):
                if (parsed_data.identity == 'NAV-RELPOSNED'):
                    relPosHeading_2 = parsed_data.relPosHeading
                    relPosHeadingValid_2 = parsed_data.relPosHeadingValid
                    accHeading_2 = parsed_data.accHeading
                    relPosLength_2 = parsed_data.relPosLength
                    #print (relPosLength_2)
                if (parsed_data.identity == 'GNRMC'):
                    Rover_2_date = parsed_data.date
                if (parsed_data.identity == 'GNVTG'):
                    Rover_2_sogk = parsed_data.sogk
                if (parsed_data.identity == 'GNGGA'):
                    Rover_2_time = parsed_data.time
                    #print ("Rover:" + str(Rover_2_time))
                    R_2_Time.queue.clear()
                    R_2_Time.put(Rover_2_time)
                    if (len(str(parsed_data.lat))>1):
                            Rover_2_lat = float(parsed_data.lat)
                            Rover_2_lon = float(parsed_data.lon)            
                            nc = transformer.transform(Rover_2_lat, Rover_2_lon)
                            Rover_2_RW = nc[0]
                            Rover_2_HW = nc[1]
                            R_2_Message.queue.clear()       
                            Rover_2_outline = ";".join(map(str,[relPosHeading_2,relPosHeadingValid_2,accHeading_2,relPosLength_2,Rover_2_date,Rover_2_time,Rover_2_sogk,Rover_2_lon,Rover_2_lat,Rover_2_RW,Rover_2_HW]))
                            Header = "R2_Heading;R2_HeadValid;R2_AccHeading;R2_BaseLength;R2_Rover_date;R2_Rover_time;R2_Rover_sogk;R2_Rover_lon;R2_Rover_lat;R2_Rover_RW;R2_Rover_HW"
                            #print ("ROVER2:")
                            #print (Rover_2_outline)
                            R_2_Message.put(Rover_2_outline)
                            
            #time.sleep(0.05)  
        except Serial.SerialException:
            break      
            
            

try:
    B_Time = queue.Queue()
    R_1_Time = queue.Queue()
    R_2_Time = queue.Queue()

    B_Message = queue.Queue()
    R_1_Message = queue.Queue()
    R_2_Message = queue.Queue()
    
    B_Thread = threading.Thread(target=BaseThread)
    R_1_Thread = threading.Thread(target=Rover1_Thread)
    R_2_Thread = threading.Thread(target=Rover2_Thread)

    B_Thread.start()
    R_1_Thread.start()
    R_2_Thread.start()
    
    Header = "R1_Heading;R1_HeadValid;R1_AccHeading;R1_BaseLength;R1_Rover_date;R1_Rover_time;R1_Rover_sogk;R1_Rover_lon;R1_Rover_lat;R1_Rover_RW;R1_Rover_HW;R2_Heading;R2_HeadValid;R2_AccHeading;R2_BaseLength;R2_Rover_date;R2_Rover_time;R2_Rover_sogk;R2_Rover_lon;R2_Rover_lat;R2_Rover_RW;R2_Rover_HW\n"
    file = open(full_path, 'w')
    file.writelines(Header)

    BaT_exists = False
    Ro_1_T_exists = False
    Ro_2_T_exists = False
    R_1_msg_exists = False
    R_2_msg_exists = False
    Bmsg_exists  = False
    PrevCommonTime = ""

    while True:
        time.sleep(0.05)
        if R_1_Time.qsize()> 0:
            R_1_TQ = [R_1_Time.get() for _ in range(R_1_Time.qsize())]
            Ro_1_T = R_1_TQ[-1]
            Ro_1_T_exists = True
        if R_2_Time.qsize()> 0:
            R_2_TQ = [R_2_Time.get() for _ in range(R_2_Time.qsize())]
            Ro_2_T = R_2_TQ[-1]
            Ro_2_T_exists = True
        if B_Time.qsize()> 0:
            BTQ = [B_Time.get() for _ in range(B_Time.qsize())]
            BaT = BTQ[-1] 
            BaT_exists = True
        
        if R_1_Message.qsize()> 0:
            R_1_MsgQ= [R_1_Message.get() for _ in range(R_1_Message.qsize())]
            R_1_msg = R_1_MsgQ[-1]
            R_1_msg_exists = True

        if R_2_Message.qsize()> 0:
            R_2_MsgQ= [R_2_Message.get() for _ in range(R_2_Message.qsize())]
            R_2_msg = R_2_MsgQ[-1]
            R_2_msg_exists = True 

        if B_Message.qsize()> 0:
            BMsgQ= [B_Message.get() for _ in range(B_Message.qsize())]
            Bmsg = BMsgQ[-1]
            Bmsg_exists = True
        
        if (Ro_1_T_exists and Ro_2_T_exists and BaT_exists):
            if BaT==Ro_1_T==Ro_2_T and BaT != PrevCommonTime:
                print("Equal and new " + str(BaT))
                file.writelines(R_1_msg + ";" + R_2_msg + '\n')
            PrevCommonTime = BaT

except KeyboardInterrupt:
    print("Beende Threads...")
    stop_event.set()
    B_Thread.join()
    R_1_Thread.join()
    R_2_Thread.join()
    print("Schließe serielle Ports...")
    streamBase.close()
    streamRover1.close()
    streamRover2.close()
    print("Datei speichern...")
    file.close()
    print("Programm beendet.")
'''