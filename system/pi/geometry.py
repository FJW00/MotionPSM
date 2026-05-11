# -*- coding: utf-8 -*-
"""
Geometrie-Helper für die Mittelachsen-Auswertung mit 3 Rovern.

Setup (Pflanzenschutzspritze):
- Base sitzt mittig auf dem Traktor (fest, definiert Ursprung).
- Rover 1 links am Gestänge.
- Rover 2 rechts am Gestänge.
- Rover 3 vorne in Fahrtrichtung (definiert die Längsachse der Maschine).

Variante A — Mittelachsen-Projektion:
    Rover 1 und Rover 2 werden senkrecht auf den Vektor Base->R3 projiziert.
    Ergebnis: senkrechte Querauslenkung jedes Rovers in Metern (signed).
    Vorteil: Stabile geometrische Referenz, funktioniert auch im Stillstand.

Variante B — Direkte Differenzvektoren:
    Vektoren R3->R1 und R3->R2 aus den relPosNED-Differenzen.
    Ergebnis: Heading und Distanz jedes Auslegers von Rover 3 aus gesehen.
    Vorteil: direkter geometrischer Bezug ohne Achsen-Projektion.

Alle Berechnungen in der horizontalen Ebene (NED-Frame, D ignoriert).
"""
from math import sqrt, atan2, degrees


# Mindest-Achsenlänge in Metern. Darunter wird der Base->R3-Vektor
# als zu kurz/unzuverlässig betrachtet (RTK-Rauschen vs. Signal).
MIN_AXIS_LENGTH_M = 0.05


def vehicle_axis(relNED_r3):
    """
    Berechne die Längsachse der Maschine aus dem Base->R3-Vektor.

    Parameters
    ----------
    relNED_r3 : tuple (N, E, D)
        relPosNED von Rover 3 gegen Base, in Metern.

    Returns
    -------
    a_len : float oder None
        Horizontale Distanz Base zu R3 in Metern. None wenn unzuverlässig.
    aN_hat, aE_hat : float oder None
        Einheitsvektor der Längsachse (NED, horizontale Komponente).
    heading_deg : float oder None
        Richtung der Achse (0 = Nord, 90 = Ost, -180..180).
    """
    aN, aE, _ = relNED_r3
    a_len = sqrt(aN * aN + aE * aE)
    if a_len < MIN_AXIS_LENGTH_M:
        return None, None, None, None
    aN_hat = aN / a_len
    aE_hat = aE / a_len
    heading_deg = degrees(atan2(aE, aN))
    return a_len, aN_hat, aE_hat, heading_deg


def lateral_offset_a(relNED_rover, aN_hat, aE_hat):
    """
    Variante A: Senkrechte Querauslenkung eines Rovers von der Längsachse.

    Konvention:
      Längsachse zeigt von Base in Fahrtrichtung (Base->R3).
      Senkrechter Einheitsvektor links zur Fahrtrichtung: (-aE_hat, aN_hat).

      lateral_m > 0 -> Rover ist links der Mittelachse (in Fahrtrichtung gesehen).
      lateral_m < 0 -> Rover ist rechts der Mittelachse.

    Parameters
    ----------
    relNED_rover : tuple (N, E, D)
        relPosNED des Rovers in Metern.
    aN_hat, aE_hat : float
        Einheitsvektor der Längsachse (von vehicle_axis()).

    Returns
    -------
    lateral_m : float oder None
        Querauslenkung in Metern (signed). None wenn Achse unzuverlässig.
    longitudinal_m : float oder None
        Komponente entlang der Achse (Validierung; bei R1/R2 ≈ 0
        wenn die Rover direkt seitlich der Base liegen).
    """
    if aN_hat is None:
        return None, None
    rN, rE, _ = relNED_rover
    longitudinal_m = rN * aN_hat + rE * aE_hat
    # Links-positiv: 2D-Cross-Product (Achse × Rover)_D negiert.
    # (axN * rE - axE * rN) ist rechts-positiv (Right-Hand-Rule in NED),
    # also wird hier das Vorzeichen umgedreht.
    lateral_m = rN * aE_hat - rE * aN_hat
    return lateral_m, longitudinal_m


def diff_vector_b(relNED_target, relNED_reference):
    """
    Variante B: Direkter Differenzvektor von Reference zu Target.

    Beispiel: diff_vector_b(R1_relNED, R3_relNED) liefert den Vektor R3 -> R1.

    Parameters
    ----------
    relNED_target : tuple (N, E, D)
    relNED_reference : tuple (N, E, D)

    Returns
    -------
    dN, dE : float
        Differenz in Nord/Ost (m).
    distance_m : float
        Horizontale euklidische Länge (m).
    heading_deg : float
        Richtung von Reference zu Target (0 = Nord, 90 = Ost, -180..180).
    """
    rN, rE, _ = relNED_target
    aN, aE, _ = relNED_reference
    dN = rN - aN
    dE = rE - aE
    distance_m = sqrt(dN * dN + dE * dE)
    heading_deg = degrees(atan2(dE, dN))
    return dN, dE, distance_m, heading_deg
