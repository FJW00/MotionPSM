from flask import Flask, render_template_string, jsonify, redirect, url_for, send_file
import time
import gps_measurement as gps
import threading
import os

# static_folder='static' ist Default — Flask serviert system/pi/static/ unter /static/
app = Flask(__name__)


class MeasurementState:
    def __init__(self):
        self.running = False
        self.start_time = None


state = MeasurementState()

HTML_PAGE = '''
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>MotionPSM – FJW Systems</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
      :root {
        --col-r1: #1976d2;
        --col-r2: #d32f2f;
        --col-r3: #2e7d32;
        --col-bg: #fafafa;
        --col-card: #ffffff;
        --col-border: #ddd;
        --col-brand: #4d4d4d;
      }
      * { box-sizing: border-box; }
      body {
        font-family: 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        margin: 0;
        padding: 20px;
        background: var(--col-bg);
        color: #222;
      }

      /* ---------- Brand Header (Logo + FJW Systems links, Real Time Monitor rechts) ---------- */
      .brand-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 14px;
        max-width: 1100px;
        margin: 0 auto 20px;
        padding: 4px 0;
      }
      .brand-left {
        display: flex;
        align-items: center;
        gap: 14px;
      }
      .brand-logo {
        height: 56px;
        width: auto;
      }
      .brand-text { display: flex; flex-direction: column; line-height: 1.1; }
      .brand-name { font-size: 28px; font-weight: 700; color: var(--col-brand); letter-spacing: 0.2px; }
      .brand-tagline { font-size: 12px; color: #888; font-weight: 400; margin-top: 3px; letter-spacing: 0.4px; text-transform: uppercase; }
      .brand-right {
        font-size: 28px;
        font-weight: 700;
        color: var(--col-brand);
        letter-spacing: 0.2px;
      }

      /* ---------- Settings-Bar (Boom Width, immer sichtbar) ---------- */
      .settings-bar {
        max-width: 1100px;
        margin: 0 auto 16px;
        padding: 12px 18px;
        background: var(--col-card);
        border: 1px solid var(--col-border);
        border-radius: 10px;
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
      }
      .settings-bar label { font-size: 13px; font-weight: 500; color: #444; }
      .settings-bar input {
        width: 100px;
        padding: 6px 8px;
        font-size: 14px;
        border: 1px solid var(--col-border);
        border-radius: 6px;
        font-family: inherit;
      }
      .settings-bar .hint {
        font-size: 12px;
        color: #999;
        margin-left: auto;
      }

      /* ---------- Controls ---------- */
      .controls { text-align: center; margin: 16px 0; }
      .controls button {
        padding: 11px 24px;
        font-size: 14px;
        font-family: inherit;
        font-weight: 500;
        border-radius: 8px;
        border: 1px solid var(--col-border);
        background: var(--col-card);
        cursor: pointer;
        margin: 0 4px;
      }
      .controls button:hover { background: #f0f0f0; }
      .runtime { text-align: center; color: green; margin: 8px 0; font-size: 14px; }
      .runtime.stopped { color: #d32f2f; }

      /* ---------- Hero: Boom Visualization ---------- */
      .boom-hero {
        background: var(--col-card);
        border: 1px solid var(--col-border);
        border-radius: 12px;
        padding: 24px;
        margin: 16px auto;
        max-width: 1100px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
      }
      .boom-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 18px;
        flex-wrap: wrap;
        gap: 12px;
      }
      .boom-header h2 { margin: 0; font-size: 22px; font-weight: 600; }
      .boom-config label { font-size: 13px; margin-right: 4px; font-weight: 500; }
      .boom-config input {
        width: 90px; padding: 6px 8px; font-size: 14px;
        border: 1px solid var(--col-border); border-radius: 6px;
        font-family: inherit;
      }
      .boom-svg-wrap {
        width: 100%;
        background: linear-gradient(to bottom, #f5f5f5, #ffffff);
        border-radius: 8px;
        padding: 16px 8px;
      }
      .boom-values {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        gap: 12px;
        margin-top: 18px;
      }
      .value-box {
        background: var(--col-card);
        border: 1px solid var(--col-border);
        border-radius: 8px;
        padding: 14px;
        text-align: center;
      }
      .value-box .label { font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 500; }
      .value-box .value { font-size: 36px; font-weight: 600; margin: 6px 0 0; }
      .value-box .unit { font-size: 14px; color: #888; font-weight: 400; }
      .value-box.r1 .value { color: var(--col-r1); }
      .value-box.r2 .value { color: var(--col-r2); }
      .value-box.delta .value { color: #444; }

      /* ---------- Secondary: Quality + Axis ---------- */
      .secondary-grid {
        display: grid;
        grid-template-columns: 2fr 1fr;
        gap: 16px;
        max-width: 1100px;
        margin: 16px auto;
      }
      .quality-grid, .axis-info {
        background: var(--col-card);
        border: 1px solid var(--col-border);
        border-radius: 12px;
        padding: 16px;
      }
      .quality-grid h3, .axis-info h3, .chart-card h3 {
        margin: 0 0 12px;
        font-size: 13px;
        color: #666;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      .quality-row {
        display: grid;
        grid-template-columns: 80px 1fr 1fr 1fr;
        gap: 8px;
        align-items: center;
        padding: 7px 0;
        font-size: 13px;
      }
      .quality-row + .quality-row { border-top: 1px dashed #eee; }
      .rover-tag { font-weight: 600; }
      .rover-tag.r1 { color: var(--col-r1); }
      .rover-tag.r2 { color: var(--col-r2); }
      .rover-tag.r3 { color: var(--col-r3); }
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

      .axis-info .row { display: flex; justify-content: space-between; padding: 4px 0; font-size: 13px; }
      .axis-info .row .v { font-weight: 600; }

      /* ---------- Single Chart ---------- */
      .chart-row { max-width: 1100px; margin: 16px auto; }
      .chart-card {
        background: var(--col-card);
        border: 1px solid var(--col-border);
        border-radius: 12px;
        padding: 18px;
      }
      canvas { max-width: 100%; }

      /* ---------- Mobile ---------- */
      @media (max-width: 800px) {
        .brand-header { flex-direction: column; align-items: flex-start; }
        .brand-logo { height: 44px; }
        .brand-name { font-size: 22px; }
        .brand-right { font-size: 22px; }
        .boom-header h2 { font-size: 18px; }
        .boom-values { grid-template-columns: 1fr; }
        .secondary-grid { grid-template-columns: 1fr; }
      }
    </style>
  </head>
  <body>

    <!-- Brand Header: Logo + FJW Systems links, Real Time Monitor rechts -->
    <div class="brand-header">
      <div class="brand-left">
        <img src="{{ url_for('static', filename='logo_fjw.png') }}" alt="FJW Logo" class="brand-logo">
        <div class="brand-text">
          <div class="brand-name">FJW Systems</div>
          <div class="brand-tagline">MotionPSM</div>
        </div>
      </div>
      <div class="brand-right">Real Time Monitor</div>
    </div>

    <!-- Settings-Bar (immer sichtbar, auch wenn Messung gestoppt) -->
    <div class="settings-bar">
      <label for="boom_width_cm">Boom Width:</label>
      <input type="number" id="boom_width_cm" step="100" min="500" max="5000">
      <span style="font-size:13px;color:#666;">cm</span>
      <span class="hint">used for live visualization · saved automatically</span>
    </div>

    {% if running %}
      <div class="runtime">Measurement running for <span id="runtime">0</span> s</div>
      <div class="controls">
        <button onclick="exportAndRedirect()">Export CSV</button>
        <a href="{{ url_for('stop') }}"><button>Stop Measurement</button></a>
      </div>

      <!-- Hero -->
      <div class="boom-hero">
        <div class="boom-header">
          <h2>Current Boom Deflection</h2>
        </div>

        <div class="boom-svg-wrap">
          <svg id="boom_svg" viewBox="-110 -40 220 80" preserveAspectRatio="xMidYMid meet" style="width:100%;height:auto;">
            <!-- Center axis -->
            <line x1="0" y1="-35" x2="0" y2="35" stroke="#bbb" stroke-dasharray="3,3" stroke-width="0.5"/>
            <text x="0" y="-37" text-anchor="middle" font-size="4" fill="#888">Center Axis</text>
            <!-- Target boom line -->
            <line x1="-90" y1="0" x2="90" y2="0" stroke="#ccc" stroke-width="1.5" stroke-dasharray="2,2"/>
            <!-- Actual boom: R1 -> mid -> R2 -->
            <line id="boom_istline_l" x1="-90" y1="0" x2="0" y2="0" stroke="#1976d2" stroke-width="2"/>
            <line id="boom_istline_r" x1="0" y1="0" x2="90" y2="0" stroke="#d32f2f" stroke-width="2"/>
            <!-- Rover markers (R1 left, R2 right) -->
            <circle id="boom_r1" cx="-90" cy="0" r="3.5" fill="#1976d2"/>
            <circle id="boom_r2" cx="90" cy="0" r="3.5" fill="#d32f2f"/>
            <text id="boom_r1_label" x="-90" y="-8" text-anchor="middle" font-size="5" fill="#1976d2" font-weight="600">R1</text>
            <text id="boom_r2_label" x="90" y="-8" text-anchor="middle" font-size="5" fill="#d32f2f" font-weight="600">R2</text>
            <!-- Direction of Travel label (oberhalb von R3, abgesetzt) -->
            <text x="0" y="-29" text-anchor="middle" font-size="3.2" fill="#888" font-style="italic">Direction of Travel</text>
            <!-- R3 (vorne, transparent, dicht am Gestänge) -->
            <circle id="boom_r3" cx="0" cy="-12" r="3" fill="#2e7d32" fill-opacity="0.45"/>
            <text x="0" y="-16" text-anchor="middle" font-size="4.5" fill="#2e7d32" font-weight="600" opacity="0.7">R3</text>
          </svg>
        </div>

        <div class="boom-values">
          <div class="value-box r1">
            <div class="label">R1 (left)</div>
            <div class="value"><span id="r1_lat">+0.0</span> <span class="unit">cm</span></div>
          </div>
          <div class="value-box delta">
            <div class="label">Total Difference R1 − R2</div>
            <div class="value"><span id="boom_total">0.0</span> <span class="unit">cm</span></div>
          </div>
          <div class="value-box r2">
            <div class="label">R2 (right)</div>
            <div class="value"><span id="r2_lat">-0.0</span> <span class="unit">cm</span></div>
          </div>
        </div>
      </div>

      <!-- Quality + Axis -->
      <div class="secondary-grid">
        <div class="quality-grid">
          <h3>Signal Quality per Module</h3>
          <div class="quality-row" style="font-weight:600;color:#888;font-size:11px;border-top:none;">
            <div>Module</div>
            <div>Fix</div>
            <div>Ang. Velocity</div>
            <div>Vibration</div>
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
          <h3>Vehicle Longitudinal Axis (Base → R3)</h3>
          <div class="row"><span>Axis Length:</span><span class="v"><span id="axis_length">0.00</span> m</span></div>
          <div class="row"><span>Heading:</span><span class="v"><span id="axis_heading">0.0</span>°</span></div>
          <div class="row"><span>Vehicle Speed:</span><span class="v"><span id="base_speed">0.0</span> km/h</span></div>
        </div>
      </div>

      <!-- Single chart: Deflection history -->
      <div class="chart-row">
        <div class="chart-card">
          <h3>Deflection History — R1 / R2 (cm)</h3>
          <canvas id="lateralChart" width="500" height="280"></canvas>
        </div>
      </div>

    {% else %}
      <div class="runtime stopped">Measurement stopped.</div>
      <div class="controls">
        <a href="{{ url_for('start') }}"><button>Start Measurement</button></a>
      </div>
    {% endif %}

    <script>
      // ----- Boom Width Persistenz (immer aktiv, auch wenn Messung gestoppt) -----
      const BOOM_WIDTH_DEFAULT = 1500;
      const BOOM_WIDTH_KEY = 'motionpsm_boom_width_cm';

      function loadBoomWidth() {
        const saved = parseFloat(localStorage.getItem(BOOM_WIDTH_KEY));
        return (saved && !isNaN(saved)) ? saved : BOOM_WIDTH_DEFAULT;
      }
      function saveBoomWidth(v) {
        localStorage.setItem(BOOM_WIDTH_KEY, String(v));
      }
      // Initial-Werte setzen sobald DOM bereit
      (function initBoomWidth() {
        const inp = document.getElementById('boom_width_cm');
        if (!inp) return;
        inp.value = loadBoomWidth();
        inp.addEventListener('change', () => {
          const v = parseFloat(inp.value) || BOOM_WIDTH_DEFAULT;
          saveBoomWidth(v);
        });
        inp.addEventListener('input', () => {
          const v = parseFloat(inp.value);
          if (v && !isNaN(v)) saveBoomWidth(v);
        });
      })();

      {% if running %}
      const lateralCtx = document.getElementById('lateralChart').getContext('2d');
      const lateralChart = new Chart(lateralCtx, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            { label: 'R1 (left)', borderColor: '#1976d2', data: [], fill: false, tension: 0.2 },
            { label: 'R2 (right)', borderColor: '#d32f2f', data: [], fill: false, tension: 0.2 },
            { label: 'R1 − R2', borderColor: '#555', data: [], fill: false, borderDash: [4,4], tension: 0.2 }
          ]
        },
        options: {
          animation: false,
          scales: {
            x: { title: { display: true, text: 'Time (s)' } },
            y: { title: { display: true, text: 'cm' } }
          }
        }
      });

      function interpretQuality(value) {
        switch (value) {
          case 1: case 2: return { label: '3D Fix',     class: 'q-1' };
          case 4:         return { label: 'RTK Fix',    class: 'q-4' };
          case 5:         return { label: 'RTK Float',  class: 'q-5' };
          case 6:         return { label: 'Dead Reck.', class: 'q-6' };
          default:        return { label: 'no Fix',     class: 'q-0' };
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
      function updateBoom(r1_cm, r2_cm) {
        const boomWidthCm = parseFloat(document.getElementById('boom_width_cm').value) || BOOM_WIDTH_DEFAULT;
        const halfWidth = boomWidthCm / 2;
        const scale = 90 / halfWidth;
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

          document.getElementById('r1_lat').innerText   = fmtSigned(d.r1_lateral_cm);
          document.getElementById('r2_lat').innerText   = fmtSigned(d.r2_lateral_cm);
          document.getElementById('boom_total').innerText = fmtSigned(d.gestaenge_total_cm);
          document.getElementById('axis_length').innerText  = (d.axis_length_m || 0).toFixed(2);
          document.getElementById('axis_heading').innerText = (d.axis_heading_deg || 0).toFixed(1);
          document.getElementById('base_speed').innerText   = (d.base_speed || 0).toFixed(1);
          document.getElementById('runtime').innerText      = d.runtime;

          document.getElementById('r1_av').innerText = (d.r1_angular_velocity || 0).toFixed(2);
          document.getElementById('r2_av').innerText = (d.r2_angular_velocity || 0).toFixed(2);
          document.getElementById('r3_av').innerText = (d.r3_angular_velocity || 0).toFixed(2);
          document.getElementById('r1_vib').innerText = (d.r1_vibration || 0).toFixed(2);
          document.getElementById('r2_vib').innerText = (d.r2_vibration || 0).toFixed(2);
          document.getElementById('r3_vib').innerText = (d.r3_vibration || 0).toFixed(2);
          setQuality('r1_q', d.r1_quality);
          setQuality('r2_q', d.r2_quality);
          setQuality('r3_q', d.r3_quality);

          updateBoom(d.r1_lateral_cm, d.r2_lateral_cm);

          if (lateralChart.data.labels.length > CHART_MAX_POINTS) {
            lateralChart.data.labels.shift();
            lateralChart.data.datasets.forEach(ds => ds.data.shift());
          }
          lateralChart.data.labels.push(t);
          lateralChart.data.datasets[0].data.push(d.r1_lateral_cm);
          lateralChart.data.datasets[1].data.push(d.r2_lateral_cm);
          lateralChart.data.datasets[2].data.push(d.gestaenge_total_cm);
          lateralChart.update();
        }).catch(err => console.warn('fetch error', err));
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


def _g(name, default=0):
    """Defensive getter — manche gps-Globals existieren erst, wenn die Threads laufen."""
    return getattr(gps, name, default)


@app.route('/data')
def data():
    r1_lat = float(_g('R1_lateral_offset_cm') or 0)
    r2_lat = float(_g('R2_lateral_offset_cm') or 0)
    q1 = _g('quality_rover1');  q2 = _g('quality_rover2');  q3 = _g('quality_rover3')
    return jsonify({
        'runtime':             calculate_runtime(),
        'r1_lateral_cm':       round(r1_lat, 2),
        'r2_lateral_cm':       round(r2_lat, 2),
        'gestaenge_total_cm':  round(r1_lat - r2_lat, 2),
        'axis_length_m':       round(float(_g('vehicle_axis_length_m') or 0), 3),
        'axis_heading_deg':    round(float(_g('vehicle_heading_via_r3') or 0), 2),
        'r1_quality':          (q1[0] if q1 else 0) if hasattr(q1, '__getitem__') else 0,
        'r2_quality':          (q2[0] if q2 else 0) if hasattr(q2, '__getitem__') else 0,
        'r3_quality':          (q3[0] if q3 else 0) if hasattr(q3, '__getitem__') else 0,
        'r1_angular_velocity': float(_g('R1_angular_velocity') or 0),
        'r2_angular_velocity': float(_g('R2_angular_velocity') or 0),
        'r3_angular_velocity': float(_g('R3_angular_velocity') or 0),
        'r1_vibration':        float(_g('current_vibration_rover1') or 0),
        'r2_vibration':        float(_g('current_vibration_rover2') or 0),
        'r3_vibration':        float(_g('current_vibration_rover3') or 0),
        'base_speed':          float(_g('Base_Speed') or 0),
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
