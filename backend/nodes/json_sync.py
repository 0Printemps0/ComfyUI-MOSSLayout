"""MOSS Layout Studio JSON Sync — force-push a whole draft JSON to open studios; passes JSON through."""

from __future__ import annotations

from comfy_api.latest import io


class MossLayoutJsonSync(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="MossLayoutJsonSync",
            display_name="MOSS Layout Studio JSON Sync",
            category="MOSS",
            description="Force-push a whole-segment MOSS draft (or compiled prompt) JSON to MOSS Layout Studios with sync on. Passes the JSON string through.",
            is_output_node=True,
            inputs=[
                io.String.Input("json", multiline=True, default="",
                                tooltip="A MOSS draft or compiled prompt JSON (paste, wire from a script/LLM, or the Studio's draft output)"),
                io.Boolean.Input("enable", default=True),
            ],
            outputs=[io.String.Output(display_name="json")],
        )

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        return float("nan")  # always re-broadcast

    @classmethod
    def execute(cls, json="", enable=True) -> io.NodeOutput:
        if enable and isinstance(json, str) and json.strip():
            import json as _json
            try:
                _json.loads(json)  # validate before broadcast
            except _json.JSONDecodeError as e:
                raise ValueError(f"MOSS Layout Studio JSON Sync: input is not valid JSON — {e}") from e
            try:
                from server import PromptServer
                PromptServer.instance.send_sync("moss-layout.json-sync", {"json": json})
            except Exception as e:
                print(f"[MossLayoutJsonSync] sync failed: {e}")
        return io.NodeOutput(json)
