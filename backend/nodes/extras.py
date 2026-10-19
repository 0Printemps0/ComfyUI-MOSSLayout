"""MOSS Layout Studio Extras — break out the studio's 'extras' bundle into overlay/alpha/width/height/bboxes."""

from __future__ import annotations

from comfy_api.latest import io

from ..io_types import MossLayoutExtrasType


class MossLayoutExtras(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="MossLayoutExtras",
            display_name="MOSS Layout Studio Extras",
            category="MOSS",
            description="Break out the MOSS Layout Studio 'extras' output into overlay (IMAGE), alpha (MASK), width, height, and the items as native BOUNDING_BOX data.",
            inputs=[MossLayoutExtrasType.Input("extras")],
            outputs=[
                io.Image.Output(display_name="overlay"),
                io.Mask.Output(display_name="alpha"),
                io.Int.Output(display_name="width"),
                io.Int.Output(display_name="height"),
                io.BoundingBox.Output(display_name="bboxes"),
            ],
        )

    @classmethod
    def execute(cls, extras=None) -> io.NodeOutput:
        e = extras if isinstance(extras, dict) else {}
        bboxes = e.get("bboxes") if isinstance(e.get("bboxes"), list) else []
        return io.NodeOutput(e.get("overlay"), e.get("alpha"), int(e.get("width") or 1024), int(e.get("height") or 1024), bboxes)
