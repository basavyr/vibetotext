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

            # Calculate frequency spectrum for waveform visualization
            if self.on_level:
                # Flatten to 1D
                audio = indata.flatten()

                # Apply FFT to get frequency spectrum
                fft = np.abs(np.fft.rfft(audio))

                # Split into 25 frequency bands
                num_bars = 25
                band_size = len(fft) // num_bars

                if band_size > 0:
                    levels = []
                    for i in range(num_bars):
                        start = i * band_size
                        end = start + band_size
                        band_magnitude = np.mean(fft[start:end])
                        # Normalize and boost for visibility
                        level = min(1.0, band_magnitude * 0.5)
                        levels.append(level)
                    self.on_level(levels)
                else:
                    self.on_level([0.0] * num_bars)

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
