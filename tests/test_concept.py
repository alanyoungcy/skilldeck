"""Tests for the creative-director Stage 4 pipeline (concept.py)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import concept


# ----------------------- helpers ------------------------------------------


def _well_formed_concept() -> dict:
    return {
        "subject": "a single chain laid diagonally across blueprint paper",
        "composition": "asymmetric — chain on the left two-thirds, right third reserved for headline",
        "metaphor": "load-bearing element hidden among uniform peers",
        "mood": "analytical, quietly confident",
        "foreground_elements": ["drafted chain in cool blue ink", "dimension lines"],
        "background_treatment": "warm off-white blueprint paper with faint grid",
        "text_overlay_zone": {"x": 0.66, "y": 0.10, "w": 0.30, "h": 0.78},
    }


def _well_formed_payload() -> dict:
    return {
        "subject": "a single chain laid diagonally across blueprint paper",
        "composition": "asymmetric layout, right third reserved for text",
        "metaphor": "load-bearing link hidden among peers",
        "mood": "analytical, calm",
        "foreground_elements": ["drafted chain", "dimension lines"],
        "background_treatment": "warm off-white blueprint paper",
        "text_overlay_zone": {"x": 0.65, "y": 0.10, "w": 0.30, "h": 0.78},
    }


# ----------------------- parse_concept ------------------------------------


class ParseConceptTests(unittest.TestCase):
    def test_well_formed_passes(self) -> None:
        out = concept.parse_concept(json.dumps(_well_formed_payload()))
        self.assertIn("subject", out)
        self.assertEqual(len(out["foreground_elements"]), 2)

    def test_strips_markdown_fences(self) -> None:
        wrapped = "```json\n" + json.dumps(_well_formed_payload()) + "\n```"
        out = concept.parse_concept(wrapped)
        self.assertIn("subject", out)

    def test_accepts_concept_wrapper(self) -> None:
        # Some models wrap the schema in {"concept": {...}}.
        wrapped = json.dumps({"concept": _well_formed_payload()})
        out = concept.parse_concept(wrapped)
        self.assertIn("subject", out)

    def test_rejects_invalid_json(self) -> None:
        with self.assertRaises(concept.ConceptError):
            concept.parse_concept("{not json")

    def test_rejects_missing_required_key(self) -> None:
        bad = _well_formed_payload()
        del bad["mood"]
        with self.assertRaises(concept.ConceptError):
            concept.parse_concept(json.dumps(bad))

    def test_rejects_bad_overlay_keys(self) -> None:
        bad = _well_formed_payload()
        bad["text_overlay_zone"] = {"x": 0.1, "y": 0.1}
        with self.assertRaises(concept.ConceptError):
            concept.parse_concept(json.dumps(bad))

    def test_rejects_overlay_out_of_range(self) -> None:
        bad = _well_formed_payload()
        bad["text_overlay_zone"]["x"] = 1.5
        with self.assertRaises(concept.ConceptError):
            concept.parse_concept(json.dumps(bad))

    def test_rejects_empty_foreground(self) -> None:
        bad = _well_formed_payload()
        bad["foreground_elements"] = []
        with self.assertRaises(concept.ConceptError):
            concept.parse_concept(json.dumps(bad))

    def test_rejects_empty_subject(self) -> None:
        bad = _well_formed_payload()
        bad["subject"] = "  "
        with self.assertRaises(concept.ConceptError):
            concept.parse_concept(json.dumps(bad))


# ----------------------- file IO + sync -----------------------------------


class WriteAndReadTests(unittest.TestCase):
    def test_write_then_read_roundtrip(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "concepts" / "01-slide-cover.concept.json"
            concept.write_concept_file(
                p,
                slide_id="01-slide-cover",
                slide_number=1,
                role="hook",
                architype="full_bleed_hero",
                style_preset="blueprint",
                headline="Resilience is plural",
                subhead="Strength lives in the chain",
                concept=_well_formed_concept(),
                outline_hash="abc123",
            )
            self.assertTrue(p.is_file())
            payload = concept.read_concept_file(p)
            assert payload is not None
            self.assertEqual(payload["slide_id"], "01-slide-cover")
            self.assertEqual(payload["outline_hash"], "abc123")
            self.assertEqual(payload["concept"]["subject"], _well_formed_concept()["subject"])
            self.assertNotEqual(payload["original_hash"], "")

    def test_read_returns_none_on_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertIsNone(concept.read_concept_file(Path(tmp) / "missing.json"))

    def test_read_returns_none_on_bad_json(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.json"
            p.write_text("{ not json", encoding="utf-8")
            self.assertIsNone(concept.read_concept_file(p))


class StalenessTests(unittest.TestCase):
    def _setup_file(self, tmp: Path, *, outline_hash: str) -> Path:
        p = tmp / "01-slide-cover.concept.json"
        concept.write_concept_file(
            p,
            slide_id="01-slide-cover",
            slide_number=1,
            role="content",
            architype="hero_with_bullets",
            style_preset="blueprint",
            headline="hello",
            subhead="",
            concept=_well_formed_concept(),
            outline_hash=outline_hash,
        )
        return p

    def test_missing_file_is_stale(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertTrue(concept.is_concept_stale(Path(tmp) / "x.json", "any"))

    def test_matching_hash_is_fresh(self) -> None:
        with TemporaryDirectory() as tmp:
            p = self._setup_file(Path(tmp), outline_hash="abc")
            self.assertFalse(concept.is_concept_stale(p, "abc"))

    def test_outline_changed_is_stale(self) -> None:
        with TemporaryDirectory() as tmp:
            p = self._setup_file(Path(tmp), outline_hash="abc")
            self.assertTrue(concept.is_concept_stale(p, "different"))

    def test_user_edit_overrides_outline_change(self) -> None:
        with TemporaryDirectory() as tmp:
            p = self._setup_file(Path(tmp), outline_hash="abc")
            # Simulate user edit: change the concept body, leave outline_hash alone.
            payload = json.loads(p.read_text(encoding="utf-8"))
            payload["concept"]["mood"] = "newly edited mood"
            p.write_text(json.dumps(payload), encoding="utf-8")
            # Outline ALSO changed, but user edit must win.
            self.assertFalse(concept.is_concept_stale(p, "different"))

    def test_corrupted_file_is_stale(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "01-slide.concept.json"
            p.write_text("{ corrupted", encoding="utf-8")
            self.assertTrue(concept.is_concept_stale(p, "abc"))


# ----------------------- generate_visual_concept --------------------------


class GenerateVisualConceptTests(unittest.TestCase):
    def test_calls_chat_and_parses(self) -> None:
        slide_block = (
            "## Slide 3 of 10\n\n"
            "**Type**: Content\n"
            "**Filename**: 03-slide-resilience.png\n\n"
            "Headline: Resilience is plural\n"
            "Subhead: Strength lives in the chain\n"
        )
        captured: dict[str, object] = {}

        def fake_chat(*, messages, model, max_tokens) -> str:
            captured["messages"] = messages
            captured["model"] = model
            return json.dumps(_well_formed_payload())

        result = concept.generate_visual_concept(
            slide_block=slide_block,
            role="claim",
            architype="metaphor_split",
            architype_description="visual on left, text on right",
            style_preset="blueprint",
            style_anchor="precise blueprint illustration ...",
            examples_text="(few-shot examples here)",
            chat_call=fake_chat,
            planning_model="claude-opus-4-7",
        )
        self.assertEqual(captured["model"], "claude-opus-4-7")
        # The Stage 4 prompt must include the slide content + style anchor + architype + examples.
        prompt_text = captured["messages"][0]["content"]
        self.assertIn("Resilience is plural", prompt_text)
        self.assertIn("metaphor_split", prompt_text)
        self.assertIn("precise blueprint illustration", prompt_text)
        self.assertIn("(few-shot examples here)", prompt_text)
        self.assertIn("subject", result.concept)

    def test_propagates_concept_error(self) -> None:
        def bad_chat(*, messages, model, max_tokens) -> str:
            return "{not even json"

        with self.assertRaises(concept.ConceptError):
            concept.generate_visual_concept(
                slide_block="## Slide 1 of 1\n",
                role="cover",
                architype="full_bleed_hero",
                architype_description="x",
                style_preset="blueprint",
                style_anchor="x",
                examples_text="",
                chat_call=bad_chat,
                planning_model="m",
            )


# ----------------------- style_anchor cache -------------------------------


class StyleAnchorTests(unittest.TestCase):
    def test_first_call_hits_llm_and_caches(self) -> None:
        with TemporaryDirectory() as tmp:
            deck = Path(tmp)
            calls = {"n": 0}

            def fake_chat(*, messages, model, max_tokens) -> str:
                calls["n"] += 1
                return "Precise technical blueprint illustration ..."

            anchor = concept.generate_style_anchor(
                style_spec="blueprint spec",
                deck_dir=deck,
                planning_model="m",
                chat_call=fake_chat,
            )
            self.assertEqual(calls["n"], 1)
            self.assertIn("blueprint", anchor.lower())
            self.assertTrue((deck / ".style-anchor-cache.json").is_file())

    def test_second_call_hits_cache(self) -> None:
        with TemporaryDirectory() as tmp:
            deck = Path(tmp)
            calls = {"n": 0}

            def fake_chat(*, messages, model, max_tokens) -> str:
                calls["n"] += 1
                return "anchor sentence"

            concept.generate_style_anchor(
                style_spec="spec", deck_dir=deck, planning_model="m", chat_call=fake_chat,
            )
            concept.generate_style_anchor(
                style_spec="spec", deck_dir=deck, planning_model="m", chat_call=fake_chat,
            )
            self.assertEqual(calls["n"], 1)

    def test_different_model_misses(self) -> None:
        with TemporaryDirectory() as tmp:
            deck = Path(tmp)
            calls = {"n": 0}

            def fake_chat(*, messages, model, max_tokens) -> str:
                calls["n"] += 1
                return f"anchor {calls['n']}"

            concept.generate_style_anchor(
                style_spec="spec", deck_dir=deck, planning_model="m1", chat_call=fake_chat,
            )
            concept.generate_style_anchor(
                style_spec="spec", deck_dir=deck, planning_model="m2", chat_call=fake_chat,
            )
            self.assertEqual(calls["n"], 2)

    def test_different_spec_misses(self) -> None:
        with TemporaryDirectory() as tmp:
            deck = Path(tmp)
            calls = {"n": 0}

            def fake_chat(*, messages, model, max_tokens) -> str:
                calls["n"] += 1
                return "x"

            concept.generate_style_anchor(
                style_spec="A", deck_dir=deck, planning_model="m", chat_call=fake_chat,
            )
            concept.generate_style_anchor(
                style_spec="B", deck_dir=deck, planning_model="m", chat_call=fake_chat,
            )
            self.assertEqual(calls["n"], 2)


# ----------------------- hashing ------------------------------------------


class HashingTests(unittest.TestCase):
    def test_outline_hash_stable(self) -> None:
        block = "## Slide 1 of 1\n\nHeadline: hello\n"
        self.assertEqual(concept.hash_outline_block(block), concept.hash_outline_block(block))

    def test_outline_hash_changes_with_content(self) -> None:
        a = concept.hash_outline_block("## Slide 1\nA")
        b = concept.hash_outline_block("## Slide 1\nB")
        self.assertNotEqual(a, b)

    def test_concept_payload_hash_ignores_bookkeeping(self) -> None:
        # Two payloads with same `concept` but different metadata must hash equal.
        p1 = {"concept": _well_formed_concept(), "outline_hash": "x"}
        p2 = {"concept": _well_formed_concept(), "outline_hash": "y", "slide_id": "anything"}
        self.assertEqual(
            concept.hash_concept_payload(p1),
            concept.hash_concept_payload(p2),
        )

    def test_concept_payload_hash_changes_with_concept_body(self) -> None:
        p1 = {"concept": _well_formed_concept()}
        modified = _well_formed_concept()
        modified["mood"] = "different mood"
        p2 = {"concept": modified}
        self.assertNotEqual(
            concept.hash_concept_payload(p1),
            concept.hash_concept_payload(p2),
        )


class RenderConceptPromptTests(unittest.TestCase):
    def _payload(self, **overrides) -> dict:
        base = {
            "slide_id": "03-slide-resilience",
            "slide_number": 3,
            "role": "claim",
            "architype": "metaphor_split",
            "style_preset": "blueprint",
            "headline": "Resilience is plural",
            "subhead": "Strength lives in the chain",
            "concept": _well_formed_concept(),
            "negative_prompts_extra": [],
        }
        base.update(overrides)
        return base

    def test_prompt_starts_with_anchor(self) -> None:
        out = concept.render_concept_prompt(
            concept_payload=self._payload(),
            style_anchor="Precise blueprint illustration with cool blue ink, no text in image.",
        )
        body_start = out.split("---\n\n", 1)[-1]
        self.assertTrue(body_start.startswith("Precise blueprint illustration"))

    def test_prompt_contains_subject_composition_mood_overlay(self) -> None:
        out = concept.render_concept_prompt(
            concept_payload=self._payload(),
            style_anchor="anchor sentence",
        )
        self.assertIn("Subject:", out)
        self.assertIn("Composition:", out)
        self.assertIn("Mood:", out)
        self.assertIn("Place the slide's headline", out)
        # Overlay is reported with two decimals.
        self.assertIn("(0.66, 0.10)", out)

    def test_prompt_contains_negative_block(self) -> None:
        out = concept.render_concept_prompt(
            concept_payload=self._payload(),
            style_anchor="anchor",
        )
        self.assertIn("Negative:", out)
        self.assertIn("no watermarks", out)
        # Post-fix: image model should render the slide's text, so we must NOT
        # tell it "no text in image" here.
        self.assertNotIn("no text in image", out)

    def test_prompt_contains_text_to_render(self) -> None:
        out = concept.render_concept_prompt(
            concept_payload=self._payload(body=["one", "two"]),
            style_anchor="anchor",
        )
        self.assertIn("Text to render inside the image", out)
        self.assertIn("Resilience is plural", out)
        self.assertIn("Strength lives in the chain", out)
        self.assertIn("one", out)
        self.assertIn("two", out)

    def test_prompt_includes_extra_negatives(self) -> None:
        out = concept.render_concept_prompt(
            concept_payload=self._payload(negative_prompts_extra=["no celebrities"]),
            style_anchor="anchor",
        )
        self.assertIn("no celebrities", out)

    def test_prompt_omits_overlay_clause_when_zero_size(self) -> None:
        bad_concept = _well_formed_concept()
        bad_concept["text_overlay_zone"] = {"x": 0, "y": 0, "w": 0, "h": 0}
        out = concept.render_concept_prompt(
            concept_payload=self._payload(concept=bad_concept),
            style_anchor="anchor",
        )
        self.assertNotIn("Reserve the area", out)

    def test_prompt_frontmatter_exposes_identity(self) -> None:
        out = concept.render_concept_prompt(
            concept_payload=self._payload(),
            style_anchor="anchor",
        )
        self.assertIn("slide_id: 03-slide-resilience", out)
        self.assertIn("role: claim", out)
        self.assertIn("architype: metaphor_split", out)
        self.assertIn("style_preset: blueprint", out)
        self.assertIn("headline: Resilience is plural", out)


if __name__ == "__main__":
    unittest.main()
