# Pollinations API reference (curated for Dream Director)

Base: `https://gen.pollinations.ai` (override with `POLLINATIONS_BASE_URL`).
Model catalog is public: `GET /models` (no key). Full OpenAPI: `/openapi.json`.
Documentation index: `https://gen.pollinations.ai/llms.txt`.

## Authentication

| Kind | Prefix | Use |
|---|---|---|
| Secret key | `sk_` | API generation, backend/CLI, no browser exposure |
| App key (Connect User Wallets) | `pk_` + redirect URIs | OAuth client id for user-authorized keys |
| Raw publishable (legacy) | `pk_` no binding | 1 pollen/IP/hour, do not mint new ones |

Send `Authorization: Bearer <key>` (preferred) or `?key=<key>`. Never log a key.
Text (`/v1/chat/completions`, `/text/{prompt}`) and TTS (`/audio/{text}`) currently
respond without a key; `/image/{prompt}` and `/video/{prompt}` return 401 without one.
Generation entitlements can change — always handle `auth_required` at runtime.

## Endpoints used by this skill

### `POST /v1/chat/completions` — creative direction
```json
{"model":"openai/gpt-5.4-nano","messages":[{"role":"system","content":"..."}],
 "temperature":0.7,"max_tokens":4000,"stream":false}
```
Response: `choices[0].message.content` (some models use `choices[0].content`).
`response_format`, `seed`, `reasoning_effort` are model-dependent — check
`supported_parameters` in `/models` before sending.

### `GET /text/{prompt}` — simple text (alternative)
Query: `model`, `system`, `seed`, `temperature`, `json`, `max_tokens`.

### `GET /image/{prompt}` — still frames
Query: `model` (default `tongyi-mai/z-image-turbo`), `width`, `height`, `seed`
(`-1` random), `quality`, `image` (public HTTPS reference), `output_format`,
`resolution`, `safe`. Returns image bytes; verify magic bytes before saving.

### `GET /audio/{text}` — narration / SFX / music
Query: `model` (default speech), `voice` (default `alloy`), `response_format`
`mp3|opus|aac|flac|wav|pcm`, `duration`/`seconds`, `instrumental`, `seed`.
Music: `elevenlabs/music-v2`, `google/lyria-3-clip-preview`.
SFX: `elevenlabs/eleven-text-to-sound-v2` (aliases `sfx`, `sound-effects`).

### `GET /video/{prompt}` — motion
Query: `model` (default `google/veo-3.1-fast`), `width`, `height`, `seed`,
`duration`, `image` (public HTTPS first frame), `resolution`, `audio`.
Flag support varies by model; verify the returned file with `ffprobe`.

## Status codes

| Code | Meaning | Skill behaviour |
|---|---|---|
| 200 | success | validate bytes, save, record provenance |
| 400/404/422 | invalid request / unsupported parameter | try next model, then fallback |
| 401/403 | key missing or unauthorized | stop the modality loop, mark `auth_required` |
| 402 | out of pollen / paid-only model | mark `payment_required`, suggest `--allow-paid` or top-up |
| 429 | rate limit | exponential backoff, then skip |
| 5xx | upstream failure | retry twice with backoff, then skip |

## Model catalog fields

`name`, `aliases`, `category`, `publisher`, `paid_only`, `health.status`,
`health.success_rate`, `health.requests`, `input_modalities`, `output_modalities`,
`supported_parameters`, `pricing`. Select healthy models; prefer free ones unless
the user opts into paid generation; filter by `input_modalities` for edits.

## CLI equivalent (`@pollinations/cli`)

```bash
npm i -g @pollinations/cli
polli auth status --json
polli models --type image --json
polli gen image "a lighthouse at dawn" --output still.jpg
polli gen audio "the light returns" --voice nova --output narration.mp3
polli gen video "waves hitting the rocks" --model alibaba/wan-2.2-fast --output clip.mp4
```

The skill talks to the REST API directly so it works without Node; the CLI is
recommended only for device login and ad-hoc experiments.
