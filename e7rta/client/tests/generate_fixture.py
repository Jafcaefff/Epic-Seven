"""Build a deterministic mock BP screenshot from downloaded templates."""

from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
TEMPLATES = HERE.parent / "templates"
OUTPUT = HERE / "fixtures/synthetic_enemy_team.png"
CODES = ["c5154", "c2124", "c1183"]
RECTS = [(80 + index * 96, 170, 64, 64) for index in range(5)]


def generate():
    screen = Image.new("RGB", (640, 400), "#18202b")
    for code, (x, y, w, h) in zip(CODES, RECTS):
        path = TEMPLATES / f"{code}.png"
        if not path.exists():
            raise FileNotFoundError(f"missing {path}; run download_templates.py first")
        portrait = Image.open(path).convert("RGB").resize((w, h), Image.Resampling.LANCZOS)
        screen.paste(portrait, (x, y))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    screen.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    generate()
