# AI smart surveillance with ESP32-CAM and YOLO

The ESP32-CAM supplies a Wi-Fi MJPEG video stream. This computer runs YOLO object detection, applies transparent rule-based event scoring, and serves an annotated Flask dashboard. The camera does **not** run YOLO; this keeps the system responsive and makes it practical for an ESP32-CAM.

## Features

- Person and object detection using Ultralytics YOLO.
- Restricted-zone entry, loitering, and crowding rules.
- Auditable score: restricted-zone entry (+30), loitering (+30), crowding (+20).
- Live dashboard with annotated video, counts, status, and recent events.
- Snapshot saving for scored events.

## 1. Flash the ESP32-CAM

Open [esp32_cam_stream/esp32_cam_stream.ino](esp32_cam_stream/esp32_cam_stream.ino), set the Wi-Fi credentials, then upload using **AI Thinker ESP32-CAM**, **PSRAM Enabled**, and **Huge APP**. Wire the programmer as follows: 5V->5V, GND->GND, TX->U0R, RX->U0T, and GPIO0->GND only while flashing. After uploading, remove GPIO0 from GND and reset the board.

Serial Monitor prints the stream URL, normally `http://CAMERA_IP:81/stream`.

## 2. Run the PC application

Use Python 3.11 or later. From this project directory:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:ESP32_STREAM_URL = 'http://192.168.1.50:81/stream'
python app.py
```

Open `http://127.0.0.1:5000`. The first run downloads the compact `yolo11n.pt` model. Use the computer's LAN IP instead of `127.0.0.1` to open the dashboard from another device on the same network.

## Configuration

All settings are optional environment variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `ESP32_STREAM_URL` | required | ESP32-CAM MJPEG stream URL |
| `YOLO_MODEL` | `yolo11n.pt` | Ultralytics model path/name |
| `YOLO_CONFIDENCE` | `0.45` | Minimum detection confidence |
| `YOLO_IMAGE_SIZE` | `320` | YOLO inference size; use `256` for faster CPU inference |
| `RESTRICTED_ZONE` | `0.30,0.15,0.70,0.90` | Relative `left,top,right,bottom` zone coordinates |
| `LOITER_SECONDS` | `30` | Time before a person is flagged for loitering |
| `CROWD_THRESHOLD` | `3` | People count that triggers crowding |
| `SNAPSHOT_DIR` | `snapshots` | Directory for event captures |

The scoring rules measure observable actions only. Treat `SUSPICIOUS` as an alert for human review, never as proof of wrongdoing.

## Project layout

```text
app.py                 Flask server and video worker
detector.py            YOLO inference, tracking, rules, and annotation
templates/index.html   Dashboard
esp32_cam_stream/      Arduino camera-streaming sketch
snapshots/             Created automatically when events occur
```

## Troubleshooting

- If the dashboard says stream unavailable, open `http://CAMERA_IP` first and confirm the camera is on the same network.
- Brownouts/restarts usually mean the ESP32-CAM power supply is weak. Use a stable regulated 5V supply capable of at least 1A.
- Raise `YOLO_CONFIDENCE` to reduce false positives. Adjust `RESTRICTED_ZONE` to match the visible camera view.
- For more FPS, keep the sketch at QVGA and set `$env:YOLO_IMAGE_SIZE = '256'` before starting `app.py`. This lowers small-object accuracy slightly.
