# -*- coding: utf-8 -*-

from serial import Serial
from pyubx2 import UBXReader
from pyproj import Transformer
from datetime import datetime, date 
from collections import deque
import time
import threading
import queue
import os
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from math import sin, asin, radians, degrees
from scipy.signal import butter, lfilter
import numpy as np

#Savepoint
folder = os.path.join(os.path.dirname(__file__), "CSV_Data")
os.makedirs(folder, exist_ok=True)

#Filename
str_current_datetime = datetime.now().strftime("%Y%m%d_%H%M%S")
file_name = str_current_datetime+"F9P"+".csv"
full_path = os.path.join(folder, file_name)

#Windows
COMBase     = 'COM3' #Base
COMRover1   = 'COM9' #Left
COMRover2   = 'COM12' #Right

'''
#Pi
COMBase     = '/dev/serial/by-id/usb-u-blox_AG_C099__ZED-F9P_<BASE-ID>-if00-port0'
COMRover1   = '/dev/serial/by-id/usb-u-blox_AG_C099__ZED-F9P_<ROVER2-ID>-if00-port0'
COMRover2   = '/dev/serial/by-id/usb-u-blox_AG_C099__ZED-F9P_<ROVER1-ID>-if00-port0'
'''

#Port and Baudrate
streamBase = Serial(COMBase, 460800, timeout=3)
streamRover1 = Serial(COMRover1, 460800, timeout=3)
streamRover2 = Serial(COMRover2, 460800, timeout=3)

#Transform Coordinatesystem
transformer = Transformer.from_crs(4326, 25832)
transformer.transform(50, -80)

# Initialize ring buffers for both rovers
heading_buffer_1 = deque(maxlen=2)  
heading_buffer_2 = deque(maxlen=2)  

rover1_vibration_buffer = deque(maxlen=30)
rover2_vibration_buffer = deque(maxlen=30)

# Include variables for vibration calculation
Rover_1_vibration = 0
Rover_2_vibration = 0
Rover_1_normalized_vibration = 0
Rover_2_normalized_vibration = 0
Rover_1_filtered_value = 0
Rover_2_filtered_value = 0

stop_event = threading.Event()

#------------------Butterworth-Filter---------------------

def butter_lowpass(cutoff, fs, order):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return b, a

def butter_lowpass_filter(data, cutoff=1.5, fs=10.0, order=2): #cutoff= Grenzfrequenzen; fs= Abtastrate; order=Komplexität der Glättung
    if len(data) < order:
        return data  # Nicht genug Daten zum Filtern
    b, a = butter_lowpass(cutoff, fs, order)
    data_array = np.array(data)
    y = lfilter(b, a, data_array)
    return y

