"""HTTP routes (under /mosslayout/) backing the browser frontend."""

from __future__ import annotations

import base64
import io as _io
import json
import os
import re

from aiohttp import web
from PIL import Image as PILImage

try:
    from server import PromptServer
    _routes = PromptServer.instance.routes
except Exception as e:  # pragma: no cover
    PromptServer = None
    _routes = None
    print(f"[MossLayout] studio routes unavailable: {e}")

from ..utils.moss import IMPORTER_NAME, IMPORTER_VERSION, import_payload, parse_json_loose
from ..utils.overlay import items_from_draft, render_overlay_rgba

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".avif"}
_PREVIEW_SIZE = 384
_JSON_SYNC_EVENT = "moss-layout.json-sync"


def _importer_info(source: str = "http-import") -> dict:
    return {
        "importer": f"{IMPORTER_NAME}/{IMPORTER_VERSION}",
        "importer_version": IMPORTER_VERSION,
        "source": source,
    }


def _broadcast_json_sync(payload: dict) -> tuple[bool, str]:
    """Send the JSON Sync event; return (sent, warning)."""
    if PromptServer is None:
        return False, "PromptServer unavailable; the import was normalized but not broadcast"
    try:
        PromptServer.instance.send_sync(_JSON_SYNC_EVENT, payload)
        return True, ""
    except Exception as e:  # pragma: no cover - depends on the live server
        return False, f"broadcast failed: {e}"


def _json_sync_payload(result: dict, *, global_flag: bool, force: bool, source: str) -> dict:
    return {
        "json": result["draft_json"],
        "global": bool(global_flag),
        "force": bool(force),
        "source": source,
        "importer": result["importer"],
        "warnings": list(result["warnings"]),
        "item_count": result["item_count"],
        "canvas": result["canvas"],
    }


def _safe_path(dirpath: str, name: str) -> str:
    """Resolve name within dirpath, rejecting path traversal."""
    if not dirpath:
        raise ValueError("no dir")
    full = os.path.abspath(os.path.join(dirpath, os.path.basename(name)))
    if os.path.commonpath([os.path.abspath(dirpath), full]) != os.path.abspath(dirpath):
        raise ValueError("outside dir")
    return full


def _list_images(dirpath: str) -> list[str]:
    if not dirpath or not os.path.isdir(dirpath):
        return []
    names = []
    for f in os.scandir(dirpath):
        if f.is_file() and os.path.splitext(f.name)[1].lower() in _IMAGE_EXTS:
            names.append(f.name)
    return sorted(names)


def _composite_preview(path: str, data: dict, size: int = _PREVIEW_SIZE) -> str:
    """Render bboxes over a resized copy of the image as a JPEG data-uri."""
    img = PILImage.open(path).convert("RGB")
    w, h = img.size
    scale = size / max(w, h)
    img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), PILImage.LANCZOS)
    overlay = render_overlay_rgba(items_from_draft(data), img.size[0], img.size[1])
    img = PILImage.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    buf = _io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


def _preview_from_json(data: dict, width: int = 768, height: int = 768) -> str:
    """Render bboxes over a dark backdrop (no source image) as a data-uri."""
    img = PILImage.new("RGBA", (width, height), (18, 18, 22, 255))
    overlay = render_overlay_rgba(items_from_draft(data), width, height)
    img = PILImage.alpha_composite(img, overlay).convert("RGB")
    buf = _io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


def _library_dir() -> str:
    """Managed library folder for saved draft templates; created on use."""
    try:
        import folder_paths
        d = os.path.join(folder_paths.get_user_directory(), "default", "MOSSHelper", "library")
    except Exception:
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "user", "default", "MOSSHelper", "library")
    os.makedirs(d, exist_ok=True)
    return d


def _list_json(dirpath: str) -> list[str]:
    """Standalone .json files with no matching image (draft templates)."""
    if not dirpath or not os.path.isdir(dirpath):
        return []
    images = {os.path.splitext(n)[0] for n in _list_images(dirpath)}
    out = []
    for f in os.scandir(dirpath):
        if f.is_file() and f.name.lower().endswith(".json") and os.path.splitext(f.name)[0] not in images:
            out.append(f.name)
    return sorted(out)


