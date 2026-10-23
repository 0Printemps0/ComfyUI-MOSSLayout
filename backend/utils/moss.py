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

# Bumped whenever the external-import contract changes. Exposed by
# POST /mosslayout/import so image-parsing scripts can assert compatibility.
IMPORTER_VERSION = "1.1.0"
IMPORTER_NAME = "mosslayout-import"


class LayoutImportError(ValueError):
    """Raised when an external payload cannot be imported losslessly."""

    def __init__(self, errors: list[str], warnings: list[str] | None = None):
        self.errors = list(errors)
        self.warnings = list(warnings or [])
        super().__init__("; ".join(self.errors))


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


def _list_of_strings(value, where: str, warnings: list[str], errors: list[str]):
    """Preserve string entries exactly (no trimming); warn about non-strings."""
    if value is None:
        return None
    if not isinstance(value, list):
        errors.append(f"{where}: expected an array of strings")
        return None
    out: list[str] = []
    for j, entry in enumerate(value):
        if isinstance(entry, str):
            out.append(entry)
        else:
            warnings.append(f"{where}[{j}]: non-string entry dropped")
    return out or None


def _canvas_dim(value, where: str, errors: list[str]) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not _is_num(value) or float(value) != int(value):
        errors.append(f"{where} must be a positive integer multiple of 16")
        return None
    n = int(value)
    if n <= 0 or n % 16 != 0:
        errors.append(f"{where} must be a positive integer multiple of 16; got {value!r}")
        return None
    return n


def _detect_payload_kind(obj: dict, errors: list[str], warnings: list[str]) -> str:
    """Return editor_draft | compiled_prompt | caption_only | invalid.

    Missing format keys are tolerated only as an editor draft, with an explicit
    warning. Unknown/conflicting values are errors — never silently interpreted.
    """
    has_coord = "bbox_coord_space" in obj
    has_fmt = "bbox_format" in obj
    coord = obj.get("bbox_coord_space")
    fmt = obj.get("bbox_format")

    if has_coord:
        if not isinstance(coord, str):
            errors.append("bbox_coord_space must be a string")
        elif coord not in ("abs", "abs_centralized"):
            errors.append(f"unsupported bbox_coord_space {coord!r}; expected 'abs' or 'abs_centralized'")
    if has_fmt:
        if not isinstance(fmt, str):
            errors.append("bbox_format must be a string")
        elif fmt not in ("xyxy", "yxyx"):
            errors.append(f"unsupported bbox_format {fmt!r}; expected 'xyxy' or 'yxyx'")

    compiled = coord == "abs_centralized" or fmt == "yxyx"
    editor = coord == "abs" or fmt == "xyxy"
    if compiled and editor:
        errors.append(
            "conflicting bbox_coord_space/bbox_format: compiled coordinates (abs_centralized/yxyx) "
            "cannot be combined with editor coordinates (abs/xyxy)"
        )
        return "invalid"
    if compiled:
        return "compiled_prompt"
    if editor:
        return "editor_draft"

    summary = obj.get("summary")
    summary_caption = summary.get("caption") if isinstance(summary, dict) else None
    if "items" not in obj and (isinstance(obj.get("caption"), str) or isinstance(summary_caption, str)):
        return "caption_only"

    warnings.append(
        "bbox_coord_space/bbox_format missing; assuming an editor draft (abs/xyxy). "
        "Compiled payloads must declare abs_centralized/yxyx."
    )
    return "editor_draft"


