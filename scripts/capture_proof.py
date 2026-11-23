#!/usr/bin/env python3
"""Capture real, verifiable Pollinations responses for the demo's API proof.

This does NOT fabricate media. It sends a small set of canonical prompts to the
live gateway, saves only bytes actually returned, and records the exact prompt,
endpoint, model, byte count and SHA-256. Anonymous gateways may serve only
cached responses for canonical prompts; with a key, any prompt works.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pollinations_client import AuthState, generate_media, generate_text


PROMPTS = {
    "audio": ["hello world", "hello", "hi", "test"],
    "text": ["Say hello in one sentence"],
}


def slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")[:32]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="examples/lighthouse")
    args = ap.parse_args()
    project = Path(args.project).resolve()
    out = project / "api-proof"
    out.mkdir(parents=True, exist_ok=True)
    auth = AuthState("none", False)
    records = []
    for kind, prompts in PROMPTS.items():
        for prompt in prompts:
            record = {"kind": kind, "prompt": prompt, "endpoint": (
                "/audio/{text}" if kind == "audio" else "/v1/chat/completions")}
            try:
                if kind == "audio":
                    name = f"tts-{slug(prompt)}.mp3"
                    info = generate_media("audio", prompt, out / name,
                                          model="openai/tts-1", auth=auth)
                else:
                    name = f"text-{slug(prompt)}.txt"
                    content = generate_text(prompt, model="openai/gpt-5.4-nano", auth=auth)
                    (out / name).write_text(content, encoding="utf-8")
                    info = {"bytes": (out / name).stat().st_size, "model": "openai/gpt-5.4-nano"}
                raw = (out / name).read_bytes()
                record.update({"status": "captured", "file": name, "model": info["model"],
                               "bytes": info["bytes"],
                               "sha256": hashlib.sha256(raw).hexdigest(),
                               "source": "pollinations"})
            except Exception as exc:
                record.update({"status": "unavailable",
                               "reason": f"{type(exc).__name__}: {str(exc)[:160]}"})
            records.append(record)
    payload = {"captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "note": "Real responses from the live Pollinations gateway. Anonymous access "
                       "serves cached canonical prompts only; a key unlocks new prompts.",
               "records": records}
    (out / "manifest.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    captured = sum(1 for r in records if r["status"] == "captured")
    print(json.dumps({"captured": captured, "attempted": len(records),
                      "files": [r.get("file") for r in records if r.get("file")]}, indent=2))


if __name__ == "__main__":
    main()
