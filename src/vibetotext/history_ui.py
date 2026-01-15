"""History viewer UI - native macOS window."""

import json
import os
import subprocess
import sys
import tempfile

# Path for IPC
_history_ipc_file = os.path.join(tempfile.gettempdir(), "vibetotext_history_ipc.json")
_history_ui_process = None

# The History UI script that runs in its own process
HISTORY_UI_SCRIPT = '''
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# PyObjC imports
from AppKit import (
    NSApplication, NSApp, NSWindow, NSView, NSColor, NSFont,
    NSBackingStoreBuffered, NSMakeRect, NSWindowStyleMaskTitled,
    NSWindowStyleMaskClosable, NSWindowStyleMaskResizable,
    NSTimer, NSTextField, NSScrollView, NSTextView,
    NSBezelBorder, NSLayoutAttributeWidth, NSLayoutAttributeHeight,
    NSPopUpButton, NSBox,
)
from Foundation import NSObject, NSAttributedString, NSMutableAttributedString
from Foundation import NSForegroundColorAttributeName, NSFontAttributeName
import objc

IPC_FILE = sys.argv[1]
HISTORY_FILE = Path.home() / ".vibetotext" / "history.json"
CONFIG_FILE = Path.home() / ".vibetotext" / "config.json"


def get_audio_devices():
    """Get list of input audio devices."""
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_devices = []
        default_idx = sd.default.device[0]
        for i, dev in enumerate(devices):
            if dev['max_input_channels'] > 0:
                is_default = (i == default_idx)
                input_devices.append({
                    'index': i,
                    'name': dev['name'],
                    'is_default': is_default,
                })
        return input_devices
    except Exception:
        return []


def load_config():
    """Load config from disk."""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_config(config):
    """Save config to disk."""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass

# Stopwords for statistics (same as history.py)
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "shall", "can", "need",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
    "my", "your", "his", "its", "our", "their", "this", "that", "these",
    "what", "which", "who", "where", "when", "why", "how", "all", "each",
    "some", "no", "not", "only", "so", "than", "too", "very", "just",
    "also", "now", "here", "there", "then", "if", "because", "about",
    "any", "up", "down", "out", "off", "over", "going", "gonna", "like",
    "okay", "ok", "yeah", "yes", "um", "uh", "ah", "oh", "well", "right",
    "actually", "basically", "really", "thing", "things", "something",
}


def load_history():
    """Load history from disk."""
    try:
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {"entries": []}


def get_statistics(entries):
    """Compute statistics from entries."""
    if not entries:
        return {"total_words": 0, "total_sessions": 0, "common_words": []}

    total_words = sum(e.get("word_count", len(e["text"].split())) for e in entries)
    total_sessions = len(entries)

    # Word frequency
    from collections import Counter
    all_words = []
    for entry in entries:
        words = entry["text"].lower().split()
        words = [w.strip(".,!?;:\\'\\\"()[]{}") for w in words]
        words = [w for w in words if w and len(w) > 2 and w not in STOPWORDS]
        all_words.extend(words)

    word_counts = Counter(all_words)
    common_words = word_counts.most_common(10)

    return {
        "total_words": total_words,
        "total_sessions": total_sessions,
        "common_words": common_words,
    }


class HistoryWindow(NSObject):
    def init(self):
        self = objc.super(HistoryWindow, self).init()
        if self:
            self.window = None
            self.visible = False
            self.text_view = None
            self.mic_dropdown = None
            self.audio_devices = []
        return self

    def applicationDidFinishLaunching_(self, notification):
        # Create window
        width = 450
        height = 550

        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(100, 100, width, height),
            NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskResizable,
            NSBackingStoreBuffered,
            False
        )

        self.window.setTitle_("Transcription History")
        self.window.setMinSize_((350, 400))

        # Dark background
        self.window.setBackgroundColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.12, 0.12, 0.14, 1.0)
        )

        # Create microphone label
        mic_label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(15, height - 40, 85, 20)
        )
        mic_label.setStringValue_("Microphone:")
        mic_label.setBezeled_(False)
        mic_label.setDrawsBackground_(False)
        mic_label.setEditable_(False)
        mic_label.setSelectable_(False)
        mic_label.setTextColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.8, 0.8, 0.8, 1.0)
        )
        mic_label.setFont_(NSFont.systemFontOfSize_(12.0))
        self.window.contentView().addSubview_(mic_label)

        # Create microphone dropdown
        self.mic_dropdown = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(100, height - 42, width - 115, 24), False
        )
        self.audio_devices = get_audio_devices()
        config = load_config()
        saved_device = config.get("audio_device_index")

        selected_idx = 0
        for i, dev in enumerate(self.audio_devices):
            name = dev['name']
            if dev['is_default']:
                name += " (System Default)"
            self.mic_dropdown.addItemWithTitle_(name)
            if saved_device is not None and dev['index'] == saved_device:
                selected_idx = i

        if self.audio_devices:
            self.mic_dropdown.selectItemAtIndex_(selected_idx)

        self.mic_dropdown.setTarget_(self)
        self.mic_dropdown.setAction_("microphoneChanged:")
        self.window.contentView().addSubview_(self.mic_dropdown)

        # Create scroll view with text view (below the dropdown)
        scroll_view = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(15, 15, width - 30, height - 60)
        )
        scroll_view.setHasVerticalScroller_(True)
        scroll_view.setBorderType_(NSBezelBorder)
        scroll_view.setAutoresizingMask_(18)  # Width + Height flexible

        # Create text view for content
        content_size = scroll_view.contentSize()
        self.text_view = NSTextView.alloc().initWithFrame_(
            NSMakeRect(0, 0, content_size.width, content_size.height)
        )
        self.text_view.setMinSize_((0, content_size.height))
        self.text_view.setMaxSize_((10000, 10000))
        self.text_view.setVerticallyResizable_(True)
        self.text_view.setHorizontallyResizable_(False)
        self.text_view.setAutoresizingMask_(2)  # Width flexible
        self.text_view.textContainer().setWidthTracksTextView_(True)
        self.text_view.setEditable_(False)
        self.text_view.setSelectable_(True)
        self.text_view.setBackgroundColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.08, 0.08, 0.1, 1.0)
        )
        self.text_view.setTextColor_(NSColor.whiteColor())

        scroll_view.setDocumentView_(self.text_view)
        self.window.contentView().addSubview_(scroll_view)

        # Center window on screen
        self.window.center()

        # Load and display content
        self.refresh_content()

        # Start IPC timer
        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.1, self, "checkIPC:", None, True
        )

        # Handle window close
        self.window.setDelegate_(self)

    def windowWillClose_(self, notification):
        """Called when window is closed via X button."""
        self.visible = False
        # Write to IPC that we're hidden
        try:
            with open(IPC_FILE, "w") as f:
                json.dump({"visible": False}, f)
        except Exception:
            pass

    def microphoneChanged_(self, sender):
        """Called when microphone dropdown selection changes."""
        idx = sender.indexOfSelectedItem()
        if 0 <= idx < len(self.audio_devices):
            device = self.audio_devices[idx]
            config = load_config()
            config["audio_device_index"] = device['index']
            config["audio_device_name"] = device['name']
            save_config(config)

    def refresh_content(self):
        """Refresh the history display."""
        data = load_history()
        entries = sorted(data.get("entries", []), key=lambda x: x.get("timestamp", ""), reverse=True)
        stats = get_statistics(entries)

        # Build content string
        content = []

        # Statistics header
        content.append("=" * 50)
        content.append("                    STATISTICS")
        content.append("=" * 50)
        content.append("")
        content.append(f"  Total Chats:     {stats['total_sessions']}")
        content.append(f"  Total Words:     {stats['total_words']}")
        content.append("")

        if stats["common_words"]:
            content.append("  Most Common Words:")
            for word, count in stats["common_words"][:10]:
                content.append(f"    {word}: {count}")

        content.append("")
        content.append("=" * 50)
        content.append("                 RECENT TRANSCRIPTIONS")
        content.append("=" * 50)
        content.append("")

        # Entries
        for entry in entries[:50]:  # Show last 50
            timestamp = entry.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(timestamp)
                time_str = dt.strftime("%b %d, %I:%M %p")
            except Exception:
                time_str = timestamp[:16] if timestamp else "Unknown"

            mode = entry.get("mode", "transcribe").upper()
            word_count = entry.get("word_count", len(entry.get("text", "").split()))
            text = entry.get("text", "")

            # Truncate long text
            preview = text[:200] + "..." if len(text) > 200 else text

            content.append(f"[{time_str}] [{mode}] ({word_count} words)")
            content.append(f"  {preview}")
            content.append("")

        if not entries:
            content.append("  No transcriptions yet.")
            content.append("  Use ctrl+shift to start recording!")
            content.append("")

        # Set content
        full_text = "\\n".join(content)

        # Create attributed string with monospace font
        font = NSFont.fontWithName_size_("Menlo", 12.0)
        if not font:
            font = NSFont.monospacedSystemFontOfSize_weight_(12.0, 0.0)

        attrs = {
            NSForegroundColorAttributeName: NSColor.colorWithCalibratedRed_green_blue_alpha_(0.9, 0.9, 0.9, 1.0),
            NSFontAttributeName: font,
        }

        attr_string = NSAttributedString.alloc().initWithString_attributes_(full_text, attrs)
        self.text_view.textStorage().setAttributedString_(attr_string)

    def checkIPC_(self, timer):
        """Check IPC file for commands."""
        try:
            if os.path.exists(IPC_FILE):
                with open(IPC_FILE, "r") as f:
                    data = json.load(f)

                if data.get("stop"):
                    NSApp.terminate_(None)
                    return

                should_show = data.get("show", False)
                should_refresh = data.get("refresh", False)

                if should_show and not self.visible:
                    self.refresh_content()
                    self.window.makeKeyAndOrderFront_(None)
                    NSApp.activateIgnoringOtherApps_(True)
                    self.visible = True
                elif not should_show and self.visible:
                    self.window.orderOut_(None)
                    self.visible = False
                elif should_refresh and self.visible:
                    self.refresh_content()
                    # Clear refresh flag
                    data["refresh"] = False
                    with open(IPC_FILE, "w") as f:
                        json.dump(data, f)
        except Exception:
            pass


def main():
    app = NSApplication.sharedApplication()
    delegate = HistoryWindow.alloc().init()
    app.setDelegate_(delegate)
    app.setActivationPolicy_(0)  # Regular app - shows in dock when active
    app.run()


if __name__ == "__main__":
    main()
'''


