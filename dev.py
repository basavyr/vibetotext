#!/usr/bin/env python3
"""Dev runner with hot reload - restarts vibetotext when source files change."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

WATCH_DIR = Path(__file__).parent / "src" / "vibetotext"
EXTENSIONS = {".py"}
CHECK_INTERVAL = 1.0  # seconds


def get_mtimes():
    """Get modification times of all watched files."""
    mtimes = {}
    for path in WATCH_DIR.rglob("*"):
        if path.suffix in EXTENSIONS:
            try:
                mtimes[path] = path.stat().st_mtime
            except OSError:
                pass
    return mtimes


def run():
    """Run vibetotext with hot reload."""
    print("\n🔥 Hot reload enabled - watching for changes...")
    print("   Press Ctrl+C to exit\n")

    process = None
    last_mtimes = get_mtimes()

    def start_process():
        nonlocal process
        # Kill any stray UI processes
        subprocess.run(["pkill", "-9", "-f", "vibetotext_ui"],
                      capture_output=True)

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        process = subprocess.Popen(
            [sys.executable, "-m", "vibetotext"],
            env=env,
        )
        return process

    def stop_process():
        nonlocal process
        if process:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
            process = None
        # Also kill UI
        subprocess.run(["pkill", "-9", "-f", "vibetotext_ui"],
                      capture_output=True)

    def signal_handler(sig, frame):
        print("\n\nShutting down...")
        stop_process()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start initial process
    start_process()

    while True:
        time.sleep(CHECK_INTERVAL)

        # Check for changes
        current_mtimes = get_mtimes()

        changed = []
        for path, mtime in current_mtimes.items():
            if path not in last_mtimes or last_mtimes[path] != mtime:
                changed.append(path)

        if changed:
            print(f"\n🔄 Detected changes in: {', '.join(p.name for p in changed)}")
            print("   Restarting...\n")
            stop_process()
            time.sleep(0.5)
            start_process()
            last_mtimes = current_mtimes
        else:
            last_mtimes = current_mtimes


if __name__ == "__main__":
    run()
