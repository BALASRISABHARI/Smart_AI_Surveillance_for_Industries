"""Flask application for ESP32-CAM AI surveillance."""
from __future__ import annotations

import os
import threading
import time
from collections import deque
from pathlib import Path

import cv2
from flask import Flask, Response, jsonify, render_template

from detector import DetectorConfig, SurveillanceDetector


def parse_zone(value: str) -> tuple[float, float, float, float]:
    values = tuple(float(part.strip()) for part in value.split(","))
    if len(values) != 4 or any(item < 0 or item > 1 for item in values):
        raise ValueError("RESTRICTED_ZONE must contain four values between 0 and 1")
    left, top, right, bottom = values
    if left >= right or top >= bottom:
        raise ValueError("RESTRICTED_ZONE must have left<right and top<bottom")
    return values


class VideoWorker:
    def __init__(self, stream_url: str, detector: SurveillanceDetector) -> None:
        self.stream_url = stream_url
        self.detector = detector
        self.lock = threading.Lock()
        self.frame_jpeg: bytes | None = None
        self.state = {"people_count": 0, "object_count": 0, "score": 0, "status": "CONNECTING", "events": [], "updated_at": None}
        self.events: deque[dict] = deque(maxlen=30)

    def start(self) -> None:
        threading.Thread(target=self._run, name="video-worker", daemon=True).start()

    def _run(self) -> None:
        while True:
            capture = cv2.VideoCapture(self.stream_url)
            if not capture.isOpened():
                self._set_error("Unable to open ESP32-CAM stream")
                time.sleep(3)
                continue
            while True:
                ok, frame = capture.read()
                if not ok:
                    self._set_error("Camera stream interrupted")
                    break
                try:
                    annotated, state = self.detector.process(frame)
                    encoded, jpeg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if encoded:
                        with self.lock:
                            self.frame_jpeg = jpeg.tobytes()
                            self.state = state
                            for message in state["events"]:
                                event = {"message": message, "time": time.strftime("%H:%M:%S")}
                                if not self.events or self.events[0] != event:
                                    self.events.appendleft(event)
                except Exception as error:  # Keep the dashboard reachable after an inference error.
                    self._set_error(f"Inference error: {error}")
                    time.sleep(1)
            capture.release()
            time.sleep(1)

    def _set_error(self, message: str) -> None:
        with self.lock:
            self.state = {"people_count": 0, "object_count": 0, "score": 0, "status": "OFFLINE", "events": [message], "updated_at": time.time()}

    def snapshot(self) -> tuple[bytes | None, dict, list[dict]]:
        with self.lock:
            events = list(self.events)
            if not events:
                events = [{"message": message, "time": ""} for message in self.state["events"]]
            return self.frame_jpeg, dict(self.state), events


stream_url = os.environ.get("ESP32_STREAM_URL", "")
if not stream_url:
    raise RuntimeError("Set ESP32_STREAM_URL, e.g. http://192.168.1.50:81/stream")

config = DetectorConfig(
    model_name=os.environ.get("YOLO_MODEL", "yolo11n.pt"),
    confidence=float(os.environ.get("YOLO_CONFIDENCE", "0.45")),
    image_size=int(os.environ.get("YOLO_IMAGE_SIZE", "320")),
    zone=parse_zone(os.environ.get("RESTRICTED_ZONE", "0.30,0.15,0.70,0.90")),
    loiter_seconds=float(os.environ.get("LOITER_SECONDS", "30")),
    crowd_threshold=int(os.environ.get("CROWD_THRESHOLD", "3")),
    snapshot_dir=Path(os.environ.get("SNAPSHOT_DIR", "snapshots")),
)
worker = VideoWorker(stream_url, SurveillanceDetector(config))
app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/video_feed")
def video_feed():
    def generate():
        while True:
            frame, _, _ = worker.snapshot()
            if frame:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            time.sleep(0.08)
    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/status")
def status():
    _, state, events = worker.snapshot()
    return jsonify({**state, "events": events})


if __name__ == "__main__":
    worker.start()
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
