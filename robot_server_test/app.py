from flask import Flask, request, jsonify, render_template
from tango_class import Tango
from action_runner import ActionRunner
from lidar_guard import LidarGuard
import threading
import time
import math
from dialog_routes import dialog_bp, init_dialog

app = Flask(__name__)

# =========================
# LIDAR Guard
# =========================
guard = LidarGuard(
    port="/dev/ttyUSB0",
    min_dist_mm=500,   # stop if obstacle within 50cm
    arc_deg=30,        # check ±30° either side of dead-ahead
)
guard.start()

# =========================
# Robot + Dialog
# =========================
robot = Tango(lidar_guard=guard)
app.register_blueprint(dialog_bp)
init_dialog(robot, "testDialogFileForPractice.txt")

# =========================
# Safety Config
# =========================
COMMAND_TIMEOUT = 0.7      # seconds before auto-stop
MAX_RATE_HZ = 20           # max commands per second
last_cmd_time = time.time()
last_drive_time = 0
lock = threading.Lock()

# =========================
# Watchdog keepalive — passed to ActionRunner so dance/gestures
# can reset the timer and prevent the watchdog killing the wheels
# =========================
def touch_cmd_time():
    global last_cmd_time
    last_cmd_time = time.time()

# =========================
# Action Runner
# =========================
runner = ActionRunner(robot, keep_alive_fn=touch_cmd_time, lidar_guard=guard)
runner.start()

# =========================
# Helpers
# =========================
def safe_float(val, default=0.0):
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except:
        return default

def clamp(v, lo=-1, hi=1):
    return max(lo, min(hi, v))

def map_servo(val, center=6000, range_=1000):
    return int(center + val * range_)

# =========================
# Watchdog Thread
# =========================
def watchdog():
    global last_cmd_time
    while True:
        time.sleep(0.1)
        if time.time() - last_cmd_time > COMMAND_TIMEOUT:
            robot.stop()

threading.Thread(target=watchdog, daemon=True).start()

# =========================
# Routes
# =========================
@app.route("/")
@app.route("/drive")
def index():
    return render_template("index.html")

@app.route("/drive", methods=["POST"])
def drive():
    global last_cmd_time, last_drive_time
    with lock:
        now = time.time()
        if now - last_drive_time < 1/MAX_RATE_HZ:
            return jsonify(ignored=True)
        data = request.json or {}
        throttle = clamp(safe_float(data.get("throttle", 0)))
        turn     = clamp(safe_float(data.get("turn", 0)))

        # Block forward movement from the joystick/drive route too
        if throttle > 0 and guard.is_blocked():
            return jsonify(success=False, reason="obstacle_detected")

        # Convert normalised (-1..1) to Maestro units
        RANGE = 800  # increase for faster, decrease for slower
        left  = int(6000 - (throttle + turn) * RANGE)
        right = int(6000 + (throttle - turn) * RANGE)
        robot.drive(left, right)
        last_cmd_time = now
        last_drive_time = now
    return jsonify(success=True)

@app.route("/head", methods=["POST"])
def head():
    global last_cmd_time
    with lock:
        data = request.json or {}
        if "headH" in data:
            v = clamp(safe_float(data["headH"]))
            robot.head_h(map_servo(v))
        if "headV" in data:
            v = clamp(safe_float(data["headV"]))
            robot.head_v(map_servo(v))
        last_cmd_time = time.time()
    return jsonify(success=True)

@app.route("/waist", methods=["POST"])
def waist():
    global last_cmd_time
    with lock:
        data = request.json or {}
        v = clamp(safe_float(data.get("waist", 0)))
        robot.move("waist", map_servo(v))
        last_cmd_time = time.time()
    return jsonify(success=True)

@app.route("/stop", methods=["POST"])
def stop():
    robot.stop()
    return jsonify(success=True)

@app.route("/status", methods=["GET"])
def status():
    return jsonify(
        status="Robot server running",
        lidar_blocked=guard.is_blocked(),
        lidar_scan_age_s=round(guard.last_scan_age, 2),
        routes=["/drive", "/head", "/waist", "/stop", "/dialog", "/dialog/reset", "/dialog/state"]
    )

# =========================
# Startup Safety
# =========================
if __name__ == "__main__":
    print("Starting server forcing robot stop for safety.")
    robot.stop()
    app.run(host="0.0.0.0", port=5000)
