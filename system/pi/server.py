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
    <title>GNSS-Schwingungsmesssystem (F.Weigand)</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
      body { font-family: Arial; text-align: center; margin-top: 50px; }
      canvas { max-width: 800px; margin: auto; }

      .flex-container {
        display: flex;
        justify-content: center;
        gap: 40px;
        margin: 30px auto;
        flex-wrap: wrap;
      }

      .flex-box {
        border: 1px solid #ccc;
        border-radius: 12px;
        padding: 20px;
        min-width: 220px;
        background-color: #f9f9f9;
        box-shadow: 2px 2px 8px rgba(0,0,0,0.1);
      }
      .plot-row {
        display: flex;
        justify-content: center;
        gap: 40px;
        flex-wrap: wrap;
      }
      canvas {
        max-width: 600px;
      }

      .quality {
        font-weight: bold;
        padding: 4px 8px;
        border-radius: 6px;
        color: white;
      }
      .q-1, .q-2 { background-color: #1976d2; }
      .q-4 { background-color: #2e7d32; }
      .q-5 { background-color: #f9a825; }
      .q-6 { background-color: #d32f2f; }
      .q-0 { background-color: #9e9e9e; }
    </style>
  </head>
  <body>
    <h1>GNSS-Schwingungsmesssystem (F.Weigand)</h1>

    {% if running %}
      <p style="color: green;">Messung läuft seit: <span id="runtime">0</span> Sekunden.</p>

      <div style="margin: 20px 0;">
        <button style="padding:10px 20px;" onclick="exportAndRedirect()">CSV exportieren</button>
        <a href="{{ url_for('stop') }}"><button style="padding:10px 20px;">Messung stoppen</button></a>
      </div>

      <div class="flex-container">
        <div class="flex-box">
          <h2>Aktuelle Schwingung</h2>
          <p>Rover1: <span id="current_rover1">0.00</span> Δ°/s</p>
          <p>Rover2: <span id="current_rover2">0.00</span> Δ°/s</p>
        </div>
        <div class="flex-box">
          <h2>10 Sekunden Mittelwert</h2>
          <p>Rover1: <span id="avg_rover1">0.00</span> Δ°/s</p>
          <p>Rover2: <span id="avg_rover2">0.00</span> Δ°/s</p>
        </div>
        <div class="flex-box">
          <h2>Signalqualität</h2>
          <p>Rover 1: <span id="Rover1_quality" class="quality q-0">Unbekannt</span></p>
          <p>Rover 2: <span id="Rover2_quality" class="quality q-0">Unbekannt</span></p>
        </div>
        <div class="flex-box">
          <h2>Geschwindigkeit</h2>
          <p>Base: <span id="Base_Speed">0.00</span> km/h</p>
        </div>
      <div class="plot-row">
        <div>
          <h2>Live-Plot Heading</h2>
          <canvas id="vibrationChart" width="600" height="400"></canvas>
        </div>
        <div>
          <h2>Lineare Regression über die letzten 2 Sekunden</h2>
          <canvas id="meanChart" width="600" height="400"></canvas>
        </div>
      </div>

    {% else %}
      <p style="color: red;">Messung gestoppt.</p>
      <a href="{{ url_for('start') }}"><button style="padding:10px 20px;">Messung starten</button></a>
    {% endif %}

    <script>
      {% if running %}
      const ctx = document.getElementById('vibrationChart').getContext('2d');
      const chart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            {
              label: 'Rover 1',
              borderColor: 'blue',
              data: [],
              fill: false,
            },
            {
              label: 'Rover 2',
              borderColor: 'red',
              data: [],
              fill: false,
            }
          ]
        },
        options: {
          animation: false,
          scales: {
            x: {
              title: { display: true, text: 'Zeit (s)' }
            },
            y: {
              title: { display: true, text: 'Grad (°)' },
              min: -2,
              max: 2
            }
          }
        }
      });

      const ctx2 = document.getElementById('meanChart').getContext('2d');
      const meanChart = new Chart(ctx2, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            {
              label: 'Rover 1',
              borderColor: 'blue',
              borderDash: [5, 5],
              data: [],
              fill: false,
            },
            {
              label: 'Rover 2',
              borderColor: 'red',
              borderDash: [5, 5],
              data: [],
              fill: false,
            }
          ]
        },
        options: {
          animation: false,
          scales: {
            x: {
              title: { display: true, text: 'Zeit (s)' }
            },
            y: {
              title: { display: true, text: 'Grad (°)' },
              min: -2,
              max: 2
            }
          }
        }
      });

      let startTime = Date.now();

      function interpretQuality(value) {
        switch (value) {
          case 1:
          case 2: return { label: '3D GNSS Fix', class: 'q-1' };
          case 4: return { label: 'RTK Fix', class: 'q-4' };
          case 5: return { label: 'RTK Float', class: 'q-5' };
          case 6: return { label: 'Dead Reckoning', class: 'q-6' };
          default: return { label: 'Unbekannt', class: 'q-0' };
        }
      }

      function updateQuality(id, value) {
        const qInfo = interpretQuality(value);
        const el = document.getElementById(id);
        el.innerText = qInfo.label;
        el.className = 'quality ' + qInfo.class;
      }

      function fetchData() {
        fetch('/data')
          .then(res => res.json())
          .then(data => {
            const now = ((Date.now() - startTime) / 1000).toFixed(1);
            if (chart.data.labels.length > 60) {
              chart.data.labels.shift();
              chart.data.datasets[0].data.shift();
              chart.data.datasets[1].data.shift();
            }
            chart.data.labels.push(now);
            chart.data.datasets[0].data.push(data.current_rover1);
            chart.data.datasets[1].data.push(data.current_rover2);
            chart.update();

            if (meanChart.data.labels.length > 60) {
              meanChart.data.labels.shift();
              meanChart.data.datasets[0].data.shift();
              meanChart.data.datasets[1].data.shift();
            }

            meanChart.data.labels.push(now);
            meanChart.data.datasets[0].data.push(data.Rover1_mean);
            meanChart.data.datasets[1].data.push(data.Rover2_mean);
            meanChart.update();


            document.getElementById('current_rover1').innerText = data.current_rover1.toFixed(2);
            document.getElementById('current_rover2').innerText = data.current_rover2.toFixed(2);
            document.getElementById('avg_rover1').innerText = data.avg_rover1.toFixed(2);
            document.getElementById('avg_rover2').innerText = data.avg_rover2.toFixed(2);
            document.getElementById('runtime').innerText = data.runtime;
            document.getElementById('Base_Speed').innerText = data.Base_Speed;
            updateQuality('Rover1_quality', data.Rover1_quality);
            updateQuality('Rover2_quality', data.Rover2_quality);
          });
      }

      setInterval(fetchData, 100);
      {% endif %}
    
      function exportAndRedirect() {
        const downloadLink = document.createElement('a');
        downloadLink.href = "{{ url_for('export_csv') }}";
        downloadLink.download = '';
        document.body.appendChild(downloadLink);
        downloadLink.click();
        document.body.removeChild(downloadLink);

        setTimeout(() => {
          window.location.href = "{{ url_for('index') }}";
        }, 100);
      }
    </script>
  </body>
</html>
'''

def calculate_runtime():
    return int(time.time() - state.start_time) if state.start_time else 0

@app.route('/')
def index():
    runtime = calculate_runtime()
    return render_template_string(
        HTML_PAGE,
        running=state.running,
        runtime=runtime,
    )

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
    avg_rover1 = sum(gps.vibration_history_rover1) / len(gps.vibration_history_rover1) if gps.vibration_history_rover1 else 0
    avg_rover2 = sum(gps.vibration_history_rover2) / len(gps.vibration_history_rover2) if gps.vibration_history_rover2 else 0
    return jsonify({
        'current_rover1': gps.current_vibration_rover1,
        'current_rover2': gps.current_vibration_rover2,
        'avg_rover1': avg_rover1,
        'avg_rover2': avg_rover2,
        'runtime': runtime,
        'Rover1_quality': gps.quality_rover1[0] if gps.quality_rover1 else 0,
        'Rover2_quality': gps.quality_rover2[0] if gps.quality_rover2 else 0,
        'Rover1_mean': gps.R1_angular_velocity,
        'Rover2_mean': gps.R2_angular_velocity,
        'Base_Speed' : gps.Base_Speed

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
