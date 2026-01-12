"""Floating recording indicator with waveform - pure PyObjC NSPanel version."""

import json
import os
import subprocess
import sys
import tempfile

# Path for IPC
_ipc_file = os.path.join(tempfile.gettempdir(), "vibetotext_ui_ipc.json")
_ui_process = None


# The UI script that runs in its own process - uses native NSPanel
UI_SCRIPT = '''
import json
import os
import sys
import time

# PyObjC imports
from AppKit import (
    NSApplication, NSApp, NSPanel, NSView, NSColor, NSBezierPath,
    NSBackingStoreBuffered, NSMakeRect, NSFloatingWindowLevel,
    NSWindowStyleMaskBorderless, NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorStationary, NSTimer, NSRunLoop,
    NSDefaultRunLoopMode
)
from Foundation import NSObject
from Quartz import kCGMaximumWindowLevelKey, CGWindowLevelForKey
import objc

IPC_FILE = sys.argv[1]


class WaveformView(NSView):
    """Custom view that draws the waveform."""

    def initWithFrame_(self, frame):
        self = objc.super(WaveformView, self).initWithFrame_(frame)
        if self:
            self.levels = [0.0] * 25  # 25 bars
            self.recording = False
        return self

    def setLevels_recording_(self, levels, recording):
        self.levels = list(levels)  # Make a copy
        self.recording = recording
        self.setNeedsDisplay_(True)

    def drawRect_(self, rect):
        # Draw rounded background
        NSColor.colorWithCalibratedRed_green_blue_alpha_(0.1, 0.1, 0.1, 0.95).set()
        path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, 8, 8)
        path.fill()

        width = rect.size.width
        height = rect.size.height
        bar_width = 4
        bar_spacing = 4
        num_bars = 25
        total_width = num_bars * bar_width + (num_bars - 1) * bar_spacing
        start_x = (width - total_width) / 2
        center_y = height / 2

        if self.recording:
            # Pink color for recording
            NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 0.4, 0.6, 1.0).set()
            for i in range(num_bars):
                level = self.levels[i] if i < len(self.levels) else 0.0
                x = start_x + i * (bar_width + bar_spacing)
                # Bar height based on level, minimum 4px
                bar_height = max(4, level * height * 0.75)
                bar_height = min(bar_height, height * 0.8)
                y = center_y - bar_height / 2
                bar_path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                    NSMakeRect(x, y, bar_width, bar_height), 2, 2
                )
                bar_path.fill()
        else:
            # Gray color for idle - flat line
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.35, 0.35, 0.35, 1.0).set()
            for i in range(num_bars):
                x = start_x + i * (bar_width + bar_spacing)
                bar_path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                    NSMakeRect(x, center_y - 2, bar_width, 4), 2, 2
                )
                bar_path.fill()


class AppDelegate(NSObject):
    def init(self):
        self = objc.super(AppDelegate, self).init()
        if self:
            self.levels = [0.0] * 25  # Match WaveformView
            self.recording = False
            self.last_mtime = 0
            self.panel = None
            self.waveform_view = None
        return self

    def applicationDidFinishLaunching_(self, notification):
        # Create floating panel
        width = 280
        height = 40

        self.panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(100, 100, width, height),
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False
        )

        # Set as floating panel - VERY HIGH level
        self.panel.setLevel_(CGWindowLevelForKey(kCGMaximumWindowLevelKey))
        self.panel.setFloatingPanel_(True)
        self.panel.setHidesOnDeactivate_(False)
        self.panel.setCanHide_(False)

        # Visible on all spaces, stationary (not affected by Expose)
        self.panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces |
            NSWindowCollectionBehaviorStationary
        )

        # Transparent background, non-opaque
        self.panel.setOpaque_(False)
        self.panel.setBackgroundColor_(NSColor.clearColor())

        # Create waveform view
        self.waveform_view = WaveformView.alloc().initWithFrame_(
            NSMakeRect(0, 0, width, height)
        )
        self.panel.setContentView_(self.waveform_view)

        # Show the panel
        self.panel.orderFrontRegardless()

        # Start update timer
        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.033,  # ~30fps
            self,
            "update:",
            None,
            True
        )

    def update_(self, timer):
        # Read IPC file every tick (don't rely on mtime which has low resolution)
        try:
            if os.path.exists(IPC_FILE):
                with open(IPC_FILE, "r") as f:
                    data = json.load(f)

                if data.get("stop"):
                    NSApp.terminate_(None)
                    return

                was_recording = self.recording
                self.recording = data.get("recording", False)

                # Position when recording starts
                if self.recording and not was_recording:
                    screen_x = data.get("screen_x", 0)
                    screen_y = data.get("screen_y", 0)
                    screen_w = data.get("screen_w", 1920)
                    width = 280
                    height = 40
                    # Center horizontally on the screen
                    new_x = screen_x + (screen_w - width) // 2
                    # Position 40px from bottom of screen
                    new_y = screen_y + 40

                    # Position and bring to front
                    self.panel.setFrameOrigin_((new_x, new_y))
                    self.panel.orderFrontRegardless()

                # Update frequency band levels with decay
                if "levels" in data and self.recording:
                    new_levels = data["levels"]
                    # Smooth transition: rise fast, fall faster
                    for i in range(len(self.levels)):
                        if i < len(new_levels):
                            if new_levels[i] > self.levels[i]:
                                self.levels[i] = new_levels[i]  # Rise instantly
                            else:
                                self.levels[i] = self.levels[i] * 0.4 + new_levels[i] * 0.6  # Decay faster
                elif self.recording:
                    # No new data but still recording - decay towards zero
                    self.levels = [l * 0.5 for l in self.levels]
                else:
                    # Not recording - reset to zero
                    self.levels = [0.0] * 25

                # Update view
                self.waveform_view.setLevels_recording_(list(self.levels), self.recording)
        except Exception as e:
            pass


def main():
    app = NSApplication.sharedApplication()
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.setActivationPolicy_(2)  # NSApplicationActivationPolicyAccessory - no dock icon
    app.run()


if __name__ == "__main__":
    main()
'''


