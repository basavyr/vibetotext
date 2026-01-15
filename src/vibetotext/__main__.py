"""Main CLI entry point."""

import argparse
import os
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

from vibetotext.recorder import AudioRecorder, HotkeyListener
from vibetotext.transcriber import Transcriber
from vibetotext.context import search_context, format_context
from vibetotext.greppy import search_files, format_files_for_context
from vibetotext.llm import cleanup_text, generate_implementation_plan
from vibetotext.output import paste_at_cursor
from vibetotext.history import TranscriptionHistory


def open_history_app():
    """Open the history Electron app."""
    # Find the history-app directory relative to this file
    src_dir = Path(__file__).parent.parent.parent
    history_app_dir = src_dir / "history-app"

    if not history_app_dir.exists():
        print(f"[HISTORY] App not found at {history_app_dir}")
        return

    # Check if already running (single instance will handle focus)
    try:
        subprocess.Popen(
            ["npm", "start"],
            cwd=str(history_app_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("[HISTORY] Opened history window")
    except Exception as e:
        print(f"[HISTORY] Failed to open: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Voice-to-text with automatic code context injection"
    )
    parser.add_argument(
        "--model",
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (default: base)",
    )
    parser.add_argument(
        "--hotkey",
        default="ctrl+shift",
        help="Hotkey to hold while speaking (default: ctrl+shift)",
    )
    parser.add_argument(
        "--greppy-hotkey",
        default="cmd+shift",
        help="Hotkey for Greppy semantic search mode (default: cmd+shift)",
    )
    parser.add_argument(
        "--cleanup-hotkey",
        default="alt+shift",
        help="Hotkey for cleanup/refine mode (default: alt+shift)",
    )
    parser.add_argument(
        "--plan-hotkey",
        default="cmd+alt",
        help="Hotkey for implementation plan mode (default: cmd+alt)",
    )
    parser.add_argument(
        "--history-hotkey",
        default="ctrl+alt",
        help="Hotkey to toggle history window (default: ctrl+alt)",
    )
    parser.add_argument(
        "--codebase",
        default=None,
        help="Path to codebase for Greppy search (default: datafeeds)",
    )
    parser.add_argument(
        "--no-context",
        action="store_true",
        help="Disable automatic code context injection",
    )
    parser.add_argument(
        "--context-limit",
        type=int,
        default=5,
        help="Max number of code snippets to include (default: 5)",
    )
    parser.add_argument(
        "--greppy-limit",
        type=int,
        default=10,
        help="Max number of files for Greppy search (default: 10)",
    )
    parser.add_argument(
        "--no-ui",
        action="store_true",
        help="Disable visual recording indicator",
    )
    parser.add_argument(
        "--device",
        type=int,
        default=None,
        help="Audio input device index (overrides saved config)",
    )

    args = parser.parse_args()

    # Initialize UI if enabled
    ui = None
    if not args.no_ui:
        try:
            from vibetotext import ui as ui_module
            ui = ui_module
        except Exception as e:
            print(f"UI disabled: {e}")

    # Load config for saved audio device (unless overridden by --device)
    import json
    config_file = Path.home() / ".vibetotext" / "config.json"
    saved_device = args.device  # Command line takes priority
    if saved_device is None:
        try:
            if config_file.exists():
                with open(config_file, "r") as f:
                    config = json.load(f)
                    saved_device = config.get("audio_device_index")
        except Exception:
            pass

    # Set audio device
    import sounddevice as sd
    if saved_device is not None:
        sd.default.device[0] = saved_device  # Set input device

    # Log available audio devices
    print("\n[AUDIO] Available input devices:")
    devices = sd.query_devices()
    default_input = sd.default.device[0]
    for i, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            if saved_device is not None and i == saved_device:
                marker = " <-- SELECTED"
            elif saved_device is None and i == default_input:
                marker = " <-- DEFAULT"
            else:
                marker = ""
            print(f"  [{i}] {dev['name']} ({dev['max_input_channels']} ch){marker}")
    print()

    # Initialize components
    recorder = AudioRecorder()
    transcriber = Transcriber(model_name=args.model)
    history = TranscriptionHistory()

    # Set up hotkeys for all modes
    hotkeys = {
        args.hotkey: "transcribe",
        args.greppy_hotkey: "greppy",
        args.cleanup_hotkey: "cleanup",
        args.plan_hotkey: "plan",
        args.history_hotkey: "history",
    }
    listener = HotkeyListener(hotkeys=hotkeys)

    # Track current mode
    current_mode = [None]  # Use list to allow mutation in nested function

    # Set up audio level callback for UI
    if ui:
        recorder.on_level = ui.update_waveform

    print(f"vibetotext ready. Hold hotkey to record, release to process.")
    print(f"  [{args.hotkey}] = transcribe + paste")
    print(f"  [{args.greppy_hotkey}] = Greppy search + attach files")
    print(f"  [{args.cleanup_hotkey}] = cleanup/refine with Gemini")
    print(f"  [{args.plan_hotkey}] = implementation plan with Gemini")
    print(f"  [{args.history_hotkey}] = toggle history window")
    print("Press Ctrl+C to exit.\n")

    # Preload model
    _ = transcriber.model

    def on_start(mode):
        try:
            # History mode: open app immediately, don't record
            if mode == "history":
                open_history_app()
                return

            current_mode[0] = mode
            mode_labels = {"greppy": "Greppy", "cleanup": "Cleanup", "transcribe": "Transcribe", "plan": "Plan"}
            mode_label = mode_labels.get(mode, "Transcribe")
            print(f"Recording ({mode_label})...", end="", flush=True)
            if ui:
                ui.show_recording()
            recorder.start()
        except Exception as e:
            error_log = os.path.join(tempfile.gettempdir(), "vibetotext_crash.log")
            error_msg = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error in on_start (mode={mode}):\n"
            error_msg += traceback.format_exc()

            with open(error_log, "a") as f:
                f.write(error_msg + "\n")

            print(f"\n[ERROR] Failed to start recording: {e}")
            print(f"[ERROR] Full traceback logged to: {error_log}")

    def on_stop(mode):
        try:
            import time as t
            total_start = t.perf_counter()

            # History mode: nothing to do on release
            if mode == "history":
                return

            t0 = t.perf_counter()
            audio = recorder.stop()
            t1 = t.perf_counter()
            print(f" done. [stop: {(t1-t0)*1000:.0f}ms]")

            if ui:
                ui.hide_recording()

            if len(audio) == 0:
                print("No audio recorded.")
                return

            # Calculate audio duration for stats
            duration_seconds = len(audio) / 16000  # Sample rate is 16000

            # Transcribe
            print("Transcribing...", end="", flush=True)
            t2 = t.perf_counter()
            text = transcriber.transcribe(audio)
            t3 = t.perf_counter()
            print(f" done. [transcribe: {(t3-t2)*1000:.0f}ms]")

            if not text:
                print("No speech detected.")
                return

            print(f"Transcribed: {text}")

            if mode == "greppy":
                # Greppy mode: search for relevant files and attach them
                print("Searching with Greppy...", end="", flush=True)
                files = search_files(text, limit=args.greppy_limit, codebase=args.codebase)
                print(f" found {len(files)} files.")

                if files:
                    for filepath, line_num in files:
                        print(f"  - {filepath}:{line_num}")

                # Format output with file contents
                context = format_files_for_context(files)
                output = text + context

            elif mode == "cleanup":
                # Cleanup mode: use Gemini to refine rambling into clear prompt
                print("Cleaning up with Gemini...", end="", flush=True)
                refined = cleanup_text(text)
                if refined:
                    print(" done.")
                    print(f"Refined: {refined[:100]}..." if len(refined) > 100 else f"Refined: {refined}")
                    output = refined
                else:
                    print(" failed, using original.")
                    output = text

            elif mode == "plan":
                # Plan mode: use Gemini to generate implementation plan
                print("Generating implementation plan...", end="", flush=True)
                plan = generate_implementation_plan(text)
                if plan:
                    print(" done.")
                    print(f"Plan: {plan[:150]}..." if len(plan) > 150 else f"Plan: {plan}")
                    output = plan
                else:
                    print(" failed, using original.")
                    output = text

            else:
                # Regular transcribe mode - just transcribe, no context search
                # Use greppy mode (cmd+shift) if you want code search
                output = text

            # Save to history with duration for WPM calculation
            history.add_entry(text, mode, duration_seconds=duration_seconds)

            # Paste at cursor
            t4 = t.perf_counter()
            paste_at_cursor(output)
            t5 = t.perf_counter()
            total_end = t.perf_counter()
            print(f"Pasted at cursor. [paste: {(t5-t4)*1000:.0f}ms] [TOTAL: {(total_end-total_start)*1000:.0f}ms]\n")

        except Exception as e:
            # Log error to file and print to console
            error_log = os.path.join(tempfile.gettempdir(), "vibetotext_crash.log")
            error_msg = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error in on_stop (mode={mode}):\n"
            error_msg += traceback.format_exc()

            with open(error_log, "a") as f:
                f.write(error_msg + "\n")

            print(f"\n[ERROR] {e}")
            print(f"[ERROR] Full traceback logged to: {error_log}")

            # Hide UI if still showing
            if ui:
                try:
                    ui.hide_recording()
                except Exception:
                    pass

    # Start listening
    hotkey_listener = listener.start(on_start, on_stop)

    # Run main loop (process UI events if enabled)
    try:
        while True:
            if ui:
                ui.process_ui_events()
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nExiting.")
        sys.exit(0)


if __name__ == "__main__":
    main()
