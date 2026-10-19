"""Custom IO types for the V3 nodes."""

from __future__ import annotations

from typing import Any

from comfy_api.latest import io


def _make_widget_input(socketless: bool = True):
    """Build a WidgetInput subclass that renders as an on-node widget (no socket)."""

    class _WidgetInput(io.WidgetInput):
        def __init__(
            self,
            id: str,
            display_name: str | None = None,
            optional: bool = False,
            tooltip: str | None = None,
            advanced: bool | None = None,
            default: Any = None,
        ):
            super().__init__(
                id,
                display_name,
                optional,
                tooltip,
                None,        # lazy
                default,     # default
                socketless,  # socketless
                None,        # widget_type
                None,        # force_input
                None,        # extra_dict
                None,        # raw_link
                advanced,
            )

    return _WidgetInput


@io.comfytype(io_type="MOSS_LAYOUT_STUDIO")
class MossLayoutStudioType:
    """Studio editor widget value ({draft: canonical draft JSON, studio: editor prefs})."""

    Type = dict
    Input = _make_widget_input()


MossLayoutExtrasType = io.Custom("MOSS_LAYOUT_EXTRAS")
