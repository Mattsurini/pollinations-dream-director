#!/usr/bin/env python3
"""Validate skill structure, links, secrets, scripts and generated assets.

Usage: python scripts/validate.py --skill . --project examples/lighthouse
"""

from __future__ import annotations

import argparse
import json
import py_compile
import re
import sys
import tempfile
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SECRET_PATTERNS = {
    "pollinations_key": re.compile(r"sk_[A-Za-z0-9]{16,}"),
    "github_token": re.compile(r"(?:ghp_|gho_|github_pat_)[A-Za-z0-9_]{20,}"),
    "aws_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
SKIP_DIRS = {".git", "node_modules", ".cache", "__pycache__", ".pytest_cache"}


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        raise ValueError("SKILL.md must start with YAML frontmatter (---)")
    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not match:
        raise ValueError("Unterminated YAML frontmatter")
    meta: dict = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip("\"'")
    return meta, match.group(2)


def check_links(root: Path, text: str) -> list[str]:
    problems = []
    for target in re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        clean = target.split("#")[0].strip()
        if not clean:
            continue
        if not (root / clean).exists():
            problems.append(f"broken relative link: {target}")
    return problems


def scan_secrets(root: Path) -> list[str]:
    hits = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".mp3", ".mp4", ".woff2"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in SECRET_PATTERNS.items():
            for match in pattern.finditer(text):
                if "SECRET_PATTERNS" in text[max(0, match.start() - 60):match.start()]:
                    continue
                hits.append(f"{path.relative_to(root)}: {label}")
    return sorted(set(hits))


def check_screenshot(path: Path) -> list[str]:
    if not path.is_file():
        return [f"screenshot missing: {path}"]
    size = path.stat().st_size
    if size > 5 * 1024 * 1024:
        return [f"screenshot too large: {size} bytes (max 5 MB)"]
    try:
        raw = path.read_bytes()
        if raw.startswith(b"\x89PNG"):
            w, h = int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")
        else:
            return ["screenshot must be PNG for this validator"]
    except OSError as exc:
        return [f"screenshot unreadable: {exc}"]
    if w < 1280 or h < 720:
        return [f"screenshot too small: {w}x{h} (min 1280x720)"]
    return []


def validate(skill: Path, project: Path | None, screenshot: Path | None) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict = {}
    skill = skill.resolve()
    skill_md = skill / "SKILL.md"
    if not skill_md.is_file():
        return {"ok": False, "errors": ["SKILL.md missing"], "checks": {}}
    text = skill_md.read_text(encoding="utf-8")
    try:
        meta, body = parse_frontmatter(text)
    except ValueError as exc:
        return {"ok": False, "errors": [str(exc)], "checks": {}}
    name = meta.get("name", "")
    description = meta.get("description", "")
    checks["name"] = name
    if not NAME_RE.match(name) or name != skill.name:
        errors.append(f"name '{name}' invalid or different from directory '{skill.name}'")
    if not (1 <= len(description) <= 1024):
        errors.append("description must be 1-1024 characters")
    if not description.startswith("Use when"):
        warnings.append("description should start with 'Use when...' for reliable discovery")
    if len(body.splitlines()) > 500:
        warnings.append("SKILL.md body exceeds 500 lines; move detail into references/")
    checks["body_lines"] = len(body.splitlines())

    errors.extend(check_links(skill, text))
    for doc in skill.rglob("*.md"):
        if doc != skill_md and ".cache" not in doc.parts:
            errors.extend(check_links(doc.parent, doc.read_text(encoding="utf-8", errors="replace")))

    secrets = scan_secrets(skill)
    checks["secrets_found"] = len(secrets)
    errors.extend(secrets)

    compiled = 0
    for script in sorted((skill / "scripts").glob("*.py")):
        with tempfile.TemporaryDirectory() as tmp:
            try:
                py_compile.compile(str(script), cfile=str(Path(tmp) / (script.stem + ".pyc")),
                                   doraise=True)
                compiled += 1
            except py_compile.PyCompileError as exc:
                errors.append(f"syntax error in {script.name}: {exc.msg}")
    checks["scripts_compiled"] = compiled

    readme = skill / "README.md"
    if readme.is_file():
        rtext = readme.read_text(encoding="utf-8")
        if "pollinations.ai" not in rtext or "badge" not in rtext.lower():
            warnings.append("README should include the Pollinations credit badge")
    else:
        errors.append("README.md missing")

    if project:
        for filename in ("brief.json", "bible.json", "storyboard.json", "manifest.json", "index.html"):
            if not (project / filename).is_file():
                errors.append(f"project artifact missing: {filename}")
        manifest_path = project / "manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            count = 0
            for entry in manifest.get("assets", []):
                for kind in ("audio", "image", "video"):
                    info = entry.get(kind, {})
                    if "path" in info:
                        asset = Path(info["path"])
                        if not asset.is_file() or asset.stat().st_size == 0:
                            errors.append(f"empty or missing asset: {asset}")
                        else:
                            count += 1
            checks["verified_assets"] = count
            proof_path = project / "api-proof" / "manifest.json"
            if proof_path.is_file():
                proof = json.loads(proof_path.read_text(encoding="utf-8"))
                for rec in proof.get("records", []):
                    if rec.get("status") == "captured" and rec.get("file"):
                        asset = project / "api-proof" / rec["file"]
                        if not asset.is_file() or asset.stat().st_size == 0:
                            errors.append(f"empty or missing proof asset: {asset}")
                        else:
                            checks["verified_assets"] = checks["verified_assets"] + 1
            if checks["verified_assets"] == 0:
                errors.append("no verified generated assets found in manifest or api-proof")

    if screenshot:
        errors.extend(check_screenshot(screenshot))

    return {"ok": not errors, "errors": errors, "warnings": warnings, "checks": checks}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", default=".")
    ap.add_argument("--project")
    ap.add_argument("--screenshot")
    args = ap.parse_args()
    project = Path(args.project).resolve() if args.project else None
    screenshot = Path(args.screenshot).resolve() if args.screenshot else None
    result = validate(Path(args.skill), project, screenshot)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
