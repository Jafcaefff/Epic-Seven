"""Non-blocking screenshot -> recognition -> API -> overlay loop."""

import sys
from pathlib import Path

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication

try:
    from .capture_stub import capture
    from .hero_recognizer import HeroRecognizer
    from .overlay_ui import Overlay
    from .recommender import Recommender
except ImportError:  # Allow ``python e7rta/client/main.py``.
    from capture_stub import capture
    from hero_recognizer import HeroRecognizer
    from overlay_ui import Overlay
    from recommender import Recommender

# Synthetic fixture positions. Replace with calibrated MuMu coordinates on Windows.
SLOT_RECTS = [(80 + index * 96, 170, 64, 64) for index in range(5)]
INTERVAL_MS = 1500


class DraftClient:
    def __init__(self, recognizer, recommender, overlay, capture_fn=capture):
        self.recognizer = recognizer
        self.recommender = recommender
        self.overlay = overlay
        self.capture_fn = capture_fn
        self.last_codes = None

    def tick(self):
        try:
            codes = self.recognizer.recognize_enemy_team(self.capture_fn(), SLOT_RECTS)
            if codes and codes != self.last_codes:
                result = self.recommender.recommend(codes, top=10)
                self.overlay.update_recommendations(result["recommendations"])
                self.last_codes = codes
        except Exception as exc:
            self.overlay.body.setText(f"客户端错误：{exc}")


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    overlay = Overlay()
    recognizer = HeroRecognizer(Path(__file__).with_name("templates"))
    client = DraftClient(recognizer, Recommender(), overlay)
    timer = QTimer()
    timer.timeout.connect(client.tick)
    timer.start(INTERVAL_MS)
    overlay.show()
    client.tick()
    # Keep Python references alive for the duration of the Qt event loop.
    overlay._client, overlay._timer = client, timer
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
