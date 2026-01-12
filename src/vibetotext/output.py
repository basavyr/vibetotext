"""Output handling - auto-paste at cursor."""

import subprocess
import time
import os
import pyperclip


def has_accessibility_permission():
    """Check if we have Accessibility permission."""
    try:
        from ApplicationServices import AXIsProcessTrusted
        trusted = AXIsProcessTrusted()
        print(f"[DEBUG] AXIsProcessTrusted() = {trusted}")
        return trusted
    except ImportError as e:
        print(f"[DEBUG] Failed to import ApplicationServices: {e}")
        return False


def request_accessibility_permission():
    """Prompt user for Accessibility permission."""
    try:
        from ApplicationServices import AXIsProcessTrustedWithOptions
        from Foundation import NSDictionary

        # This will show the system prompt
        options = NSDictionary.dictionaryWithObject_forKey_(
            True,
            "AXTrustedCheckOptionPrompt"
        )
        trusted = AXIsProcessTrustedWithOptions(options)
        print(f"[DEBUG] AXIsProcessTrustedWithOptions() = {trusted}")
        return trusted
    except Exception as e:
        print(f"[DEBUG] Failed to request permission: {e}")
        return False


def get_running_app_info():
    """Get info about current process for debugging."""
    try:
        import sys
        print(f"[DEBUG] Python executable: {sys.executable}")
        print(f"[DEBUG] PID: {os.getpid()}")
        print(f"[DEBUG] __file__: {__file__}")

        # Get the actual app that needs permission
        from AppKit import NSRunningApplication, NSWorkspace
        current_app = NSRunningApplication.currentApplication()
        print(f"[DEBUG] Bundle ID: {current_app.bundleIdentifier()}")
        print(f"[DEBUG] Localized Name: {current_app.localizedName()}")
        print(f"[DEBUG] Bundle URL: {current_app.bundleURL()}")
        print(f"[DEBUG] Executable URL: {current_app.executableURL()}")
    except Exception as e:
        print(f"[DEBUG] Failed to get app info: {e}")


def simulate_paste():
    """Simulate Cmd+V using CGEventPost."""
    try:
        from Quartz import (
            CGEventCreateKeyboardEvent,
            CGEventPost,
            kCGHIDEventTap,
            kCGSessionEventTap,
            CGEventSetFlags,
            kCGEventFlagMaskCommand
        )

        V_KEY = 9  # Virtual key code for 'V'

        print(f"[DEBUG] Creating keyboard events for Cmd+V (key code {V_KEY})")

        # Key down with Command modifier
        event_down = CGEventCreateKeyboardEvent(None, V_KEY, True)
        if event_down is None:
            print("[DEBUG] ERROR: CGEventCreateKeyboardEvent returned None for key down")
            return False

        CGEventSetFlags(event_down, kCGEventFlagMaskCommand)
        print(f"[DEBUG] Created key down event: {event_down}")

        # Key up
        event_up = CGEventCreateKeyboardEvent(None, V_KEY, False)
        if event_up is None:
            print("[DEBUG] ERROR: CGEventCreateKeyboardEvent returned None for key up")
            return False
        CGEventSetFlags(event_up, kCGEventFlagMaskCommand)
        print(f"[DEBUG] Created key up event: {event_up}")

        # Try posting to HID event tap first
        print(f"[DEBUG] Posting to kCGHIDEventTap...")
        CGEventPost(kCGHIDEventTap, event_down)
        time.sleep(0.02)
        CGEventPost(kCGHIDEventTap, event_up)

        print(f"[DEBUG] Events posted successfully")
        return True

    except Exception as e:
        print(f"[DEBUG] simulate_paste() exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def paste_at_cursor(text: str):
    """
    Copy text to clipboard and auto-paste at cursor.
    Falls back to clipboard-only if no Accessibility permission.
    """
    # Copy to clipboard first
    pyperclip.copy(text)
    print(f"[DEBUG] Copied {len(text)} chars to clipboard")

    # Debug: show what app we are
    get_running_app_info()

    # Check permission
    if has_accessibility_permission():
        print("[DEBUG] Have accessibility permission, attempting auto-paste...")
        time.sleep(0.1)  # Let clipboard sync

        if simulate_paste():
            print("[DEBUG] Auto-paste attempted")
            return
        else:
            print("[DEBUG] Auto-paste failed, falling back to sound")
    else:
        print("[DEBUG] No accessibility permission")
        # Try to request it (shows system dialog)
        request_accessibility_permission()

    # Fallback: play sound to signal manual paste needed
    print("[DEBUG] Playing sound for manual paste")
    subprocess.run(["afplay", "/System/Library/Sounds/Pop.aiff"], check=False)
