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
    """Listens for hotkey to toggle recording."""

    def __init__(self, hotkey: str = "ctrl+shift"):
        self.hotkey = hotkey
        self.on_start = None
        self.on_stop = None
        self._pressed = set()
        self._recording = False

    def start(self, on_start, on_stop):
        """Start listening for hotkey."""
        from pynput import keyboard

        self.on_start = on_start
        self.on_stop = on_stop

        # Parse hotkey
        self._hotkey_parts = set(self.hotkey.lower().split("+"))

        def on_press(key):
            try:
                key_name = key.char.lower() if hasattr(key, 'char') and key.char else key.name.lower()
            except AttributeError:
                return

            self._pressed.add(key_name)

            # Check if hotkey combo is pressed
            if self._hotkey_parts.issubset(self._pressed):
                if not self._recording:
                    self._recording = True
                    if self.on_start:
                        self.on_start()

        def on_release(key):
            try:
                key_name = key.char.lower() if hasattr(key, 'char') and key.char else key.name.lower()
            except AttributeError:
                return

            # If any hotkey part is released while recording, stop
            if self._recording and key_name in self._hotkey_parts:
                self._recording = False
                # Clear pressed set to avoid stale state
                self._pressed.clear()
                if self.on_stop:
                    self.on_stop()
            else:
                self._pressed.discard(key_name)

        self.listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self.listener.start()
        return self.listener
