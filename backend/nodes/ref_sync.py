"""MOSS Layout Studio Ref Sync — push an image to the studio's reference backdrop."""

from __future__ import annotations

from comfy_api.latest import io


class MossLayoutRefSync(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="MossLayoutRefSync",
            display_name="MOSS Layout Studio Ref Sync",
            category="MOSS",
            description="Sync this image to the MOSS Layout Studio reference backdrop (studios with 'sync' on). Passes the image through.",
            is_output_node=True,
            inputs=[
                io.Image.Input("image"),
                io.Boolean.Input("enable", default=True),
            ],
            outputs=[io.Image.Output(display_name="image")],
        )

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        # re-run every execution so the image re-broadcasts (a cached node would
        # never re-sync after a page refresh or repeat run); nan == IS_CHANGED
        return float("nan")

    @classmethod
    def execute(cls, image, enable=True) -> io.NodeOutput:
        ui_images = []
        if enable and image is not None and getattr(image, "ndim", 0) == 4 and image.shape[0] > 0:
            try:
                import os
                import time
                import random
                import numpy as np
                import folder_paths
                from PIL import Image as PILImage
                from server import PromptServer

                out_dir = folder_paths.get_temp_directory()
                os.makedirs(out_dir, exist_ok=True)
                arr = (image[0].cpu().numpy() * 255.0).clip(0, 255).astype(np.uint8)
                fn = f"moss_layout_ref_{int(time.time() * 1000)}_{random.randint(0, 9999)}.png"
                PILImage.fromarray(arr).save(os.path.join(out_dir, fn))
                payload = {"filename": fn, "subfolder": "", "type": "temp"}
                PromptServer.instance.send_sync("moss-layout.ref-sync", payload)
                ui_images = [payload]
            except Exception as e:
                print(f"[MossLayoutRefSync] sync failed: {e}")

        return io.NodeOutput(image, ui={"images": ui_images})
