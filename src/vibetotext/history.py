"""Transcription history storage and analytics."""

import json
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import List, Optional


# Common English stopwords to exclude from word frequency
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "shall", "can", "need",
    "dare", "ought", "used", "i", "you", "he", "she", "it", "we", "they",
    "me", "him", "her", "us", "them", "my", "your", "his", "its", "our",
    "their", "this", "that", "these", "those", "what", "which", "who",
    "whom", "whose", "where", "when", "why", "how", "all", "each", "every",
    "both", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "also", "now", "here", "there", "then", "once", "if", "because",
    "until", "while", "about", "into", "through", "during", "before",
    "after", "above", "below", "between", "under", "again", "further",
    "any", "up", "down", "out", "off", "over", "under", "again", "once",
    "going", "gonna", "like", "okay", "ok", "yeah", "yes", "no", "um",
    "uh", "ah", "oh", "well", "right", "actually", "basically", "really",
    "just", "thing", "things", "something", "anything", "everything",
}


class TranscriptionHistory:
    """Manages persistent storage of transcription history."""

    def __init__(self, path: Optional[Path] = None):
        """
        Initialize history storage.

        Args:
            path: Path to history JSON file. Defaults to ~/.vibetotext/history.json
        """
        if path is None:
            path = Path.home() / ".vibetotext" / "history.json"
        self.path = Path(path)
        self._ensure_storage()

    def _ensure_storage(self):
        """Create storage directory and file if they don't exist."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._save({"entries": []})

    def _load(self) -> dict:
        """Load history from disk."""
        try:
            with open(self.path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"entries": []}

    def _save(self, data: dict):
        """Save history to disk."""
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)

    def add_entry(
        self,
        text: str,
        mode: str,
        timestamp: Optional[datetime] = None,
        duration_seconds: Optional[float] = None,
    ):
        """
        Add a transcription entry to history (non-blocking).

        Args:
            text: Transcribed text
            mode: Mode used (transcribe, greppy, cleanup, plan)
            timestamp: When transcription occurred (defaults to now)
            duration_seconds: Audio recording duration in seconds
        """
        if timestamp is None:
            timestamp = datetime.now()

        word_count = len(text.split())

        # Calculate WPM if we have duration
        wpm = None
        if duration_seconds and duration_seconds > 0:
            minutes = duration_seconds / 60
            wpm = round(word_count / minutes) if minutes > 0 else None

        # Save in background thread to not block pasting
        def save_async():
            try:
                data = self._load()
                entry = {
                    "text": text,
                    "mode": mode,
                    "timestamp": timestamp.isoformat(),
                    "word_count": word_count,
                    "duration_seconds": duration_seconds,
                    "wpm": wpm,
                }
                data["entries"].append(entry)
                self._save(data)
                print(f"[HISTORY] Saving entry to {self.path}, total entries: {len(data['entries'])}")
                print(f"[HISTORY] Save complete")
            except Exception as e:
                print(f"[HISTORY] Error saving: {e}")

        thread = threading.Thread(target=save_async, daemon=True)
        thread.start()

    def get_entries(self, limit: Optional[int] = None) -> List[dict]:
        """
        Get transcription entries, newest first.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of entry dicts with text, mode, timestamp, word_count
        """
        data = self._load()
        entries = sorted(
            data["entries"],
            key=lambda x: x["timestamp"],
            reverse=True,
        )
        if limit:
            entries = entries[:limit]
        return entries

    def get_statistics(self) -> dict:
        """
        Compute statistics from all history.

        Returns:
            Dict with total_words, total_sessions, common_words, avg_wpm, time_saved_minutes
        """
        data = self._load()
        entries = data["entries"]

        if not entries:
            return {
                "total_words": 0,
                "total_sessions": 0,
                "common_words": [],
                "avg_wpm": 0,
                "time_saved_minutes": 0,
                "total_duration_seconds": 0,
            }

        # Total counts
        total_words = sum(e.get("word_count", len(e["text"].split())) for e in entries)
        total_sessions = len(entries)

        # Calculate average WPM from entries that have it
        wpm_entries = [e["wpm"] for e in entries if e.get("wpm")]
        avg_wpm = round(sum(wpm_entries) / len(wpm_entries)) if wpm_entries else 0

        # Total recording duration
        total_duration = sum(e.get("duration_seconds", 0) or 0 for e in entries)

        # Time saved calculation:
        # Only count entries that have duration_seconds (entries before this feature don't count)
        # Average typing speed is ~40 WPM
        # Time to type = words / 40 minutes
        # Time spent dictating = duration / 60 minutes
        # Time saved = time_to_type - time_dictating
        typing_wpm = 40
        entries_with_duration = [e for e in entries if e.get("duration_seconds")]
        words_with_duration = sum(e.get("word_count", len(e["text"].split())) for e in entries_with_duration)
        time_to_type_minutes = words_with_duration / typing_wpm
        time_dictating_minutes = total_duration / 60
        time_saved_minutes = max(0, time_to_type_minutes - time_dictating_minutes)

        # Word frequency (excluding stopwords)
        all_words = []
        for entry in entries:
            words = entry["text"].lower().split()
            # Filter out stopwords and short words
            words = [w.strip(".,!?;:'\"()[]{}") for w in words]
            words = [w for w in words if w and len(w) > 2 and w not in STOPWORDS]
            all_words.extend(words)

        word_counts = Counter(all_words)
        common_words = word_counts.most_common(20)

        return {
            "total_words": total_words,
            "total_sessions": total_sessions,
            "common_words": common_words,
            "avg_wpm": avg_wpm,
            "time_saved_minutes": round(time_saved_minutes, 1),
            "total_duration_seconds": round(total_duration, 1),
        }

    def clear(self):
        """Clear all history."""
        self._save({"entries": []})
