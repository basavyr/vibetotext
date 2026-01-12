"""Whisper transcription."""

import numpy as np
from typing import Optional
import whisper


# Technical vocabulary prompt to bias Whisper toward programming terms
# This helps Whisper recognize domain-specific words correctly
TECH_PROMPT = """Programming terms: Firebase, Firestore, MongoDB, PostgreSQL, MySQL, Redis,
API, REST, GraphQL, JSON, YAML, HTML, CSS, JavaScript, TypeScript, Python, React, Vue, Angular,
Node.js, npm, yarn, webpack, Vite, Docker, Kubernetes, AWS, GCP, Azure, GitHub, GitLab,
CI/CD, DevOps, microservices, serverless, lambda, async, await, callback, promise,
useState, useEffect, useContext, useRef, useMemo, useCallback, Redux, Zustand,
NextJS, Vercel, Netlify, Supabase, Prisma, tRPC, Zod, TypeORM, Sequelize,
component, props, state, hook, middleware, endpoint, route, controller, service,
repository, schema, migration, query, mutation, subscription, resolver,
authentication, authorization, OAuth, JWT, token, session, cookie, CORS,
deployment, production, staging, development, environment, config, env,
variable, function, class, interface, type, enum, const, let, var,
import, export, module, package, dependency, devDependency,
Claude, Anthropic, OpenAI, GPT, LLM, embedding, vector, RAG, prompt, completion,
Whisper, transcription, speech-to-text, voice recognition, NLP, ML, AI."""


class Transcriber:
    """Transcribes audio using local Whisper model."""

    def __init__(self, model_name: str = "base"):
        """
        Initialize transcriber.

        Args:
            model_name: Whisper model size. Options: tiny, base, small, medium, large
                       Bigger = more accurate but slower.
                       'base' is a good balance for real-time use.
        """
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        """Lazy load the model."""
        if self._model is None:
            print(f"Loading Whisper model '{self.model_name}'...")
            self._model = whisper.load_model(self.model_name)
        return self._model

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """
        Transcribe audio to text.

        Args:
            audio: Audio data as numpy array (float32, mono)
            sample_rate: Sample rate of audio (Whisper expects 16000)

        Returns:
            Transcribed text
        """
        if len(audio) == 0:
            return ""

        # Whisper expects float32 audio normalized to [-1, 1]
        audio = audio.astype(np.float32)

        # Transcribe with tech vocabulary prompt to improve recognition
        result = self.model.transcribe(
            audio,
            language="en",
            fp16=False,  # Use fp32 for CPU compatibility
            initial_prompt=TECH_PROMPT,  # Bias toward programming terms
        )

        return result["text"].strip()
