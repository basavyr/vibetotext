"""LLM integration for text cleanup and refinement."""

import os
import google.generativeai as genai
from typing import Optional


# Configure Gemini
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))


CLEANUP_PROMPT = """You are an expert prompt optimizer and thought clarifier. The user has recorded a rambling voice message and needs you to transform it into a clear, well-structured prompt or request.

Your task:
1. **Extract the core intent** - What is the user actually trying to accomplish? Cut through the rambling to find their real goal.
2. **Resolve contradictions** - If they say conflicting things, use context to determine what they most likely meant.
3. **Apply expert knowledge** - The user may not know the correct terminology. As an expert in whatever domain they're discussing, use precise technical terms and concepts.
4. **Optimize for LLM consumption** - Structure the output so an AI assistant can best understand and act on it.
5. **Be concise but complete** - Remove filler words and repetition, but keep all important details.

Rules:
- Output ONLY the refined prompt/request. No explanations, no "Here's what you meant", just the clean output.
- Preserve the user's voice and intent - don't add requirements they didn't mention.
- If they're asking a question, make it a clear question. If they're giving instructions, make them clear instructions.
- Use markdown formatting if it helps clarity (bullet points, headers, etc.)

User's rambling input:
{text}

Refined output:"""


IMPLEMENTATION_PLAN_PROMPT = """You are a senior software architect creating an implementation plan from a voice-recorded feature request. Transform the rambling description into a structured technical implementation plan.

## Output Format

Create a markdown document following this EXACT structure:

```markdown
# [Feature Name] - Implementation Plan

## Overview

[1-3 sentences describing what's being built and its purpose]

---

## Phase 1: [Phase Name]

### Objective
[What this phase accomplishes]

### Backend Changes

**New/Modified Files:**
- `path/to/file.py` - [description]

**API Endpoints (if applicable):**
- `POST /api/endpoint` - [description]
  - Request body: [fields]
  - Response: [fields]

**Database/Storage Changes (if applicable):**
```
collection/
  └── document structure
```

### Frontend Changes

**New/Modified Files:**
- `path/to/component.tsx` - [description]

**Component Structure (if applicable):**
```tsx
interface Props {{
  // key props
}}
```

---

## Phase 2: [Phase Name]
[Continue pattern...]

---

## File Summary

### New Files
```
/path/to/new/file.py
/path/to/new/component.tsx
```

### Modified Files
```
/path/to/existing/file.py
```

---

## Data Flow

```
Step 1
  │
  ▼
Step 2
  │
  ▼
Step 3
```
```

## Rules

1. **Extract the feature** - Identify the core feature being requested
2. **Break into phases** - Logical implementation steps (typically 2-4 phases)
3. **Be specific about files** - Use realistic file paths based on typical project structures
4. **Include code snippets** - Show interfaces, schemas, key function signatures
5. **No time estimates** - Never include timing like "2-3 days" or "later"
6. **No fluff** - Skip explanations, just output the plan document
7. **Use markdown formatting** - Headers, code blocks, tables, bullet points
8. **Include data flow diagram** - ASCII diagram showing how data moves

User's voice-recorded feature request:
{text}

Implementation Plan:"""


def cleanup_text(text: str) -> Optional[str]:
    """
    Use Gemini to clean up rambling text into a clear, refined prompt.

    Args:
        text: The raw transcribed text from the user's rambling

    Returns:
        Cleaned up, refined text or None if failed
    """
    try:
        model = genai.GenerativeModel("gemini-3-flash-preview")

        prompt = CLEANUP_PROMPT.format(text=text)

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,  # Lower temperature for more focused output
                max_output_tokens=2048,
            )
        )

        if response.text:
            return response.text.strip()
        return None

    except Exception as e:
        print(f"Gemini cleanup error: {e}")
        return None


def generate_implementation_plan(text: str) -> Optional[str]:
    """
    Use Gemini to generate a structured implementation plan from rambling voice input.

    Args:
        text: The raw transcribed text describing a feature request

    Returns:
        Structured markdown implementation plan or None if failed
    """
    try:
        model = genai.GenerativeModel("gemini-3-flash-preview")

        prompt = IMPLEMENTATION_PLAN_PROMPT.format(text=text)

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.4,  # Slightly higher for creative structure
                max_output_tokens=4096,  # Longer output for detailed plans
            )
        )

        if response.text:
            return response.text.strip()
        return None

    except Exception as e:
        print(f"Gemini plan generation error: {e}")
        return None