def _resolve_dimensions(obj: dict, target_width, target_height, kind: str,
                        errors: list[str], warnings: list[str],
                        warn_target_mismatch: bool) -> tuple[int | None, int | None]:
    tw = _canvas_dim(target_width, "target width", errors)
    th = _canvas_dim(target_height, "target height", errors)
    if (target_width is None) != (target_height is None):
        errors.append("target width and height must be provided together")
    if target_width is not None and (tw is None or th is None):
        tw = th = None

    has_w = "width" in obj
    has_h = "height" in obj
    if has_w != has_h:
        errors.append("width and height must both be provided")
    pw = _canvas_dim(obj.get("width"), "width", errors) if has_w else None
    ph = _canvas_dim(obj.get("height"), "height", errors) if has_h else None
    payload_canvas = pw is not None and ph is not None

    if payload_canvas:
        if warn_target_mismatch and tw and th and (tw, th) != (pw, ph):
            warnings.append(
                f"target canvas {tw}x{th} ignored: payload declares {pw}x{ph} "
                "(external width/height take priority)"
            )
        if kind == "compiled_prompt":
            warnings.append(f"compiled prompt de-centered onto its declared canvas {pw}x{ph}")
        return pw, ph

    if tw and th:
        if kind == "compiled_prompt":
            warnings.append(
                f"compiled prompt has no width/height; de-centered onto target canvas {tw}x{th}"
            )
        elif kind != "caption_only":
            warnings.append(f"width/height missing; using target canvas {tw}x{th}")
        return tw, th

    if kind == "compiled_prompt":
        errors.append(
            "compiled prompt has no width/height; pass target width/height "
            "(the canvas cannot be inferred from center-origin boxes)"
        )
        return None, None

    warnings.append("width/height missing; defaulted to 1024x1024")
    return 1024, 1024


def _canonical_summary(obj: dict, kind: str, errors: list[str], warnings: list[str]) -> dict:
    raw = obj.get("summary")
    if raw is None:
        raw = {}
    elif not isinstance(raw, dict):
        errors.append("summary must be an object")
        raw = {}

    caption = ""
    if kind == "caption_only" and "caption" in obj:
        root_caption = obj.get("caption")
        if not isinstance(root_caption, str):
            errors.append("caption must be a string")
        else:
            caption = root_caption
        summary_caption = raw.get("caption")
        if isinstance(summary_caption, str) and summary_caption and summary_caption != caption:
            warnings.append("caption-only payload: root caption overrides summary.caption")
    elif "caption" in raw:
        if not isinstance(raw.get("caption"), str):
            errors.append("summary.caption must be a string")
        else:
            caption = raw["caption"]
    if not caption.strip():
        warnings.append("summary.caption is empty; compile will fail until it is filled")

    meta = _list_of_strings(raw.get("meta"), "summary.meta", warnings, errors)
    palette = _list_of_strings(raw.get("palette"), "summary.palette", warnings, errors)

    canvas = raw.get("canvas", "single")
    if canvas not in CANVAS_MODES:
        errors.append(f"summary.canvas {canvas!r} invalid; expected one of {', '.join(CANVAS_MODES)}")
        canvas = "single"

    for key in raw:
        if key not in SUMMARY_KEYS:
            warnings.append(f"summary.{key}: not an official summary field; dropped")

    summary: dict = {}
    if meta is not None:
        summary["meta"] = meta
    summary["canvas"] = canvas
    summary["caption"] = caption
    if palette is not None:
        summary["palette"] = palette
    return summary


def _box_text(box) -> str:
    try:
        return "[" + ", ".join(f"{float(v):g}" for v in box) + "]"
    except (TypeError, ValueError):
        return repr(box)


