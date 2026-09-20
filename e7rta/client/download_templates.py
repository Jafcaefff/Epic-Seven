"""Download hero portrait templates from the E7 asset CDN."""

import json
from pathlib import Path
from urllib.request import urlopen

HERE = Path(__file__).parent
HERO_DATA = HERE.parent / "data/hero_static.json"
OUTPUT = HERE / "templates"
URL = "https://cdn.jsdelivr.net/gh/CeciliaBot/E7Assets-Temp@main/assets/face/{code}_s.png"


def download_all(output=OUTPUT):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    codes = sorted(json.loads(HERO_DATA.read_text(encoding="utf-8")))
    downloaded = skipped = failed = 0
    for code in codes:
        target = output / f"{code}.png"
        if target.exists():
            skipped += 1
            continue
        try:
            target.write_bytes(urlopen(URL.format(code=code), timeout=20).read())
            downloaded += 1
        except Exception as exc:
            failed += 1
            print(f"WARN {code}: {exc}")
    print(f"downloaded={downloaded} skipped={skipped} failed={failed}")
    return failed


if __name__ == "__main__":
    raise SystemExit(1 if download_all() else 0)
