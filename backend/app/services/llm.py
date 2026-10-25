"""Local LLM via Ollama (offline). Used only to explain and draft: it never decides, never calls tools,
and its output is validated against a JSON schema. Everything works without it (deterministic fallbacks)."""
import json
import time

import httpx

from ..config import settings

_cache = {"t": 0.0, "ok": False, "model": settings.ollama_model}


def available() -> bool:
    if settings.llm_backend == "none":
        return False
    if time.time() - _cache["t"] < 60:
        return _cache["ok"]
    ok = False
    try:
        r = httpx.get(f"{settings.ollama_url}/api/tags", timeout=0.8)
        names = [m.get("name", "") for m in r.json().get("models", [])]
        exact = [n for n in names if n.split(":")[0] == settings.ollama_model.split(":")[0]]
        # Use the configured model if pulled; otherwise any local chat model (embedding models excluded).
        usable = exact or [n for n in names if not any(k in n for k in ("embed", "bge", "nomic", "minilm"))]
        if usable:
            _cache["model"] = exact[0] if exact else usable[0]
            ok = True
    except Exception:
        ok = False
    _cache.update(t=time.time(), ok=ok)
    return ok


def chat_json(system: str, user: str, schema: dict, timeout: float = 60) -> dict | None:
    try:
        r = httpx.post(f"{settings.ollama_url}/api/chat", timeout=timeout, json={
            "model": _cache["model"], "stream": False, "format": schema,
            "options": {"temperature": 0},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        })
        data = json.loads(r.json()["message"]["content"])
        missing = [k for k in schema.get("required", []) if k not in data]
        return None if missing else data
    except Exception:
        return None


def name() -> str:
    return f"ollama:{_cache['model']}" if available() else "none (deterministic templates)"
