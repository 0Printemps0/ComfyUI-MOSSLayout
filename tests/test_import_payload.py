"""Stdlib tests for the external MOSS Layout import contract.

Run from the repository root:
    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOSS_PATH = ROOT / "backend" / "utils" / "moss.py"


def _load_moss():
    spec = importlib.util.spec_from_file_location("moss_import_under_test", MOSS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


m = _load_moss()


def editor_payload(**overrides):
    payload = {
        "width": 1536,
        "height": 1024,
        "bbox_coord_space": "abs",
        "bbox_format": "xyxy",
        "summary": {
            "caption": "A poster with a cup and a headline",
            "meta": ["poster", "coffee"],
            "canvas": "single",
            "palette": ["#ffffff", "#101010"],
        },
        "items": [
            {
                "label": "object",
                "caption": "coffee cup",
                "bbox": [120, 180, 520, 720],
                "text": "cup",
                "tags": ["drink", "ceramic"],
                "palette": ["#c08040"],
            },
            {
                "label": "character",
                "caption": "barista",
                "bbox": [640, 200, 980, 760],
                "tags": ["person"],
                "palette": ["#334455"],
            },
            {
                "label": "text",
                "caption": "headline",
                "bbox": [1000, 80, 1450, 220],
                "text": "OPEN DAILY",
                "tags": ["headline"],
                "palette": ["#ffffff"],
            },
        ],
    }
    payload.update(overrides)
    return payload


def compiled_payload(**overrides):
    payload = {
        "summary": {
            "caption": "A compiled poster",
            "meta": ["compiled"],
            "canvas": "multi_panel",
            "palette": ["#eeeeee"],
        },
        "bbox_coord_space": "abs_centralized",
        "bbox_format": "yxyx",
        "items": [
            {
                "label": "object",
                "caption": "cup",
                "bbox": [-300, -500, 200, 300],
                "tags": ["drink"],
                "palette": ["#aa5500"],
            },
            {
                "label": "text",
                "caption": "headline",
                "bbox": [-450, 400, -200, 700],
                "text": "HELLO",
                "tags": ["headline"],
                "palette": ["#000000"],
            },
        ],
    }
    payload.update(overrides)
    return payload


class ImportPayloadTests(unittest.TestCase):
    def test_editor_draft_preserves_all_official_fields_and_count(self):
        result = m.import_payload(editor_payload())

        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["source_format"], "editor_draft")
        self.assertEqual(result["item_count"], 3)
        self.assertEqual(result["input_item_count"], 3)
        self.assertEqual(result["output_item_count"], 3)
        self.assertEqual(result["importer_version"], m.IMPORTER_VERSION)

        draft = result["draft"]
        self.assertEqual((draft["width"], draft["height"]), (1536, 1024))
        self.assertEqual((draft["bbox_coord_space"], draft["bbox_format"]), ("abs", "xyxy"))
        self.assertEqual(
            draft["summary"],
            {
                "meta": ["poster", "coffee"],
                "canvas": "single",
                "caption": "A poster with a cup and a headline",
                "palette": ["#ffffff", "#101010"],
            },
        )
        self.assertEqual(
            draft["items"][0],
            {
                "label": "object",
                "caption": "coffee cup",
                "bbox": [120, 180, 520, 720],
                "text": "cup",
                "tags": ["drink", "ceramic"],
                "palette": ["#c08040"],
            },
        )
        self.assertEqual(draft["items"][2]["text"], "OPEN DAILY")
        self.assertTrue(result["compilable"])
        self.assertIsNotNone(result["compiled"])

    def test_compiled_prompt_decenters_and_preserves_fields(self):
        result = m.import_payload(compiled_payload(), target_width=1536, target_height=1024)

        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["source_format"], "compiled_prompt")
        self.assertEqual(result["item_count"], 2)
        self.assertEqual((result["draft"]["width"], result["draft"]["height"]), (1536, 1024))
        self.assertEqual(
            result["draft"]["summary"],
            {
                "meta": ["compiled"],
                "canvas": "multi_panel",
                "caption": "A compiled poster",
                "palette": ["#eeeeee"],
            },
        )
        # half canvas = 768x512
        self.assertEqual(result["draft"]["items"][0]["bbox"], [268, 212, 1068, 712])
        self.assertEqual(result["draft"]["items"][1]["bbox"], [1168, 62, 1468, 312])
        self.assertEqual(result["draft"]["items"][0]["tags"], ["drink"])
        self.assertEqual(result["draft"]["items"][0]["palette"], ["#aa5500"])
        self.assertEqual(result["draft"]["items"][1]["text"], "HELLO")
        self.assertTrue(any("target canvas 1536x1024" in w for w in result["warnings"]))

    def test_compiled_payload_canvas_takes_priority_over_target(self):
        payload = compiled_payload(width=1536, height=1024)
        result = m.import_payload(payload, target_width=1024, target_height=1024)

        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(
            (result["draft"]["width"], result["draft"]["height"]), (1536, 1024)
        )
        self.assertEqual(result["draft"]["items"][0]["bbox"], [268, 212, 1068, 712])
        self.assertTrue(any("target canvas 1024x1024 ignored" in w for w in result["warnings"]))

    def test_editor_payload_canvas_takes_priority_over_target(self):
        result = m.import_payload(editor_payload(), target_width=1024, target_height=1024)
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual((result["draft"]["width"], result["draft"]["height"]), (1536, 1024))
        self.assertTrue(any("target canvas 1024x1024 ignored" in w for w in result["warnings"]))

    def test_caption_only(self):
        result = m.import_payload(
            {"caption": "caption only", "summary": {"meta": ["m"], "canvas": "collage", "palette": ["#fff"]}},
            target_width=1024,
            target_height=1536,
        )
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["source_format"], "caption_only")
        self.assertEqual(result["item_count"], 0)
        self.assertEqual(result["draft"]["summary"]["caption"], "caption only")
        self.assertEqual(result["draft"]["summary"]["meta"], ["m"])
        self.assertEqual(result["draft"]["summary"]["canvas"], "collage")
        self.assertEqual(result["draft"]["summary"]["palette"], ["#fff"])
        self.assertFalse(result["compilable"])
        self.assertTrue(any("caption-only" in w for w in result["warnings"]))

    def test_invalid_label_reports_item_index_and_does_not_return_draft(self):
        payload = editor_payload()
        payload["items"][1]["label"] = "person"
        result = m.import_payload(payload)

        self.assertFalse(result["ok"])
        self.assertIsNone(result["draft"])
        self.assertTrue(any("items[1].label" in e for e in result["errors"]))

    def test_text_item_missing_text_reports_item_index(self):
        payload = editor_payload()
        payload["items"][2].pop("text")
        result = m.import_payload(payload)

        self.assertFalse(result["ok"])
        self.assertTrue(any("items[2]" in e and "text" in e for e in result["errors"]))

    def test_out_of_bounds_reject_and_clamp(self):
        payload = editor_payload()
        payload["items"][0]["bbox"] = [120, 180, 1700, 720]

        rejected = m.import_payload(payload)
        self.assertFalse(rejected["ok"])
        self.assertTrue(any("items[0].bbox" in e and "reject" in e for e in rejected["errors"]))

        clamped = m.import_payload(payload, bbox_mode="clamp")
        self.assertTrue(clamped["ok"], clamped["errors"])
        self.assertEqual(clamped["item_count"], 3)
        self.assertEqual(clamped["draft"]["items"][0]["bbox"], [120, 180, 1536, 720])
        self.assertTrue(any("clamped" in w and "items[0].bbox" in w for w in clamped["warnings"]))
        self.assertEqual(clamped["bbox_mode"], "clamp")

    def test_unsupported_bbox_format_is_an_error(self):
        payload = editor_payload(bbox_format="coco")
        result = m.import_payload(payload)
        self.assertFalse(result["ok"])
        self.assertTrue(any("bbox_format 'coco'" in e for e in result["errors"]))

    def test_unsupported_bbox_coord_space_is_an_error(self):
        payload = editor_payload(bbox_coord_space="normalized")
        result = m.import_payload(payload)
        self.assertFalse(result["ok"])
        self.assertTrue(any("bbox_coord_space 'normalized'" in e for e in result["errors"]))

    def test_conflicting_formats_are_an_error(self):
        payload = editor_payload(bbox_format="yxyx")
        result = m.import_payload(payload)
        self.assertFalse(result["ok"])
        self.assertTrue(any("conflicting" in e for e in result["errors"]))

    def test_canvas_must_be_a_multiple_of_16(self):
        payload = editor_payload(width=1000)
        result = m.import_payload(payload)
        self.assertFalse(result["ok"])
        self.assertTrue(any("width" in e and "multiple of 16" in e for e in result["errors"]))

    def test_invalid_target_canvas_is_an_error(self):
        result = m.import_payload(compiled_payload(), target_width=1000, target_height=1024)
        self.assertFalse(result["ok"])
        self.assertTrue(any("target width" in e for e in result["errors"]))

    def test_compiled_without_any_canvas_is_an_error(self):
        result = m.import_payload(compiled_payload())
        self.assertFalse(result["ok"])
        self.assertTrue(any("compiled prompt has no width/height" in e for e in result["errors"]))

    def test_missing_format_assumes_editor_draft_with_warning(self):
        payload = editor_payload()
        payload.pop("bbox_coord_space")
        payload.pop("bbox_format")
        result = m.import_payload(payload)
        self.assertTrue(result["ok"], result["errors"])
        self.assertTrue(any("assuming an editor draft" in w for w in result["warnings"]))

    def test_tags_and_palette_order_and_duplicates_are_preserved(self):
        payload = editor_payload()
        payload["items"][0]["tags"] = ["b", "a", "b", ""]
        payload["items"][0]["palette"] = ["#111111", "#111111", "#222222"]
        result = m.import_payload(payload)
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["draft"]["items"][0]["tags"], ["b", "a", "b", ""])
        self.assertEqual(
            result["draft"]["items"][0]["palette"], ["#111111", "#111111", "#222222"]
        )

    def test_non_object_item_is_reported_not_silently_dropped(self):
        payload = editor_payload()
        payload["items"].insert(0, "not an item")
        result = m.import_payload(payload)
        self.assertFalse(result["ok"])
        self.assertTrue(any("items[0] is not an object" in e for e in result["errors"]))
        self.assertEqual(result["input_item_count"], 4)
        self.assertEqual(result["output_item_count"], 3)

    def test_unknown_fields_warn_instead_of_vanishing(self):
        payload = editor_payload()
        payload["extra_root"] = 1
        payload["summary"]["extra_summary"] = 2
        payload["items"][0]["extra_item"] = 3
        result = m.import_payload(payload)
        self.assertTrue(result["ok"], result["errors"])
        joined = "\n".join(result["warnings"])
        self.assertIn("root.extra_root", joined)
        self.assertIn("summary.extra_summary", joined)
        self.assertIn("items[0].extra_item", joined)
        self.assertNotIn("extra_root", result["draft"])

    def test_caption_only_item_count_matches_zero_input_items(self):
        result = m.import_payload({"caption": "only"}, target_width=1024, target_height=1024)
        self.assertEqual(result["input_item_count"], 0)
        self.assertEqual(result["output_item_count"], 0)
        self.assertEqual(result["item_count"], 0)

    def test_resolve_payload_is_strict_and_returns_canonical_draft(self):
        warnings = []
        draft = m.resolve_payload(compiled_payload(), 1536, 1024, warnings)
        self.assertEqual(len(draft["items"]), 2)
        self.assertEqual(draft["items"][0]["bbox"], [268, 212, 1068, 712])
        self.assertTrue(warnings)

        broken = editor_payload(bbox_format="coco")
        with self.assertRaises(m.LayoutImportError) as ctx:
            m.resolve_payload(broken, 1024, 1024, [])
        self.assertTrue(any("coco" in e for e in ctx.exception.errors))

    def test_compiled_item_count_is_preserved(self):
        result = m.import_payload(compiled_payload(), target_width=1536, target_height=1024)
        self.assertEqual(result["item_count"], len(compiled_payload()["items"]))
        self.assertEqual(len(result["draft"]["items"]), len(compiled_payload()["items"]))

    def test_compiled_output_is_minified_canonical_prompt(self):
        result = m.import_payload(compiled_payload(), target_width=1536, target_height=1024)
        compiled = json.loads(result["compiled"])
        self.assertEqual(compiled["bbox_coord_space"], "abs_centralized")
        self.assertEqual(compiled["bbox_format"], "yxyx")
        self.assertEqual(len(compiled["items"]), 2)


if __name__ == "__main__":
    unittest.main()

