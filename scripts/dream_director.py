#!/usr/bin/env python3
"""Dream Director — turn one idea into a cinematic, reproducible media package.

Pipeline: idea -> creative bible -> storyboard -> assets -> presentation site.
Every artifact records its provenance; nothing is invented when a capability is
unavailable (fallbacks are explicit and visible in the final site).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pollinations_client as api  # noqa: E402
import site_render as site_module  # noqa: E402

DEFAULT_TONE = ["NOIR", "INTIMATE", "MEMORY"]
DEFAULT_PALETTE = {"primary": "#e8b96b", "secondary": "#242838", "accent": "#6fd3c7"}
SHOT_COUNT = 6


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def seed_for(project_id: str, shot_id: str) -> int:
    """Stable seed: the same shot always reproduces the same generated image."""
    return int(sha(f"{project_id}:{shot_id}")[:8], 16) % 2_000_000_000


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def offline_bible(brief: dict) -> dict:
    idea = brief["idea"].strip()
    title = brief.get("title") or idea.split(".")[0].strip().title()[:46] or "Untitled"
    protagonist = {"name": "The Wanderer", "id": "protagonist",
                   "description": f"Central figure moving through the world of: {idea[:110]}"}
    place = {"name": "The Threshold", "id": "location",
             "description": "One recurring location holds the story together across shots."}
    motif = {"name": "A single point of light", "id": "motif",
             "description": "Repeated light source used as a visual rhyme between scenes."}
    beats = [
        ("The Arrival", "wide establishing frame, slow push-in", "establishing",
         "It began with a small light that refused to go out."),
        ("The Signal", "medium shot, handheld drift", "anticipation",
         "Something in the quiet answered back."),
        ("The Crossing", "tracking shot, lateral movement", "tension",
         "Every step forward cost a memory."),
        ("The Ledger", "close-up, shallow depth of field", "intimate",
         "She counted what she had left, and began again."),
        ("The Reckoning", "low angle, slow crane", "climax",
         "The light was never outside. It had been carried all along."),
        ("The Afterimage", "locked-off wide, long hold", "resolution",
         "By morning, the world looked the same. It was not."),
    ]
    shots = []
    for i, (name, camera, mood, narration) in enumerate(beats, 1):
        sid = f"s{i:02d}"
        shots.append({
            "id": sid, "title": name,
            "description": f"{idea[:120]} — {name.lower()}: {camera}.",
            "camera": camera, "mood": mood, "narration": narration,
            "duration_seconds": 5,
            "image_prompt": (f"Cinematic film still, {name.lower()}, {camera}, "
                             f"{mood} mood, subject: {idea[:180]}. "
                             "Consistent character design and warm amber/teal palette, "
                             "35mm anamorphic, shallow depth of field, subtle film grain."),
        })
    return {
        "title": title, "logline": f"A short cinematic study of {idea[:150]}",
        "genre": "visual short", "tone": DEFAULT_TONE, "palette": DEFAULT_PALETTE,
        "visual_grammar": "Amber key light, teal fill, long lenses, patient compositions.",
        "continuity": {"characters": [protagonist], "locations": [place], "props": [motif]},
        "shots": shots, "source": "offline-template",
    }


SYSTEM_PROMPT = """You are a film director and storyboard artist. Return ONLY one JSON object,
no prose, no markdown fences. Schema:
{
 "title": string (<=46 chars),
 "logline": string (<=180 chars),
 "genre": string,
 "tone": array of 3-5 short uppercase words,
 "palette": {"primary":"#RRGGBB","secondary":"#RRGGBB","accent":"#RRGGBB"},
 "visual_grammar": string,
 "continuity": {
   "characters":[{"id":string,"name":string,"description":string}],
   "locations":[{"id":string,"name":string,"description":string}],
   "props":[{"id":string,"name":string,"description":string}]
 },
 "shots":[{ "id":"s01".."s06", "title":string, "description":string,
   "camera":string, "mood":string, "narration":string (one spoken sentence),
   "duration_seconds":5,
   "image_prompt":string (detailed, self-contained, includes character/location/prop
   anchors verbatim for continuity) }]
}
Exactly 6 shots. Every shot image_prompt must repeat the continuity anchors it uses
so separate generations stay visually consistent. Keep narration under 180 chars."""


def extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start:end + 1])


def normalize_bible(data: dict, brief: dict, source: str) -> dict:
    fallback = offline_bible(brief)
    palette = data.get("palette") if isinstance(data.get("palette"), dict) else {}
    for key, value in DEFAULT_PALETTE.items():
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(palette.get(key, ""))):
            palette[key] = value
    shots = []
    source_shots = data.get("shots") if isinstance(data.get("shots"), list) else []
    for i in range(SHOT_COUNT):
        base = dict(fallback["shots"][i])
        incoming = source_shots[i] if i < len(source_shots) and isinstance(source_shots[i], dict) else {}
        for field in ("id", "title", "description", "camera", "mood", "narration", "image_prompt"):
            value = incoming.get(field)
            if isinstance(value, str) and value.strip():
                base[field] = value.strip()[:1800]
        try:
            base["duration_seconds"] = max(2, min(15, int(incoming.get("duration_seconds", 5))))
        except (TypeError, ValueError):
            pass
        shots.append(base)
    continuity = {}
    incoming_cont = data.get("continuity") if isinstance(data.get("continuity"), dict) else {}
    for group in ("characters", "locations", "props"):
        items = incoming_cont.get(group)
        if isinstance(items, list) and items and all(isinstance(x, dict) for x in items):
            continuity[group] = [{"id": str(x.get("id", f"{group}-{n}")),
                                  "name": str(x.get("name", x.get("id", f"Anchor {n}"))),
                                  "description": str(x.get("description", ""))[:400]}
                                 for n, x in enumerate(items[:4], 1)]
        else:
            continuity[group] = fallback["continuity"][group]
    tone = data.get("tone") if isinstance(data.get("tone"), list) else []
    tone = [str(t).upper()[:18] for t in tone[:5] if str(t).strip()] or fallback["tone"]
    return {
        "title": str(data.get("title") or fallback["title"])[:46],
        "logline": str(data.get("logline") or fallback["logline"])[:240],
        "genre": str(data.get("genre") or fallback["genre"])[:80],
        "tone": tone,
        "palette": palette,
        "visual_grammar": str(data.get("visual_grammar") or fallback["visual_grammar"])[:400],
        "continuity": continuity,
        "shots": shots,
        "source": source,
    }


def cmd_init(args) -> dict:
    project = Path(args.out).resolve()
    if (project / "brief.json").exists() and not args.force:
        raise SystemExit(f"Refusing to overwrite existing project: {project} (use --force)")
    idea = args.idea.strip()
    if len(idea) < 5:
        raise SystemExit("--idea must be at least 5 characters")
    title = args.title or idea.split(".")[0].strip().title()[:46]
    brief = {"idea": idea, "title": title, "project_id": sha(idea + title)[:12],
             "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "skill": "pollinations-dream-director/1.0"}
    write_json(project / "brief.json", brief)
    return {"project": str(project), "project_id": brief["project_id"], "status": "initialized"}


def cmd_plan(args) -> dict:
    project = Path(args.project).resolve()
    brief = read_json(project / "brief.json")
    models = api.discover_models(project / ".cache")
    text_models = api.select_models(models, "text", allow_paid=args.allow_paid, limit=3)
    source = "offline-template"
    data = {}
    model_used = None
    if not args.offline:
        for model in text_models:
            try:
                raw = api.generate_text(
                    f"Idea: {brief['idea']}\nWorking title: {brief['title']}",
                    system=SYSTEM_PROMPT, model=model)
                data = extract_json(raw)
                model_used = model
                source = f"pollinations-text:{model}"
                break
            except api.PollinationsError as exc:
                print(f"note: text model {model} failed ({exc.code}); trying next", file=sys.stderr)
            except (ValueError, json.JSONDecodeError) as exc:
                print(f"note: text model {model} returned unusable JSON ({exc}); trying next",
                      file=sys.stderr)
    bible = normalize_bible(data, brief, source)
    bible["text_model"] = model_used
    write_json(project / "bible.json", bible)
    storyboard = {"project_id": brief["project_id"], "title": bible["title"],
                  "visual_grammar": bible["visual_grammar"],
                  "shots": [{"id": s["id"], "title": s["title"], "camera": s["camera"],
                             "duration_seconds": s["duration_seconds"],
                             "image_prompt": s["image_prompt"]} for s in bible["shots"]]}
    write_json(project / "storyboard.json", storyboard)
    return {"bible": str(project / "bible.json"), "source": source,
            "shots": len(bible["shots"]), "model": model_used}


def cmd_assets(args) -> dict:
    project = Path(args.project).resolve()
    brief = read_json(project / "brief.json")
    bible = read_json(project / "bible.json")
    auth = api.detect_auth()
    models = api.discover_models(project / ".cache")
    caps = api.capabilities(auth, models)
    if args.no_images:
        caps["image"] = False
        caps["video"] = False
    selected = {
        "text": api.select_models(models, "text", allow_paid=args.allow_paid, limit=1)[0],
        "image": api.select_models(models, "image", allow_paid=args.allow_paid, limit=2),
        "audio": api.select_models(models, "audio", allow_paid=args.allow_paid, limit=2),
        "video": api.select_models(models, "video", allow_paid=args.allow_paid, limit=1),
    }
    image_models = selected["image"]
    audio_model = selected["audio"][0]
    assets = []
    image_blocked_reason = None
    for shot in bible["shots"]:
        sid = shot["id"]
        seed = seed_for(brief["project_id"], sid)
        entry = {"shot_id": sid, "seed": seed, "duration": shot.get("duration_seconds", 5)}
        if caps["audio"]:
            try:
                entry["audio"] = api.generate_media(
                    "audio", shot["narration"][:180], project / "audio" / f"{sid}.mp3",
                    model=audio_model, auth=auth, voice=args.voice, seed=seed)
            except api.PollinationsError as exc:
                entry["audio"] = {"status": "unavailable", "reason": f"{exc.code}: {exc.message[:120]}"}
        else:
            entry["audio"] = {"status": "unavailable", "reason": "capability disabled"}
        if caps["image"] and image_models:
            if image_blocked_reason:
                entry["image"] = {"status": "unavailable", "reason": image_blocked_reason}
            else:
                try:
                    entry["image"] = api.generate_media(
                        "image", shot["image_prompt"], project / "scenes" / f"{sid}.jpg",
                        model=image_models[0], auth=auth, seed=seed, width=1152, height=648)
                except api.AuthRequired as exc:
                    image_blocked_reason = exc.message[:120]
                    entry["image"] = {"status": "unavailable", "reason": image_blocked_reason}
                except api.PollinationsError as exc:
                    entry["image"] = {"status": "unavailable", "reason": f"{exc.code}: {exc.message[:120]}"}
        else:
            entry["image"] = {"status": "unavailable",
                              "reason": "API key required" if not caps["image"] else "capability disabled"}
        if args.video and caps["video"]:
            try:
                entry["video"] = api.generate_media(
                    "video", shot["description"], project / "video" / f"{sid}.mp4",
                    model=selected["video"][0], auth=auth, seed=seed,
                    duration=shot.get("duration_seconds", 5), width=1152, height=648)
            except api.PollinationsError as exc:
                entry["video"] = {"status": "unavailable", "reason": f"{exc.code}: {exc.message[:120]}"}
        assets.append(entry)
    cap_info = {
        "text": {"enabled": True, "model": bible.get("text_model") or selected["text"],
                 "count": 1 if bible.get("source", "").startswith("pollinations") else 0},
        "audio": {"enabled": caps["audio"], "model": audio_model,
                  "count": sum(1 for a in assets if "bytes" in a.get("audio", {}))},
        "image": {"enabled": caps["image"],
                  "model": image_models[0] if image_models else "—",
                  "count": sum(1 for a in assets if "bytes" in a.get("image", {}))},
        "video": {"enabled": bool(args.video and caps["video"]),
                  "model": selected["video"][0],
                  "count": sum(1 for a in assets if "bytes" in a.get("video", {}))},
    }
    manifest = {"project_id": brief["project_id"], "title": bible["title"],
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "auth": auth.redacted(), "capabilities": cap_info, "assets": assets,
                "model_catalog_size": len(models)}
    write_json(project / "manifest.json", manifest)
    return {"manifest": str(project / "manifest.json"),
            "audio": cap_info["audio"]["count"], "images": cap_info["image"]["count"],
            "video": cap_info["video"]["count"], "auth": auth.redacted()}


def cmd_site(args) -> dict:
    project = Path(args.project).resolve()
    bible = read_json(project / "bible.json")
    manifest = read_json(project / "manifest.json")
    out = site_module.render(project, bible, manifest)
    return {"site": str(project / "index.html"), "bytes": len(out)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dream_director.py", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init", help="create a project and record the idea")
    p.add_argument("--idea", required=True); p.add_argument("--out", required=True)
    p.add_argument("--title"); p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init)
    p = sub.add_parser("plan", help="write creative bible + storyboard")
    p.add_argument("--project", required=True); p.add_argument("--offline", action="store_true")
    p.add_argument("--allow-paid", action="store_true"); p.set_defaults(func=cmd_plan)
    p = sub.add_parser("assets", help="generate narration, stills and optional video")
    p.add_argument("--project", required=True); p.add_argument("--no-images", action="store_true")
    p.add_argument("--allow-paid", action="store_true"); p.add_argument("--video", action="store_true")
    p.add_argument("--voice", default="alloy"); p.set_defaults(func=cmd_assets)
    p = sub.add_parser("site", help="render the responsive presentation")
    p.add_argument("--project", required=True); p.set_defaults(func=cmd_site)
    p = sub.add_parser("all", help="init, plan, assets and site in one pass")
    p.add_argument("--idea", required=True); p.add_argument("--out", required=True)
    p.add_argument("--title"); p.add_argument("--force", action="store_true")
    p.add_argument("--offline", action="store_true"); p.add_argument("--no-images", action="store_true")
    p.add_argument("--allow-paid", action="store_true"); p.add_argument("--video", action="store_true")
    p.add_argument("--voice", default="alloy")
    def run_all(a):
        a.project = a.out
        results = [cmd_init(a), cmd_plan(a), cmd_assets(a), cmd_site(a)]
        return {"steps": len(results), "project": a.out, "site": results[-1]["site"]}
    p.set_defaults(func=run_all)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        print(json.dumps(args.func(args), ensure_ascii=False, indent=2))
    except (OSError, ValueError, api.PollinationsError) as exc:
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
