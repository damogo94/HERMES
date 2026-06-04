"""
Cliente LLM mínimo (API compatible OpenAI, p. ej. OpenRouter).

Solo se usa como **señal/juez** (p. ej. ¿son el mismo evento dos mercados?).
NUNCA tiene autoridad de gasto ni decide órdenes — principio de diseño de HERMES.

Configuración (.env):
    HERMES_LLM_API_KEY   clave (OpenRouter sk-or-... u OpenAI)
    HERMES_LLM_BASE_URL  por defecto https://openrouter.ai/api/v1
    HERMES_LLM_MODEL     p. ej. google/gemini-3-flash-preview
"""

from __future__ import annotations

import json
import re

import requests

from hermes.core.config import Settings, get_settings
from hermes.core.logging import get_logger

logger = get_logger("utils.llm")


def llm_available(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    return bool(s.llm_api_key and s.llm_model)


class LLMClient:
    def __init__(self, settings: Settings | None = None):
        s = settings or get_settings()
        self.key = s.llm_api_key
        self.base = (s.llm_base_url or "https://openrouter.ai/api/v1").rstrip("/")
        self.model = s.llm_model

    def chat(self, system: str, user: str, temperature: float = 0.0, max_tokens: int = 300) -> str:
        if not self.key:
            raise RuntimeError("HERMES_LLM_API_KEY no configurado en .env")
        if not self.model:
            raise RuntimeError("HERMES_LLM_MODEL no configurado en .env")
        resp = requests.post(
            f"{self.base}/chat/completions",
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=40,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def chat_json(self, system: str, user: str) -> dict:
        """Como chat() pero parsea JSON (tolerante a ```fences``` y prosa)."""
        txt = self.chat(system, user)
        s = re.sub(r"^```(?:json)?\s*", "", txt.strip())
        s = re.sub(r"\s*```$", "", s)
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", s, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
        return {}
