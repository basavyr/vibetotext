"""Floating recording indicator with waveform - subprocess version."""

import json
import os
import subprocess
import sys
import tempfile
import time

# Path for IPC
_ipc_file = os.path.join(tempfile.gettempdir(), "vibetotext_ui_ipc.json")
_ui_process = None


# The UI script that runs in its own process
UI_SCRIPT = '''
import json
import os
import sys
import time

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
import pygame

IPC_FILE = sys.argv[1]

def main():
    pygame.init()

    width = 280
    height = 50

    screen = pygame.display.set_mode((width, height), pygame.NOFRAME)
    pygame.display.set_caption("")

    # Position at bottom center
    try:
        from pygame._sdl2 import Window
        window = Window.from_display_module()
        info = pygame.display.Info()
        x = (info.current_w - width) // 2
        y = info.current_h - height - 100
        window.position = (x, y)
    except:
        pass

    clock = pygame.time.Clock()
    bg_color = (26, 26, 26)
    bar_color = (255, 102, 153)

    levels = [0.0] * 30
    visible = False
    last_mtime = 0

    # Start hidden
    pygame.display.iconify()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break

        # Read IPC file
        try:
            if os.path.exists(IPC_FILE):
                mtime = os.path.getmtime(IPC_FILE)
                if mtime > last_mtime:
                    last_mtime = mtime
                    with open(IPC_FILE, "r") as f:
                        data = json.load(f)

                    if data.get("stop"):
                        running = False
                        break

                    if data.get("show") and not visible:
                        visible = True
                        pygame.display.set_mode((width, height), pygame.NOFRAME)
                        try:
                            from pygame._sdl2 import Window
                            window = Window.from_display_module()
                            info = pygame.display.Info()
                            x = (info.current_w - width) // 2
                            y = info.current_h - height - 100
                            window.position = (x, y)
                        except:
                            pass

                    if data.get("hide") and visible:
                        visible = False
                        pygame.display.iconify()

                    if "level" in data and visible:
                        levels = levels[1:] + [data["level"]]
        except:
            pass

        if visible:
            screen.fill(bg_color)

            bar_width = 6
            bar_spacing = 3
            num_bars = len(levels)
            total_width = num_bars * (bar_width + bar_spacing)
            start_x = (width - total_width) // 2 + 10
            center_y = height // 2

            for i, level in enumerate(levels):
                x = start_x + i * (bar_width + bar_spacing)
                bar_height = max(4, min(int(level * height * 0.7), int(height * 0.7)))
                y1 = center_y - bar_height // 2
                pygame.draw.rect(screen, bar_color, (x, y1, bar_width, bar_height))

            pygame.display.flip()

        clock.tick(33)

    pygame.quit()

    # Clean up IPC file
    try:
        os.remove(IPC_FILE)
    except:
        pass

if __name__ == "__main__":
    main()
'''


def _write_ipc(data):
    """Write data to IPC file."""
    try:
        with open(_ipc_file, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def _ensure_ui_process():
    """Start the UI process if not running."""
    global _ui_process

    if _ui_process is not None and _ui_process.poll() is None:
        return

    # Write the UI script to a temp file
    script_file = os.path.join(tempfile.gettempdir(), "vibetotext_ui.py")
    with open(script_file, "w") as f:
        f.write(UI_SCRIPT)

    # Clear any old IPC file
    if os.path.exists(_ipc_file):
        os.remove(_ipc_file)

    # Start the UI process
    _ui_process = subprocess.Popen(
        [sys.executable, script_file, _ipc_file],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def show_recording():
    """Show recording indicator."""
    _ensure_ui_process()
    _write_ipc({"show": True, "hide": False, "level": 0.0})


def hide_recording():
    """Hide recording indicator."""
    _write_ipc({"show": False, "hide": True})


def update_waveform(level):
    """Update waveform with audio level (0.0 to 1.0)."""
    _write_ipc({"show": True, "hide": False, "level": level})


def process_ui_events():
    """No-op for compatibility."""
    pass


def stop_ui():
    """Stop the UI process."""
    global _ui_process
    _write_ipc({"stop": True})
    if _ui_process is not None:
        try:
            _ui_process.terminate()
            _ui_process.wait(timeout=1)
        except Exception:
            pass
        _ui_process = None
