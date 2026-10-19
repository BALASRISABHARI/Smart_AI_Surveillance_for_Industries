"""Detection, lightweight person tracking, scoring, and frame annotation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Iterable

import cv2
import numpy as np
from ultralytics import YOLO


@dataclass(frozen=True)
class DetectorConfig:
    model_name: str
    confidence: float
    image_size: int
    zone: tuple[float, float, float, float]
    loiter_seconds: float
    crowd_threshold: int
    snapshot_dir: Path


@dataclass
class Track:
    center: tuple[int, int]
    first_seen: float
    last_seen: float
    zone_entry_at: float | None = None


class SurveillanceDetector:
    """A deliberately small centroid tracker suitable for a fixed camera."""

    def __init__(self, config: DetectorConfig) -> None:
        self.config = config
        self.model = YOLO(config.model_name)
        self.tracks: dict[int, Track] = {}
        self.next_track_id = 1
        self.last_snapshot_at = 0.0

    def process(self, frame: np.ndarray) -> tuple[np.ndarray, dict]:
        now = time.monotonic()
        height, width = frame.shape[:2]
        zone_px = self._zone_pixels(width, height)
        # Infer at a compact square size. The original frame is still used for
        # drawing, so the dashboard stays at the camera's native resolution.
        results = self.model(frame, conf=self.config.confidence,
                             imgsz=self.config.image_size, verbose=False)[0]
        persons: list[tuple[int, int, int, int, float]] = []
        objects: list[tuple[int, int, int, int, float, str]] = []

        for box in results.boxes:
            class_id = int(box.cls[0])
            label = results.names[class_id]
            confidence = float(box.conf[0])
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            objects.append((x1, y1, x2, y2, confidence, label))
            if label == "person":
                persons.append((x1, y1, x2, y2, confidence))

        track_assignments = self._assign_tracks(persons, now)
        active_ids = set(track_assignments)
        self.tracks = {track_id: track for track_id, track in self.tracks.items()
                       if track_id in active_ids or now - track.last_seen < 3.0}

        restricted_entries = 0
        restricted_zone_people = 0
        loitering = 0
        for track_id, person in track_assignments.items():
            x1, y1, x2, y2, _ = person
            center = ((x1 + x2) // 2, (y1 + y2) // 2)
            track = self.tracks[track_id]
            if self._inside(center, zone_px):
                restricted_zone_people += 1
                if track.zone_entry_at is None:
                    track.zone_entry_at = now
                    restricted_entries += 1
                if now - track.zone_entry_at >= self.config.loiter_seconds:
                    loitering += 1
            else:
                track.zone_entry_at = None

        people_count = len(persons)
        crowding = people_count >= self.config.crowd_threshold
        score = min(100, (30 if restricted_zone_people else 0) + (30 if loitering else 0) + (20 if crowding else 0))
        status = "SUSPICIOUS" if score >= 60 else "MONITOR" if score >= 30 else "NORMAL"
        events = []
        if restricted_entries:
            events.append("Person entered restricted zone")
        if loitering:
            events.append("Person loitering in restricted zone")
        if crowding:
            events.append(f"Crowding: {people_count} people")

        annotated = self._annotate(frame, objects, track_assignments, zone_px, score, status)
        state = {"people_count": people_count, "object_count": len(objects), "score": score,
                 "status": status, "events": events, "updated_at": time.time()}
        if score >= 30 and now - self.last_snapshot_at >= 10:
            self._save_snapshot(annotated, state)
            self.last_snapshot_at = now
        return annotated, state

    def _assign_tracks(self, persons: Iterable[tuple[int, int, int, int, float]], now: float) -> dict[int, tuple[int, int, int, int, float]]:
        assignments = {}
        unmatched = set(self.tracks)
        for person in persons:
            x1, y1, x2, y2, _ = person
            center = ((x1 + x2) // 2, (y1 + y2) // 2)
            nearest = min(unmatched, key=lambda key: self._distance(center, self.tracks[key].center), default=None)
            if nearest is not None and self._distance(center, self.tracks[nearest].center) < 100:
                track_id = nearest
                unmatched.remove(track_id)
                self.tracks[track_id].center = center
                self.tracks[track_id].last_seen = now
            else:
                track_id = self.next_track_id
                self.next_track_id += 1
                self.tracks[track_id] = Track(center=center, first_seen=now, last_seen=now)
            assignments[track_id] = person
        return assignments

    def _zone_pixels(self, width: int, height: int) -> tuple[int, int, int, int]:
        left, top, right, bottom = self.config.zone
        return int(left * width), int(top * height), int(right * width), int(bottom * height)

    @staticmethod
    def _inside(point: tuple[int, int], zone: tuple[int, int, int, int]) -> bool:
        x, y = point; left, top, right, bottom = zone
        return left <= x <= right and top <= y <= bottom

    @staticmethod
    def _distance(a: tuple[int, int], b: tuple[int, int]) -> float:
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    def _annotate(self, frame: np.ndarray, objects: list, tracks: dict, zone: tuple[int, int, int, int], score: int, status: str) -> np.ndarray:
        annotated = frame.copy()
        left, top, right, bottom = zone
        cv2.rectangle(annotated, (left, top), (right, bottom), (0, 165, 255), 2)
        cv2.putText(annotated, "RESTRICTED ZONE", (left, max(22, top - 8)), cv2.FONT_HERSHEY_SIMPLEX, .55, (0, 165, 255), 2)
        for x1, y1, x2, y2, confidence, label in objects:
            color = (50, 220, 50) if label == "person" else (255, 180, 40)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            cv2.putText(annotated, f"{label} {confidence:.0%}", (x1, max(18, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, .55, color, 2)
        for track_id, person in tracks.items():
            x1, y1, _, _, _ = person
            cv2.putText(annotated, f"ID {track_id}", (x1, y1 + 18), cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1)
        color = (30, 40, 220) if status == "SUSPICIOUS" else (0, 190, 255) if status == "MONITOR" else (30, 200, 80)
        cv2.rectangle(annotated, (8, 8), (235, 44), color, -1)
        cv2.putText(annotated, f"{status}  score: {score}", (16, 32), cv2.FONT_HERSHEY_SIMPLEX, .65, (255, 255, 255), 2)
        return annotated

    def _save_snapshot(self, frame: np.ndarray, state: dict) -> None:
        self.config.snapshot_dir.mkdir(parents=True, exist_ok=True)
        filename = self.config.snapshot_dir / f"event_{int(time.time())}_{state['status'].lower()}.jpg"
        cv2.imwrite(str(filename), frame)
