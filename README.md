# MicroSentry

A Raspberry Pi ping-pong turret that tracks targets with computer vision, aims with a pan/tilt servo mount, and is controlled through a Flask web dashboard with live video.

## Overview

MicroSentry uses a Pi Camera and OpenCV to detect and follow a target in real time. Two servos on a pan/tilt mount point the turret at the target, and a mounted pipe holds a stack of ping-pong balls with holes for flywheel motors, forming the launcher. A browser-based control panel streams annotated video and lets you switch to manual aiming at any time.

## Features

- **Real-time target tracking**: Gaussian blur, HSV thresholding, erode/dilate filtering, and contour detection to find the target in each frame
- **Smooth servo aiming**: pixel position mapped to pan/tilt angles through a PCA9685 servo driver, with exponential smoothing to remove jitter
- **Web control panel**: live MJPEG video feed with tracking overlay, served by Flask
- **Manual mode**: toggle auto-tracking off and aim with pan and tilt sliders
- **Actuation**: buzzer and laser controlled over GPIO from the dashboard
- **Ping-pong launcher mount**: pipe magazine with motor cutouts for a flywheel launcher

## Hardware

- Raspberry Pi with a Pi Camera (Picamera2)
- Adafruit PCA9685 16-channel servo driver
- 2 servos for pan and tilt (channels 0 and 1)
- Buzzer on GPIO 17
- Laser on GPIO 27
- Pipe ball magazine with flywheel motor mounts

## Software Requirements

- Python 3
- OpenCV, NumPy, imutils
- Flask
- picamera2
- adafruit-circuitpython-servokit
- gpiozero

```bash
pip install opencv-python numpy imutils flask adafruit-circuitpython-servokit gpiozero
```

`picamera2` is typically installed on Raspberry Pi OS with `sudo apt install python3-picamera2`.

## Usage

```bash
python microsentry.py
```

Then open `http://<raspberry-pi-ip>:5000` in a browser on the same network.

- **Buzz**: sounds the buzzer
- **Fire**: triggers the fire action (currently blinks the laser three times)
- **Toggle Manual Mode**: switches between auto-tracking and slider control

## Configuration

Tunable settings are at the top of `microsentry.py`:

| Setting | Purpose |
|---|---|
| `LOWER_HSV` / `UPPER_HSV` | Color range of the target to track |
| `MIN_RADIUS` | Minimum detected size to count as a target |
| `PAN_MIN` / `PAN_MAX`, `TILT_MIN` / `TILT_MAX` | Servo travel limits |
| `ALPHA` | Smoothing factor (lower is smoother but slower) |

## Safety

The web server listens on all network interfaces and has no authentication. Run it only on a trusted local network, and handle the laser with care.
