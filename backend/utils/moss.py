"""MOSS-Image Layout draft model: validation, canonical draft serialization and
model-prompt compilation. Ports the official compiler in
OpenMOSS/MOSS-Image skills/moss-image-prompt-enhancer/scripts/compile_prompt.py."""

from __future__ import annotations

import json
import math
from typing import Any

LABELS = ("object", "character", "text")
CANVAS_MODES = ("single", "multi_panel", "collage")

ROOT_KEYS = ["width", "height", "bbox_coord_space", "bbox_format", "summary", "items"]
ITEM_KEYS = ["label", "caption", "bbox", "text", "tags", "palette"]
SUMMARY_KEYS = ["meta", "canvas", "caption", "palette"]


def _is_num(v) -> bool:
    return type(v) in (int, float) and math.isfinite(v)


def centered_box(box, width, height, location):
    """[x1,y1,x2,y2] abs pixels -> integer center-origin yxyx, as the official compiler."""
    if not isinstance(box, list) or len(box) != 4 or not all(_is_num(v) for v in box):
        raise ValueError(f"{location} must be four finite numbers [x1,y1,x2,y2]")
    x1, y1, x2, y2 = box
    if not (x1 < x2 and y1 < y2):
        raise ValueError(f"{location} must have positive width and height")
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError(f"{location} exceeds the {width}x{height} canvas")
    out = [
        math.floor(round(y1, 9)) - height // 2,
        math.floor(round(x1, 9)) - width // 2,
        math.ceil(round(y2, 9)) - height // 2,
        math.ceil(round(x2, 9)) - width // 2,
    ]
    if not (out[0] < out[2] and out[1] < out[3]):
        raise ValueError(f"{location} is too small at export precision")
    return out


def _clean_str_list(v, where, warnings):
    if v is None or (isinstance(v, list) and not v):
        return None
    if not isinstance(v, list):
        warnings.append(f"{where}: expected a string list; dropped")
        return None
    out = [s.strip() for s in v if isinstance(s, str) and s.strip()]
    if len(out) != len(v):
        warnings.append(f"{where}: non-string / empty entries dropped")
    return out or None


