#!/usr/bin/env python3
"""Cross-platform floating waveform indicator using tkinter."""

import json
import os
import sys
import tkinter as tk
from tkinter import Canvas

IPC_FILE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.environ.get("TEMP", os.environ.get("TMPDIR", "/tmp")),
    "vibetotext_ui_ipc.json"
)


class WaveformWindow:
    """Floating waveform indicator window."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("")

        # Window dimensions
        self.width = 140
        self.height = 20

        # Configure window for floating overlay
        self.root.overrideredirect(True)  # Remove window decorations
        self.root.attributes("-topmost", True)  # Always on top
        self.root.attributes("-alpha", 0.95)  # Slightly transparent

        # Try to make window click-through on Windows
        if sys.platform == "win32":
            try:
                self.root.attributes("-transparentcolor", "black")
            except tk.TclError:
                pass

        # Set initial position (bottom center of screen)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - self.width) // 2
        y = screen_h - self.height - 40
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")

        # Dark background
        self.root.configure(bg="#1a1a1a")

        # Canvas for drawing waveform
        self.canvas = Canvas(
            self.root,
            width=self.width,
            height=self.height,
            bg="#1a1a1a",
            highlightthickness=0
        )
        self.canvas.pack()

        # State
        self.levels = [0.0] * 25
        self.recording = False
        self.last_data = {}

        # Start update loop
        self.update()

    def update(self):
        """Update waveform from IPC file."""
        try:
            if os.path.exists(IPC_FILE):
                with open(IPC_FILE, "r") as f:
                    data = json.load(f)

                if data.get("stop"):
                    self.root.quit()
                    return

                was_recording = self.recording
                self.recording = data.get("recording", False)

                # Reposition when recording starts
                if self.recording and not was_recording:
                    screen_x = data.get("screen_x", 0)
                    screen_y = data.get("screen_y", 0)
                    screen_w = data.get("screen_w", self.root.winfo_screenwidth())
                    screen_h = data.get("screen_h", self.root.winfo_screenheight())

                    # Center horizontally, 20px from bottom
                    x = screen_x + (screen_w - self.width) // 2
                    y = screen_y + screen_h - self.height - 40

                    # On macOS, y is from bottom; on Windows, from top
                    if sys.platform == "darwin":
                        y = screen_y + 20

                    self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")
                    self.root.deiconify()
                    self.root.lift()

                # Update levels with decay
                if "levels" in data and self.recording:
                    new_levels = data["levels"]
                    for i in range(len(self.levels)):
                        if i < len(new_levels):
                            if new_levels[i] > self.levels[i]:
                                self.levels[i] = new_levels[i]
                            else:
                                self.levels[i] = self.levels[i] * 0.86 + new_levels[i] * 0.14
                elif self.recording:
                    self.levels = [l * 0.9 for l in self.levels]
                else:
                    self.levels = [0.0] * 25

                self.draw_waveform()

        except Exception:
            pass

        # Schedule next update (~30fps)
        self.root.after(33, self.update)

    def draw_waveform(self):
        """Draw the waveform bars."""
        self.canvas.delete("all")

        # Draw rounded background
        self.canvas.create_rectangle(
            0, 0, self.width, self.height,
            fill="#1a1a1a", outline=""
        )

        bar_width = 2
        bar_spacing = 2
        num_bars = 25
        total_width = num_bars * bar_width + (num_bars - 1) * bar_spacing
        start_x = (self.width - total_width) / 2
        center_y = self.height / 2

        if self.recording:
            # Pink color for recording
            color = "#ff6699"
            for i in range(num_bars):
                level = self.levels[i] if i < len(self.levels) else 0.0
                x = start_x + i * (bar_width + bar_spacing)
                # Bar height based on level, minimum 2px
                bar_height = max(2, level * self.height * 0.75)
                bar_height = min(bar_height, self.height * 0.8)
                y1 = center_y - bar_height / 2
                y2 = center_y + bar_height / 2
                self.canvas.create_rectangle(
                    x, y1, x + bar_width, y2,
                    fill=color, outline=""
                )
        else:
            # Gray color for idle - flat line
            color = "#595959"
            for i in range(num_bars):
                x = start_x + i * (bar_width + bar_spacing)
                self.canvas.create_rectangle(
                    x, center_y - 1, x + bar_width, center_y + 1,
                    fill=color, outline=""
                )

    def run(self):
        """Start the tkinter main loop."""
        self.root.mainloop()


def main():
    window = WaveformWindow()
    window.run()


if __name__ == "__main__":
    main()
