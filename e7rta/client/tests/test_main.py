from unittest.mock import Mock

from PIL import Image

from e7rta.client.main import DraftClient


def test_tick_only_requests_when_team_changes():
    recognizer = Mock()
    recognizer.recognize_enemy_team.return_value = ["c5154"]
    recommender = Mock()
    recommender.recommend.return_value = {"recommendations": [{"code": "c1168"}]}
    overlay = Mock()
    client = DraftClient(
        recognizer, recommender, overlay, capture_fn=lambda: Image.new("RGB", (1, 1))
    )

    client.tick()
    client.tick()

    recommender.recommend.assert_called_once_with(["c5154"], top=10)
    overlay.update_recommendations.assert_called_once()