#-------------------Thread Functions----------------------

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
                    #Base_Quality = parsed_data_Base.quality
                    Base_NumSV = parsed_data_Base.numSV
                    Base_HDOP = parsed_data_Base.HDOP
                    Base_alt = parsed_data_Base.alt

                elif (parsed_data_Base.identity == 'NAV-PVT'):    
                    Base_time = parsed_data_Base.iTOW
                    print('Base_Time:',Base_time)
                    Base_Quality = parsed_data_Base.fixType

                    Base_outline = ";".join(map(str,[Base_UTC,Base_lon,Base_lat,Base_RW,Base_HW, Base_Quality,Base_NumSV,Base_HDOP, Base_alt]))
                    #time.sleep (0.05)
                    #print('BASE:')
                    print ('Base:',Base_outline)
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
    
    global Rover_1_vibration
    global Rover_1_normalized_vibration
    global Rover_1_filtered_value

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

                    #if len(heading_buffer_1) == 2 and relPosHeading_1 != 0:
                    if len(heading_buffer_1) == 2 :
                        last_heading, last_time = heading_buffer_1[-1]
                        delta_heading = relPosHeading_1 - last_heading

                        now_date = date.today()
                        dt1 = datetime.combine(now_date, Rover_1_time)
                        dt2 = datetime.combine(now_date, last_time)
                        delta_time = (dt1 - dt2).total_seconds()

                        Rover_1_vibration = float(delta_heading / delta_time if delta_time != 0 else 0)
                        Rover_1_normalized_vibration = degrees(asin(sin(radians(Rover_1_vibration))))

                        if (len(str(parsed_data.lat))>1):
                            Rover_1_lat = float(parsed_data.lat)
                            Rover_1_lon = float(parsed_data.lon)            
                            nc = transformer.transform(Rover_1_lat, Rover_1_lon)
                            Rover_1_RW = nc[0]
                            Rover_1_HW = nc[1]

                    # Nur filtern, wenn genügend Werte vorhanden sind
                    if len(rover1_vibration_buffer) >= 4:  # 4 = minimal für order=4
                       filtered_values = butter_lowpass_filter(list(rover1_vibration_buffer))
                       Rover_1_filtered_value = filtered_values[-1]  # Letzter gefilterter Wert

                    rover1_vibration_buffer.append(Rover_1_normalized_vibration)
                    heading_buffer_1.append((relPosHeading_1, Rover_1_time))

                    R_1_Message.queue.clear()   

                    Rover_1_outline = ";".join(map(str,[Rover_1_filtered_value,Rover_1_normalized_vibration,Rover_1_vibration,relPosHeading_1,Rover_1_date,Rover_1_time,Rover_1_lon,Rover_1_lat]))
                    Header = "Rover_1_Filtered;Rover_1_norm_vibration;Rover_1_vibration;R1_Heading;R1_Rover_date;R1_Rover_time;R1_Rover_lon;R1_Rover_lat"

                    #Rover_1_outline = ";".join(map(str,[Rover_1_vibration, relPosHeading_1,relPosHeadingValid_1,accHeading_1,relPosLength_1,Rover_1_date,Rover_1_time,Rover_1_sogk,Rover_1_lon,Rover_1_lat,Rover_1_RW,Rover_1_HW]))
                    #Header = "Rover_1_vibration;R1_Heading;R1_HeadValid;R1_AccHeading;R1_BaseLength;R1_Rover_date;R1_Rover_time;R1_Rover_sogk;R1_Rover_lon;R1_Rover_lat;R1_Rover_RW;R1_Rover_HW"
                    
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

    global Rover_2_vibration
    global Rover_2_normalized_vibration
    global Rover_2_filtered_value

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
                    #if len(heading_buffer_2) == 2 and relPosHeading_2 != 0:
                    if len(heading_buffer_2) == 2:
                        # Calculate delta heading and delta time
                        last_heading, last_time = heading_buffer_2[-1]
                        delta_heading = relPosHeading_2 - last_heading

                        now_date = date.today()
                        dt1 = datetime.combine(now_date, Rover_2_time)
                        dt2 = datetime.combine(now_date, last_time)
                        delta_time = (dt1 - dt2).total_seconds()

                        Rover_2_vibration = float(delta_heading / delta_time if delta_time != 0 else 0)
                        Rover_2_normalized_vibration = degrees(asin(sin(radians(Rover_2_vibration))))

                        if (len(str(parsed_data.lat))>1):
                                Rover_2_lat = float(parsed_data.lat)
                                Rover_2_lon = float(parsed_data.lon)            
                                nc = transformer.transform(Rover_2_lat, Rover_2_lon)
                                Rover_2_RW = nc[0]
                                Rover_2_HW = nc[1]

                    # Nur filtern, wenn genügend Werte vorhanden sind
                    if len(rover2_vibration_buffer) >= 4:  # 4 = minimal für order=4
                       filtered_values = butter_lowpass_filter(list(rover2_vibration_buffer))
                       Rover_2_filtered_value = filtered_values[-1]  # Letzter gefilterter Wert

                    # Update the ring buffer
                    rover2_vibration_buffer.append(Rover_2_normalized_vibration)
                    heading_buffer_2.append((relPosHeading_2, Rover_2_time))

                    R_2_Message.queue.clear() 

                    Rover_2_outline = ";".join(map(str,[Rover_2_filtered_value,Rover_2_normalized_vibration,Rover_2_vibration,relPosHeading_2,Rover_2_date,Rover_2_time,Rover_2_lon,Rover_2_lat]))
                    Header = "Rover_2_Filtered;Rover_2_norm_vibration;Rover_2_vibration;R2_Heading;R2_Rover_date;R2_Rover_time;R2_Rover_lon;R2_Rover_lat"

                    #Rover_2_outline = ";".join(map(str,[Rover_2_vibration,relPosHeading_2,relPosHeadingValid_2,accHeading_2,relPosLength_2,Rover_2_date,Rover_2_time,Rover_2_sogk,Rover_2_lon,Rover_2_lat,Rover_2_RW,Rover_2_HW]))
                    #Header = "Rover_2_vibration;R2_Heading;R2_HeadValid;R2_AccHeading;R2_BaseLength;R2_Rover_date;R2_Rover_time;R2_Rover_sogk;R2_Rover_lon;R2_Rover_lat;R2_Rover_RW;R2_Rover_HW"
                    #print ("ROVER2:")
                    #print (Rover_2_outline)
                    R_2_Message.put(Rover_2_outline)
                            
            #time.sleep(0.05)  
        except Serial.SerialException:
            break   
      
