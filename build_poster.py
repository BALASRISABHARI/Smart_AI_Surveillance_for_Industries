from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

OUT = Path("output/pdf/esp32_cam_ai_surveillance_poster.pdf")
W, H = landscape(A3)

NAVY = HexColor("#0B1628")
PANEL = HexColor("#12233E")
TEAL = HexColor("#13C4B3")
CYAN = HexColor("#46C5FF")
ORANGE = HexColor("#FFB34C")
GREEN = HexColor("#55D68A")
RED = HexColor("#FA6B73")
MUTED = HexColor("#B7C5D9")


def text(c, value, x, y, size=12, color=white, font="Helvetica", leading=None):
    c.setFont(font, size)
    c.setFillColor(color)
    if leading is None:
        leading = size * 1.35
    for line in value.split("\n"):
        c.drawString(x, y, line)
        y -= leading
    return y


def wrapped(c, value, x, y, width, size=11, color=MUTED, font="Helvetica", leading=None):
    if leading is None:
        leading = size * 1.35
    words, line = value.split(), ""
    for word in words:
        trial = f"{line} {word}".strip()
        if stringWidth(trial, font, size) > width and line:
            text(c, line, x, y, size, color, font, leading)
            y -= leading
            line = word
        else:
            line = trial
    if line:
        text(c, line, x, y, size, color, font, leading)
        y -= leading
    return y


def panel(c, x, y, w, h, title, accent):
    c.setFillColor(PANEL)
    c.roundRect(x, y, w, h, 13, fill=1, stroke=0)
    c.setFillColor(accent)
    c.roundRect(x, y + h - 9, w, 9, 13, fill=1, stroke=0)
    text(c, title.upper(), x + 18, y + h - 32, 13, white, "Helvetica-Bold")


def bullet(c, value, x, y, width, accent=TEAL):
    c.setFillColor(accent)
    c.circle(x + 4, y + 3, 3, fill=1, stroke=0)
    return wrapped(c, value, x + 15, y, width - 20, 10.2)


def arrow(c, x1, y1, x2, y2):
    c.setStrokeColor(CYAN); c.setLineWidth(2.2)
    c.line(x1, y1, x2, y2)
    c.line(x2, y2, x2 - 10, y2 + 5)
    c.line(x2, y2, x2 - 10, y2 - 5)


def node(c, x, y, w, label, subtitle, accent):
    c.setFillColor(HexColor("#17304F"))
    c.roundRect(x, y, w, 48, 10, fill=1, stroke=0)
    c.setFillColor(accent); c.circle(x + 18, y + 24, 9, fill=1, stroke=0)
    text(c, label, x + 35, y + 28, 10.2, white, "Helvetica-Bold")
    text(c, subtitle, x + 35, y + 14, 8.5, MUTED)


