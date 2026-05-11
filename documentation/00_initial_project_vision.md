# BA_Weigand


# Erfassung von Schwingungen im Spritzengestänge durch Low-Cost Messsystem

## Projektübersicht
Dieses Projekt zielt darauf ab, ein kostengünstiges und modulares System zu entwickeln, das die Schwingungen von Spritzgestängen in der Landwirtschaft erfasst. Die erfassten Daten sollen gespeichert und zur Optimierung von Precision-Farming-Anwendungen genutzt werden.

## Zielsetzung
- **Modularität**: Flexible Anpassung an verschiedene Spritzgestänge und Sensoren.
- **Datenerfassung und -speicherung**: Aufzeichnung der Messdaten auf einer SD-Karte.
- **Analyse der Schwingungen**: Berechnung der Schwingungsdaten relativ zur Gesamtbreite des Gestänges.

## Systemansätze
Es werden drei mögliche Ansätze untersucht, wobei die ersten beiden priorisiert werden:

1. **GNSS-Modul (F9P)**:
   - Verwendung von 3-4 GNSS-Empfängern:
     - Zwei Empfänger in der Mitte des Gestänges zur Bestimmung von Heading und Offset.
     - Jeweils ein Empfänger an den Enden zur Detektion der Schwingungen.
   - **Offene Fragen**: Konfiguration und serielle Kommunikation.

2. **Beschleunigungssensoren**:
   - Platzierung von Sensoren an den Enden und in der Mitte des Gestänges.
   - Messung der Beschleunigungen zur Analyse der Schwingungen.
   - **Offene Fragen**: Nutzung von Interrupts oder Dataloggern.

3. **Kamerabasierte Lösung (OpenCV)**:
   - Kamera in der Mitte des Gestänges, die zwei markierte Bälle an den Enden verfolgt.
   - Analyse der Ballbewegung zur Erkennung von Schwingungen.
   - **Herausforderung**: Hoher Umsetzungsaufwand, daher aktuell nicht priorisiert.

## Anforderungen
- **Modularität**: Das System muss einfach erweiterbar sein.
- **Datenaufzeichnung**: Speicherung aller relevanten Daten auf einer SD-Karte.
- **Prozentuale Analyse**: Berechnung der Schwingungen relativ zur Breite des Gestänges.

## Vorgehensweise
1. **Entwicklung der Testsysteme**:
   - Umsetzung der Ansätze mit GNSS-Modulen und Beschleunigungssensoren.
2. **Validierung und Tests**:
   - Durchführung von Tests an der Landwirtschaftlichen Lehranstalt (LLA) mit Spritzgestängen verschiedener Hersteller.
   - Kalibrierung der Sensoren durch Vergleich mit Bodenmessungen (z. B. Meterstab oder Skala).

## Offene Fragen
Während des Projekts sind folgende Punkte zu klären:
- Wie können Korrekturdaten effizient verteilt werden?
- Ist eine Berechnung über den Dopplereffekt sinnvoll?
- Welche bestehenden Systeme können als Referenz dienen?
- Welcher Ansatz ist am zuverlässigsten, kostengünstigsten und genauesten?

## Motivation
Das Projekt unterstützt die Weiterentwicklung des Precision Farming, indem es präzisere Daten für die Optimierung von Spritzgestängen liefert. Dies trägt zur Effizienzsteigerung und Ressourcenschonung in der Landwirtschaft bei.
