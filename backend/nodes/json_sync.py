"""MOSS Layout Studio JSON Sync — push a whole draft JSON to open studios; passes JSON through."""

from __future__ import annotations

from comfy_api.latest import io

from ..utils.moss import import_payload, parse_json_loose


class MossLayoutJsonSync(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="MossLayoutJsonSync",
            display_name="MOSS Layout Studio JSON Sync",
            category="MOSS",
            description="Validate, canonicalize and push a whole-segment MOSS draft (or compiled prompt) "
                        "JSON to open studios. 'global' ignores each studio's json-sync toggle; "
                        "'force' overrides it even when global is off. Passes the JSON string through.",
            is_output_node=True,
            inputs=[
                io.String.Input("json", multiline=True, default="",
                                tooltip="A MOSS draft or compiled prompt JSON (paste, wire from a script/LLM, or the Studio's draft output)"),
                io.Boolean.Input("enable", default=True),
                io.Int.Input("width", default=0, min=0, max=8192, step=16,
                             tooltip="Target canvas width for compiled JSON without width/height (0 = use the payload's canvas)"),
                io.Int.Input("height", default=0, min=0, max=8192, step=16,
                             tooltip="Target canvas height for compiled JSON without width/height (0 = use the payload's canvas)"),
                io.Boolean.Input("global", default=False,
                                 tooltip="Apply to every open Studio, including ones with json sync off"),
                io.Boolean.Input("force", default=False,
                                 tooltip="Override the per-studio json-sync toggle (implied by global)"),
            ],
            outputs=[io.String.Output(display_name="json")],
        )

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        return float("nan")  # always re-broadcast

    @classmethod
    def execute(cls, json="", enable=True, width=0, height=0, force=False, **kwargs) -> io.NodeOutput:
        if not (enable and isinstance(json, str) and json.strip()):
            return io.NodeOutput(json)

        try:
            payload = parse_json_loose(json)
        except ValueError as e:
            raise ValueError(f"MOSS Layout Studio JSON Sync: {e}") from e

        width_i, height_i = int(width or 0), int(height or 0)
        if bool(width_i) != bool(height_i):
            raise ValueError(
                "MOSS Layout Studio JSON Sync: width and height must both be set "
                "(or both 0 to use the payload's canvas)"
            )

        result = import_payload(
            payload,
            target_width=width_i or None,
            target_height=height_i or None,
            bbox_mode="reject",
            source="json-sync-node",
        )
        if result["errors"]:
            raise ValueError(
                "MOSS Layout Studio JSON Sync: " + " | ".join(result["errors"])
            )
        for warning in result["warnings"]:
            print(f"[MossLayoutJsonSync] warning: {warning}")

        global_flag = bool(kwargs.get("global", False))
        try:
            from server import PromptServer
            PromptServer.instance.send_sync("moss-layout.json-sync", {
                "json": result["draft_json"],
                "global": global_flag,
                "force": bool(force),
                "source": "json-sync-node",
                "importer": result["importer"],
                "warnings": result["warnings"],
            })
        except Exception as e:
            print(f"[MossLayoutJsonSync] sync failed: {e}")
        return io.NodeOutput(json)
