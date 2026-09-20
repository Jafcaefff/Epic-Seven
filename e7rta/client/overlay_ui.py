"""Always-on-top recommendation overlay."""

import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget


class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("第七史诗 BP 推荐")
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.9)
        self.setFixedWidth(430)

        self.title = QLabel("实时 BP 推荐")
        self.title.setObjectName("title")
        self.body = QLabel("等待识别敌方阵容…")
        self.body.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(10)
        layout.addWidget(self.title)
        layout.addWidget(self.body)
        self.setStyleSheet(
            "QWidget { background: rgba(10, 12, 18, 225); color: #f7f7f7; "
            "border-radius: 12px; font-size: 14px; }"
            "QLabel#title { color: #ffd34d; font-size: 18px; font-weight: 700; }"
        )

    def update_recommendations(self, recommendations):
        lines = []
        for index, rec in enumerate(recommendations[:10], 1):
            score = round(float(rec.get("score", 0)) * 100)
            lineup = rec.get("lineup")
            if lineup:
                evidence = (
                    f"vs 阵容{lineup.get('size', '?')}人 "
                    f"{float(lineup.get('wr', 0)):.1f}% · {lineup.get('games', 0)}场"
                )
            else:
                evidence = f"对位 {float(rec.get('counter_score', 0)):.1f}%"
            lines.append(f"{index:>2}. {rec.get('name', rec.get('code', '未知'))}  推{score}  {evidence}")
        self.body.setText("\n\n".join(lines) if lines else "暂无推荐")
        self.adjustSize()

    # Compatibility with the name used by the integration guide.
    update_recs = update_recommendations


def _demo():
    app = QApplication.instance() or QApplication(sys.argv)
    overlay = Overlay()
    overlay.update_recommendations(
        [{"name": "利纳柯", "score": 0.82, "counter_score": 68.3, "lineup": None}]
    )
    overlay.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(_demo())
