"""Audio recording with hotkey trigger."""

import numpy as np
import sounddevice as sd
from typing import Optional
import threading
import queue


class AudioRecorder:
    """Records audio from microphone."""

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.recording = False
        self.audio_queue = queue.Queue()
        self._audio_data = []
        self.on_level = None  # Callback for audio level updates

    def _callback(self, indata, frames, time, status):
        """Callback for sounddevice stream."""
        if self.recording:
            self._audio_data.append(indata.copy())

            # Debug: always write to file to confirm callback runs
            if not hasattr(self, '_cb_count'):
                self._cb_count = 0
            self._cb_count += 1
            if self._cb_count <= 3:
                with open('/tmp/vibetotext_callback_debug.txt', 'a') as f:
                    f.write(f"Callback #{self._cb_count}, on_level={self.on_level is not None}\n")

            # Calculate waveform visualization based on audio amplitude
            if self.on_level:
                audio = indata.flatten()

                # Get RMS (overall volume)
                rms = np.sqrt(np.mean(audio**2))

                # Scale RMS: 0.001 (quiet) → 0.1, 0.005 (normal) → 0.5, 0.01 (loud) → 1.0
                base_level = min(1.0, rms * 100)

                # Threshold: if base level is very low, treat as silence
                # Increased threshold to handle background noise
                if base_level < 0.1:
                    self.on_level([0.0] * 25)
                    return

                # Create 25 bars with variation based on audio samples
                num_bars = 25
                levels = []

                # Use actual audio samples to create variation across bars
                if len(audio) >= num_bars:
                    step = len(audio) // num_bars
                    for i in range(num_bars):
                        sample = abs(audio[i * step])
                        # Combine base level with sample variation
                        level = min(1.0, (base_level * 0.7) + (sample * 50))
                        # Floor small values to zero
                        if level < 0.05:
                            level = 0.0
                        levels.append(level)
                else:
                    # Fallback: use base level with random variation
                    for i in range(num_bars):
                        variation = np.random.uniform(0.7, 1.3)
                        level = min(1.0, base_level * variation)
                        if level < 0.05:
                            level = 0.0
                        levels.append(level)

                self.on_level(levels)

    def start(self):
        """Start recording."""
        self._audio_data = []
        self.recording = True
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype=np.float32,
            callback=self._callback,
        )
        self.stream.start()

    def stop(self) -> np.ndarray:
        """Stop recording and return audio data."""
        self.recording = False
        self.stream.stop()
        self.stream.close()

        if not self._audio_data:
            return np.array([], dtype=np.float32)

        # Concatenate all recorded chunks
        audio = np.concatenate(self._audio_data, axis=0)
        return audio.flatten()


class HotkeyListener:
    """Listens for multiple hotkeys to toggle recording."""

    def __init__(self, hotkeys: dict = None, max_recording_seconds: int = 60):
        """
        Args:
            hotkeys: Dict mapping hotkey strings to mode names.
                     e.g. {"ctrl+shift": "transcribe", "cmd+shift": "greppy"}
            max_recording_seconds: Auto-stop recording after this many seconds (default: 60)
        """
        if hotkeys is None:
            hotkeys = {"ctrl+shift": "transcribe"}
        self.hotkeys = hotkeys
        self.max_recording_seconds = max_recording_seconds
        self.on_start = None  # Called with mode name
        self.on_stop = None   # Called with mode name
        self._pressed = set()
        self._recording = False
        self._active_mode = None
        self._timeout_timer = None

    def _cancel_timeout(self):
        """Cancel any pending timeout."""
        if self._timeout_timer:
            self._timeout_timer.cancel()
            self._timeout_timer = None

    def _timeout_stop(self):
        """Called when recording times out."""
        if self._recording:
            print(f"\n[TIMEOUT] Recording exceeded {self.max_recording_seconds}s, auto-stopping...")
            mode = self._active_mode
            self._recording = False
            self._active_mode = None
            self._active_parts = None
            self._pressed.clear()
            if self.on_stop:
                self.on_stop(mode)

    def start(self, on_start, on_stop):
        """Start listening for hotkeys."""
        from pynput import keyboard

        self.on_start = on_start
        self.on_stop = on_stop

        # Parse all hotkeys
        self._parsed_hotkeys = {}
        for hotkey, mode in self.hotkeys.items():
            parts = set(hotkey.lower().split("+"))
            self._parsed_hotkeys[mode] = parts

        def on_press(key):
            try:
                key_name = key.char.lower() if hasattr(key, 'char') and key.char else key.name.lower()
            except AttributeError:
                return

            self._pressed.add(key_name)

            # Check if any hotkey combo is pressed (check longer combos first)
            if not self._recording:
                # Sort by length descending to match most specific first
                for mode, parts in sorted(self._parsed_hotkeys.items(),
                                          key=lambda x: len(x[1]), reverse=True):
                    if parts.issubset(self._pressed):
                        self._recording = True
                        self._active_mode = mode
                        self._active_parts = parts

                        # Start timeout timer
                        self._cancel_timeout()
                        self._timeout_timer = threading.Timer(
                            self.max_recording_seconds,
                            self._timeout_stop
                        )
                        self._timeout_timer.daemon = True
                        self._timeout_timer.start()

                        if self.on_start:
                            self.on_start(mode)
                        break

        def on_release(key):
            try:
                key_name = key.char.lower() if hasattr(key, 'char') and key.char else key.name.lower()
            except AttributeError:
                return

            # If any hotkey part is released while recording, stop
            if self._recording and key_name in self._active_parts:
                self._cancel_timeout()
                mode = self._active_mode
                self._recording = False
                self._active_mode = None
                self._active_parts = None
                # Clear pressed set to avoid stale state
                self._pressed.clear()
                if self.on_stop:
                    self.on_stop(mode)
            else:
                self._pressed.discard(key_name)

        self.listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self.listener.start()
        return self.listener
