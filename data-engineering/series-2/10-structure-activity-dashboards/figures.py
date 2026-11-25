"""Make the figure of Module 10 (figures/dashboard.png): a screenshot of the running dashboard.

Usage (from the series folder, after running the lesson, so that work/dashboard.py and the
published warehouse exist; needs Google Chrome or Chromium):
    uv run python 10-structure-activity-dashboards/figures.py

It starts the app with `streamlit run` and drives headless Chrome through its DevTools protocol
(with the `websockets` package, which Streamlit already installs): open the page, wait until the
metrics and both charts are drawn, take a screenshot. A Streamlit page fills itself in after it
loads, so Chrome's plain --screenshot would only catch the empty page. The PNG is committed, so the
course site builds without running anything.
"""

from __future__ import annotations

import asyncio
import base64
import itertools
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from websockets.asyncio.client import connect

HERE = Path(__file__).parent
OUT = HERE / "figures" / "dashboard.png"
APP_PORT, CHROME_PORT = 8599, 9333
WIDTH, HEIGHT = 1400, 1300
READY = (  # JavaScript that is true once the page is drawn: four metrics and two charts
    "document.querySelectorAll('[data-testid=stMetric]').length === 4 && "
    "document.querySelectorAll('canvas, svg.marks').length >= 2"
)
CHROMES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome",
    "chromium",
]


def chrome() -> str:
    """The path of a Chrome or Chromium on this computer.

    Returns:
        The executable.

    Raises:
        FileNotFoundError: If none is installed.
    """
    for candidate in CHROMES:
        if Path(candidate).exists() or shutil.which(candidate):
            return candidate
    raise FileNotFoundError("Chrome or Chromium is needed for the screenshot")


def wait_for(url: str, seconds: int = 60) -> bytes:
    """Fetch a URL, retrying until it answers.

    Args:
        url: The address.
        seconds: How long to keep trying.

    Returns:
        The answer's body.

    Raises:
        TimeoutError: If it never answered.
    """
    for _ in range(seconds):
        try:
            return urllib.request.urlopen(url, timeout=2).read()
        except OSError:
            time.sleep(1)
    raise TimeoutError(url)


async def screenshot(page_ws: str) -> bytes:
    """Open the app in a Chrome tab, wait until it is drawn and capture it.

    Args:
        page_ws: The tab's DevTools websocket address.

    Returns:
        The PNG.
    """
    ws = await connect(page_ws, max_size=100 * 2**20)
    ids = itertools.count(1)

    async def call(method: str, **params) -> dict:
        """Send one DevTools command and wait for its answer."""
        number = next(ids)
        await ws.send(json.dumps({"id": number, "method": method, "params": params}))
        while True:
            message = json.loads(await ws.recv())
            if message.get("id") == number:
                return message.get("result", {})

    await call("Emulation.setDeviceMetricsOverride", width=WIDTH, height=HEIGHT,
               deviceScaleFactor=1, mobile=False)  # fmt: skip
    await call("Page.navigate", url=f"http://localhost:{APP_PORT}")
    for _ in range(120):
        result = await call("Runtime.evaluate", expression=READY)
        if result.get("result", {}).get("value"):
            break
        await asyncio.sleep(0.5)
    await asyncio.sleep(2)  # let the charts finish drawing
    shot = await call("Page.captureScreenshot", format="png")
    await ws.close()
    return base64.b64decode(shot["data"])


def main() -> None:
    """Start the app and Chrome, screenshot the app, stop both."""
    app = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "work/dashboard.py", "--server.headless",
         "true", "--server.port", str(APP_PORT), "--browser.gatherUsageStats", "false"],
        cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )  # fmt: skip
    with tempfile.TemporaryDirectory() as profile:
        browser = subprocess.Popen(
            [chrome(), "--headless=new", "--hide-scrollbars", f"--user-data-dir={profile}",
             f"--remote-debugging-port={CHROME_PORT}", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )  # fmt: skip
        try:
            wait_for(f"http://localhost:{APP_PORT}/_stcore/health")
            tabs = json.loads(wait_for(f"http://localhost:{CHROME_PORT}/json"))
            page = next(tab for tab in tabs if tab["type"] == "page")
            png = asyncio.run(screenshot(page["webSocketDebuggerUrl"]))
            OUT.parent.mkdir(exist_ok=True)
            OUT.write_bytes(png)
            print(f"wrote {OUT.relative_to(HERE)}")
        finally:
            browser.terminate()
            app.terminate()
            browser.wait(timeout=30)


if __name__ == "__main__":
    main()
