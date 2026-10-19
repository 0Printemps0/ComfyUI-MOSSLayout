"""MOSS Helper node registry."""

from __future__ import annotations

from comfy_api.latest import ComfyExtension, io

# import before any node schema references the custom IO types
from . import io_types  # noqa: F401

try:
    from .server import api  # noqa: F401
except Exception as _api_err:  # pragma: no cover
    print(f"[MossLayout] API routes failed to load: {_api_err}")

from .nodes.extras import MossLayoutExtras
from .nodes.json_sync import MossLayoutJsonSync
from .nodes.ref_sync import MossLayoutRefSync
from .nodes.studio import MossLayoutStudio


class MossLayoutExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            MossLayoutStudio,
            MossLayoutExtras,
            MossLayoutRefSync,
            MossLayoutJsonSync,
        ]


async def comfy_entrypoint() -> MossLayoutExtension:
    return MossLayoutExtension()


__all__ = ["MossLayoutExtension", "comfy_entrypoint"]
