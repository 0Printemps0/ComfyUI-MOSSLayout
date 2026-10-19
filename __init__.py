"""ComfyUI-MOSSLayout entry point (V3).

ComfyUI loads this module, calls `comfy_entrypoint` to register the nodes, and
serves `WEB_DIRECTORY` for the frontend.
"""

from .backend import comfy_entrypoint  # noqa: F401

WEB_DIRECTORY = "./web"

print("[MossLayout] loaded")
