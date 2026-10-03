import cv2
import numpy as np
import imutils
import time
from flask import Flask, Response, render_template_string, request, jsonify
from picamera2 import Picamera2
from adafruit_servokit import ServoKit
from collections import deque
import gpiozero


# ---------------- SETTINGS ----------------
# PCB Green HSV
LOWER_HSV = (40, 50, 50)
UPPER_HSV = (85, 255, 255)

FRAME_WIDTH = 600
FRAME_HEIGHT = 480
BUFFER_SIZE = 64
MIN_RADIUS = 10
MAX_RADIUS = 120

# Servo ranges
PAN_MIN = 10
PAN_MAX = 170
TILT_MIN = 10
TILT_MAX = 170

# Servo smoothing
ALPHA = 0.12

# Manual control
manual_mode = False
manual_pan = 90
manual_tilt = 90

# ---------------- SERVO SETUP ----------------
kit = ServoKit(channels=16)
servo_x = 90
servo_y = 90

kit.servo[0].angle = servo_x
kit.servo[1].angle = servo_y

pts = deque(maxlen=BUFFER_SIZE)
buzzer = gpiozero.Buzzer(17)
laser = gpiozero.LED(27)


# -------------- CAMERA ---------------------
picam2 = Picamera2()
config = picam2.create_video_configuration(
    main={"size": (2028, 1520), "format": "XBGR8888"},
    controls={
        "NoiseReductionMode": 0,
        "Sharpness": 1.0,
        "AwbEnable": True,
        "AeEnable": True
    }
)
picam2.configure(config)
picam2.start()
time.sleep(1)

# --------------- FLASK ---------------------
app = Flask("MicroSentry")

# HTML page (inline template)
PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>MicroSentry Control Panel</title>
    <style>
        body {
            font-family: 'Segoe UI', Roboto, sans-serif;
            background: #0d1117;
            color: #e6edf3;
            margin: 0;
            padding: 0;
            text-align: center;
        }

        h1 {
            margin-top: 30px;
            font-size: 40px;
            letter-spacing: 1px;
        }

        .container {
            width: 90%;
            max-width: 900px;
            margin: 30px auto;
            background: #161b22;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 0 20px rgba(0,0,0,0.4);
        }

        img {
            width: 100%;
            max-width: 750px;
            border-radius: 10px;
            border: 3px solid #30363d;
            margin-bottom: 20px;
        }

        button {
            padding: 14px 22px;
            margin: 10px;
            font-size: 18px;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            background: #238636;
            color: white;
            transition: 0.2s;
        }

        button:hover {
            background: #2ea043;
        }

        .danger {
            background: #da3633;
        }

        .danger:hover {
            background: #f85149;
        }

        .secondary {
            background: #30363d;
        }

        .secondary:hover {
            background: #484f58;
        }

        #status {
            font-size: 20px;
            color: #58a6ff;
            margin-top: 10px;
        }

        #manualControls {
            margin-top: 25px;
            padding: 20px;
            background: #21262d;
            border-radius: 12px;
        }

        input[type=range] {
            width: 80%;
            margin: 10px 0 25px 0;
            appearance: none;
            height: 6px;
            border-radius: 3px;
            background: #484f58;
        }

        input[type=range]::-webkit-slider-thumb {
            appearance: none;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: #58a6ff;
            cursor: pointer;
        }
    </style>
</head>
<body>

<h1>MicroSentry</h1>

<div class="container">

    <img src="/video_feed">

    <div>
        <button onclick="buzz()" class="secondary">Buzz</button>
        <button onclick="fire()" class="danger">Fire</button>
        <button onclick="toggleManual()">Toggle Manual Mode</button>
    </div>

    <p><b>Status:</b> <span id="status">Idle</span></p>

    <div id="manualControls" style="display:none">
        <h3>Manual Servo Control</h3>

        <label>Pan</label><br>
        <input type="range" min="10" max="170" value="90" oninput="setPan(this.value)">

        <label>Tilt</label><br>
        <input type="range" min="10" max="170" value="90" oninput="setTilt(this.value)">
    </div>