def _write_history_ipc(data):
    """Write data to history IPC file."""
    try:
        tmp_file = _history_ipc_file + ".tmp"
        with open(tmp_file, "w") as f:
            json.dump(data, f)
        os.replace(tmp_file, _history_ipc_file)
    except Exception:
        pass


def _ensure_history_ui_process():
    """Start the history UI process if not running."""
    global _history_ui_process

    if _history_ui_process is not None and _history_ui_process.poll() is None:
        return

    # Write the UI script to a temp file
    script_file = os.path.join(tempfile.gettempdir(), "vibetotext_history_ui.py")
    with open(script_file, "w") as f:
        f.write(HISTORY_UI_SCRIPT)

    # Clear any old IPC file
    if os.path.exists(_history_ipc_file):
        os.remove(_history_ipc_file)

    # Start the UI process
    error_log = os.path.join(tempfile.gettempdir(), "vibetotext_history_ui_error.log")
    with open(error_log, "w") as err_file:
        _history_ui_process = subprocess.Popen(
            [sys.executable, script_file, _history_ipc_file],
            stdout=subprocess.PIPE,
            stderr=err_file,
        )


# Track visibility state
_history_visible = False


def toggle_history():
    """Toggle the history window visibility."""
    global _history_visible
    _ensure_history_ui_process()
    _history_visible = not _history_visible
    _write_history_ipc({"show": _history_visible})


def show_history():
    """Show the history window."""
    global _history_visible
    _ensure_history_ui_process()
    _history_visible = True
    _write_history_ipc({"show": True})


def hide_history():
    """Hide the history window."""
    global _history_visible
    _history_visible = False
    _write_history_ipc({"show": False})


def refresh_history():
    """Refresh the history display (call after adding new entry)."""
    if _history_visible:
        _write_history_ipc({"show": True, "refresh": True})


def stop_history_ui():
    """Stop the history UI process."""
    global _history_ui_process
    _write_history_ipc({"stop": True})
    if _history_ui_process is not None:
        try:
            _history_ui_process.terminate()
            _history_ui_process.wait(timeout=1)
        except Exception:
            pass
        _history_ui_process = None
