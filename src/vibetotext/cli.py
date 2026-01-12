"""Main CLI entry point."""

import argparse
import sys
import time

from .recorder import AudioRecorder, HotkeyListener
from .transcriber import Transcriber
from .context import search_context, format_context
from .greppy import search_files, format_files_for_context
from .llm import cleanup_text, generate_implementation_plan
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
        default="fn",
        help="Hotkey for implementation plan mode (default: fn)",
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

    # Set up hotkeys for all modes
    hotkeys = {
        args.hotkey: "transcribe",
        args.greppy_hotkey: "greppy",
        args.cleanup_hotkey: "cleanup",
        args.plan_hotkey: "plan",
    }
    listener = HotkeyListener(hotkeys=hotkeys)

    # Track current mode
    current_mode = [None]  # Use list to allow mutation in nested function

    # Set up audio level callback for UI
    if ui:
        recorder.on_level = ui.update_waveform

    print(f"vibetotext ready.")
    print(f"  [{args.hotkey}] = transcribe + paste")
    print(f"  [{args.greppy_hotkey}] = transcribe + Greppy search + attach files")
    print(f"  [{args.cleanup_hotkey}] = transcribe + cleanup/refine with Gemini")
    print(f"  [{args.plan_hotkey}] = transcribe + implementation plan with Gemini")
    print("Press Ctrl+C to exit.\n")

    # Preload model
    _ = transcriber.model

    def on_start(mode):
        current_mode[0] = mode
        mode_labels = {"greppy": "Greppy", "cleanup": "Cleanup", "transcribe": "Transcribe", "plan": "Plan"}
        mode_label = mode_labels.get(mode, "Transcribe")
        print(f"Recording ({mode_label})...", end="", flush=True)
        if ui:
            ui.show_recording()
        recorder.start()

    def on_stop(mode):
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
            # Regular transcribe mode
            if not args.no_context:
                print("Searching for relevant code...", end="", flush=True)
                snippets = search_context(text, limit=args.context_limit)
                context = format_context(snippets)
                print(f" found {len(snippets)} snippets.")
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