def normalize_draft(data: dict, warnings: list[str]) -> dict:
    """Loose dict -> canonical key-ordered draft. Geometry is clamped to the canvas
    instead of erroring (the editor draws boxes, it should not lose them)."""
    def wh(v, name):
        try:
            n = int(round(float(v)))
        except (TypeError, ValueError):
            n = 1024
            warnings.append(f"{name} invalid; reset to 1024")
        if n <= 0 or n % 16 != 0:
            n = max(16, (n // 16) * 16)
            warnings.append(f"{name} snapped to a multiple of 16")
        return n

    width = wh(data.get("width"), "width")
    height = wh(data.get("height"), "height")

    raw_summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    caption = raw_summary.get("caption")
    if not isinstance(caption, str) or not caption.strip():
        caption = ""
        warnings.append("summary.caption is empty")
    summary = {"caption": caption}
    meta = _clean_str_list(raw_summary.get("meta"), "summary.meta", warnings)
    palette = _clean_str_list(raw_summary.get("palette"), "summary.palette", warnings)
    canvas = raw_summary.get("canvas")
    if canvas not in CANVAS_MODES:
        if canvas is not None:
            warnings.append(f"summary.canvas '{canvas}' invalid; using 'single'")
        canvas = "single"
    if meta is not None:
        summary["meta"] = meta
    if canvas is not None:
        summary["canvas"] = canvas
    if palette is not None:
        summary["palette"] = palette
    # canonical order: meta, canvas, caption (matches the official example)
    summary = {k: summary[k] for k in ("meta", "canvas", "caption", "palette") if k in summary}

    items = []
    for i, it in enumerate(data.get("items") or []):
        where = f"items[{i}]"
        if not isinstance(it, dict):
            warnings.append(f"{where}: not an object; dropped")
            continue
        label = it.get("label")
        if label not in LABELS:
            warnings.append(f"{where}: label '{label}' invalid; using 'object'")
            label = "object"
        cap = it.get("caption")
        if not isinstance(cap, str) or not cap.strip():
            cap = ""
            warnings.append(f"{where}.caption empty")
        bbox = it.get("bbox")
        if isinstance(bbox, list) and len(bbox) == 4 and all(_is_num(v) for v in bbox):
            x1, y1, x2, y2 = bbox
            x1, x2 = sorted((max(0.0, x1), min(float(width), x2)))
            y1, y2 = sorted((max(0.0, y1), min(float(height), y2)))
            if x1 >= x2 or y1 >= y2:
                x1, y1, x2, y2 = 0.0, 0.0, min(64.0, width), min(64.0, height)
                warnings.append(f"{where}.bbox degenerate; reset")
            bbox = [x1, y1, x2, y2]
        else:
            bbox = [0.0, 0.0, min(256.0, width), min(256.0, height)]
            warnings.append(f"{where}.bbox invalid; reset")
        item = {"label": label, "caption": cap, "bbox": bbox}
        if label == "text":
            text = it.get("text")
            if not isinstance(text, str) or not text.strip():
                text = ""
                warnings.append(f"{where}: text item has no literal text")
            else:
                item["text"] = text
        elif isinstance(it.get("text"), str) and it["text"].strip():
            item["text"] = it["text"]
        tags = _clean_str_list(it.get("tags"), f"{where}.tags", warnings)
        pal = _clean_str_list(it.get("palette"), f"{where}.palette", warnings)
        if tags is not None:
            item["tags"] = tags
        if pal is not None:
            item["palette"] = pal
        items.append(item)

    if not items:
        warnings.append("items is empty; the compiled prompt requires at least one item")

    return {
        "width": width, "height": height,
        "bbox_coord_space": "abs", "bbox_format": "xyxy",
        "summary": summary, "items": items,
    }


def compile_prompt(draft: dict) -> tuple[str, list[str]]:
    """Canonical draft -> (minified model prompt JSON, warnings). Raises ValueError
    on schema violations the official compiler would reject."""
    warnings: list[str] = []
    if not draft.get("items"):
        raise ValueError("items must be a nonempty array — add at least one box")
    summary = draft.get("summary") or {}
    if not str(summary.get("caption") or "").strip():
        raise ValueError("summary.caption must be nonempty text")
    width, height = draft["width"], draft["height"]
    if not (isinstance(width, int) and width > 0 and width % 16 == 0):
        raise ValueError("width must be a positive integer multiple of 16")
    if not (isinstance(height, int) and height > 0 and height % 16 == 0):
        raise ValueError("height must be a positive integer multiple of 16")

    compiled_items = []
    for i, it in enumerate(draft["items"]):
        where = f"items[{i}]"
        if it.get("label") not in LABELS:
            raise ValueError(f"{where}.label must be object, character or text")
        if not str(it.get("caption") or "").strip():
            raise ValueError(f"{where}.caption must be nonempty text")
        if it["label"] == "text" and not str(it.get("text") or "").strip():
            raise ValueError(f"{where}: text items require literal text")
        out = {"label": it["label"], "caption": it["caption"]}
        out["bbox"] = centered_box(it["bbox"], width, height, f"{where}.bbox")
        if "text" in it:
            out["text"] = it["text"]
        for key in ("tags", "palette"):
            if it.get(key):
                out[key] = it[key]
        compiled_items.append(out)

    result = {"summary": summary, "items": compiled_items,
              "bbox_coord_space": "abs_centralized", "bbox_format": "yxyx"}
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False), warnings


def parse_json_loose(text: str) -> dict:
    """Parse a whole-segment JSON string (fences/prose tolerated) into an object."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("empty JSON input")
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s[:4].lower() == "json":
            s = s[4:]
        s = s.strip()
    start = s.find("{")
    end = s.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object found in input")
    try:
        obj = json.loads(s[start:end + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON — {e}") from e
    if not isinstance(obj, dict):
        raise ValueError("JSON payload must be an object")
    return obj


def resolve_payload(obj: dict, width: int, height: int, warnings: list[str]) -> dict:
    """Any of: draft JSON, compiled prompt JSON, or {'caption': ...} -> canonical draft.
    Compiled boxes are de-centered onto the given canvas (its dims are not in the payload)."""
    if not isinstance(obj, dict):
        raise ValueError("payload must be a JSON object")
    if obj.get("bbox_format") == "yxyx" or obj.get("bbox_coord_space") == "abs_centralized":
        items = []
        for it in obj.get("items") or []:
            if not isinstance(it, dict):
                continue
            bbox = it.get("bbox")
            if isinstance(bbox, list) and len(bbox) == 4 and all(_is_num(v) for v in bbox):
                y1, x1, y2, x2 = bbox
                bbox = [x1 + width // 2, y1 + height // 2, x2 + width // 2, y2 + height // 2]
            items.append({**it, "bbox": bbox})
        obj = {"width": width, "height": height,
               "bbox_coord_space": "abs", "bbox_format": "xyxy",
               "summary": obj.get("summary") or {}, "items": items}
        warnings.append("imported a compiled prompt; boxes mapped onto the current canvas "
                        f"{width}x{height} — set the canvas to the generation size for exact coordinates")
    elif "caption" in obj and "items" not in obj:
        obj = {"width": width, "height": height,
               "bbox_coord_space": "abs", "bbox_format": "xyxy",
               "summary": {"caption": str(obj.get("caption") or "")}, "items": []}
        warnings.append("caption-only payload imported; add boxes to build a Layout")
    return normalize_draft(obj, warnings)
