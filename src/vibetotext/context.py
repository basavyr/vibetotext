"""Greppy integration for code context."""

import subprocess
import json
from pathlib import Path
from typing import List, Optional


def get_project_root() -> Optional[Path]:
    """Get current project root (git root or cwd)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except Exception:
        pass
    return Path.cwd()


def search_context(query: str, limit: int = 5) -> List[dict]:
    """
    Search codebase for relevant context using Greppy.

    Args:
        query: Natural language query (the transcribed voice input)
        limit: Max number of results

    Returns:
        List of relevant code snippets
    """
    project_root = get_project_root()

    try:
        result = subprocess.run(
            ["greppy", "search", query, "-n", str(limit), "-p", str(project_root)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return []

        # Parse greppy output
        # Format: file_path:start_line-end_line (score: X.XX)
        # followed by code content
        snippets = []
        lines = result.stdout.strip().split("\n")

        current_snippet = None
        for line in lines:
            if line.startswith("/") or line.startswith("./"):
                # New file match
                if current_snippet:
                    snippets.append(current_snippet)
                current_snippet = {"header": line, "content": []}
            elif current_snippet is not None:
                current_snippet["content"].append(line)

        if current_snippet:
            snippets.append(current_snippet)

        return snippets

    except subprocess.TimeoutExpired:
        return []
    except FileNotFoundError:
        # Greppy not installed
        return []


def format_context(snippets: List[dict]) -> str:
    """Format code snippets for inclusion in prompt."""
    if not snippets:
        return ""

    parts = ["\n---\nRelevant code context:\n"]

    for snippet in snippets:
        parts.append(f"\n{snippet['header']}")
        parts.append("```")
        parts.append("\n".join(snippet["content"]))
        parts.append("```\n")

    return "\n".join(parts)
