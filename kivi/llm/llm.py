"""LLM helpers for Hey Kivi — Groq or Gemini only (see LLM_PROVIDER in config)."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable

from hindsight_pipeline_2.kivi.config import Settings

GenerateFn = Callable[[str, str], str]


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError(f"No JSON object in LLM output: {text[:200]!r}")


def create_generator(settings: Settings | None = None) -> GenerateFn:
    cfg = settings or Settings.from_env()
    cfg.require_llm()
    if cfg.llm_provider == "gemini":
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        model = os.getenv("GEMINI_MODEL")

        def generate(system_prompt: str, user_message: str) -> str:
            response = client.models.generate_content(
                model=model,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=1200,
                    response_mime_type="application/json",
                ),
            )
            if not response.text:
                raise ValueError("Empty Gemini response")
            return response.text

        return generate

    from groq import Groq

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    model = os.getenv("GROQ_MODEL")

    def generate(system_prompt: str, user_message: str) -> str:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_completion_tokens=1200,
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content
        if not content:
            raise ValueError("Empty Groq response")
        return content

    return generate


def create_text_generator(settings: Settings | None = None) -> Callable[[str, str], str]:
    """Non-JSON chat/polish generator."""
    cfg = settings or Settings.from_env()
    cfg.require_llm()
    if cfg.llm_provider == "gemini":
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        model = os.getenv("GEMINI_MODEL")

        def generate(system_prompt: str, user_message: str) -> str:
            response = client.models.generate_content(
                model=model,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=1200,
                ),
            )
            if not response.text:
                raise ValueError("Empty Gemini response")
            return response.text

        return generate

    from groq import Groq

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    model = os.getenv("GROQ_MODEL")

    def generate(system_prompt: str, user_message: str) -> str:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_completion_tokens=1000,
            reasoning_effort="none",
        )
    
        content = completion.choices[0].message.content
        if not content:
            raise ValueError("Empty Groq response")
    
        return content.strip()
    
    return generate


def llm_json(generate: GenerateFn, system: str, user: str) -> dict[str, Any]:
    return _extract_json(generate(system, user))
