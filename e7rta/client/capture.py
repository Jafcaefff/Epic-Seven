"""Capture E7 BP screen from MuMu 12 Pro via ADB screencap.

Usage:
    from capture import capture
    img = capture()                # PIL Image of current screen
    img = capture().resize((640, 360))  # optional resize for faster OCR

ADB endpoint: 127.0.0.1:5555 (MuMu 12 Pro default; MuMu 12 is 7555,
MuMu Pro old is 5555). Override via env var MUMU_ADB.

Output: PIL.Image.Image in RGB mode.

Notes:
    - `adb shell screencap -p` returns PNG bytes (~100ms latency).
    - Tested with MuMu 12 Pro on 2560x1440 window; game typically renders
      at 1920x1080 inside the window regardless of display resolution.
    - Set ADB path if adb.exe not in PATH (e.g. C:/MuMu/Hyper-V/tools/adb.exe).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from io import BytesIO

from PIL import Image


ADB_HOST = os.environ.get("MUMU_ADB", "127.0.0.1:5555")
ADB_BIN = os.environ.get("ADB_BIN", shutil.which("adb") or r"C:\MuMu\Hyper-V\tools\adb.exe")


def _run(cmd: list[str], timeout: float = 5.0) -> bytes:
    """Run subprocess, return stdout bytes. Raise if non-zero exit."""
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(
            f"adb failed: {' '.join(cmd)}\nstdout={proc.stdout.decode(errors='replace')[:200]}\n"
            f"stderr={proc.stderr.decode(errors='replace')[:200]}"
        )
    return proc.stdout


def connect() -> None:
    """Ensure ADB is connected to MuMu. Idempotent."""
    if not os.path.exists(ADB_BIN):
        raise FileNotFoundError(f"adb not found at {ADB_BIN}; set ADB_BIN env var")
    try:
        out = _run([ADB_BIN, "-s", ADB_HOST, "shell", "echo", "ok"], timeout=3.0)
        if b"ok" in out:
            return
    except (RuntimeError, subprocess.TimeoutExpired):
        pass
    # Try to connect
    _run([ADB_BIN, "connect", ADB_HOST], timeout=5.0)
    _run([ADB_BIN, "-s", ADB_HOST, "shell", "echo", "ok"], timeout=3.0)


def screencap_raw() -> bytes:
    """Run adb shell screencap and return PNG bytes."""
    connect()
    return _run(
        [ADB_BIN, "-s", ADB_HOST, "exec-out", "screencap", "-p"],
        timeout=10.0,
    )


def capture() -> Image.Image:
    """Capture the current MuMu screen as a PIL Image (RGB)."""
    png_bytes = screencap_raw()
    return Image.open(BytesIO(png_bytes)).convert("RGB")


def capture_resized(max_width: int = 1920) -> Image.Image:
    """Capture and resize so width <= max_width. Keeps aspect ratio."""
    img = capture()
    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    return img


def device_size() -> tuple[int, int]:
    """Return the device's physical screen resolution (w, h)."""
    connect()
    out = _run(
        [ADB_BIN, "-s", ADB_HOST, "shell", "wm", "size"],
        timeout=3.0,
    ).decode()
    # Output example: "Physical size: 1920x1080"
    for line in out.splitlines():
        if "size" in line.lower():
            wh = line.split(":", 1)[-1].strip()
            w, h = wh.lower().split("x")
            return int(w), int(h)
    raise RuntimeError(f"could not parse wm size: {out}")


def window_size() -> tuple[int, int]:
    """Return the MuMu window size on host (w, h) using ADB dumpsys."""
    connect()
    out = _run(
        [ADB_BIN, "-s", ADB_HOST, "shell", "dumpsys", "window"],
        timeout=3.0,
    ).decode()
    for line in out.splitlines():
        if "mUnrestricted" in line or "init=" in line and "x" in line:
            # mUnrestricted=1920x1080  (best-effort fallback)
            pass
    return device_size()


def benchmark(n: int = 5) -> float:
    """Measure average screencap latency (ms). Returns total elapsed / n."""
    times = []
    for _ in range(n):
        t0 = time.time()
        capture()
        times.append(time.time() - t0)
    avg = sum(times) / len(times)
    return avg * 1000


if __name__ == "__main__":
    print(f"ADB host: {ADB_HOST}")
    print(f"adb bin: {ADB_BIN}")
    w, h = device_size()
    print(f"Device size: {w}x{h}")
    img = capture()
    print(f"Captured: {img.size} {img.mode}")
    avg = benchmark(3)
    print(f"Screencap avg latency: {avg:.0f}ms (3 samples)")