if _routes is not None:

    @_routes.get("/mosslayout/thumb")
    async def moss_thumb(request):
        d = request.rel_url.query.get("dir", "").strip()
        name = request.rel_url.query.get("name", "").strip()
        try:
            size = int(request.rel_url.query.get("size", "256"))
        except ValueError:
            size = 256
        try:
            path = _safe_path(d, name)
        except ValueError:
            return web.Response(status=400, text="bad path")
        if not os.path.isfile(path):
            return web.Response(status=404, text="not found")
        try:
            img = PILImage.open(path).convert("RGB")
            w, h = img.size
            longest = max(w, h)
            if longest > size:
                scale = size / longest
                img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), PILImage.LANCZOS)
            buf = _io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return web.Response(body=buf.getvalue(), content_type="image/jpeg",
                                headers={"Cache-Control": "no-cache"})
        except Exception as e:
            return web.Response(status=500, text=str(e))

    @_routes.post("/mosslayout/preview")
    async def moss_preview(request):
        """Render a bbox preview for a draft (or compiled) JSON plus validity."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json body"}, status=400)
        if not isinstance(body, dict):
            return web.json_response({"error": "body must be a JSON object"}, status=400)
        text = body.get("json") or ""
        try:
            width = int(body.get("width") or 768)
            height = int(body.get("height") or 768)
        except (TypeError, ValueError):
            width, height = 768, 768
        d = (body.get("dir") or "").strip()
        name = (body.get("name") or "").strip()
        errors: list[str] = []
        warnings: list[str] = []
        data: dict = {}
        source_format = "invalid"
        item_count = 0
        compilable = False
        try:
            if isinstance(text, str):
                raw = parse_json_loose(text) if text.strip() else {}
            elif isinstance(text, dict):
                raw = text
            else:
                raise ValueError("json must be a JSON string or object")
            result = import_payload(
                raw, target_width=width, target_height=height,
                bbox_mode="reject", source="preview",
            )
            data = result["draft"] or {}
            errors = result["errors"]
            warnings = result["warnings"]
            source_format = result["source_format"]
            item_count = result["item_count"]
            compilable = result["compilable"]
        except ValueError as e:
            errors.append(str(e))
        preview = ""
        try:
            # Composite over the source image when known, else a dark backdrop.
            img_path = None
            if d and name:
                try:
                    p = _safe_path(d, name)
                    if os.path.isfile(p):
                        img_path = p
                except ValueError:
                    img_path = None
            if img_path:
                preview = _composite_preview(img_path, data)
            elif data:
                preview = _preview_from_json(data, data.get("width", width), data.get("height", height))
        except Exception as e:
            print(f"[MossLayout] preview failed: {e}")
        return web.json_response({
            "preview": preview,
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
            "source_format": source_format,
            "item_count": item_count,
            "compilable": compilable,
            **_importer_info("preview"),
        })

    @_routes.post("/mosslayout/import")
    async def moss_import(request):
        """Normalize and globally import an external MOSS Layout JSON.

        Body: {json | object, width?, height?, broadcast?=true, global?=true,
               force?=true, bbox_mode?='reject'|'clamp'}

        Returns the canonical abs/xyxy draft, warnings, errors, item counts and
        importer version. With broadcast=true (default) the same canonical JSON
        is pushed as moss-layout.json-sync with global/force flags.
        """
        base = {
            **_importer_info("http-import"),
            "ok": False,
            "source_format": "invalid",
            "bbox_mode": None,
            "canvas": None,
            "draft": None,
            "draft_json": None,
            "compiled": None,
            "compilable": False,
            "compile_error": None,
            "warnings": [],
            "errors": [],
            "input_item_count": 0,
            "output_item_count": 0,
            "item_count": 0,
            "broadcast": False,
            "event": _JSON_SYNC_EVENT,
        }
        try:
            body = await request.json()
        except Exception as e:
            base["errors"] = [f"invalid JSON body — {e}"]
            return web.json_response(base, status=400)
        if not isinstance(body, dict):
            base["errors"] = ["body must be a JSON object"]
            return web.json_response(base, status=400)

        raw_json = body.get("json")
        if isinstance(raw_json, str):
            try:
                raw = parse_json_loose(raw_json)
            except ValueError as e:
                base["errors"] = [str(e)]
                return web.json_response(base, status=400)
        elif isinstance(raw_json, dict):
            raw = raw_json
        else:
            base["errors"] = ["json must be a JSON string or object"]
            return web.json_response(base, status=400)

        extra_warnings: list[str] = []
        broadcast = body.get("broadcast", True)
        global_flag = body.get("global", True)
        force = body.get("force", True)
        for key, value in (("broadcast", broadcast), ("global", global_flag), ("force", force)):
            if not isinstance(value, bool):
                extra_warnings.append(f"{key} must be a boolean; defaulted to true")
        if not isinstance(broadcast, bool):
            broadcast = True
        if not isinstance(global_flag, bool):
            global_flag = True
        if not isinstance(force, bool):
            force = True

        result = import_payload(
            raw,
            target_width=body.get("width"),
            target_height=body.get("height"),
            bbox_mode=body.get("bbox_mode", "reject"),
            source="http-import",
        )
        result["warnings"] = extra_warnings + result["warnings"]
        result["event"] = _JSON_SYNC_EVENT
        result["global"] = global_flag
        result["force"] = force
        result["broadcast"] = False
        result["ok"] = not result["errors"]
        if result["errors"]:
            return web.json_response(result, status=400 if result["errors"] else 200)

        if broadcast:
            payload = _json_sync_payload(
                result, global_flag=global_flag, force=force, source="http-import"
            )
            sent, warning = _broadcast_json_sync(payload)
            result["broadcast"] = sent
            if warning:
                result["warnings"].append(warning)
        return web.json_response(result)

    @_routes.post("/mosslayout/save_template")
    async def moss_save_template(request):
        """Write a single draft to {out_dir}/{name}.json."""
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "invalid json"}, status=400)
        out_dir = (body.get("out_dir") or "").strip()
        name = (body.get("name") or "").strip()
        text = body.get("json") or ""
        if not name:
            return web.json_response({"error": "name is required"}, status=400)
        if not out_dir:
            out_dir = _library_dir()
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            return web.json_response({"error": f"draft is not valid JSON — {e}"}, status=400)
        stem = os.path.splitext(name)[0]
        if os.path.basename(stem) != stem:
            return web.json_response({"error": "name must not contain path separators"}, status=400)
        overwrite = bool(body.get("overwrite", False))
        try:
            os.makedirs(out_dir, exist_ok=True)
            path = os.path.join(out_dir, stem + ".json")
            # On name collision, roll to the next free numbered variant.
            if not overwrite and os.path.exists(path):
                m = re.match(r"^(.*?)(\d+)$", stem)
                if m:
                    base, num, width = m.group(1), int(m.group(2)), len(m.group(2))
                else:
                    base, num, width = stem + "_", 0, 3
                while os.path.exists(path):
                    num += 1
                    stem = f"{base}{str(num).zfill(width)}"
                    path = os.path.join(out_dir, stem + ".json")
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False, indent=2))
            # optional reference thumbnail sidecar ({stem}.thumb.jpg)
            thumb = body.get("thumb") or ""
            if isinstance(thumb, str) and thumb.startswith("data:"):
                try:
                    raw = base64.b64decode(thumb.split(",", 1)[1])
                    with open(os.path.join(out_dir, stem + ".thumb.jpg"), "wb") as tf:
                        tf.write(raw)
                except Exception:
                    pass
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)
        return web.json_response({"ok": True, "path": path, "name": stem})

    @_routes.post("/mosslayout/delete_template")
    async def moss_delete_template(request):
        """Delete a library template ({stem}.json + optional {stem}.thumb.jpg)."""
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "invalid json"}, status=400)
        stem = os.path.splitext((body.get("name") or "").strip())[0]
        if not stem or os.path.basename(stem) != stem:
            return web.json_response({"error": "bad name"}, status=400)
        d = _library_dir()
        removed = []
        for suffix in (".json", ".thumb.jpg"):
            p = os.path.join(d, stem + suffix)
            if os.path.isfile(p):
                try:
                    os.remove(p)
                    removed.append(os.path.basename(p))
                except Exception as e:
                    return web.json_response({"error": str(e)}, status=500)
        if not removed:
            return web.json_response({"error": "not found"}, status=404)
        return web.json_response({"ok": True, "removed": removed})

    @_routes.get("/mosslayout/library")
    async def moss_library(request):
        """List saved draft templates from the default managed library folder."""
        d = _library_dir()
        templates = []
        for name in _list_json(d):
            stem = os.path.splitext(name)[0]
            draft = ""
            try:
                with open(os.path.join(d, name), encoding="utf-8") as f:
                    draft = f.read()
            except Exception:
                draft = ""
            has_thumb = os.path.isfile(os.path.join(d, stem + ".thumb.jpg"))
            templates.append({"name": name, "stem": stem, "caption": draft, "thumb": has_thumb})
        return web.json_response({"dir": d, "templates": templates})

    print("[MossLayout] studio routes registered under /mosslayout/")
