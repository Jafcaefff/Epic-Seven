"""Non-blocking screenshot -> recognition -> API -> overlay loop.

Usage:
    python e7rta/client/main.py              # uses MuMu ADB (real capture)
    python e7rta/client/main.py --stub      # uses synthetic fixture
    python e7rta/client/main.py --interval 2000
"""
import argparse
import json
import sys
from pathlib import Path

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication

# Real ADB capture is the default on Windows; stub is for Mac dev / tests.
try:
    from .capture import capture as adb_capture
    from .hero_recognizer import HeroRecognizer
    from .overlay_ui import Overlay
    from .recommender import Recommender
except ImportError:  # Allow ``python e7rta/client/main.py``.
    from capture import capture as adb_capture
    from hero_recognizer import HeroRecognizer
    from overlay_ui import Overlay
    from recommender import Recommender

try:
    from .capture_stub import capture as stub_capture
except ImportError:
    from capture_stub import capture as stub_capture

HERE = Path(__file__).parent
SLOT_RECTS_FILE = HERE / "slot_rects.json"
DEFAULT_RECTS = [(80 + index * 96, 170, 64, 64) for index in range(5)]
INTERVAL_MS = 1500


def _load_slot_rects():
    if SLOT_RECTS_FILE.exists():
        try:
            return [tuple(rect) for rect in json.loads(SLOT_RECTS_FILE.read_text())]
        except Exception as exc:  # noqa: BLE001
            print(f"failed to load {SLOT_RECTS_FILE}: {exc}; using defaults")
    return DEFAULT_RECTS


class DraftClient:
    def __init__(self, recognizer, recommender, overlay, slot_rects, capture_fn):
        self.recognizer = recognizer
        self.recommender = recommender
        self.overlay = overlay
        self.slot_rects = slot_rects
        self.capture_fn = capture_fn
        self.last_codes = None

    def tick(self):
        try:
            codes = self.recognizer.recognize_enemy_team(self.capture_fn(), self.slot_rects)
            if codes and codes != self.last_codes:
                result = self.recommender.recommend(codes, top=10)
                self.overlay.update_recommendations(result["recommendations"])
                self.last_codes = codes
        except Exception as exc:
            self.overlay.body.setText(f"客户端错误：{exc}")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--stub", action="store_true", help="use synthetic fixture (Mac dev)")
    parser.add_argument("--interval", type=int, default=INTERVAL_MS, help="loop interval (ms)")
    args = parser.parse_args(argv)

    app = QApplication.instance() or QApplication(sys.argv)
    overlay = Overlay()
    recognizer = HeroRecognizer(HERE / "templates")
    capture_fn = stub_capture if args.stub else adb_capture
    client = DraftClient(recognizer, Recommender(), overlay,
                          slot_rects=_load_slot_rects(), capture_fn=capture_fn)
    timer = QTimer()
    timer.timeout.connect(client.tick)
    timer.start(args.interval)
    overlay.show()
    client.tick()
    overlay._client, overlay._timer = client, timer
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())