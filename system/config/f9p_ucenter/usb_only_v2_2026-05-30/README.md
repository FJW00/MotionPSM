# USB-only Configs für ZED-F9P (Stand 2026-05-30)

## Zweck
Diese Configs lösen das 5-Hz-Problem auf den Rovern: ZED-F9P-Module wurden intern
gedrosselt weil NMEA-Messages auf ALLEN 5 Ports (I2C + UART1 + UART2 + USB + SPI)
gleichzeitig ausgegeben wurden. Bei 10 Hz Mess-Rate × 18 Output-Operationen
landeten effektiv nur 5 Hz NAV-RELPOSNED auf USB.

## Was geändert wurde
Für jedes Modul gegenüber Original:
- USB-Outputs für NMEA-GGA, NMEA-RMC, NMEA-VTG, NAV-RELPOSNED, NAV-PVT: **bleiben aktiv (= 1)**
- I2C, UART1, UART2, SPI Outputs für UBX/NMEA: **auf 0 gesetzt**
- **RTCM-Settings unverändert** (Base UART2-RTCM-Output → Rover Moving-Base-RTK weiterhin funktional)
- CFG-RATE-MEAS = 100 ms (10 Hz) und CFG-RATE-NAV = 1 unverändert

## Wie die korrekten Item-IDs ermittelt wurden
Wichtig: die Item-IDs für jede UBX/NMEA-Message + Port wurden direkt aus
`pyubx2.UBX_CONFIG_DATABASE` extrahiert — autoritative u-blox Doku, identisch
mit der Library die auch der MotionPSM-Logger nutzt.

Ein erster Versuch (Ordner `usb_only_2026-05-25` — wurde verworfen, nicht im Repo)
hatte geschätzte Item-IDs für NAV-RELPOSNED genutzt (offset 0x8C statt 0x8D),
dadurch landete USB auf 0 statt UART2 — Pi konnte kein NAV-RELPOSNED lesen.
Daraus die Lektion: bei UBX-Config-Modifikationen immer pyubx2-DB als Quelle.

## Anwendung in u-center
1. Modul per USB an Laptop
2. Tools → Receiver Configuration → Browse → `..._USBonly_v2.txt`
3. Transfer file → GNSS
4. View → Configuration View → CFG → Save current configuration (BBR + Flash) → Send
5. Disconnect, nächstes Modul

## Verifikation
Auf dem Pi mit pyubx2-Hz-Test:
```bash
sudo systemctl stop motionpsm 2>/dev/null
for port in usb-B_B-if00 usb-R_1-if00 usb-R_2-if00 usb-R_3-if00; do
  echo -n "$port: "
  timeout 5 python3 -c "
import serial,pyubx2,time
s=serial.Serial('/dev/serial/by-id/$port')
u=pyubx2.UBXReader(s,validate=0)
n=0; e=time.time()+5
while time.time()<e:
    try:
        _,p=u.read()
        if p and p.identity in ('NAV-RELPOSNED','NAV-PVT'): n+=1
    except: pass
print(f'{n/5:.1f} Hz')"
done
```
Erwartung: alle Module 10.0 Hz auf NAV-RELPOSNED (Rover) bzw. NAV-PVT (Base).

## Hinweise
- Base-Config liegt vor, ist aber bei Stand 2026-05-30 **noch nicht** geflasht
  (Base war nie der 5-Hz-Engpass, sie lief schon bei vollen 10 Hz).
  Sauberkeitshalber kann sie post-DLG mit dieser Config nachgeflasht werden.
- NAV-PVT USB ist bei den Rovern bewusst aus (war auch in Original-Configs schon so);
  der Logger nutzt NAV-RELPOSNED + die 3 NMEA-Messages.
