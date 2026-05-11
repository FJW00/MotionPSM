from flask import Flask, render_template_string, redirect, url_for
import subprocess
import signal
import os
import time

app = Flask(__name__)
process = None
start_time = None

HTML_PAGE = '''
<!doctype html>
<html lang="de">
  <head>
    <meta charset="utf-8">
    <title>Schwingungsaufnahme</title>
  </head>
  <body style="font-family: Arial; text-align: center; margin-top: 100px;">
    <h1>Schwingungsaufnahme</h1>
    {% if running %}
      <p style="color: green;">Messung läuft seit: {{ runtime }} Sekunden.</p>
      <a href="{{ url_for('stop') }}"><button style="padding:10px 20px;">Messung stoppen</button></a>
    {% else %}
      <p style="color: red;">Messung gestoppt.</p>
      <a href="{{ url_for('start') }}"><button style="padding:10px 20px;">Messung starten</button></a>
    {% endif %}
  </body>
</html>
'''

@app.route('/')
def index():
    global process, start_time
    runtime = int(time.time() - start_time) if start_time else 0
    return render_template_string(HTML_PAGE, running=process is not None, runtime=runtime)

@app.route('/start')
def start():
    global process, start_time
    if process is None:
        process = subprocess.Popen(['python3', 'gps_measurement.py'])
        start_time = time.time()
    return redirect(url_for('index'))

@app.route('/stop')
def stop():
    global process, start_time
    if process:
        os.kill(process.pid, signal.SIGTERM)
        process = None
        start_time = None
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
