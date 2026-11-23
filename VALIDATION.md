# Validation report (real tool output, 2026-11-23)

## Offline unit tests

Command: `python3 -m unittest discover -s tests -v`

```
Ran 10 tests in 0.045s
OK
```

Covers seed determinism, model ranking, capability ladder, auth redaction,
Authorization header behaviour, error taxonomy, fenced-JSON parsing, bible
normalisation, HTML escaping and secret scanning.

## Skill + project validation

Command:
`python3 scripts/validate.py --skill . --project examples/lighthouse --screenshot examples/lighthouse/screenshot.png`

```json
{
  "ok": true,
  "errors": [],
  "warnings": [],
  "checks": {
    "name": "pollinations-dream-director",
    "body_lines": 158,
    "secrets_found": 0,
    "scripts_compiled": 5,
    "verified_assets": 5
  }
}
```

## Live API observations

- `GET https://gen.pollinations.ai/models` → 200, 489 models
  (98 image, 45 audio, 30 video, 283 text, 4 3D, 11 embedding, 11 decision, 7 realtime).
- `GET /image/{prompt}` and `GET /video/{prompt}` → 401 `UNAUTHORIZED`
  without a secret key. No key was available in this environment.
- Anonymous text and TTS answer only for canonical cached prompts; new prompts
  return 401. The demo therefore records an `offline-template` bible and
  explicitly marked unavailable narration/stills — no fabricated assets.

## Real captured Pollinations media

`examples/lighthouse/api-proof/manifest.json` records exact prompt, endpoint,
byte count and SHA-256 for every file:

| Kind | Prompt | Bytes | SHA-256 prefix |
|---|---|---:|---|
| audio | hello world | 17598 | 615a385580cfc6d3 |
| audio | hello | 21359 | c25b957a2c3ca66bc |
| audio | hi | 40979 | feb06a0933f1ea2a |
| audio | test | 40979 | 40a0e83a18352bcc |
| text | Say hello in one sentence | 6 | 334d016f755cd6dc |

All five are bytes actually returned by `gen.pollinations.ai`, saved by
`scripts/capture_proof.py`. The text response is `Hello!`.

## Screenshot

`examples/lighthouse/screenshot.png` — real headless-browser capture of the
built `index.html`: 1600×900 PNG, 952,979 bytes (≤5 MB, ≥1280×720).

## Honest limitations

The demo is a previsualisation cut. Six shot cards show CSS previs frames and
"narration unavailable" labels instead of invented stills/audio. With
`POLLINATIONS_API_KEY` set, re-running the pipeline replaces them with real
generated assets and records them in `manifest.json`; the code path is exercised
by the client's error handling and unit tests but could not be exercised here
because no credential was available.
