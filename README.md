# pollinations-dream-director

[![Made with pollinations.ai](https://raw.githubusercontent.com/pollinations/pollinations/main/packages/ui/src/brand/badge-made-with.svg)](https://pollinations.ai)

**An Agent Skill that turns one idea into a directed cinematic package.**

Most Pollinations skills teach an agent *how to call the API*. This one directs the
whole film: a creative bible, a six-shot storyboard with a continuity ledger, stable
seeds for visual consistency, real narration tracks, optional stills and motion, and
a polished responsive presentation site — with a provenance manifest proving what
was actually generated.

Built for [Pollinations Quest #20020](https://github.com/pollinations/pollinations/issues/20020).
App URL is intentionally empty: the repository is the app.

## Install

Copy this folder into any Agent Skills directory:

```bash
# Claude Code
cp -r pollinations-dream-director ~/.claude/skills/

# Cross-runtime alias / Codex / Copilot CLI
cp -r pollinations-dream-director ~/.agents/skills/

# Hermes Agent
cp -r pollinations-dream-director ~/.hermes/skills/

# Or let a skills manager fetch the repo
npx skills add https://github.com/Mattsurini/pollinations-dream-director
```

Requirements: Python 3.9+ (standard library only) and network access to
`gen.pollinations.ai`. Node is optional — needed only for `polli` device login.

## Run

```bash
python scripts/dream_director.py all \
  --idea "a lighthouse keeper who remembers every ship lost at sea" \
  --out examples/my-film --title "The Last Light"
```

Text generation and narration work with no API key. For stills and video:

```bash
export POLLINATIONS_API_KEY=...        # secret key from enter.pollinations.ai/keys
# or: npm i -g @pollinations/cli && polli auth login

python scripts/dream_director.py all --idea "..." --out examples/my-film --force \
  --allow-paid --video
```

Individual stages: `init`, `plan`, `assets`, `site`. Run `python scripts/dream_director.py --help`
for the full flag list. `--offline` forces the deterministic planner for air-gapped testing.

## Capabilities

| Modality | Without a key | With a key |
|---|---|---|
| Direction / script | free healthy text model | plus premium models with `--allow-paid` |
| Narration | real MP3 from the Pollinations audio API | same, more voices/models |
| Stills | labelled CSS previsualisation, no fake files | real 1152×648 generated frames |
| Video | disabled | optional per-shot motion clips |

Model IDs are discovered from `GET /models` at runtime and ranked by category,
health, free-first policy and capability — never hardcoded as the only option.

## Demo

[`examples/lighthouse/`](examples/lighthouse/) is a real built project: six shots,
a stable-seed continuity ledger, a provenance manifest, a responsive `index.html`,
and five genuinely captured Pollinations responses in `api-proof/`. Because no API
key was available at build time, the scene cards honestly show CSS previsualisation
and "narration unavailable" labels instead of invented stills or audio. The finished
screen is captured in
[`examples/lighthouse/screenshot.png`](examples/lighthouse/screenshot.png).

Open `examples/lighthouse/index.html` in a browser — it has no external assets.

## Validate

```bash
python -m unittest discover -s tests -v
python scripts/validate.py --skill . --project examples/lighthouse \
  --screenshot examples/lighthouse/screenshot.png
```

`validate.py` checks the Agent Skills frontmatter and naming rules, relative links,
script syntax, secret patterns, README credit, project artifacts, asset byte counts
and the 16:9 screenshot requirement.

## Security

No key is ever written to a project file, printed, or embedded in a URL that is
logged. The client reads `POLLINATIONS_API_KEY` or `~/.pollinations/credentials.json`
and exposes only a redacted auth summary. Add `.env` and credential files to your
global ignore; never commit them.

## Repository layout

```
SKILL.md                 Agent Skills entry point
scripts/                 client, director pipeline, site renderer, validator
references/              API and workflow references
tests/                   offline unit tests
examples/lighthouse/     built demo project + screenshot
VALIDATION.md            real validation output
```

## License

MIT — see [LICENSE](LICENSE).
