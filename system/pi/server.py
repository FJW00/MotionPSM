from flask import Flask, render_template_string, jsonify, redirect, url_for, send_file, after_this_request
import time
import gps_measurement as gps
import threading
import os
import glob
import subprocess

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
      .brand-right-block {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 6px;
      }
      .data-mode-toggle {
        display: inline-flex;
        background: #eee;
        border-radius: 6px;
        padding: 2px;
        font-size: 12px;
        font-weight: 500;
        user-select: none;
      }
      .data-mode-toggle button {
        background: transparent;
        border: none;
        padding: 4px 12px;
        border-radius: 4px;
        cursor: pointer;
        color: #888;
        font-family: inherit;
        font-weight: 500;
        font-size: 12px;
        transition: all 0.15s;
      }
      .data-mode-toggle button.active {
        background: white;
        color: #222;
        box-shadow: 0 1px 2px rgba(0,0,0,0.08);
      }
      /* Tare-Steuerung dezent, links neben Toggle */
      .tare-controls {
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .tare-btn {
        background: transparent;
        border: 1px solid #ccc;
        border-radius: 5px;
        padding: 3px 9px;
        font-family: inherit;
        font-size: 11px;
        font-weight: 500;
        color: #777;
        cursor: pointer;
        transition: all 0.15s;
      }
      .tare-btn:hover {
        background: #f5f5f5;
        color: #222;
        border-color: #999;
      }
      .tare-status {
        font-size: 11px;
        color: #2e7d32;
        font-weight: 500;
        display: none;  /* nur sichtbar wenn tariert */
        align-items: center;
        gap: 4px;
      }
      .tare-status.active { display: inline-flex; }
      .tare-clear {
        background: transparent;
        border: none;
        color: #888;
        cursor: pointer;
        font-size: 14px;
        line-height: 1;
        padding: 0 2px;
        margin-left: 2px;
      }
      .tare-clear:hover { color: #d32f2f; }

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
      <div class="brand-right-block">
        <div style="display:flex; align-items:center; gap:10px;">
          <div class="brand-right">Real Time Monitor</div>
          <button type="button" onclick="systemRestart()"
                  title="Pi komplett neustarten (~60s)"
                  style="background:#c0392b;color:white;padding:6px 12px;border:none;
                         border-radius:4px;cursor:pointer;font-weight:bold;font-size:12px;">
            🔄 Pi neustarten
          </button>
        </div>
        <div style="display:flex; align-items:center; gap:10px;">
          <div class="tare-controls">
            <button type="button" class="tare-btn" id="tare_btn" title="Save current values as zero reference">⌖ Set Zero</button>
            <span class="tare-status" id="tare_status">
              <span>Tared <span id="tare_time">--:--:--</span></span>
              <button type="button" class="tare-clear" id="tare_clear" title="Clear tare">×</button>
            </span>
          </div>
          <div class="data-mode-toggle" id="data_mode_toggle">
            <button type="button" data-mode="filtered" class="active">Smoothed</button>
            <button type="button" data-mode="raw">Raw</button>
          </div>
        </div>
      </div>
    </div>

    {% if running %}
      <div class="runtime">Measurement running for <span id="runtime">0</span> s</div>
      <div class="controls">
        <button onclick="exportAndRedirect()">Export CSV</button>
        <a href="{{ url_for('stop') }}"><button>Stop Measurement</button></a>
      </div>

      <!-- Hero — Boom Motion (longitudinal = Schwingungs-Hauptmetrik) -->
      <div class="boom-hero">
        <div class="boom-header">
          <h2>Boom Motion — Longitudinal Deflection</h2>
          <div style="font-size:12px;color:#888;">
            + = forward (in driving direction) &nbsp;&middot;&nbsp; − = backward
          </div>
        </div>

        <div class="boom-svg-wrap">
          <!-- Top-Down View. Schlepper fährt nach oben. R1 wandert vertikal um Sollposition. -->
          <svg id="boom_svg" viewBox="-110 -60 220 120" preserveAspectRatio="xMidYMid meet" style="width:100%;height:auto;">
            <!-- Direction of Travel: Pfeil oben Mitte -->
            <text x="0" y="-52" text-anchor="middle" font-size="3.6" fill="#666" font-style="italic">Direction of Travel</text>
            <path d="M 0 -50 L -2 -46 L 0 -47 L 2 -46 Z" fill="#666"/>
            <line x1="0" y1="-47" x2="0" y2="-30" stroke="#aaa" stroke-width="0.4" stroke-dasharray="2,2"/>

            <!-- Längsachse Base->R3 (vertikal, dünn gestrichelt) -->
            <line x1="0" y1="-30" x2="0" y2="30" stroke="#ddd" stroke-dasharray="2,2" stroke-width="0.4"/>

            <!-- R3 oben (klein, transparent) -->
            <circle cx="0" cy="-25" r="2.2" fill="#2e7d32" fill-opacity="0.5"/>
            <text x="4" y="-23" font-size="3.5" fill="#2e7d32" opacity="0.7">R3</text>

            <!-- Base in der Mitte -->
            <circle cx="0" cy="0" r="2.5" fill="#444"/>
            <text x="4" y="2" font-size="3.5" fill="#444">Base</text>

            <!-- Soll-Gestänge (horizontale Linie durch Base) -->
            <line x1="-90" y1="0" x2="90" y2="0" stroke="#ccc" stroke-width="1" stroke-dasharray="2,2"/>

            <!-- Soll-Marker R1/R2 (grau, halbtransparent, fix bei y=0) -->
            <circle id="boom_r1_soll" cx="-90" cy="0" r="2" fill="#bbb" fill-opacity="0.5"/>
            <circle id="boom_r2_soll" cx="90" cy="0" r="2" fill="#bbb" fill-opacity="0.5"/>

            <!-- Ist-Gestänge: R1 — Base — R2 (zeigt geknicktes Gestänge bei Schwingung) -->
            <line id="boom_istline_l" x1="-90" y1="0" x2="0" y2="0" stroke="#1976d2" stroke-width="1.6" stroke-opacity="0.7"/>
            <line id="boom_istline_r" x1="0" y1="0" x2="90" y2="0" stroke="#d32f2f" stroke-width="1.6" stroke-opacity="0.7"/>

            <!-- Ist-Marker R1/R2 (wandern vertikal) -->
            <circle id="boom_r1" cx="-90" cy="0" r="3.5" fill="#1976d2"/>
            <circle id="boom_r2" cx="90" cy="0" r="3.5" fill="#d32f2f"/>
            <text id="boom_r1_label" x="-90" y="-6" text-anchor="middle" font-size="5" fill="#1976d2" font-weight="600">R1</text>
            <text id="boom_r2_label" x="90" y="-6" text-anchor="middle" font-size="5" fill="#d32f2f" font-weight="600">R2</text>

            <!-- Y-Skala-Anzeige rechts (dynamisch beschriftet via JS) -->
            <line x1="100" y1="-30" x2="100" y2="30" stroke="#999" stroke-width="0.3"/>
            <line x1="98" y1="-30" x2="102" y2="-30" stroke="#999" stroke-width="0.3"/>
            <line x1="98" y1="0" x2="102" y2="0" stroke="#999" stroke-width="0.3"/>
            <line x1="98" y1="30" x2="102" y2="30" stroke="#999" stroke-width="0.3"/>
            <text id="scale_top"  x="103" y="-29" font-size="3" fill="#999">+0 cm</text>
            <text x="103" y="1" font-size="3" fill="#999">0</text>
            <text id="scale_bot"  x="103" y="31" font-size="3" fill="#999">−0 cm</text>
          </svg>
        </div>

        <div class="boom-values">
          <div class="value-box r1">
            <div class="label">R1 (left)</div>
            <div class="value"><span id="r1_long">+0.0</span> <span class="unit">cm</span></div>
          </div>
          <div class="value-box delta">
            <div class="label">Symmetric Yaw &nbsp;<span style="font-weight:400;font-size:11px;">(boom rotation)</span></div>
            <div class="value"><span id="sym_yaw">0.0</span> <span class="unit">cm</span></div>
          </div>
          <div class="value-box r2">
            <div class="label">R2 (right)</div>
            <div class="value"><span id="r2_long">-0.0</span> <span class="unit">cm</span></div>
          </div>
        </div>

        <div class="boom-values" style="margin-top:8px;">
          <div class="value-box" style="background:#f7f7f7;">
            <div class="label">R1 Angle to Baseline</div>
            <div class="value" style="font-size:24px;color:#1976d2;"><span id="r1_angle">0.00</span> <span class="unit">°</span></div>
          </div>
          <div class="value-box" style="background:#f7f7f7;">
            <div class="label">Asymmetric Yaw &nbsp;<span style="font-weight:400;font-size:11px;">(boom shift fore/aft)</span></div>
            <div class="value" style="font-size:24px;color:#666;"><span id="asym_yaw">0.0</span> <span class="unit">cm</span></div>
          </div>
          <div class="value-box" style="background:#f7f7f7;">
            <div class="label">R2 Angle to Baseline</div>
            <div class="value" style="font-size:24px;color:#d32f2f;"><span id="r2_angle">0.00</span> <span class="unit">°</span></div>
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
          <h3>Geometry &amp; Speed</h3>
          <div class="row"><span>Axis Length (Base → R3):</span><span class="v"><span id="axis_length">0.00</span> m</span></div>
          <div class="row"><span>Vehicle Heading:</span><span class="v"><span id="axis_heading">0.0</span>°</span></div>
          <div class="row"><span>Detected Boom Width:</span><span class="v"><span id="boom_width">0.00</span> m</span></div>
          <div class="row"><span>Vehicle Speed:</span><span class="v"><span id="base_speed">0.0</span> km/h</span></div>
        </div>
      </div>

      <!-- Single chart: Longitudinal (Schwingungs-) History -->
      <div class="chart-row">
        <div class="chart-card">
          <h3>Longitudinal Deflection History — R1 / R2 / Sym. Yaw (cm)</h3>
          <canvas id="longChart" width="500" height="280"></canvas>
        </div>
      </div>

    {% else %}
      <div class="runtime stopped">Measurement stopped.</div>
      <div class="controls">
        <a href="{{ url_for('start') }}"><button>Start Measurement</button></a>
      </div>
    {% endif %}

    <script>
      // ----- Data-Mode-Toggle (Smoothed/Raw) — wirkt nur auf die UI, CSV bleibt immer beide Spalten -----
      const DATA_MODE_KEY = 'motionpsm_data_mode';
      let dataMode = localStorage.getItem(DATA_MODE_KEY) || 'filtered';

      function setDataMode(mode) {
        dataMode = mode;
        localStorage.setItem(DATA_MODE_KEY, mode);
        document.querySelectorAll('#data_mode_toggle button').forEach(b => {
          b.classList.toggle('active', b.dataset.mode === mode);
        });
      }
      // Initial-State aus localStorage
      (function initDataMode() {
        document.querySelectorAll('#data_mode_toggle button').forEach(b => {
          b.classList.toggle('active', b.dataset.mode === dataMode);
          b.addEventListener('click', () => setDataMode(b.dataset.mode));
        });
      })();

      // ----- Tare (Set Zero / Clear) -----
      function updateTareUI(setAt) {
        const status = document.getElementById('tare_status');
        const time = document.getElementById('tare_time');
        if (setAt) {
          status.classList.add('active');
          time.innerText = setAt;
        } else {
          status.classList.remove('active');
        }
      }
      (function initTare() {
        const btn = document.getElementById('tare_btn');
        if (btn) btn.addEventListener('click', () => {
          fetch('/zero', { method: 'POST' })
            .then(r => r.json())
            .then(d => updateTareUI(d.tare_set_at))
            .catch(err => console.warn('tare error', err));
        });
        const clr = document.getElementById('tare_clear');
        if (clr) clr.addEventListener('click', () => {
          fetch('/zero/clear', { method: 'POST' })
            .then(r => r.json())
            .then(d => updateTareUI(null))
            .catch(err => console.warn('tare clear error', err));
        });
      })();

      {% if running %}
      const longCtx = document.getElementById('longChart').getContext('2d');
      const longChart = new Chart(longCtx, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            { label: 'R1 longitudinal',  borderColor: '#1976d2', data: [], fill: false, tension: 0.2 },
            { label: 'R2 longitudinal',  borderColor: '#d32f2f', data: [], fill: false, tension: 0.2 },
            { label: 'Symmetric Yaw',    borderColor: '#555',    data: [], fill: false, borderDash: [4,4], tension: 0.2 }
          ]
        },
        options: {
          animation: false,
          scales: {
            x: { title: { display: true, text: 'Time (s)' } },
            y: { title: { display: true, text: 'cm  (+ forward, − backward)' } }
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
      // Top-Down-View: R1 und R2 sitzen seitlich (x ≈ konstant), schwingen vertikal (y) mit der longitudinal-Komponente.
      // x-Position wird aus lateral_cm dynamisch berechnet (auto-Skalierung).
      // y-Position aus longitudinal_cm mit dynamischer Skala (mind. ±30 cm).
      function updateBoom(r1_long_cm, r2_long_cm, r1_lat_cm, r2_lat_cm) {
        // X-Skalierung: SVG-Breite ±90, fits to physical lateral.
        // lateral_r1 ist positiv (links), lateral_r2 ist negativ (rechts).
        const maxLat = Math.max(Math.abs(r1_lat_cm), Math.abs(r2_lat_cm), 50);
        const xScale = 90 / maxLat;
        // R1 (lat > 0, links) → SVG-x negativ. R2 (lat < 0, rechts) → SVG-x positiv.
        const r1_x = -r1_lat_cm * xScale;
        const r2_x = -r2_lat_cm * xScale;

        // Y-Skalierung: dynamisch, min ±30 cm.
        const maxLong = Math.max(Math.abs(r1_long_cm), Math.abs(r2_long_cm), 30);
        const yRange = 30;  // SVG-units von y=0 zu y=±30 (top/bot)
        const yScale = yRange / maxLong;
        // longitudinal > 0 = nach vorne = nach OBEN = negativer SVG-y
        const r1_y = -r1_long_cm * yScale;
        const r2_y = -r2_long_cm * yScale;

        document.getElementById('boom_r1').setAttribute('cx', r1_x);
        document.getElementById('boom_r1').setAttribute('cy', r1_y);
        document.getElementById('boom_r2').setAttribute('cx', r2_x);
        document.getElementById('boom_r2').setAttribute('cy', r2_y);
        document.getElementById('boom_r1_label').setAttribute('x', r1_x);
        document.getElementById('boom_r1_label').setAttribute('y', r1_y - 5);
        document.getElementById('boom_r2_label').setAttribute('x', r2_x);
        document.getElementById('boom_r2_label').setAttribute('y', r2_y - 5);
        document.getElementById('boom_r1_soll').setAttribute('cx', r1_x);
        document.getElementById('boom_r2_soll').setAttribute('cx', r2_x);
        document.getElementById('boom_istline_l').setAttribute('x1', r1_x);
        document.getElementById('boom_istline_l').setAttribute('y1', r1_y);
        document.getElementById('boom_istline_r').setAttribute('x2', r2_x);
        document.getElementById('boom_istline_r').setAttribute('y2', r2_y);

        // Skala-Beschriftung
        document.getElementById('scale_top').textContent = '+' + maxLong.toFixed(0) + ' cm';
        document.getElementById('scale_bot').textContent = '−' + maxLong.toFixed(0) + ' cm';
      }

      let startTime = Date.now();
      const CHART_MAX_POINTS = 80;

      function fetchData() {
        fetch('/data').then(r => r.json()).then(d => {
          const t = ((Date.now() - startTime) / 1000).toFixed(1);

          // Tare-Status-Anzeige synchron halten (falls per anderem Browser-Tab geändert)
          updateTareUI(d.tare_set_at);

          // Mode-abhängige Werte wählen (CSV bekommt immer beide Spalten unabhängig vom Toggle)
          const r1_long_disp  = (dataMode === 'filtered') ? d.r1_longitudinal_filtered_cm : d.r1_longitudinal_cm;
          const r2_long_disp  = (dataMode === 'filtered') ? d.r2_longitudinal_filtered_cm : d.r2_longitudinal_cm;
          const sym_yaw_disp  = (dataMode === 'filtered') ? d.symmetric_yaw_filtered_cm  : d.symmetric_yaw_cm;
          const asym_yaw_disp = (dataMode === 'filtered') ? d.asymmetric_yaw_filtered_cm : d.asymmetric_yaw_cm;

          // Hauptmetriken — Schwingung
          document.getElementById('r1_long').innerText  = fmtSigned(r1_long_disp);
          document.getElementById('r2_long').innerText  = fmtSigned(r2_long_disp);
          document.getElementById('sym_yaw').innerText  = fmtSigned(sym_yaw_disp);
          document.getElementById('asym_yaw').innerText = fmtSigned(asym_yaw_disp);
          document.getElementById('r1_angle').innerText = fmtSigned(d.r1_angle_deg, 2);
          document.getElementById('r2_angle').innerText = fmtSigned(d.r2_angle_deg, 2);

          // Geometrie + Speed
          document.getElementById('axis_length').innerText  = (d.axis_length_m || 0).toFixed(2);
          document.getElementById('axis_heading').innerText = (d.axis_heading_deg || 0).toFixed(1);
          document.getElementById('base_speed').innerText   = (d.base_speed || 0).toFixed(1);
          document.getElementById('runtime').innerText      = d.runtime;
          // Detected Boom Width = lateral_r1 - lateral_r2 (in m)
          const boomWidth = ((d.r1_lateral_cm || 0) - (d.r2_lateral_cm || 0)) / 100;
          document.getElementById('boom_width').innerText = boomWidth.toFixed(2);

          // Quality / pro Rover
          document.getElementById('r1_av').innerText = (d.r1_angular_velocity || 0).toFixed(2);
          document.getElementById('r2_av').innerText = (d.r2_angular_velocity || 0).toFixed(2);
          document.getElementById('r3_av').innerText = (d.r3_angular_velocity || 0).toFixed(2);
          document.getElementById('r1_vib').innerText = (d.r1_vibration || 0).toFixed(2);
          document.getElementById('r2_vib').innerText = (d.r2_vibration || 0).toFixed(2);
          document.getElementById('r3_vib').innerText = (d.r3_vibration || 0).toFixed(2);
          setQuality('r1_q', d.r1_quality);
          setQuality('r2_q', d.r2_quality);
          setQuality('r3_q', d.r3_quality);

          // SVG: Marker wandern vertikal mit longitudinal (Mode-abhängig)
          updateBoom(r1_long_disp, r2_long_disp, d.r1_lateral_cm, d.r2_lateral_cm);

          // Chart: longitudinal-Verlauf (Mode-abhängig)
          if (longChart.data.labels.length > CHART_MAX_POINTS) {
            longChart.data.labels.shift();
            longChart.data.datasets.forEach(ds => ds.data.shift());
          }
          longChart.data.labels.push(t);
          longChart.data.datasets[0].data.push(r1_long_disp);
          longChart.data.datasets[1].data.push(r2_long_disp);
          longChart.data.datasets[2].data.push(sym_yaw_disp);
          longChart.update();
        }).catch(err => console.warn('fetch error', err));
      }
      setInterval(fetchData, 100);
      {% endif %}

      function systemRestart() {
        if (!confirm("Pi wirklich neustarten?\n\nDie UI ist ~60s nicht erreichbar.\nDie laufende Messung wird gestoppt.")) return;
        fetch('/system_restart', {method: 'POST'})
          .then(r => r.json())
          .then(d => {
            alert("Pi startet neu.\n\nIn ~60s Seite neu laden (F5).\nDer Server kommt durch den Autostart automatisch zurueck.");
          })
          .catch(e => alert("Fehler beim Neustart-Aufruf: " + e));
      }

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


@app.route('/zero', methods=['POST', 'GET'])
def zero():
    """Tariert: speichert aktuelle longitudinal+lateral als Nullpunkt."""
    ts = gps.set_tare()
    return jsonify({'ok': True, 'tare_set_at': ts})


@app.route('/zero/clear', methods=['POST', 'GET'])
def zero_clear():
    """Setzt die Tare-Offsets zurück auf 0."""
    gps.clear_tare()
    return jsonify({'ok': True, 'tare_set_at': None})


def _g(name, default=0):
    """Defensive getter — manche gps-Globals existieren erst, wenn die Threads laufen."""
    return getattr(gps, name, default)


@app.route('/data')
def data():
    from math import degrees, atan2, sqrt
    r1_lat       = float(_g('R1_lateral_offset_cm') or 0)
    r2_lat       = float(_g('R2_lateral_offset_cm') or 0)
    r1_long_raw  = float(_g('R1_longitudinal_offset_cm') or 0)
    r2_long_raw  = float(_g('R2_longitudinal_offset_cm') or 0)
    r1_long_filt = float(_g('R1_longitudinal_filtered_cm') or 0)
    r2_long_filt = float(_g('R2_longitudinal_filtered_cm') or 0)

    # Tare-Offsets anwenden — NUR longitudinal (lateral bleibt unveraendert, weil lateral
    # die geometrische Hebelarm-Laenge zur Achse ist und nicht weg-tariert werden soll).
    tare_r1_long = float(_g('TARE_R1_LONG_CM') or 0)
    tare_r2_long = float(_g('TARE_R2_LONG_CM') or 0)
    tare_set_at  = _g('TARE_SET_AT', None)
    r1_long_raw  -= tare_r1_long
    r2_long_raw  -= tare_r2_long
    r1_long_filt -= tare_r1_long
    r2_long_filt -= tare_r2_long
    # r1_lat / r2_lat: unveraendert

    # Gieren-Komponenten (nach Falks GeoGebra-Notation) — Raw + Filtered
    symmetric_yaw_raw_cm   = (r2_long_raw  - r1_long_raw)  / 2.0  # Gestänge dreht um Mittelpunkt
    asymmetric_yaw_raw_cm  = (r1_long_raw  + r2_long_raw)  / 2.0  # Gestänge wandert gesamt vor/zurück
    symmetric_yaw_filt_cm  = (r2_long_filt - r1_long_filt) / 2.0
    asymmetric_yaw_filt_cm = (r1_long_filt + r2_long_filt) / 2.0

    # Frontend-Kompat: r1_long / symmetric_yaw_cm bleiben als roh-Default
    r1_long = r1_long_raw
    r2_long = r2_long_raw
    symmetric_yaw_cm  = symmetric_yaw_raw_cm
    asymmetric_yaw_cm = asymmetric_yaw_raw_cm

    # Hebellänge je Rover = Abstand zur Baseline (für Winkel-Berechnung)
    r1_arm = abs(r1_lat) if r1_lat else 1.0  # avoid div-by-0
    r2_arm = abs(r2_lat) if r2_lat else 1.0
    # Winkel zwischen "R1-zur-Baseline-Senkrechten" und "Vektor Base->R1" (in °)
    # Vereinfacht: asin(longitudinal / arm) wenn Werte plausibel
    def safe_angle_deg(long_cm, arm_cm):
        if arm_cm < 1 or abs(long_cm) > arm_cm: return 0.0
        from math import asin
        return degrees(asin(long_cm / arm_cm))
    r1_angle_deg = safe_angle_deg(r1_long, r1_arm)
    r2_angle_deg = safe_angle_deg(r2_long, r2_arm)

    q1 = _g('quality_rover1');  q2 = _g('quality_rover2');  q3 = _g('quality_rover3')
    return jsonify({
        'runtime':             calculate_runtime(),
        # Hauptmetriken — die Schwingung (Raw)
        'r1_longitudinal_cm':           round(r1_long_raw, 2),
        'r2_longitudinal_cm':           round(r2_long_raw, 2),
        'symmetric_yaw_cm':             round(symmetric_yaw_raw_cm, 2),
        'asymmetric_yaw_cm':            round(asymmetric_yaw_raw_cm, 2),
        # Hauptmetriken — Filtered (Moving-Average aus config.json FILTER_WINDOW_S)
        'r1_longitudinal_filtered_cm':  round(r1_long_filt, 2),
        'r2_longitudinal_filtered_cm':  round(r2_long_filt, 2),
        'symmetric_yaw_filtered_cm':    round(symmetric_yaw_filt_cm, 2),
        'asymmetric_yaw_filtered_cm':   round(asymmetric_yaw_filt_cm, 2),
        # Winkel zur Baseline (immer aus raw — sind sub-Grad-Werte sowieso ruhig)
        'r1_angle_deg':        round(r1_angle_deg, 2),
        'r2_angle_deg':        round(r2_angle_deg, 2),
        # Geometrie (für SVG-Skalierung)
        'r1_lateral_cm':       round(r1_lat, 2),
        'r2_lateral_cm':       round(r2_lat, 2),
        'gestaenge_total_cm':  round(r1_lat - r2_lat, 2),
        'axis_length_m':       round(float(_g('vehicle_axis_length_m') or 0), 3),
        'axis_heading_deg':    round(float(_g('vehicle_heading_via_r3') or 0), 2),
        'tare_set_at':         tare_set_at,
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

    # /tmp-Cleanup NACH erfolgreichem Download:
    # Pi's /tmp ist tmpfs (RAM). Alte CSVs akkumulieren sich → RAM-Druck.
    # Erst loeschen wenn die gerade gesendete Datei beim Client angekommen ist.
    # Sicherheits-Check: nur Dateien aelter als 30s (gerade gesendete sicher ausgeschlossen).
    @after_this_request
    def cleanup_tmp_csvs(response):
        if response.status_code in (200, 206):
            try:
                now = time.time()
                cleaned = 0
                freed_kb = 0
                for old in glob.glob("/tmp/Records_F9P_*.csv"):
                    try:
                        if os.path.abspath(old) == os.path.abspath(path):
                            continue
                        if now - os.path.getmtime(old) < 30:
                            continue
                        size_kb = os.path.getsize(old) // 1024
                        os.remove(old)
                        cleaned += 1
                        freed_kb += size_kb
                    except OSError:
                        pass
                if cleaned:
                    print(f"[Export] /tmp aufgeraeumt: {cleaned} alte CSV(s) geloescht ({freed_kb} KB frei)")
            except Exception as e:
                print(f"[Export] /tmp cleanup-Fehler (ignoriert): {e}")
        return response

    return send_file(path, as_attachment=True, download_name=filename, mimetype="text/csv")


@app.route('/system_restart', methods=['POST'])
def system_restart():
    """Pi neu starten via sudo reboot.

    Voraussetzung: /etc/sudoers.d/motionpsm-reboot existiert
    und erlaubt dem Service-User NOPASSWD: /sbin/reboot.
    Setup einmalig per: sudo bash tools/setup_sudoers_reboot.sh
    """
    try:
        # Falls eine Messung laeuft, vorher sauber stoppen
        if state.running:
            try:
                gps.stop_measurement()
            except Exception as e:
                print(f"[Reboot] stop_measurement Fehler (ignoriert): {e}")
            state.running = False
            state.start_time = None

        # subprocess.Popen detached, damit Flask die Response noch zurueck
        # gibt bevor der Pi runter geht (~1 s Vorlauf).
        subprocess.Popen(['sudo', '-n', '/sbin/reboot'])
        return jsonify({
            "status": "ok",
            "message": "Pi startet neu. UI in ~60s wieder verfuegbar."
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
