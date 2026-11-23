"""Pollinations API client for pollinations-dream-director.

Design rules:
  * stdlib only (urllib), no pip dependencies
  * secrets are read from the environment or the official CLI credential file
    and are NEVER logged, echoed, or written into project artifacts
  * model IDs are discovered from the live /models endpoint, never hardcoded
    as the only option (the constants below are last-resort fallbacks)
  * every generation failure is classified so callers can degrade gracefully
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

BASE = os.environ.get("POLLINATIONS_BASE_URL", "https://gen.pollinations.ai").rstrip("/")
CACHE_TTL = 6 * 60 * 60  # model catalog is cached for 6 hours

# Last-resort fallbacks only used when the live catalog cannot be fetched.
FALLBACK_MODELS = {
    "text": ["openai/gpt-5.4-nano", "deepseek/deepseek-v4.1-flash"],
    "image": ["tongyi-mai/z-image-turbo", "black-forest-labs/flux.1-schnell"],
    "audio": ["openai/tts-1", "microsoft/mai-voice-2.1"],
    "video": ["alibaba/wan-2.2-fast", "bytedance/seedance-2.0-mini"],
}


class PollinationsError(RuntimeError):
    def __init__(self, code: str, message: str, status: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class AuthRequired(PollinationsError):
    def __init__(self, message: str = "A Pollinations API key is required for this capability."):
        super().__init__("auth_required", message, 401)


class CapabilityUnavailable(PollinationsError):
    pass


@dataclass
class AuthState:
    source: str
    authenticated: bool
    key: str = ""

    def redacted(self) -> dict:
        return {"source": self.source, "authenticated": self.authenticated}


def detect_auth() -> AuthState:
    """Find a key without ever printing it. Order: env, polli credential file."""
    key = os.environ.get("POLLINATIONS_API_KEY", "").strip()
    if key:
        return AuthState("environment", True, key)
    cred = Path.home() / ".pollinations" / "credentials.json"
    if cred.is_file():
        try:
            data = json.loads(cred.read_text(encoding="utf-8"))
            for candidate in (
                data.get("apiKey"),
                data.get("key"),
                data.get("token"),
                (data.get("keys") or {}).get("secret") if isinstance(data.get("keys"), dict) else None,
            ):
                if isinstance(candidate, str) and candidate.strip():
                    return AuthState(f"credentials file ({cred.name})", True, candidate.strip())
        except (OSError, ValueError):
            pass
    return AuthState("none", False)


def _headers(auth: AuthState | None, extra: dict | None = None) -> dict:
    headers = {"User-Agent": "dream-director/1.0 (+agentskills.io)"}
    headers.update(extra or {})
    if auth and auth.key:
        headers["Authorization"] = f"Bearer {auth.key}"
    return headers


def _parse_error(body: bytes, status: int) -> PollinationsError:
    text = body.decode("utf-8", "replace")[:500]
    code = "http_error"
    message = text
    try:
        payload = json.loads(text)
        err = payload.get("error", payload)
        if isinstance(err, dict):
            code = str(err.get("code", code))
            message = str(err.get("message", message))
    except ValueError:
        pass
    if status in (401, 403):
        return AuthRequired(message)
    if status == 402:
        return PollinationsError("payment_required", message, status)
    if status == 429:
        return PollinationsError("rate_limited", message, status)
    if status in (400, 404, 422):
        return CapabilityUnavailable(code, message, status)
    return PollinationsError(code, message, status)


def _request(url: str, auth: AuthState | None = None, *, method: str = "GET",
             payload: dict | None = None, timeout: float = 120.0,
             retries: int = 4, expect: str = "json") -> bytes:
    data = None
    headers = _headers(auth, {"Accept": "*/*"})
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    last_error: PollinationsError | None = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            body = exc.read()
            err = _parse_error(body, exc.code)
            # The gateway sometimes answers 401 to throttle bursty anonymous
            # traffic. Retry with backoff before treating it as an auth failure.
            anonymous_throttle = (exc.code == 401 and not (auth and auth.key))
            if (err.code in ("rate_limited", "http_error") and exc.code >= 500) or anonymous_throttle:
                if attempt < retries:
                    last_error = err
                    time.sleep(min(2.0 * (2 ** attempt), 16.0))
                    continue
            if err.code == "rate_limited" and attempt < retries:
                last_error = err
                time.sleep(2.0 * (attempt + 1))
                continue
            raise err from None
        except urllib.error.URLError as exc:
            last_error = PollinationsError("network_error", str(exc.reason))
            if attempt < retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            raise last_error from None
    raise last_error or PollinationsError("network_error", "request failed")


def discover_models(cache_dir: Path | None = None, *, refresh: bool = False) -> list[dict]:
    """Fetch the live model catalog; cache it locally to avoid repeated calls."""
    cache = (cache_dir or Path.cwd() / ".cache") / "pollinations-models.json"
    if not refresh and cache.is_file() and time.time() - cache.stat().st_mtime < CACHE_TTL:
        try:
            return json.loads(cache.read_text(encoding="utf-8"))["models"]
        except (ValueError, KeyError, OSError):
            pass
    raw = _request(f"{BASE}/models", timeout=45)
    models = json.loads(raw.decode("utf-8"))
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"fetched_at": time.time(), "models": models}),
                     encoding="utf-8")
    return models


def select_models(models: list[dict], category: str, *, allow_paid: bool = False,
                  require_input: str | None = None, limit: int = 4) -> list[str]:
    """Rank healthy models: free first (unless paid allowed), then reliability."""
    candidates = []
    for m in models:
        if m.get("category") != category or m.get("name", "").startswith("community/"):
            continue
        health = (m.get("health") or {}).get("status", "unknown")
        if health != "healthy":
            continue
        if m.get("paid_only") and not allow_paid:
            continue
        if require_input and require_input not in (m.get("input_modalities") or []):
            continue
        paid_rank = (1 if m.get("paid_only") else 0) if allow_paid else (0 if m.get("paid_only") else 1)
        # Free models with real traffic are the safest no-key default: request
        # volume is a proxy for a working free tier, success rate breaks ties.
        score = (paid_rank,
                 min((m.get("health") or {}).get("requests", 0), 100000),
                 (m.get("health") or {}).get("success_rate", 0))
        candidates.append((score, m["name"]))
    candidates.sort(key=lambda item: item[0], reverse=True)
    names = [name for _, name in candidates]
    for fallback in FALLBACK_MODELS.get(category, []):
        if fallback not in names:
            names.append(fallback)
    return names[:limit]


def capabilities(auth: AuthState | None = None, models: list[dict] | None = None) -> dict:
    """Capability ladder. Text and TTS are available without a key; image and
    video generation require a key on the current Pollinations gateway."""
    a = auth or detect_auth()
    return {
        "text": True,
        "audio": True,
        "image": bool(a.authenticated),
        "video": bool(a.authenticated),
        "auth": a.redacted(),
        "models": len(models or []),
    }


def generate_text(prompt: str, *, system: str = "", model: str = "openai/gpt-5.4-nano",
                  auth: AuthState | None = None, temperature: float = 0.7,
                  max_tokens: int = 4000, timeout: float = 180.0) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = {"model": model, "messages": messages, "stream": False}
    # The unauthenticated tier is deliberately minimal: only model + one user
    # message + stream are accepted. System roles, temperature, max_tokens,
    # response_format and seeds all require a key. Fold the instructions into
    # the user turn and degrade gracefully instead of demanding credentials.
    authenticated = bool(auth and auth.key)
    if authenticated:
        body["temperature"] = temperature
        body["max_tokens"] = max_tokens
    else:
        body["messages"] = [{"role": "user", "content": f"{system}\n\n{prompt}" if system else prompt}]
    raw = _request(f"{BASE}/v1/chat/completions", auth, method="POST", payload=body,
                   timeout=timeout)
    data = json.loads(raw.decode("utf-8"))
    try:
        choice = data["choices"][0]
        content = choice.get("message", {}).get("content")
        if content is None:
            content = choice.get("content") or choice.get("text") or ""
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        return str(content).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise PollinationsError("unexpected_response", f"No text in response: {exc}") from None


def generate_media(kind: str, prompt: str, destination: Path, *, model: str,
                   auth: AuthState | None = None, timeout: float = 300.0,
                   **params) -> dict:
    """Generate one binary asset. Returns provenance metadata. Raises on failure."""
    endpoint = "image" if kind == "image" else "audio" if kind == "audio" else "video"
    if endpoint == "audio":
        path = f"/audio/{urllib.parse.quote(prompt[:1200], safe='')}"
        # Bare audio requests work without a key; voice/seed/format parameters
        # are treated as authenticated-tier features by the gateway.
        if auth and auth.key:
            query = {"model": model, "voice": params.get("voice", "alloy"),
                     "response_format": params.get("response_format", "mp3")}
            if params.get("seed") is not None:
                query["seed"] = params["seed"]
            if params.get("duration"):
                query["duration"] = params["duration"]
        else:
            query = {}
    else:
        path = f"/{endpoint}/{urllib.parse.quote(prompt[:1600], safe='')}"
        query = {"model": model, "width": params.get("width", 1024),
                 "height": params.get("height", 1024), "seed": params.get("seed", 0)}
        if params.get("quality"):
            query["quality"] = params["quality"]
        if params.get("duration"):
            query["duration"] = params["duration"]
    url = f"{BASE}{path}?{urllib.parse.urlencode(query)}"
    raw = _request(url, auth, timeout=timeout)
    if len(raw) < 128:
        raise PollinationsError("empty_asset", f"Only {len(raw)} bytes returned")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    ext = destination.suffix.lower()
    if ext in (".jpg", ".jpeg") and not raw.startswith(b"\xff\xd8"):
        raise PollinationsError("invalid_asset", "JPEG magic bytes missing")
    if ext == ".png" and not raw.startswith(b"\x89PNG"):
        raise PollinationsError("invalid_asset", "PNG magic bytes missing")
    if ext == ".mp3" and not (raw.startswith(b"ID3") or raw[:2] in (b"\xff\xfb", b"\xff\xf3")):
        raise PollinationsError("invalid_asset", "MP3 frame header missing")
    return {"path": str(destination), "bytes": len(raw), "model": model,
            "seed": params.get("seed"), "source": "pollinations"}
