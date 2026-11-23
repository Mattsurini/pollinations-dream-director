"""Render the responsive 'cinematic dailies' presentation site."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from string import Template

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def safe_hex(value: str, fallback: str) -> str:
    return value if isinstance(value, str) and _HEX.match(value) else fallback


def _scene_card(shot: dict, asset: dict, index: int, palette: dict) -> str:
    sid = re.sub(r"[^A-Za-z0-9_-]", "", str(shot.get("id", f"s{index:02d}")))
    title = esc(shot.get("title", f"Scene {index:02d}"))
    desc = esc(shot.get("description", ""))
    camera = esc(shot.get("camera", "—"))
    mood = esc(shot.get("mood", "—"))
    narration = esc(shot.get("narration", ""))
    still = asset.get("image", {}).get("path") if asset else None
    audio = asset.get("audio", {}).get("path") if asset else None
    if still and Path(still).is_file():
        visual = (f'<img class="still" src="{esc(still)}" '
                  f'alt="AI-generated still for {title}" loading="lazy">')
        tag = '<span class="tag tag-live">GENERATED STILL</span>'
    else:
        reason = (asset.get("image", {}).get("reason", "not requested")
                  if asset else "not requested")
        visual = ('<div class="previs" role="img" aria-label="Stylized previsualisation, '
                  'no generated still available">'
                  '<span class="previs-sun"></span><span class="previs-ridge"></span>'
                  f'<span class="previs-num">{index:02d}</span>'
                  '<span class="previs-label">PREVISUALISATION</span></div>')
        tag = f'<span class="tag tag-previs">STILL UNAVAILABLE · {esc(reason)}</span>'
    audio_html = ""
    if audio and Path(audio).is_file():
        audio_html = (f'<div class="player"><span class="player-label">NARRATION</span>'
                      f'<audio controls preload="none" src="{esc(audio)}"></audio></div>')
    else:
        audio_html = '<div class="player muted">Narration unavailable for this scene</div>'
    return f"""
    <article class="shot" id="{sid}" style="--scene-a:{safe_hex(palette.get('primary'), '#e8b96b')};--scene-b:{safe_hex(palette.get('accent'), '#6fd3c7')}">
      <div class="shot-visual">{visual}{tag}</div>
      <div class="shot-copy">
        <div class="shot-head"><span class="shot-index">{index:02d}</span>
          <div><p class="shot-kicker">SHOT {index:02d} / {esc((asset or {}).get('duration', shot.get('duration_seconds', '—')))}s</p>
          <h3>{title}</h3></div></div>
        <p class="shot-desc">{desc}</p>
        <dl class="shot-meta"><div><dt>CAMERA</dt><dd>{camera}</dd></div>
          <div><dt>MOOD</dt><dd>{mood}</dd></div></dl>
        <blockquote>“{narration}”</blockquote>
        {audio_html}
      </div>
    </article>"""


CSS = r"""
:root{--bg:#0a0b0f;--panel:#12141b;--line:#262a35;--ink:#f2efe8;--muted:#9aa0ad;
--gold:#e8b96b;--teal:#6fd3c7;--radius:18px}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);
font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
line-height:1.6;-webkit-font-smoothing:antialiased}
body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:9;opacity:.16;
background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.28'/%3E%3C/svg%3E")}
a{color:inherit}
.wrap{width:min(1160px,92vw);margin:0 auto}
header{position:sticky;top:0;z-index:20;backdrop-filter:blur(14px);
background:rgba(10,11,15,.78);border-bottom:1px solid var(--line)}
.nav{display:flex;align-items:center;justify-content:space-between;padding:14px 0;gap:16px}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;letter-spacing:.02em}
.dot{width:10px;height:10px;border-radius:50%;background:var(--gold);box-shadow:0 0 18px var(--gold)}
.nav-links{display:flex;gap:20px;font-size:.78rem;text-transform:uppercase;letter-spacing:.14em;color:var(--muted)}
.nav-links a{text-decoration:none}.nav-links a:hover{color:var(--gold)}
.hero{position:relative;min-height:82vh;display:flex;align-items:center;overflow:hidden}
.orb{position:absolute;border-radius:50%;filter:blur(90px);opacity:.35;animation:drift 22s ease-in-out infinite alternate}
.orb.a{width:46vw;height:46vw;left:-8vw;top:-10vw;background:var(--gold)}
.orb.b{width:38vw;height:38vw;right:-6vw;bottom:-12vw;background:var(--teal);animation-delay:-8s}
@keyframes drift{to{transform:translate3d(7vw,5vh,0) scale(1.12)}}
.hero-inner{position:relative;padding:70px 0 90px;max-width:860px}
.eyebrow{font-size:.72rem;letter-spacing:.32em;text-transform:uppercase;color:var(--gold);margin:0 0 22px}
h1{font-family:Georgia,"Times New Roman",serif;font-size:clamp(3rem,9vw,7.4rem);
line-height:.94;letter-spacing:-.035em;margin:0 0 24px;font-weight:500}
.logline{font-size:clamp(1.05rem,2.3vw,1.5rem);color:#d8d4cc;max-width:640px;margin:0 0 28px}
.tags{display:flex;flex-wrap:wrap;gap:9px}
.tags span{border:1px solid var(--line);border-radius:999px;padding:6px 13px;font-size:.72rem;
letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.cue{position:absolute;bottom:28px;left:0;font-size:.7rem;letter-spacing:.24em;color:var(--muted);text-transform:uppercase}
section{padding:78px 0;border-top:1px solid var(--line)}
.section-head{display:flex;align-items:baseline;justify-content:space-between;gap:20px;margin-bottom:38px}
h2{font-family:Georgia,serif;font-size:clamp(2rem,4.5vw,3.4rem);font-weight:500;margin:0;letter-spacing:-.02em}
.section-note{font-size:.74rem;letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}
.shots{display:grid;gap:22px}
.shot{display:grid;grid-template-columns:1.05fr .95fr;gap:0;background:var(--panel);
border:1px solid var(--line);border-radius:var(--radius);overflow:hidden}
.shot-visual{position:relative;min-height:340px;background:#0d0f15;overflow:hidden}
.still{width:100%;height:100%;object-fit:cover;display:block;min-height:340px}
.previs{position:relative;width:100%;height:100%;min-height:340px;overflow:hidden;
background:radial-gradient(circle at 30% 26%,var(--scene-a),transparent 48%),
linear-gradient(160deg,#171a24,#0b0d13 72%)}
.previs::after{content:"";position:absolute;inset:0;
background:repeating-linear-gradient(0deg,rgba(255,255,255,.025) 0 2px,transparent 2px 5px)}
.previs-sun{position:absolute;width:44%;aspect-ratio:1;border-radius:50%;left:34%;top:19%;
background:radial-gradient(circle,var(--scene-b),transparent 68%);opacity:.55;filter:blur(2px)}
.previs-ridge{position:absolute;left:-10%;right:-10%;bottom:-14%;height:52%;
background:linear-gradient(180deg,rgba(255,255,255,.05),transparent);
clip-path:polygon(0 62%,18% 38%,34% 58%,52% 22%,70% 55%,86% 34%,100% 60%,100% 100%,0 100%);
backdrop-filter:blur(1px);border-top:1px solid rgba(255,255,255,.12)}
.previs-num{position:absolute;left:20px;bottom:8px;font-family:Georgia,serif;font-size:5.5rem;
line-height:1;color:rgba(255,255,255,.09)}
.previs-label{position:absolute;right:16px;top:16px;font-size:.62rem;letter-spacing:.22em;color:rgba(255,255,255,.5)}
.tag{position:absolute;left:14px;top:14px;font-size:.6rem;letter-spacing:.16em;padding:5px 9px;
border-radius:6px;backdrop-filter:blur(6px);z-index:2}
.tag-live{background:rgba(111,211,199,.18);color:#a9f0e6;border:1px solid rgba(111,211,199,.35)}
.tag-previs{background:rgba(232,185,107,.12);color:#f0cf9b;border:1px solid rgba(232,185,107,.3)}
.shot-copy{padding:32px}
.shot-head{display:flex;gap:20px;align-items:flex-start;margin-bottom:20px}
.shot-index{font-family:Georgia,serif;font-size:3.6rem;line-height:1;color:var(--gold);opacity:.75}
.shot-kicker{margin:0 0 4px;font-size:.66rem;letter-spacing:.2em;color:var(--muted);text-transform:uppercase}
.shot h3{margin:0;font-family:Georgia,serif;font-size:1.7rem;font-weight:500}
.shot-desc{color:#d3cfc7;margin:0 0 22px}
.shot-meta{display:flex;gap:34px;margin:0 0 20px}
.shot-meta div{display:flex;flex-direction:column;gap:3px}
.shot-meta dt{font-size:.62rem;letter-spacing:.18em;color:var(--muted)}
.shot-meta dd{margin:0;font-size:.9rem}
blockquote{margin:0 0 22px;padding:14px 18px;border-left:2px solid var(--gold);
background:rgba(255,255,255,.025);font-family:Georgia,serif;font-style:italic;color:#e6e0d4}
.player{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.player-label{font-size:.62rem;letter-spacing:.18em;color:var(--muted)}
.player audio{height:36px;flex:1;min-width:220px}
.player.muted{font-size:.78rem;color:var(--muted)}
.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:22px}
.card h3{margin:0 0 8px;font-family:Georgia,serif;font-weight:500;font-size:1.2rem}
.card p{margin:0;color:var(--muted);font-size:.9rem}
.card .kind{display:block;font-size:.62rem;letter-spacing:.2em;color:var(--gold);margin-bottom:10px;text-transform:uppercase}
table{width:100%;border-collapse:collapse;font-size:.85rem}
th,td{text-align:left;padding:12px 10px;border-bottom:1px solid var(--line)}
th{font-size:.64rem;letter-spacing:.16em;color:var(--muted);text-transform:uppercase}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.8rem;color:#cfe9e4}
.notice{border:1px dashed rgba(232,185,107,.4);background:rgba(232,185,107,.06);
border-radius:12px;padding:16px 18px;color:#e9d9b8;font-size:.85rem;margin-bottom:28px}
footer{border-top:1px solid var(--line);padding:34px 0 60px;color:var(--muted);font-size:.82rem}
.foot{display:flex;justify-content:space-between;gap:18px;flex-wrap:wrap;align-items:center}
.badge{display:inline-flex;align-items:center;gap:8px;text-decoration:none;border:1px solid var(--line);
border-radius:999px;padding:8px 14px;color:var(--ink)}
.badge:hover{border-color:var(--gold)}
@media(max-width:820px){.shot{grid-template-columns:1fr}.shot-visual{min-height:260px}
.previs{min-height:260px}.still{min-height:260px}.nav-links{display:none}
.shot-copy{padding:24px}.hero{min-height:70vh}}
@media(prefers-reduced-motion:reduce){*{animation:none!important;scroll-behavior:auto!important}}
"""

PAGE = Template(r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="$description">
<title>$title · Dream Director</title>
<style>$css</style></head>
<body>
<header><div class="wrap nav">
  <div class="brand"><span class="dot"></span><span>DREAM DIRECTOR / $title</span></div>
  <nav class="nav-links"><a href="#film">The Film</a><a href="#continuity">Continuity</a><a href="#provenance">Provenance</a></nav>
</div></header>
<main>
<div class="hero"><div class="orb a"></div><div class="orb b"></div>
  <div class="wrap hero-inner">
    <p class="eyebrow">$eyebrow</p>
    <h1>$title</h1>
    <p class="logline">$logline</p>
    <div class="tags">$tags</div>
    <div class="cue">Scroll for the dailies ↓</div>
  </div>
</div>
<section id="film"><div class="wrap">
  <div class="section-head"><h2>The Film</h2><span class="section-note">$shot_count shots · $runtime</span></div>
  $notice
  <div class="shots">$shots</div>
</div></section>
<section id="continuity"><div class="wrap">
  <div class="section-head"><h2>Continuity Ledger</h2><span class="section-note">locked anchors</span></div>
  <div class="grid3">$continuity</div>
</div></section>
<section id="proof"><div class="wrap">
  <div class="section-head"><h2>Live API Proof</h2><span class="section-note">$proof_count</span></div>
  $proof
</div></section>
<section id="provenance"><div class="wrap">
  <div class="section-head"><h2>Provenance</h2><span class="section-note">generated $generated</span></div>
  <div class="notice">$fallback_note</div>
  <table><thead><tr><th>Capability</th><th>Status</th><th>Model</th><th>Asset</th></tr></thead>
  <tbody>$provenance</tbody></table>
</div></section>
</main>
<footer><div class="wrap foot">
  <span>Built with the <code>pollinations-dream-director</code> Agent Skill.</span>
  <a class="badge" href="https://pollinations.ai" rel="noopener">Made with pollinations.ai ↗</a>
</div></footer>
</body></html>""")


def render(project: Path, bible: dict, manifest: dict) -> str:
    palette = bible.get("palette") or {}
    shots = bible.get("shots") or []
    cards = []
    for i, shot in enumerate(shots, 1):
        asset = next((a for a in manifest.get("assets", [])
                      if a.get("shot_id") == shot.get("id")), None)
        cards.append(_scene_card(shot, asset, i, palette))
    total = sum(int(s.get("duration_seconds", 5) or 5) for s in shots)

    continuity = []
    for group in ("characters", "locations", "props"):
        for item in (bible.get("continuity", {}).get(group) or []):
            name = item.get("name", item.get("id", "Anchor")) if isinstance(item, dict) else str(item)
            detail = item.get("description", "") if isinstance(item, dict) else ""
            continuity.append(
                f'<div class="card"><span class="kind">{esc(group)}</span>'
                f'<h3>{esc(name)}</h3><p>{esc(detail)}</p></div>')
    if not continuity:
        continuity.append('<div class="card"><p>No locked anchors were declared.</p></div>')

    rows = []
    for cap in ("text", "image", "audio", "video"):
        info = (manifest.get("capabilities") or {}).get(cap, {})
        status = "AVAILABLE" if info.get("enabled") else "FALLBACK / UNAVAILABLE"
        rows.append(f'<tr><td>{cap.upper()}</td><td>{esc(status)}</td>'
                    f'<td><code>{esc(info.get("model", "—"))}</code></td>'
                    f'<td>{esc(info.get("count", 0))}</td></tr>')

    proof_path = project / "api-proof" / "manifest.json"
    proof_records = []
    if proof_path.is_file():
        try:
            proof_records = json.loads(proof_path.read_text(encoding="utf-8")).get("records", [])
        except ValueError:
            proof_records = []
    proof_cards = []
    for rec in proof_records:
        if rec.get("status") != "captured":
            continue
        prompt = esc(rec.get("prompt", ""))
        sha = esc(str(rec.get("sha256", ""))[:16])
        if rec.get("kind") == "audio":
            body = (f'<audio controls preload="none" '
                    f'src="api-proof/{esc(rec.get("file", ""))}"></audio>')
        else:
            response = esc((project / "api-proof" / rec.get("file", "")).read_text(
                encoding="utf-8"))[:400] if rec.get("file") else ""
            body = f'<blockquote>{response}</blockquote>'
        proof_cards.append(
            f'<div class="card"><span class="kind">{esc(rec.get("endpoint", ""))}</span>'
            f'<h3>“{prompt}”</h3>{body}'
            f'<p><code>sha256:{sha}</code> · {esc(rec.get("bytes", 0))} bytes · '
            f'source: {esc(rec.get("source", "pollinations"))}</p></div>')
    if not proof_cards:
        proof_cards.append('<div class="card"><p>No live response captured at build time.</p></div>')

    unavailable = [c for c in ("image", "video")
                   if not (manifest.get("capabilities", {}).get(c, {}).get("enabled"))]
    if unavailable:
        note = ("Live " + " and ".join(unavailable) +
                " generation and newly written narration need a Pollinations API key "
                "(POLLINATIONS_API_KEY or `polli auth login`). This cut uses the skill's "
                "built-in previsualisation frames instead of fabricated stills. The Live "
                "API Proof section contains real bytes returned by the Pollinations gateway "
                "for canonical prompts; no scene asset is mislabelled as generated.")
    else:
        note = "All generated media in this cut came from live Pollinations API calls."

    notice = ('<div class="notice">This presentation is a <strong>previsualisation cut</strong>: '
              'story and layout are real; generated stills and narration appear automatically '
              'once a Pollinations key is present at build time.</div>')

    out = PAGE.substitute(
        css=CSS,
        title=esc(bible.get("title", "Untitled")),
        description=esc(bible.get("logline", "A cinematic experience directed by an Agent Skill."))[:200],
        eyebrow=esc(" / ".join(bible.get("tone", ["A MEMORY IN MOTION"])[:3])).upper(),
        logline=esc(bible.get("logline", "")),
        tags="".join(f"<span>{esc(t)}</span>" for t in bible.get("tone", [])[:5]),
        notice=notice,
        shots="\n".join(cards),
        shot_count=len(shots),
        runtime=f"~{total}s",
        continuity="\n".join(continuity),
        generated=esc(manifest.get("generated_at", "unknown")),
        fallback_note=esc(note),
        provenance="\n".join(rows),
        proof_count=f"{sum(1 for r in proof_records if r.get('status') == 'captured')} real responses",
        proof="\n".join(proof_cards),
    )
    (project / "index.html").write_text(out, encoding="utf-8")
    return out