#-------------------Threading-----------------------------  
try:
    #start_new_thread(BaseThread)
    #start_new_thread(Rover1_Thread)
    #start_new_thread(Rover2_Thread)
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
    
    #Vibration Data
    Header = "Rover_1_Filtered;Rover_1_norm_vibration;Rover_1_vibration;R1_Heading;R1_Rover_date;R1_Rover_time;R1_Rover_lon;R1_Rover_lat;Rover_2_Filtered;Rover_2_norm_vibration;Rover_2_vibration;R2_Heading;R2_Rover_date;R2_Rover_time;R2_Rover_lon;R2_Rover_lat;Base_UTC;Base_lon;Base_lat;Base_RW;Base_HW;Base_Quality;Base_NumSV;Base_HDOP;Base_alt" + '\n'
    
    #All Data
    #Header = "Rover_1_vibration;R1_Heading;R1_HeadValid;R1_AccHeading;R1_BaseLength;R1_Rover_date;R1_Rover_time;R1_Rover_sogk;R1_Rover_lon;R1_Rover_lat;R1_Rover_RW;R1_Rover_HW;Rover_2_vibration;R2_Heading;R2_HeadValid;R2_AccHeading;R2_BaseLength;R2_Rover_date;R2_Rover_time;R2_Rover_sogk;R2_Rover_lon;R2_Rover_lat;R2_Rover_RW;R2_Rover_HW;Base_UTC;Base_lon;Base_lat;Base_RW;Base_HW;Base_Quality;Base_NumSV;Base_HDOP;Base_alt" + '\n'
    
    # create a file object along with extension
    file = open(full_path, 'w')
    file.writelines(Header)
    BaT_exists = False
    Ro_1_T_exists = False
    Ro_2_T_exists = False

    R_1_msg_Exits = False
    R_2_msg_Exits = False
    Bmsg_Exists  = False
    PrevCommonTime = ""


#-------------------Live Plot-----------------------------   
    # Für Live-Plot-Daten
    plot_data_length = 100  # Anzahl der Datenpunkte im Plot
    time_series = deque(maxlen=plot_data_length)
    vib_rover1_series = deque(maxlen=plot_data_length)
    vib_rover2_series = deque(maxlen=plot_data_length)


    def update_plot(frame):
        plt.cla()
        plt.title("Live Vibration Plot")
        plt.xlabel("Time (s)")
        plt.ylabel("Vibration Δheading/s")
        plt.grid(True)

        if len(time_series) > 0:
            plt.plot(time_series,vib_rover1_series, label="Rover 1", color="blue")
            plt.plot(time_series,vib_rover2_series, label="Rover 2", color="red")
            plt.legend(loc="upper right")

    def start_live_plot():
        fig = plt.figure()
        ani = FuncAnimation(fig, update_plot, interval=500)  # update every 500ms
        plt.show() 

    # Startet den Plot-Thread
    plot_thread = threading.Thread(target=start_live_plot)
    plot_thread.daemon = True
    plot_thread.start() 

 #-------------------Loop Data mining-----------------------------
    while True:
        #RT = R_Time.get()
        #BT = B_Time.get()
        #print ("Hallo")
        time.sleep(0.1) #<-------------Time mining Data
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
            print("Rover1: ", R_1_msg)

        if R_2_Message.qsize()> 0:
            R_2_MsgQ= [R_2_Message.get() for _ in range(R_2_Message.qsize())]
            R_2_msg = R_2_MsgQ[-1]
            R_2_msg_exists = True 
            print("Rover2: ", R_2_msg) 

        if B_Message.qsize()> 0:
            BMsgQ= [B_Message.get() for _ in range(B_Message.qsize())]
            Bmsg = BMsgQ[-1]
            Bmsg_exists = True
        
        
        #print (R_Message.get())
        if (Ro_1_T_exists and Ro_2_T_exists and BaT_exists):
            
            #print (str(BaT) + '|' + str(RoT))
        #if (BT==RT):
            if BaT==Ro_1_T==Ro_2_T and BaT != PrevCommonTime:
                
                
                # Für den Plot die aktuelle Zeit und Vibrationen speichern welche geplottet werden
                timestamp = time.time()
                time_series.append(timestamp)
                #vib_rover1_series.append(Rover_1_normalized_vibration)
                #vib_rover2_series.append(Rover_2_normalized_vibration)

                vib_rover1_series.append(Rover_1_filtered_value)
                vib_rover2_series.append(Rover_2_filtered_value)
                
                print("Equal and new" + str(BaT))
                #print (R_1_msg + R_2_msg + Bmsg)
                R_1_msg = R_1_msg.replace('.', ',')
                R_2_msg = R_2_msg.replace('.', ',')
                Bmsg = Bmsg.replace('.', ',')
                file.writelines(R_1_msg + ";" + R_2_msg + ";" + Bmsg + '\n')
                #file.writelines(R_1_msg + ";" + R_2_msg +'\n')
                PrevCommonTime = BaT
            
        #print (R_1_Message.get())
        #print (R_2_Message.get())
        #print ("Test " + R_Message.get().time)
        #time.sleep(.2) 

#-------------------End Programm--------------------------
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
