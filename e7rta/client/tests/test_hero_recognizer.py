from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from e7rta.client.hero_recognizer import HeroRecognizer


def _portrait(seed):
    rng = np.random.default_rng(seed)
    pixels = rng.integers(0, 255, (64, 64, 3), dtype=np.uint8)
    image = Image.fromarray(pixels, "RGB")
    ImageDraw.Draw(image).ellipse((12, 8, 52, 56), outline="white", width=4)
    return image


def test_recognize_known_images(tmp_path):
    codes = ["c5154", "c2124", "c1183"]
    templates = tmp_path / "templates"
    templates.mkdir()
    portraits = []
    for index, code in enumerate(codes):
        portrait = _portrait(index)
        portrait.save(templates / f"{code}.png")
        portraits.append(portrait)

    screen = Image.new("RGB", (640, 400), "#18202b")
    rects = [(80 + index * 96, 170, 64, 64) for index in range(3)]
    for portrait, (x, y, _, _) in zip(portraits, rects):
        screen.paste(portrait, (x, y))

    recognizer = HeroRecognizer(templates)
    assert recognizer.recognize_enemy_team(screen, rects) == codes


def test_invalid_or_empty_slot_returns_none(tmp_path):
    template = tmp_path / "templates"
    template.mkdir()
    _portrait(1).save(template / "c1001.png")
    recognizer = HeroRecognizer(template, threshold=0.95)
    screen = Image.new("RGB", (100, 100), "black")
    assert recognizer.recognize_slots(screen, [(-1, 0, 64, 64), (0, 0, 64, 64)]) == [None, None]
