"""Output handling - copy to clipboard."""

import subprocess
import pyperclip


def paste_at_cursor(text: str):
    """
    Copy text to clipboard. User presses Cmd+V to paste.
    Plays a sound to signal ready.
    """
    pyperclip.copy(text)

    # Play system sound to signal ready to paste
    subprocess.run(["afplay", "/System/Library/Sounds/Pop.aiff"], check=False)
