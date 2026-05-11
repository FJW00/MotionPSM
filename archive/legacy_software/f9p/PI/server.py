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
        #self.csv_logging_enabled = False
        #self.csv_thread = None


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
    </style>
  </head>
  <body>
    <h1>GNSS-Schwingungsmesssystem (F.Weigand)</h1>

    {% if running %}
      <p style="color: green;">Messung läuft seit: <span id="runtime">0</span> Sekunden.</p>
      <h2>Aktuelle Schwingung</h2>
      <p>Links: <span id="current_left">0.00</span> Δ°/s</p>
      <p>Rechts: <span id="current_right">0.00</span> Δ°/s</p>
      <h2>30 Sekunden Mittelwert</h2>
      <p>Links: <span id="avg_left">0.00</span> Δ°/s</p>
      <p>Rechts: <span id="avg_right">0.00</span> Δ°/s</p>
      
      <h2>Live-Plot</h2>
      <canvas id="vibrationChart" width="800" height="400"></canvas>

      <a href="{{ url_for('export_csv') }}">
        <button style="padding:10px 20px;">CSV exportieren</button>
      </a>

      <a href="{{ url_for('stop') }}"><button style="padding:10px 20px;">Messung stoppen</button></a>
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
              label: 'Rover 1 (links)',
              borderColor: 'blue',
              data: [],
              fill: false,
            },
            {
              label: 'Rover 2 (rechts)',
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
              title: { display: true, text: 'Δ°/s' },
              min: -50,
              max: 50
            }
          }
        }
      });

      let startTime = Date.now();

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
            chart.data.datasets[0].data.push(data.current_left);
            chart.data.datasets[1].data.push(data.current_right);
            chart.update();

            document.getElementById('current_left').innerText = data.current_left.toFixed(2);
            document.getElementById('current_right').innerText = data.current_right.toFixed(2);
            document.getElementById('avg_left').innerText = data.avg_left.toFixed(2);
            document.getElementById('avg_right').innerText = data.avg_right.toFixed(2);
            document.getElementById('runtime').innerText = data.runtime;
          });
      }

      setInterval(fetchData, 100);
      {% endif %}
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
        #csv_logging_enabled=state.csv_logging_enabled
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
        #state.csv_logging_enabled = False
    return redirect(url_for('index'))

@app.route('/data')
def data():
    runtime = calculate_runtime()
    avg_left = sum(gps.vibration_history_rover1) / len(gps.vibration_history_rover1) if gps.vibration_history_rover1 else 0
    avg_right = sum(gps.vibration_history_rover2) / len(gps.vibration_history_rover2) if gps.vibration_history_rover2 else 0
    return jsonify({
        'current_left': gps.current_vibration_rover1,
        'current_right': gps.current_vibration_rover2,
        'avg_left': avg_left,
        'avg_right': avg_right,
        'runtime': runtime
    })
@app.route('/export')
def export_csv():
    path = gps.export_to_csv()
    if path is None:
        return "Keine Daten vorhanden", 404

    filename = os.path.basename(path)
    return send_file(path, as_attachment=True, download_name=filename, mimetype="text/csv")

#@app.route('/toggle_csv')
#def toggle_csv():
    if not state.csv_logging_enabled:
        print("[Web] CSV-Logger wird gestartet...")
        state.csv_thread = threading.Thread(target=gps.csv_logger_thread_buffered, daemon=True)
        state.csv_thread.start()
        state.csv_logging_enabled = True
    else:
        print("[Web] Exportiere CSV...")
        path = gps.export_to_csv()
        state.csv_logging_enabled = False
        if path is None:
            return "Keine Daten vorhanden", 404
        filename = os.path.basename(path)
        return send_file(path, as_attachment=True, download_name=filename, mimetype="text/csv")

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
