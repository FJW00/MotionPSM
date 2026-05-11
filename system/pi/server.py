from flask import Flask, render_template_string, jsonify, redirect, url_for, send_file
import time
import gps_measurement as gps
import threading
import os

app = Flask(__name__)


class MeasurementState:
    def __init__(self):
        self.running = False
        self.start_time = None


state = MeasurementState()

HTML_PAGE = '''
<!doctype html>
<html lang="de">
  <head>
    <meta charset="utf-8">
    <title>MotionPSM – Gestängebewegungs-Messsystem (FJW Systems)</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
      :root {
        --col-r1: #1976d2;
        --col-r2: #d32f2f;
        --col-r3: #2e7d32;
        --col-base: #555;
        --col-bg: #fafafa;
        --col-card: #ffffff;
        --col-border: #ddd;
      }
      * { box-sizing: border-box; }
      body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
        margin: 0;
        padding: 20px;
        background: var(--col-bg);
        color: #222;
      }
      h1 { text-align: center; margin: 0 0 4px; font-size: 22px; }
      .subtitle { text-align: center; color: #666; margin: 0 0 20px; font-size: 13px; }
      .controls { text-align: center; margin: 16px 0; }
      .controls button {
        padding: 10px 22px;
        font-size: 14px;
        border-radius: 8px;
        border: 1px solid var(--col-border);
        background: var(--col-card);
        cursor: pointer;
        margin: 0 4px;
      }
      .controls button:hover { background: #f0f0f0; }
      .runtime { text-align: center; color: green; margin: 8px 0; }
      .runtime.stopped { color: #d32f2f; }

      /* --- Hero: Gestänge-Visualisierung --- */
      .boom-hero {
        background: var(--col-card);
        border: 1px solid var(--col-border);
        border-radius: 12px;
        padding: 20px;
        margin: 16px auto;
        max-width: 1100px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
      }
      .boom-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
        flex-wrap: wrap;
        gap: 12px;
      }
      .boom-header h2 { margin: 0; font-size: 18px; }
      .boom-config label {
        font-size: 13px;
        margin-right: 4px;
      }
      .boom-config input {
        width: 90px;
        padding: 6px 8px;
        font-size: 14px;
        border: 1px solid var(--col-border);
        border-radius: 6px;
      }
      .boom-svg-wrap {
        width: 100%;
        background: linear-gradient(to bottom, #f5f5f5, #ffffff);
        border-radius: 8px;
        padding: 16px 8px;
        position: relative;
      }
      .boom-values {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        gap: 12px;
        margin-top: 16px;
      }
      .value-box {
        background: var(--col-card);
        border: 1px solid var(--col-border);
        border-radius: 8px;
        padding: 14px;
        text-align: center;
      }
      .value-box .label { font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }
      .value-box .value { font-size: 34px; font-weight: 600; margin: 6px 0 0; }
      .value-box .unit { font-size: 14px; color: #888; }
      .value-box.r1 .value { color: #1976d2; }
      .value-box.r2 .value { color: #d32f2f; }
      .value-box.delta .value { color: #444; }

      /* --- Sekundärer Bereich: Qualität + Achse --- */
      .secondary-grid {
        display: grid;
        grid-template-columns: 2fr 1fr;
        gap: 16px;
        max-width: 1100px;
        margin: 16px auto;
      }
      .quality-grid {
        background: var(--col-card);
        border: 1px solid var(--col-border);
        border-radius: 12px;
        padding: 16px;
      }
      .quality-grid h3 { margin: 0 0 12px; font-size: 14px; color: #666; }
      .quality-row {
        display: grid;
        grid-template-columns: 80px 1fr 1fr 1fr;
        gap: 8px;
        align-items: center;
        padding: 6px 0;
        font-size: 13px;
      }
      .quality-row + .quality-row { border-top: 1px dashed #eee; }
      .rover-tag {
        font-weight: 600;
      }
      .rover-tag.r1 { color: #1976d2; }
      .rover-tag.r2 { color: #d32f2f; }
      .rover-tag.r3 { color: #2e7d32; }
      .rover-tag.base { color: var(--col-base); }
      .quality {
        display: inline-block;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 5px;
        color: white;
        font-size: 12px;
      }
      .q-0 { background-color: #9e9e9e; }
      .q-1, .q-2 { background-color: #1976d2; }
      .q-4 { background-color: #2e7d32; }
      .q-5 { background-color: #f9a825; color: #333; }
      .q-6 { background-color: #d32f2f; }

      .axis-info {
        background: var(--col-card);
        border: 1px solid var(--col-border);
        border-radius: 12px;
        padding: 16px;
      }
      .axis-info h3 { margin: 0 0 12px; font-size: 14px; color: #666; }
      .axis-info .row { display: flex; justify-content: space-between; padding: 4px 0; font-size: 13px; }
      .axis-info .row .v { font-weight: 600; }

      /* --- Charts --- */
      .charts-row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
        max-width: 1100px;
        margin: 16px auto;
      }
      .chart-card {
        background: var(--col-card);
        border: 1px solid var(--col-border);
        border-radius: 12px;
        padding: 16px;
      }
      .chart-card h3 { margin: 0 0 8px; font-size: 14px; color: #666; }
      canvas { max-width: 100%; }

      @media (max-width: 800px) {
        .boom-values { grid-template-columns: 1fr; }
        .secondary-grid { grid-template-columns: 1fr; }
        .charts-row { grid-template-columns: 1fr; }
      }
    </style>
  </head>
  <body>
    <h1>MotionPSM – Gestängebewegungs-Messsystem</h1>
    <div class="subtitle">FJW Systems · Live-Anzeige</div>

    {% if running %}
      <div class="runtime">Messung läuft seit <span id="runtime">0</span> s</div>
      <div class="controls">
        <button onclick="exportAndRedirect()">CSV exportieren</button>
        <a href="{{ url_for('stop') }}"><button>Messung stoppen</button></a>
      </div>

      <!-- ============ HERO: Gestänge ============ -->
      <div class="boom-hero">
        <div class="boom-header">
          <h2>Aktuelle Gestänge-Auslenkung</h2>
          <div class="boom-config">
            <label for="boom_width_cm">Gestängebreite (cm):</label>
            <input type="number" id="boom_width_cm" value="1500" step="100" min="500" max="5000">
          </div>
        </div>

        <div class="boom-svg-wrap">
          <svg id="boom_svg" viewBox="-110 -40 220 80" preserveAspectRatio="xMidYMid meet" style="width:100%;height:auto;">
            <!-- Mittelachse -->
            <line x1="0" y1="-35" x2="0" y2="35" stroke="#bbb" stroke-dasharray="3,3" stroke-width="0.5"/>
            <text x="0" y="-37" text-anchor="middle" font-size="4" fill="#888">Mittelachse</text>
            <!-- Soll-Gestänge -->
            <line id="boom_sollline" x1="-90" y1="0" x2="90" y2="0" stroke="#ccc" stroke-width="1.5" stroke-dasharray="2,2"/>
            <!-- Ist-Gestänge: R1 -> Mittelpunkt(0) -> R2 -->
            <line id="boom_istline_l" x1="-90" y1="0" x2="0" y2="0" stroke="#1976d2" stroke-width="2"/>
            <line id="boom_istline_r" x1="0" y1="0" x2="90" y2="0" stroke="#d32f2f" stroke-width="2"/>
            <!-- Rover-Marker -->
            <circle id="boom_r1" cx="-90" cy="0" r="3.5" fill="#1976d2"/>
            <circle id="boom_r2" cx="90" cy="0" r="3.5" fill="#d32f2f"/>
            <text id="boom_r1_label" x="-90" y="-8" text-anchor="middle" font-size="5" fill="#1976d2" font-weight="600">R1</text>
            <text id="boom_r2_label" x="90" y="-8" text-anchor="middle" font-size="5" fill="#d32f2f" font-weight="600">R2</text>
            <!-- R3 Marker oben (Fahrtrichtung) -->
            <circle id="boom_r3" cx="0" cy="-25" r="3.5" fill="#2e7d32"/>
            <text x="0" y="-28" text-anchor="middle" font-size="5" fill="#2e7d32" font-weight="600">R3</text>
            <text x="0" y="-30.5" text-anchor="middle" font-size="3" fill="#888">(Fahrtrichtung)</text>
          </svg>
        </div>

        <div class="boom-values">
          <div class="value-box r1">
            <div class="label">R1 (links)</div>
            <div class="value"><span id="r1_lat">+0.0</span> <span class="unit">cm</span></div>
          </div>
          <div class="value-box delta">
            <div class="label">Gesamt-Differenz R1 − R2</div>
            <div class="value"><span id="boom_total">0.0</span> <span class="unit">cm</span></div>
          </div>
          <div class="value-box r2">
            <div class="label">R2 (rechts)</div>
            <div class="value"><span id="r2_lat">-0.0</span> <span class="unit">cm</span></div>
          </div>
        </div>
      </div>

      <!-- ============ Sekundär: Qualität + Achse ============ -->
      <div class="secondary-grid">
        <div class="quality-grid">
          <h3>Signalqualität pro Modul</h3>
          <div class="quality-row" style="font-weight:600;color:#888;font-size:11px;border-top:none;">
            <div>Modul</div>
            <div>Fix</div>
            <div>Ang.Velo</div>
            <div>Schwingung</div>
          </div>
          <div class="quality-row">
            <div class="rover-tag r1">Rover 1</div>
            <div><span id="r1_q" class="quality q-0">?</span></div>
            <div><span id="r1_av">0.00</span> °/s</div>
            <div><span id="r1_vib">0.00</span> °</div>
          </div>
          <div class="quality-row">
            <div class="rover-tag r2">Rover 2</div>
            <div><span id="r2_q" class="quality q-0">?</span></div>
            <div><span id="r2_av">0.00</span> °/s</div>
            <div><span id="r2_vib">0.00</span> °</div>
          </div>
          <div class="quality-row">
            <div class="rover-tag r3">Rover 3</div>
            <div><span id="r3_q" class="quality q-0">?</span></div>
            <div><span id="r3_av">0.00</span> °/s</div>
            <div><span id="r3_vib">0.00</span> °</div>
          </div>
        </div>
        <div class="axis-info">
          <h3>Maschinen-Längsachse (Base → R3)</h3>
          <div class="row"><span>Achsenlänge:</span><span class="v"><span id="axis_length">0.00</span> m</span></div>
          <div class="row"><span>Heading:</span><span class="v"><span id="axis_heading">0.0</span>°</span></div>
          <div class="row"><span>Fahrgeschwindigkeit:</span><span class="v"><span id="base_speed">0.0</span> km/h</span></div>
        </div>
      </div>

      <!-- ============ Charts ============ -->
      <div class="charts-row">
        <div class="chart-card">
          <h3>Verlauf: Auslenkung R1 / R2 (cm)</h3>
          <canvas id="lateralChart" width="500" height="280"></canvas>
        </div>
        <div class="chart-card">
          <h3>Heading-Schwingung (°, Moving-Avg)</h3>
          <canvas id="vibrationChart" width="500" height="280"></canvas>
        </div>
      </div>

    {% else %}
      <div class="runtime stopped">Messung gestoppt.</div>
      <div class="controls">
        <a href="{{ url_for('start') }}"><button>Messung starten</button></a>
      </div>
    {% endif %}

    <script>
      {% if running %}
      // ---------- Charts ----------
      const lateralCtx = document.getElementById('lateralChart').getContext('2d');
      const lateralChart = new Chart(lateralCtx, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            { label: 'R1 (links)', borderColor: '#1976d2', data: [], fill: false, tension: 0.2 },
            { label: 'R2 (rechts)', borderColor: '#d32f2f', data: [], fill: false, tension: 0.2 },
            { label: 'R1 − R2', borderColor: '#555', data: [], fill: false, borderDash: [4,4], tension: 0.2 }
          ]
        },
        options: {
          animation: false,
          scales: {
            x: { title: { display: true, text: 'Zeit (s)' } },
            y: { title: { display: true, text: 'cm' } }
          }
        }
      });

      const vibCtx = document.getElementById('vibrationChart').getContext('2d');
      const vibChart = new Chart(vibCtx, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            { label: 'R1', borderColor: '#1976d2', data: [], fill: false },
            { label: 'R2', borderColor: '#d32f2f', data: [], fill: false },
            { label: 'R3', borderColor: '#2e7d32', data: [], fill: false }
          ]
        },
        options: {
          animation: false,
          scales: {
            x: { title: { display: true, text: 'Zeit (s)' } },
            y: { title: { display: true, text: '°' }, min: -2, max: 2 }
          }
        }
      });

      function interpretQuality(value) {
        switch (value) {
          case 1: case 2: return { label: '3D Fix',     class: 'q-1' };
          case 4:         return { label: 'RTK Fix',    class: 'q-4' };
          case 5:         return { label: 'RTK Float',  class: 'q-5' };
          case 6:         return { label: 'Dead Reck.', class: 'q-6' };
          default:        return { label: 'kein Fix',   class: 'q-0' };
        }
      }
      function setQuality(id, value) {
        const q = interpretQuality(value);
        const el = document.getElementById(id);
        el.innerText = q.label;
        el.className = 'quality ' + q.class;
      }
      function fmtSigned(v, decimals=1) {
        if (v === null || v === undefined) return '–';
        const s = v >= 0 ? '+' : '';
        return s + v.toFixed(decimals);
      }

      // ---------- Boom-SVG-Update ----------
      function updateBoom(r1_cm, r2_cm) {
        const boomWidthCm = parseFloat(document.getElementById('boom_width_cm').value) || 1500;
        // SVG-Halbbreite: ±90 entspricht der halben Gestängebreite
        const halfWidth = boomWidthCm / 2;  // in cm
        const scale = 90 / halfWidth;       // SVG-units pro cm
        // R1 ist links = positiver Wert. Im SVG: links = negatives x.
        // Position der Rover: x = -halfWidth*scale + abweichung*scale_im_svg
        const r1_svg_x = -90 + (r1_cm) * scale;
        const r2_svg_x = +90 + (r2_cm) * scale;
        document.getElementById('boom_r1').setAttribute('cx', r1_svg_x);
        document.getElementById('boom_r2').setAttribute('cx', r2_svg_x);
        document.getElementById('boom_r1_label').setAttribute('x', r1_svg_x);
        document.getElementById('boom_r2_label').setAttribute('x', r2_svg_x);
        document.getElementById('boom_istline_l').setAttribute('x1', r1_svg_x);
        document.getElementById('boom_istline_r').setAttribute('x2', r2_svg_x);
      }

      let startTime = Date.now();
      const CHART_MAX_POINTS = 80;

      function fetchData() {
        fetch('/data').then(r => r.json()).then(d => {
          const t = ((Date.now() - startTime) / 1000).toFixed(1);

          // Werte-Boxen
          document.getElementById('r1_lat').innerText   = fmtSigned(d.r1_lateral_cm);
          document.getElementById('r2_lat').innerText   = fmtSigned(d.r2_lateral_cm);
          document.getElementById('boom_total').innerText = fmtSigned(d.gestaenge_total_cm);
          document.getElementById('axis_length').innerText  = (d.axis_length_m || 0).toFixed(2);
          document.getElementById('axis_heading').innerText = (d.axis_heading_deg || 0).toFixed(1);
          document.getElementById('base_speed').innerText   = (d.base_speed || 0).toFixed(1);
          document.getElementById('runtime').innerText      = d.runtime;

          // Pro-Rover Stats
          document.getElementById('r1_av').innerText = (d.r1_angular_velocity || 0).toFixed(2);
          document.getElementById('r2_av').innerText = (d.r2_angular_velocity || 0).toFixed(2);
          document.getElementById('r3_av').innerText = (d.r3_angular_velocity || 0).toFixed(2);
          document.getElementById('r1_vib').innerText = (d.r1_vibration || 0).toFixed(2);
          document.getElementById('r2_vib').innerText = (d.r2_vibration || 0).toFixed(2);
          document.getElementById('r3_vib').innerText = (d.r3_vibration || 0).toFixed(2);
          setQuality('r1_q', d.r1_quality);
          setQuality('r2_q', d.r2_quality);
          setQuality('r3_q', d.r3_quality);

          // Boom-Visualisierung
          updateBoom(d.r1_lateral_cm, d.r2_lateral_cm);

          // Charts
          if (lateralChart.data.labels.length > CHART_MAX_POINTS) {
            lateralChart.data.labels.shift();
            lateralChart.data.datasets.forEach(ds => ds.data.shift());
          }
          lateralChart.data.labels.push(t);
          lateralChart.data.datasets[0].data.push(d.r1_lateral_cm);
          lateralChart.data.datasets[1].data.push(d.r2_lateral_cm);
          lateralChart.data.datasets[2].data.push(d.gestaenge_total_cm);
          lateralChart.update();

          if (vibChart.data.labels.length > CHART_MAX_POINTS) {
            vibChart.data.labels.shift();
            vibChart.data.datasets.forEach(ds => ds.data.shift());
          }
          vibChart.data.labels.push(t);
          vibChart.data.datasets[0].data.push(d.r1_vibration);
          vibChart.data.datasets[1].data.push(d.r2_vibration);
          vibChart.data.datasets[2].data.push(d.r3_vibration);
          vibChart.update();
        }).catch(err => console.warn('fetch fehler', err));
      }
      setInterval(fetchData, 200);
      {% endif %}

      function exportAndRedirect() {
        const a = document.createElement('a');
        a.href = "{{ url_for('export_csv') }}";
        a.download = '';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => { window.location.href = "{{ url_for('index') }}"; }, 100);
      }
    </script>
  </body>
</html>
'''


