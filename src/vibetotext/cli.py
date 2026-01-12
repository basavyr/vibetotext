"""Main CLI entry point."""

import argparse
import sys
import time

from .recorder import AudioRecorder, HotkeyListener
from .transcriber import Transcriber
from .context import search_context, format_context
from .output import paste_at_cursor


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
        "--no-ui",
        action="store_true",
        help="Disable visual recording indicator",
    )

    args = parser.parse_args()

    # Initialize UI if enabled
    ui = None
    if not args.no_ui:
        try:
            from . import ui as ui_module
            ui = ui_module
        except Exception as e:
            print(f"UI disabled: {e}")

    # Initialize components
    recorder = AudioRecorder()
    transcriber = Transcriber(model_name=args.model)
    listener = HotkeyListener(hotkey=args.hotkey)

    # Set up audio level callback for UI
    if ui:
        recorder.on_level = ui.update_waveform

    print(f"vibetotext ready. Hold [{args.hotkey}] to record.")
    print("Release to transcribe and paste at cursor.")
    print("Press Ctrl+C to exit.\n")

    # Preload model
    _ = transcriber.model

    def on_start():
        print("Recording...", end="", flush=True)
        if ui:
            ui.show_recording()
        recorder.start()

    def on_stop():
        audio = recorder.stop()
        if ui:
            ui.hide_recording()
        print(" done.")

        if len(audio) == 0:
            print("No audio recorded.")
            return

        # Transcribe
        print("Transcribing...", end="", flush=True)
        text = transcriber.transcribe(audio)
        print(" done.")

        if not text:
            print("No speech detected.")
            return

        print(f"Transcribed: {text}")

        # Get code context
        if not args.no_context:
            print("Searching for relevant code...", end="", flush=True)
            snippets = search_context(text, limit=args.context_limit)
            context = format_context(snippets)
            print(f" found {len(snippets)} snippets.")

            # Combine transcript + context
            output = text + context
        else:
            output = text

        # Paste at cursor
        paste_at_cursor(output)
        print("Pasted at cursor.\n")

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
