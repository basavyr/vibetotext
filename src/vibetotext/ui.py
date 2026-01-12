"""Floating recording indicator with waveform - subprocess version."""

import json
import os
import subprocess
import sys
import tempfile

# Path for IPC
_ipc_file = os.path.join(tempfile.gettempdir(), "vibetotext_ui_ipc.json")
_ui_process = None


# The UI script that runs in its own process
UI_SCRIPT = '''
import json
import os
import sys

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
import pygame

IPC_FILE = sys.argv[1]

def main():
    pygame.init()

    width = 280
    height = 50

    screen = pygame.display.set_mode((width, height), pygame.NOFRAME)
    pygame.display.set_caption("")

    # Get window handle for positioning
    try:
        from pygame._sdl2 import Window
        window = Window.from_display_module()
    except:
        window = None

    clock = pygame.time.Clock()
    bg_color = (26, 26, 26)
    bar_color = (255, 102, 153)  # Pink when recording
    idle_color = (80, 80, 80)    # Gray when idle

    levels = [0.0] * 30
    recording = False
    last_mtime = 0

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

                    # Update recording state
                    recording = data.get("recording", False)

                    # Position window near cursor when recording starts
                    if window and "cursor_x" in data and "cursor_y" in data:
                        cx = data["cursor_x"]
                        cy = data["cursor_y"]
                        # Position below cursor, centered horizontally
                        new_x = cx - width // 2
                        new_y = cy + 60  # 60px below cursor
                        window.position = (new_x, new_y)

                    # Update levels if recording
                    if "level" in data and recording:
                        levels = levels[1:] + [data["level"]]
        except:
            pass

        # Always draw - waveform when recording, flat line when idle
        screen.fill(bg_color)

        bar_width = 6
        bar_spacing = 3
        num_bars = len(levels)
        total_width = num_bars * (bar_width + bar_spacing)
        start_x = (width - total_width) // 2 + 10
        center_y = height // 2

        if recording:
            # Animated waveform
            for i, level in enumerate(levels):
                x = start_x + i * (bar_width + bar_spacing)
                bar_height = max(4, min(int(level * height * 0.7), int(height * 0.7)))
                y1 = center_y - bar_height // 2
                pygame.draw.rect(screen, bar_color, (x, y1, bar_width, bar_height))
        else:
            # Flat idle line
            for i in range(num_bars):
                x = start_x + i * (bar_width + bar_spacing)
                pygame.draw.rect(screen, idle_color, (x, center_y - 2, bar_width, 4))

        pygame.display.flip()
        clock.tick(33)

    pygame.quit()

    try:
        os.remove(IPC_FILE)
    except:
        pass

if __name__ == "__main__":
    main()
'''


def _get_cursor_position():
    """Get current cursor position using Quartz."""
    try:
        from Quartz import CGEventCreate, CGEventGetLocation
        event = CGEventCreate(None)
        pos = CGEventGetLocation(event)
        return int(pos.x), int(pos.y)
    except Exception:
        return 500, 500  # Fallback


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
    """Show recording indicator near cursor."""
    _ensure_ui_process()
    cx, cy = _get_cursor_position()
    _write_ipc({
        "recording": True,
        "level": 0.0,
        "cursor_x": cx,
        "cursor_y": cy,
    })


def hide_recording():
    """Switch to idle state (flat line, don't hide)."""
    _write_ipc({"recording": False})


def update_waveform(level):
    """Update waveform with audio level (0.0 to 1.0)."""
    _write_ipc({"recording": True, "level": level})


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
