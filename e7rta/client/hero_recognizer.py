"""Recognize hero portraits in fixed draft-screen slots."""

from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image

SlotRect = Tuple[int, int, int, int]


class HeroRecognizer:
    """Cached OpenCV template matcher for hero portraits."""

    def __init__(self, templates_dir, threshold: float = 0.70, size=(64, 64)):
        self.templates_dir = Path(templates_dir)
        self.threshold = float(threshold)
        self.size = tuple(size)
        self.templates = self._load_templates()
        if not self.templates:
            raise ValueError(f"no hero templates found in {self.templates_dir}")

    def _load_templates(self):
        templates = {}
        for path in sorted(self.templates_dir.glob("c[0-9][0-9][0-9][0-9]*.png")):
            image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if image is None:
                continue
            templates[path.stem.removesuffix("_s")] = cv2.resize(
                image, self.size, interpolation=cv2.INTER_AREA
            )
        return templates

    def recognize_slots(
        self, image: Image.Image, slot_rects: Iterable[SlotRect]
    ) -> List[Optional[str]]:
        """Return one code (or ``None``) for every supplied slot."""
        gray = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
        height, width = gray.shape[:2]
        results: List[Optional[str]] = []
        for x, y, w, h in slot_rects:
            if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > width or y + h > height:
                results.append(None)
                continue
            roi = gray[y : y + h, x : x + w]
            roi = cv2.resize(roi, self.size, interpolation=cv2.INTER_AREA)
            best_code, best_score = None, -1.0
            for code, template in self.templates.items():
                score = float(
                    cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)[0, 0]
                )
                if score > best_score:
                    best_code, best_score = code, score
            results.append(best_code if best_score >= self.threshold else None)
        return results

    def recognize_enemy_team(
        self, image: Image.Image, slot_rects: Iterable[SlotRect]
    ) -> List[str]:
        """Return recognized codes in slot order, omitting empty slots."""
        return [code for code in self.recognize_slots(image, slot_rects) if code]


def recognize_enemy_team(
    image: Image.Image,
    slot_rects: Sequence[SlotRect],
    templates_dir=None,
    threshold: float = 0.70,
) -> List[str]:
    """Convenience wrapper used by small integrations and examples."""
    if templates_dir is None:
        templates_dir = Path(__file__).with_name("templates")
    return HeroRecognizer(templates_dir, threshold).recognize_enemy_team(image, slot_rects)