</div>

<script>
function buzz(){
    fetch('/buzz', {method: "POST"})
    .then(r=>r.json())
    .then(d=>document.getElementById("status").innerText=d.status);
}

function fire(){
    fetch('/fire', {method: "POST"})
    .then(r=>r.json())
    .then(d=>document.getElementById("status").innerText=d.status);
}

function toggleManual(){
    fetch('/toggle_manual', {method:"POST"})
    .then(r=>r.json())
    .then(d=>{
        document.getElementById("status").innerText = "Manual Mode: " + d.manual;

        document.getElementById("manualControls").style.display =
            d.manual ? "block" : "none";
    });
}

function setPan(val){
    fetch("/set_pan", {
        method:"POST",
        body:"value="+val,
        headers: {'Content-Type': 'application/x-www-form-urlencoded'}
    });
}

function setTilt(val){
    fetch("/set_tilt", {
        method:"POST",
        body:"value="+val,
        headers: {'Content-Type': 'application/x-www-form-urlencoded'}
    });
}
</script>

</body>
</html>
"""

# ------------ VIDEO + TRACKING LOOP -------------
def generate_frames():
    global servo_x, servo_y, manual_mode, manual_pan, manual_tilt

    while True:
        frame = picam2.capture_array()
        frame = frame[:, :, :3]
        frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))

        blurred = cv2.GaussianBlur(frame, (11, 11), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

        mask = cv2.inRange(hsv, LOWER_HSV, UPPER_HSV)
        mask = cv2.erode(mask, None, iterations=2)
        mask = cv2.dilate(mask, None, iterations=2)

        cnts = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        cnts = imutils.grab_contours(cnts)

        center = None

        if not manual_mode and len(cnts) > 0:
            c = max(cnts, key=cv2.contourArea)
            ((x, y), radius) = cv2.minEnclosingCircle(c)

            if radius > MIN_RADIUS:
                center = (int(x), int(y))
                cv2.circle(frame, center, int(radius), (0, 255, 255), 2)

                target_x = int(
                    np.interp(
                        x,
                        [0, FRAME_WIDTH],
                        [PAN_MAX, PAN_MIN]
                    )
                )

                target_y = int(
                    np.interp(
                        y,
                        [0, FRAME_HEIGHT],
                        [TILT_MIN, TILT_MAX]
                    )
                )

                servo_x = (
                    (1 - ALPHA) * servo_x +
                    ALPHA * target_x
                )

                servo_y = (
                    (1 - ALPHA) * servo_y +
                    ALPHA * target_y
                )

                kit.servo[0].angle = int(servo_x)
                kit.servo[1].angle = int(servo_y)

        if manual_mode:
            kit.servo[0].angle = manual_pan
            kit.servo[1].angle = manual_tilt

        _, jpeg = cv2.imencode('.jpg', frame)

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" +
            jpeg.tobytes() +
            b"\r\n"
        )


# ------------------ ROUTES -----------------------
@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/buzz", methods=["POST"])
def buzz():
    buzzer.on()
    time.sleep(0.15)
    buzzer.off()
    return jsonify({"status": "buzzed"})


@app.route("/fire", methods=["POST"])
def fire():
    print("FIRED")

    # Blink laser 3 times
    for _ in range(3):
        laser.on()
        time.sleep(0.5)
        laser.off()
        time.sleep(0.5)

    return jsonify({"status": "laser blinked"})


@app.route("/toggle_manual", methods=["POST"])
def toggle_manual():
    global manual_mode

    manual_mode = not manual_mode

    return jsonify({"manual": manual_mode})


@app.route("/set_pan", methods=["POST"])
def set_pan():
    global manual_pan

    manual_pan = int(request.form["value"])

    return jsonify({"pan": manual_pan})


@app.route("/set_tilt", methods=["POST"])
def set_tilt():
    global manual_tilt

    manual_tilt = int(request.form["value"])

    return jsonify({"tilt": manual_tilt})


# -------- START SERVER -------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
