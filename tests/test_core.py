"""Offline test suite — no network, no credentials, no generated media required."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dream_director as dd  # noqa: E402
import pollinations_client as api  # noqa: E402
import site_render as site_module  # noqa: E402
import validate as validator  # noqa: E402


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False


class ClientTests(unittest.TestCase):
    def test_seed_is_stable_and_scoped(self):
        self.assertEqual(dd.seed_for("abc", "s01"), dd.seed_for("abc", "s01"))
        self.assertNotEqual(dd.seed_for("abc", "s01"), dd.seed_for("abc", "s02"))
        self.assertLess(dd.seed_for("abc", "s01"), 2_000_000_000)

    def test_model_selection_prefers_free_and_healthy(self):
        models = [
            {"name": "free/ok", "category": "image", "paid_only": False,
             "health": {"status": "healthy", "success_rate": 99, "requests": 20}},
            {"name": "paid/ok", "category": "image", "paid_only": True,
             "health": {"status": "healthy", "success_rate": 100, "requests": 30}},
            {"name": "free/down", "category": "image", "paid_only": False,
             "health": {"status": "down", "success_rate": 0, "requests": 5}},
            {"name": "community/x", "category": "image", "paid_only": False,
             "health": {"status": "healthy", "success_rate": 100, "requests": 5}},
        ]
        free = api.select_models(models, "image", limit=3)
        self.assertEqual(free[0], "free/ok")
        self.assertNotIn("paid/ok", free[:1])
        self.assertNotIn("free/down", free)
        self.assertNotIn("community/x", free)
        paid = api.select_models(models, "image", allow_paid=True, limit=3)
        self.assertEqual(paid[0], "paid/ok")

    def test_capability_ladder(self):
        caps = api.capabilities(api.AuthState("none", False), [])
        self.assertTrue(caps["text"] and caps["audio"])
        self.assertFalse(caps["image"] or caps["video"])
        caps2 = api.capabilities(api.AuthState("env", True, "secret"), [])
        self.assertTrue(all(caps2[k] for k in ("text", "audio", "image", "video")))
        self.assertNotIn("secret", json.dumps(caps2))

    def test_auth_redaction(self):
        with patch.dict(os.environ, {"POLLINATIONS_API_KEY": "sk_" + "A" * 24}):
            state = api.detect_auth()
            self.assertTrue(state.authenticated)
            self.assertEqual(state.source, "environment")
            self.assertNotIn(state.key, json.dumps(state.redacted()))

    def test_authorization_header_only_with_key(self):
        seen = {}
        def fake_urlopen(req, timeout=None):
            seen["auth"] = req.headers.get("Authorization")
            return FakeResponse(b"{}")
        with patch.object(api.urllib.request, "urlopen", fake_urlopen):
            api._request("https://example.test", api.AuthState("none", False))
            self.assertIsNone(seen.get("auth"))
            api._request("https://example.test", api.AuthState("env", True, "sk_TESTKEY"))
            self.assertEqual(seen["auth"], "Bearer sk_TESTKEY")

    def test_error_classification(self):
        err = api._parse_error(b'{"error":{"code":"UNAUTHORIZED","message":"nope"}}', 401)
        self.assertIsInstance(err, api.AuthRequired)
        err2 = api._parse_error(b'{"error":{"code":"BAD","message":"bad prompt"}}', 400)
        self.assertIsInstance(err2, api.CapabilityUnavailable)


class PipelineTests(unittest.TestCase):
    def test_extract_json_accepts_fenced_output(self):
        data = dd.extract_json('Here you go:\n```json\n{"title":"X","shots":[]}\n```')
        self.assertEqual(data["title"], "X")

    def test_normalize_fills_gaps(self):
        brief = {"idea": "a lighthouse that remembers", "title": "The Keeper", "project_id": "abc"}
        bible = dd.normalize_bible({"title": "The Keeper", "shots": [{"title": "Opening"}]},
                                   brief, "pollinations-text:test")
        self.assertEqual(len(bible["shots"]), 6)
        self.assertEqual(bible["shots"][0]["title"], "Opening")
        self.assertEqual(bible["shots"][1]["title"], "The Signal")
        self.assertTrue(all(s["image_prompt"] for s in bible["shots"]))

    def test_render_escapes_html_and_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            bible = {"title": "<script>alert(1)</script>", "logline": "A & B",
                     "palette": {}, "tone": ["NOIR"],
                     "continuity": {"characters": [{"name": "<b>X</b>", "description": "d"}]},
                     "shots": [{"id": "s01", "title": "One", "description": "d",
                                "camera": "wide", "mood": "calm", "narration": "hi",
                                "duration_seconds": 5, "image_prompt": "p"}]}
            manifest = {"generated_at": "now", "capabilities": {
                "image": {"enabled": False, "model": "—", "count": 0}}, "assets": []}
            out = site_module.render(project, bible, manifest)
            self.assertIn("&lt;script&gt;", out)
            self.assertNotIn("<script>alert(1)</script>", out)
            self.assertIn("PREVISUALISATION", out)
            self.assertTrue((project / "index.html").is_file())

    def test_frontmatter_and_secret_scan(self):
        meta, body = validator.parse_frontmatter(
            "---\nname: demo-skill\ndescription: Use when testing.\n---\nBody\n")
        self.assertEqual(meta["name"], "demo-skill")
        self.assertEqual(body.strip(), "Body")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bad.md").write_text("key: ghp_" + "A" * 30, encoding="utf-8")
            hits = validator.scan_secrets(root)
            self.assertTrue(any("github_token" in h for h in hits))
            (root / "bad.md").unlink()
            self.assertEqual(validator.scan_secrets(root), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