def _canonical_item(raw, index: int, kind: str, width: int | None, height: int | None,
                    bbox_mode: str, bbox_tolerance: float,
                    errors: list[str], warnings: list[str]) -> dict | None:
    where = f"items[{index}]"
    if not isinstance(raw, dict):
        errors.append(f"{where} is not an object; the item was not imported")
        return None

    for key in raw:
        if key not in ITEM_KEYS:
            warnings.append(f"{where}.{key}: not an official item field; dropped")

    label = raw.get("label")
    if label not in LABELS:
        errors.append(f"{where}.label {label!r} invalid; expected one of {', '.join(LABELS)}")
        label = None

    caption = raw.get("caption", "")
    if not isinstance(caption, str):
        errors.append(f"{where}.caption must be a string")
        caption = ""
    elif not caption.strip():
        warnings.append(f"{where}.caption is empty; compile will fail until it is filled")

    raw_box = raw.get("bbox")
    box = None
    if not isinstance(raw_box, list) or len(raw_box) != 4 or not all(_is_num(v) for v in raw_box):
        errors.append(f"{where}.bbox must be four finite numbers")
    elif width is None or height is None:
        pass  # the canvas error above is the actionable one
    else:
        if kind == "compiled_prompt":
            y1, x1, y2, x2 = raw_box
            box = [x1 + width // 2, y1 + height // 2, x2 + width // 2, y2 + height // 2]
        else:
            box = list(raw_box)
        if not (box[0] < box[2] and box[1] < box[3]):
            errors.append(f"{where}.bbox must have positive width and height; got {_box_text(box)}")
            box = None
        elif not (0 <= box[0] and box[2] <= width and 0 <= box[1] and box[3] <= height):
            shown = _box_text(box)
            if kind == "compiled_prompt":
                shown += f" after de-centering onto {width}x{height}"
            overflow = max(0.0 - box[0], box[2] - width, 0.0 - box[1], box[3] - height)
            should_clamp = bbox_mode == "clamp" or (
                bbox_mode == "auto" and overflow <= bbox_tolerance
            )
            if should_clamp:
                cx1 = min(max(box[0], 0), width)
                cx2 = min(max(box[2], 0), width)
                cy1 = min(max(box[1], 0), height)
                cy2 = min(max(box[3], 0), height)
                if not (cx1 < cx2 and cy1 < cy2):
                    errors.append(
                        f"{where}.bbox {shown} collapses to zero area when clamped to "
                        f"{width}x{height}; refusing to import it"
                    )
                    box = None
                else:
                    how = "auto-clamped" if bbox_mode == "auto" else "clamped"
                    extra = (
                        f" (overflow {overflow:g}px <= tolerance {bbox_tolerance:g}px)"
                        if bbox_mode == "auto" else ""
                    )
                    warnings.append(
                        f"{where}.bbox {shown} exceeded canvas {width}x{height}; "
                        f"{how} to {_box_text([cx1, cy1, cx2, cy2])}{extra}"
                    )
                    box = [cx1, cy1, cx2, cy2]
            elif bbox_mode == "auto":
                errors.append(
                    f"{where}.bbox {shown} exceeds canvas {width}x{height} by "
                    f"{overflow:g}px (bbox_mode='auto', tolerance={bbox_tolerance:g}px; "
                    "use 'clamp' to accept a clamped box)"
                )
                box = None
            else:
                errors.append(
                    f"{where}.bbox {shown} exceeds canvas {width}x{height} "
                    "(bbox_mode='reject'; use 'auto' with a tolerance or 'clamp' "
                    "to accept a clamped box)"
                )
                box = None

    item: dict = {"label": label, "caption": caption, "bbox": box}
    if label == "text":
        text = raw.get("text")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{where}: text items require a non-empty literal 'text'")
        else:
            item["text"] = text
    elif "text" in raw:
        text = raw.get("text")
        if isinstance(text, str) and text.strip():
            item["text"] = text
        elif isinstance(text, str):
            warnings.append(f"{where}.text is empty; omitted from the canonical draft")
        else:
            warnings.append(f"{where}.text is not a string; omitted from the canonical draft")

    for key in ("tags", "palette"):
        if key in raw:
            values = _list_of_strings(raw.get(key), f"{where}.{key}", warnings, errors)
            if values is not None:
                item[key] = values
    return item


def import_payload(payload, target_width=None, target_height=None, bbox_mode: str = "reject",
                   bbox_tolerance: float = 2.0, source: str = "external",
                   warn_target_mismatch: bool = True) -> dict:
    """Loose external payload -> canonical abs/xyxy draft, with explicit diagnostics.

    Accepted: editor draft (abs/xyxy), compiled prompt (abs_centralized/yxyx),
    caption-only. Every valid item survives with label/caption/bbox/text/tags/
    palette; invalid items produce indexed errors instead of being dropped.
    """
    warnings: list[str] = []
    errors: list[str] = []
    result = {
        "ok": False,
        "importer": f"{IMPORTER_NAME}/{IMPORTER_VERSION}",
        "importer_version": IMPORTER_VERSION,
        "source": source,
        "source_format": "invalid",
        "bbox_mode": bbox_mode,
        "bbox_tolerance": bbox_tolerance,
        "canvas": None,
        "draft": None,
        "draft_json": None,
        "compiled": None,
        "compilable": False,
        "compile_error": None,
        "warnings": warnings,
        "errors": errors,
        "input_item_count": 0,
        "output_item_count": 0,
        "item_count": 0,
    }
    if not isinstance(payload, dict):
        errors.append("payload must be a JSON object")
        return result
    if bbox_mode not in ("reject", "auto", "clamp"):
        errors.append(
            f"bbox_mode {bbox_mode!r} invalid; expected 'reject', 'auto' or 'clamp'"
        )
        bbox_mode = "reject"
        result["bbox_mode"] = bbox_mode
    try:
        bbox_tolerance = float(bbox_tolerance)
    except (TypeError, ValueError):
        errors.append("bbox_tolerance must be a finite number >= 0")
        bbox_tolerance = 2.0
    if not math.isfinite(bbox_tolerance) or bbox_tolerance < 0:
        errors.append("bbox_tolerance must be a finite number >= 0")
        bbox_tolerance = 2.0
    result["bbox_tolerance"] = bbox_tolerance

    kind = _detect_payload_kind(payload, errors, warnings)
    result["source_format"] = kind
    width, height = _resolve_dimensions(
        payload, target_width, target_height, kind, errors, warnings, warn_target_mismatch
    )
    if width and height:
        result["canvas"] = {"width": width, "height": height}

    summary = _canonical_summary(payload, kind, errors, warnings)

    raw_items = payload.get("items")
    if raw_items is None:
        if kind == "caption_only":
            raw_items = []
            warnings.append("caption-only payload imported; 0 items")
        else:
            raw_items = []
            warnings.append("items is missing; imported an empty layout")
    elif not isinstance(raw_items, list):
        errors.append("items must be an array")
        raw_items = []
    result["input_item_count"] = len(raw_items)

    for key in payload:
        allowed = ROOT_KEYS + (["caption"] if kind == "caption_only" else [])
        if key not in allowed:
            warnings.append(f"root.{key}: not an official draft field; dropped")

    items: list[dict] = []
    for i, raw in enumerate(raw_items):
        item = _canonical_item(
            raw, i, kind, width, height, bbox_mode, bbox_tolerance, errors, warnings
        )
        if item is not None:
            items.append(item)
    result["output_item_count"] = len(items)
    result["item_count"] = len(items)

    if not errors and width and height:
        if len(items) != len(raw_items):
            errors.append(
                f"item count invariant violated: input {len(raw_items)}, output {len(items)}"
            )
        else:
            canonical = {
                "width": width,
                "height": height,
                "bbox_coord_space": "abs",
                "bbox_format": "xyxy",
                "summary": summary,
                "items": items,
            }
            result["draft"] = canonical
            result["draft_json"] = json.dumps(canonical, ensure_ascii=False, indent=2)
            try:
                compiled, compile_warnings = compile_prompt(canonical)
            except ValueError as e:
                result["compile_error"] = str(e)
                warnings.append(f"canonical draft is not compilable yet: {e}")
            else:
                warnings.extend(compile_warnings)
                result["compiled"] = compiled
                result["compilable"] = True

    result["ok"] = not errors
    return result


def resolve_payload(obj: dict, width: int, height: int, warnings: list[str],
                    bbox_mode: str = "reject", bbox_tolerance: float = 0.0) -> dict:
    """Any of: draft JSON, compiled prompt JSON, or {'caption': ...} -> canonical draft.

    Strict on schema and geometry: unsupported formats, invalid labels, missing
    text and out-of-canvas boxes raise LayoutImportError instead of being
    silently rewritten. The given canvas is only a fallback when the payload
    does not declare width/height.
    """
    result = import_payload(
        obj, target_width=width, target_height=height, bbox_mode=bbox_mode,
        bbox_tolerance=bbox_tolerance, source="resolve", warn_target_mismatch=False,
    )
    warnings.extend(result["warnings"])
    if result["errors"]:
        raise LayoutImportError(result["errors"], result["warnings"])
    return result["draft"]
