"""
ADB interface module for Candy Crush Saga bot.
Handles screenshot capture and touch input via adb.
"""

import subprocess
from io import BytesIO
from pathlib import Path
from PIL import Image

DEVICE_SERIAL = "AI9D6PGMW8DEEIJN"
SCREEN_W = 1220
SCREEN_H = 2712

# All intermediate files go here
WORKSPACE = Path(__file__).parent.parent.parent / "workspace" / "candy-crush-saga_playbot"
SCREENSHOT_DIR = WORKSPACE / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def _adb(*args):
    """Run an adb command with the configured device serial."""
    return subprocess.run(
        ["adb", "-s", DEVICE_SERIAL] + list(args),
        capture_output=True,
    )


def screenshot(save_as: str | None = None) -> Image.Image:
    """Capture the current screen and return as a PIL Image.

    Args:
        save_as: optional filename (no path) to save inside SCREENSHOT_DIR.
    """
    result = subprocess.check_output(
        ["adb", "-s", DEVICE_SERIAL, "exec-out", "screencap", "-p"]
    )
    img = Image.open(BytesIO(result))
    if save_as:
        img.save(SCREENSHOT_DIR / save_as)
    return img


def tap(x: int, y: int):
    """Simulate a tap at pixel coordinates (x, y)."""
    _adb("shell", "input", "tap", str(x), str(y))


def swipe(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 150):
    """Simulate a swipe from (x1,y1) to (x2,y2)."""
    _adb("shell", "input", "swipe",
         str(x1), str(y1), str(x2), str(y2), str(duration_ms))


def keyevent(key: str):
    """Send a keyevent (e.g. 'KEYCODE_BACK')."""
    _adb("shell", "input", "keyevent", key)


def current_activity() -> str:
    """Return the current foreground activity name."""
    result = _adb("shell", "dumpsys", "window")
    for line in result.stdout.decode(errors="replace").splitlines():
        if "mCurrentFocus" in line:
            return line.strip()
    return ""