def make():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT), pagesize=landscape(A3))
    c.setTitle("ESP32-CAM AI Surveillance Poster")
    c.setFillColor(NAVY); c.rect(0, 0, W, H, fill=1, stroke=0)

    # Header
    c.setFillColor(TEAL); c.rect(0, H - 12, W, 12, fill=1, stroke=0)
    text(c, "AI-BASED SMART SURVEILLANCE", 48, H - 58, 29, white, "Helvetica-Bold")
    text(c, "ESP32-CAM + YOLO Object Detection + Flask Dashboard", 50, H - 82, 14, CYAN)
    c.setFillColor(HexColor("#183253")); c.roundRect(W - 270, H - 94, 220, 46, 15, fill=1, stroke=0)
    text(c, "WORKING MODEL", W - 245, H - 67, 13, TEAL, "Helvetica-Bold")
    text(c, "Real-time, explainable alerts", W - 245, H - 82, 9.5, MUTED)

    # top summary strip
    c.setFillColor(HexColor("#0E1D34")); c.roundRect(48, H - 158, W - 96, 52, 14, fill=1, stroke=0)
    text(c, "PROBLEM", 68, H - 131, 11, ORANGE, "Helvetica-Bold")
    wrapped(c, "Conventional cameras record incidents but do not immediately identify restricted-zone entry, loitering, or crowding.", 145, H - 132, 420, 10.5)
    text(c, "OBJECTIVE", 620, H - 131, 11, TEAL, "Helvetica-Bold")
    wrapped(c, "Build an affordable live surveillance system that detects people and objects, scores observable events, and supports human review.", 710, H - 132, 410, 10.5)

    # three columns
    y, h, gap = 426, 222, 20
    col = (W - 96 - 2 * gap) / 3
    xs = [48, 48 + col + gap, 48 + 2 * (col + gap)]
    panel(c, xs[0], y, col, h, "Principle & Components", TEAL)
    py = y + h - 58
    for v in ["ESP32-CAM provides a compact Wi-Fi MJPEG camera stream.", "Laptop/PC runs YOLO for object and person detection.", "Flask dashboard presents annotated video, score, status, and events.", "Optional: PIR sensor, buzzer, LED, microSD snapshots."]:
        py = bullet(c, v, xs[0] + 18, py, col - 36)
        py -= 6

    panel(c, xs[1], y, col, h, "Working Mechanism", CYAN)
    py = y + h - 58
    for v in ["Capture: ESP32-CAM streams QVGA frames over local Wi-Fi.", "Analyze: YOLO finds people and common objects; a centroid tracker maintains identities.", "Evaluate: restricted-zone entry, dwell time, and crowd count update the score.", "Respond: dashboard labels NORMAL, MONITOR, or SUSPICIOUS and saves snapshots."]:
        py = bullet(c, v, xs[1] + 18, py, col - 36, CYAN)
        py -= 6

    panel(c, xs[2], y, col, h, "Results & Innovation", ORANGE)
    py = y + h - 58
    for v in ["Live bounding boxes, class names, confidence, and people count.", "Orange restricted zone makes the rule visible and adjustable.", "Transparent scoring uses measurable events - not judgments about appearance.", "Low-cost architecture: ESP32-CAM for capture, PC for AI inference."]:
        py = bullet(c, v, xs[2] + 18, py, col - 36, ORANGE)
        py -= 6

    # Flow
    panel(c, 48, 270, W - 96, 125, "System Workflow", CYAN)
    nodes = [(75, "ESP32-CAM", "Wi-Fi stream", TEAL), (286, "YOLO AI", "Objects + people", CYAN), (497, "RULE ENGINE", "Zone + loiter + crowd", ORANGE), (708, "DASHBOARD", "Video + score", GREEN), (919, "ALERT / SNAPSHOT", "Human review", RED)]
    for i, (x, label, sub, accent) in enumerate(nodes):
        node(c, x, 300, 165, label, sub, accent)
        if i < len(nodes) - 1:
            arrow(c, x + 168, 324, nodes[i + 1][0] - 5, 324)

    # bottom content
    panel(c, 48, 84, 445, 158, "Suspicion Scoring", ORANGE)
    text(c, "+30", 76, 183, 18, ORANGE, "Helvetica-Bold"); text(c, "Restricted-zone entry", 126, 188, 10.5)
    text(c, "+30", 76, 153, 18, ORANGE, "Helvetica-Bold"); text(c, "Loitering beyond configured time", 126, 158, 10.5)
    text(c, "+20", 76, 123, 18, ORANGE, "Helvetica-Bold"); text(c, "Crowding at or above threshold", 126, 128, 10.5)
    c.setFillColor(GREEN); c.roundRect(295, 176, 145, 23, 8, fill=1, stroke=0); text(c, "0-29  NORMAL", 310, 183, 9.5, NAVY, "Helvetica-Bold")
    c.setFillColor(ORANGE); c.roundRect(295, 145, 145, 23, 8, fill=1, stroke=0); text(c, "30-59  MONITOR", 303, 152, 9.5, NAVY, "Helvetica-Bold")
    c.setFillColor(RED); c.roundRect(295, 114, 145, 23, 8, fill=1, stroke=0); text(c, "60+  SUSPICIOUS", 301, 121, 9.5, white, "Helvetica-Bold")

    panel(c, 513, 84, 314, 158, "Applications", TEAL)
    py = 187
    for v in ["Classrooms and laboratories", "Offices, shops, and warehouses", "Restricted rooms and entry points", "Prototype for smart-campus safety"]:
        py = bullet(c, v, 536, py, 270); py -= 6

    panel(c, 847, 84, W - 895, 158, "Conclusion", GREEN)
    wrapped(c, "A practical, affordable surveillance model that converts an ESP32-CAM feed into real-time, explainable decision support. Alerts are designed to prompt human review, not automated accusations.", 870, 184, W - 940, 11)
    wrapped(c, "Future scope: multi-camera tracking, secure alerts, and stronger event models.", 870, 112, W - 940, 9.2, CYAN, "Helvetica-Bold", 11)

    text(c, "AI-BASED SMART SURVEILLANCE AND SUSPICIOUS ACTIVITY DETECTION", 48, 45, 9, MUTED, "Helvetica-Bold")
    text(c, "ESP32-CAM | YOLO | OpenCV | Flask", W - 280, 45, 9, MUTED)
    c.save()


if __name__ == "__main__":
    make()