def calculate_runtime():
    return int(time.time() - state.start_time) if state.start_time else 0


@app.route('/')
def index():
    return render_template_string(HTML_PAGE, running=state.running, runtime=calculate_runtime())


@app.route('/start')
def start():
    if not state.running:
        print(">>> Messung wird gestartet...")
        thread = threading.Thread(target=gps.start_measurement, daemon=True)
        thread.start()
        state.start_time = time.time()
        state.running = True
    return redirect(url_for('index'))


@app.route('/stop')
def stop():
    if state.running:
        gps.stop_measurement()
        state.running = False
        state.start_time = None
    return redirect(url_for('index'))


@app.route('/data')
def data():
    runtime = calculate_runtime()
    return jsonify({
        'runtime': runtime,
        # Mittelachsen-Auswertung (Variante A)
        'r1_lateral_cm':       round(float(gps.R1_lateral_offset_cm), 2),
        'r2_lateral_cm':       round(float(gps.R2_lateral_offset_cm), 2),
        'gestaenge_total_cm':  round(float(gps.R1_lateral_offset_cm - gps.R2_lateral_offset_cm), 2),
        # Längsachse Base->R3
        'axis_length_m':       round(float(gps.vehicle_axis_length_m), 3),
        'axis_heading_deg':    round(float(gps.vehicle_heading_via_r3), 2),
        # Pro Rover
        'r1_quality':          gps.quality_rover1[0] if gps.quality_rover1 else 0,
        'r2_quality':          gps.quality_rover2[0] if gps.quality_rover2 else 0,
        'r3_quality':          gps.quality_rover3[0] if gps.quality_rover3 else 0,
        'r1_angular_velocity': float(gps.R1_angular_velocity or 0),
        'r2_angular_velocity': float(gps.R2_angular_velocity or 0),
        'r3_angular_velocity': float(gps.R3_angular_velocity or 0),
        'r1_vibration':        float(gps.current_vibration_rover1 or 0),
        'r2_vibration':        float(gps.current_vibration_rover2 or 0),
        'r3_vibration':        float(gps.current_vibration_rover3 or 0),
        # Geschwindigkeit Base (km/h)
        'base_speed':          float(gps.Base_Speed or 0),
    })


@app.route('/export')
def export_csv():
    if state.running:
        gps.stop_measurement()
        state.running = False
        state.start_time = None

    path = gps.export_to_csv()
    if path is None:
        return "Keine Daten vorhanden", 404

    filename = os.path.basename(path)
    return send_file(path, as_attachment=True, download_name=filename, mimetype="text/csv")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
