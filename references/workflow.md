# Directing method and fallback matrix

## The six-beat spine

The planner deliberately uses six shots: enough for a short arc (setup, disturbance,
decision, cost, revelation, afterimage) while keeping generation cost bounded.
Every beat carries five fields that matter visually:

- `camera` — one lens/movement note ("low angle, slow crane").
- `mood` — one word the image model can anchor on.
- `narration` — one spoken sentence, ≤180 characters (TTS endpoint path limit).
- `image_prompt` — self-contained; repeats continuity anchors verbatim.
- `duration_seconds` — used in the site and as a video generation hint.

## Continuity ledger

Anchors are grouped as `characters`, `locations`, `props`. Each is an object with
`id`, `name`, `description`. The bible is the single source of truth; the site
renders it as a visible ledger so a viewer can audit continuity. When writing your
own bible, keep anchor descriptions short and concrete — the exact phrase is what
gets repeated across prompts.

## Determinism

`seed = int(sha256(project_id + ':' + shot_id)[:8], 16) % 2_000_000_000`
Combined with a fixed model and unchanged prompt, this makes re-runs reproducible
on models that honour the `seed` parameter. Record the seed in the manifest; never
claim reproducibility for a model that ignores seeds.

## Capability ladder

```
text available?  ── no ──> offline-template bible (labelled)
     │ yes
     v
audio available? ── no ──> shot card shows "narration unavailable"
     │ yes
     v
key present? ── no ──> CSS previsualisation frames, no image files
     │ yes
     v
generate stills ── 401/402 ──> stop image loop once, keep audio, mark reason
     │ ok
     v
--video? ── yes ──> generate motion; on failure keep still
```

The ladder never produces a file that pretends to be model output. A fallback is
a DOM element or a labelled status string, not a fabricated JPEG.

## Prompt hygiene

- Describe the frame, not the intention: "an old keeper in a salt-stained coat
  beside a brass lamp" beats "show his loneliness".
- Include the palette words ("amber key light, teal fill") and lens in every shot.
- Avoid safety-tripping phrasing; rephrase neutrally and change the seed on 400.
- Keep narration under the TTS path limit; split longer lines into two shots.

## Cost discipline

Text and TTS are the cheapest way to prove a pipeline works. Generate all six
narration tracks first; only then spend on stills. Use `--allow-paid` explicitly,
`polli models --stats` for health, and the cheapest healthy video model for motion.
Check `polli usage --history --json` to reconcile real costs after a run.

## Validation checklist

- [ ] `python -m unittest discover -s tests -v` passes offline.
- [ ] `python scripts/validate.py --skill . --project <project>` returns `"ok": true`.
- [ ] Every manifest path points to a non-empty file.
- [ ] Screenshot is PNG, 16:9, ≥1280×720 and ≤5 MB.
- [ ] `grep -r` finds no `sk_` keys, tokens, or credential files in the repo.
- [ ] README carries the "Made with pollinations.ai" credit badge.
