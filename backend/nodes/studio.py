"""MOSS Layout Studio node: the Vue editor's draft payload -> compiled model prompt +
overlay IMAGE/MASK + the editable draft JSON."""

from __future__ import annotations

import json

from comfy_api.latest import io

from ..io_types import MossLayoutStudioType, MossLayoutExtrasType
from ..utils.moss import compile_prompt, normalize_draft, parse_json_loose, resolve_payload
from ..utils.overlay import render_overlay, items_from_draft, bboxes_from_items, hex_to_rgb


def _int(v, default, lo, hi):
    try:
        return max(lo, min(hi, int(round(float(v)))))
    except (TypeError, ValueError):
        return default


def _float(v, default, lo, hi):
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return default


class MossLayoutStudio(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="MossLayoutStudio",
            display_name="MOSS Layout Studio",
            category="MOSS",
            description="Visually compose a MOSS-Image Layout JSON. Draw boxes on the canvas, edit their captions, "
                        "and get the compiled model prompt (center-origin yxyx) plus the editable draft JSON. "
                        "A non-empty 'draft' input overrides the editor content.",
            inputs=[
                MossLayoutStudioType.Input("studio"),
                io.String.Input("draft", multiline=True, default="", optional=True,
                                tooltip="Whole-segment MOSS draft (or compiled prompt) JSON — overrides the editor when non-empty"),
            ],
            outputs=[
                io.String.Output(display_name="prompt"),
                io.String.Output(display_name="draft"),
                MossLayoutExtrasType.Output(display_name="extras"),
            ],
        )

    @classmethod
    def execute(cls, studio, draft=None) -> io.NodeOutput:
        payload = studio
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {}
        if not isinstance(payload, dict):
            payload = {}

        editor_draft = payload.get("draft") if isinstance(payload.get("draft"), dict) else {}
        studio_state = payload.get("studio") if isinstance(payload.get("studio"), dict) else {}
        warnings: list[str] = []

        if isinstance(draft, str) and draft.strip():
            data = resolve_payload(parse_json_loose(draft),
                                   _int(editor_draft.get("width"), 1024, 16, 8192),
                                   _int(editor_draft.get("height"), 1024, 16, 8192), warnings)
        else:
            data = normalize_draft(editor_draft, warnings)

        try:
            prompt_str, compile_warnings = compile_prompt(data)
        except ValueError as e:
            raise ValueError(f"MOSS Layout Studio: {e}") from e
        warnings += compile_warnings
        for w in warnings:
            print(f"[MossLayoutStudio] warning: {w}")

        width = _int(data.get("width"), 1024, 16, 8192)
        height = _int(data.get("height"), 1024, 16, 8192)
        ov = studio_state.get("overlay") if isinstance(studio_state.get("overlay"), dict) else {}
        muted = [i for i in (studio_state.get("muted") or []) if isinstance(i, int)]
        box_colors = {i: hex_to_rgb(c, None) for i, c in (studio_state.get("boxColors") or {}).items()
                      if isinstance(i, int)}

        items = items_from_draft(data, muted=muted, box_colors=box_colors)
        overlay, alpha = render_overlay(
            items, width, height,
            line_width=_int(ov.get("lineWidth"), 3, 1, 40),
            fill_alpha=_float(ov.get("fillAlpha"), 0.18, 0.0, 1.0),
            label_size=_int(ov.get("labelSize"), 16, 6, 96),
            show_index=bool(ov.get("showIndex", True)),
            show_text=bool(ov.get("showText", True)),
        )

        extras = {
            "overlay": overlay, "alpha": alpha, "width": width, "height": height,
            "bboxes": bboxes_from_items(items, width, height),
        }
        draft_str = json.dumps(data, ensure_ascii=False, indent=2)
        return io.NodeOutput(prompt_str, draft_str, extras)