def _get_cursor_and_screen():
    """Get cursor position and screen bounds using Quartz."""
    try:
        from Quartz import CGEventCreate, CGEventGetLocation
        from AppKit import NSScreen

        # Get cursor position
        event = CGEventCreate(None)
        pos = CGEventGetLocation(event)
        cursor_x, cursor_y = int(pos.x), int(pos.y)

        # Find which screen the cursor is on
        for screen in NSScreen.screens():
            frame = screen.frame()
            if (frame.origin.x <= cursor_x <= frame.origin.x + frame.size.width and
                frame.origin.y <= cursor_y <= frame.origin.y + frame.size.height):
                return {
                    "screen_x": int(frame.origin.x),
                    "screen_y": int(frame.origin.y),
                    "screen_w": int(frame.size.width),
                    "screen_h": int(frame.size.height),
                }

        # Fallback to main screen
        main = NSScreen.mainScreen().frame()
        return {
            "screen_x": int(main.origin.x),
            "screen_y": int(main.origin.y),
            "screen_w": int(main.size.width),
            "screen_h": int(main.size.height),
        }
    except Exception:
        return {"screen_x": 0, "screen_y": 0, "screen_w": 1920, "screen_h": 1080}


def _write_ipc(data):
    """Write data to IPC file atomically."""
    try:
        # Write to temp file first, then rename (atomic)
        tmp_file = _ipc_file + ".tmp"
        with open(tmp_file, "w") as f:
            json.dump(data, f)
        os.replace(tmp_file, _ipc_file)  # Atomic rename
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

    # Start the UI process with error logging
    error_log = os.path.join(tempfile.gettempdir(), "vibetotext_ui_error.log")
    with open(error_log, "w") as err_file:
        _ui_process = subprocess.Popen(
            [sys.executable, script_file, _ipc_file],
            stdout=subprocess.PIPE,
            stderr=err_file,
        )


def show_recording():
    """Show recording indicator at bottom center of screen."""
    _ensure_ui_process()
    screen_info = _get_cursor_and_screen()
    _write_ipc({
        "recording": True,
        "level": 0.0,
        **screen_info,
    })


def hide_recording():
    """Switch to idle state (flat line, don't hide)."""
    _write_ipc({"recording": False})


_update_counter = 0

def update_waveform(levels):
    """Update waveform with frequency band levels (list of 0.0 to 1.0)."""
    global _update_counter
    _update_counter += 1
    # Include counter so UI can detect changes even when mtime doesn't update
    _write_ipc({"recording": True, "levels": levels, "seq": _update_counter})


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
