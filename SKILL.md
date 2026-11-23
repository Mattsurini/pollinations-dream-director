---
name: pollinations-dream-director
description: "Use when a user wants to turn an idea, story, or short brief into a complete cinematic package — creative direction, script, storyboard, consistent AI stills, narration, sound, music, video and a responsive presentation site — using Pollinations models through the API or polli CLI. Triggers on 'make a short film from this idea', 'dream director', 'cinematic storyboard with AI images and audio', 'Pollinations creative project', or any request for an end-to-end AI film preproduction workflow."
license: MIT
compatibility: "Python 3.9+ (stdlib only) and network access to gen.pollinations.ai. Optional: @pollinations/cli for device login. API key needed only for image/video generation; text and TTS work unauthenticated."
metadata:
  author: pollinations-dream-director
  version: "1.0.0"
  quest: "pollinations/pollinations#20020"
  category: image
  platform: cli
---

# Pollinations Dream Director

Turn one idea into a directed, reproducible cinematic package: creative bible →
storyboard → consistent stills → narration/audio → optional video → responsive
presentation site, with proof of what was actually generated.

## Core principle

**Never invent a generated asset.** If a capability is unavailable, say so in the
artifact and render an explicit previsualisation fallback. A credible cut with a
labelled empty frame beats a fake "AI-generated" image every time. All model IDs
come from the live Pollinations catalog; all secrets stay out of files and logs.

## When to use

- "Make a short film / visual story from this idea using Pollinations"
- "Give me a director's treatment, shot list and images with the same character"
- "Build a cinematic landing page with AI narration and stills"
- Any task needing coordinated text + image + audio + video generation on Pollinations

Do **not** use for a single standalone image or one-line TTS — call the Pollinations
API directly instead.

## Non-negotiables

1. Run `scripts/dream_director.py` — do not hand-write bibles, manifests or sites.
2. Discover models from `https://gen.pollinations.ai/models`; never assume a model exists.
3. Read the key from `POLLINATIONS_API_KEY` or `polli` credentials. Never write it to
   a project file, print it, or put it in a URL that gets logged.
4. Record every asset in `manifest.json` with model, seed, byte count and source.
5. Use `offline-template` and `PREVIS` labels when generation is unavailable.

## Quickstart

```bash
# 1. Generate a complete project (text + narration work with no key)
python scripts/dream_director.py all \
  --idea "a lighthouse keeper who remembers every ship lost at sea" \
  --out examples/my-film --title "The Last Light"

# 2. With a Pollinations key, the same command also generates real stills
export POLLINATIONS_API_KEY=...          # or: polli auth login
python scripts/dream_director.py all --idea "..." --out examples/my-film --force
# Optional: --allow-paid for premium models, --video for motion clips

# 3. Validate structure, assets, links and secrets
python scripts/validate.py --skill . --project examples/my-film \
  --screenshot examples/my-film/screenshot.png
```

## Workflow

### 1. Brief (`init`)
Writes `brief.json` with the idea, title and a stable `project_id` derived from a
SHA-256 hash. Re-running with the same idea yields the same seeds.

### 2. Creative direction (`plan`)
Calls a live healthy **text** model with a strict JSON system prompt and writes:
- `bible.json` — title, logline, genre, tone, palette, visual grammar,
  continuity ledger, six shots.
- `storyboard.json` — camera, duration and the full image prompt per shot.

If text generation fails, the deterministic `offline-template` planner is used and
the `source` field says so. Never present offline copy as model-generated.

### 3. Continuity ledger (built into the bible)
Three groups — `characters`, `locations`, `props`. Every shot's `image_prompt`
repeats the anchor descriptions verbatim. This is what keeps the same keeper,
coat and lamp recognizable across six independently generated frames.

### 4. Assets (`assets`)
For each shot, a stable seed is derived as
`int(sha256(project_id + ":" + shot_id)[:8], 16) % 2_000_000_000`.

| Capability | Auth needed | Default behaviour | Fallback |
|---|---|---|---|
| Text / direction | No | free healthy text model | offline template |
| Narration (TTS) | No | free healthy audio model, MP3 | "unavailable" label |
| Stills | **Yes** | free healthy image model, 1152×648 | CSS previsualisation frame |
| Video | **Yes** | cheapest healthy video model | shot card stays a still |

Failures are classified as `auth_required`, `payment_required`, `rate_limited`,
`capability_unavailable`, `network_error` or `invalid_asset`. Auth failure stops
the whole image loop once (no six identical 401s); audio still completes.

### 5. Presentation (`site`)
Renders a self-contained, responsive `index.html`: hero, film-strip shot cards,
audio players, continuity ledger and a provenance table. All dynamic text is
HTML-escaped; palette values are validated as `#RRGGBB`. No external CSS, fonts
or scripts — the site works offline.

### 6. Verify (`validate`)
Checks frontmatter/name agreement, relative links, Python syntax, secrets,
README credit, project artifacts, non-empty asset files and screenshot size.

## Authentication policy

- Check in this order: `POLLINATIONS_API_KEY`, `~/.pollinations/credentials.json`.
- For interactive setup use `polli auth login` (device flow). For agents use
  `polli --json auth login --no-browser` and let the human approve in the browser.
- `AuthState.redacted()` is the only form ever printed. A key is never added to
  a prompt, README, manifest, commit message or screenshot.
- Never commit `.env`, credential JSON, or files matching secrets patterns.

## Model selection policy

`select_models()` filters `category`, excludes `community/*`, requires
`health.status == "healthy"`, respects `paid_only` unless `--allow-paid`, and ranks
by free-first, then observed request volume (a proxy for a working free tier),
then success rate. Capability filters
(e.g. `require_input="image"` for img2img) are applied before ranking. Last-resort
constants are used only when the catalog request itself fails.

## Output contract

A finished project contains:

```
brief.json  bible.json  storyboard.json  manifest.json  index.html
audio/s01.mp3 ...        scenes/s01.jpg ... (only when generated)
video/  (only with --video)
```

`manifest.json.capabilities` reports `enabled`, `model` and `count` per modality.
`manifest.json.assets` is an array keyed by `shot_id`; each kind holds either a
provenance object (`path`, `bytes`, `model`, `seed`, `source`) or
`{"status": "unavailable", "reason": "..."}`.

## Example: The Last Light

```bash
python scripts/dream_director.py all \
  --idea "a lighthouse keeper who remembers every ship lost at sea" \
  --out examples/lighthouse --title "The Last Light"

# Result: 6 shots, stable-seed continuity ledger, labelled fallbacks, and a
# Live API Proof gallery of real captured Pollinations responses.
# With a key, the same command produces real stills and narration instead.
```

See `examples/lighthouse/` in this repository for the checked-in output and its
provenance manifest.

## Common mistakes

- **Saying "images generated" when the API returned 401.** Check the manifest first.
- **Hardcoding today's model name.** Availability changes; call `/models`.
- **Putting the key in `image.pollinations.ai/...?key=`.** Use the Authorization header.
- **Reusing a single prompt for all six shots.** Continuity comes from ledger anchors.
- **Committing generated credentials or the browser's downloaded key file.**
- **Treating a 5-second video model flag as guaranteed.** Verify the file with `ffprobe`.

## References

- `references/api.md` — endpoint shapes, parameters, error codes, rate limits.
- `references/workflow.md` — directing method, prompt construction, fallback matrix.
- `scripts/pollinations_client.py` — auth, discovery, generation, error taxonomy.
- `scripts/validate.py` — the exact checks this skill promises.
