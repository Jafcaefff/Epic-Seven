"""Development capture source; Windows will replace this with MuMu ADB capture."""

from pathlib import Path

from PIL import Image


def capture(path=None):
    fixture = Path(path) if path else Path(__file__).parent / "tests/fixtures/synthetic_enemy_team.png"
    if not fixture.exists():
        raise FileNotFoundError(
            f"missing fixture {fixture}; run client/download_templates.py and the fixture generator"
        )
    return Image.open(fixture).convert("RGB")
