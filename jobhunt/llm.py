"""Thin wrapper around the OpenAI Chat Completions API.

Kept deliberately small so swapping providers means editing one file.
"""
from __future__ import annotations

from openai import OpenAI

from .config import cfg

_client = OpenAI(api_key=cfg.llm_key)


def complete(
    prompt: str,
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    system: str | None = None,
    json_mode: bool = False,
) -> str:
    """Single-turn chat completion. Returns assistant text."""
    kwargs: dict = dict(
        model=model or cfg.llm_model,
        max_tokens=max_tokens if max_tokens is not None else cfg.llm_draft_max_tokens,
        temperature=temperature if temperature is not None else cfg.llm_draft_temperature,
        messages=[
            {"role": "system", "content": system or "You are a precise, terse assistant."},
            {"role": "user", "content": prompt},
        ],
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    msg = _client.chat.completions.create(**kwargs)
    return (msg.choices[0].message.content or "").strip()
