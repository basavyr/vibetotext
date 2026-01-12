"""py2app setup for vibetotext."""

from setuptools import setup

APP = ['src/vibetotext/cli.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'plist': {
        'CFBundleName': 'VibeToText',
        'CFBundleDisplayName': 'VibeToText',
        'CFBundleIdentifier': 'com.vibetotext.app',
        'CFBundleVersion': '0.1.0',
        'CFBundleShortVersionString': '0.1.0',
        'LSUIElement': True,  # Menu bar app (no dock icon)
        'NSMicrophoneUsageDescription': 'VibeToText needs microphone access to transcribe your voice.',
    },
    'packages': ['whisper', 'torch', 'numpy', 'sounddevice', 'pynput', 'tiktoken'],
    'includes': ['vibetotext'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
