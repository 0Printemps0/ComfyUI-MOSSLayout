#!/usr/bin/env python3
"""MOSS-Image Layout draft tool for ComfyUI-MOSSLayout workflows.

Commands:
  validate <draft.json>
  compile  <draft.json> [--out FILE]
  get      <workflow.json> [--out FILE]
  set      <workflow.json> <draft.json>
  new      <draft.json> <width> <height> [caption]

Stdlib only. The compile step is the official MOSS-Image algorithm:
floor(min)/ceil(max) edges, then subtract the canvas center, yxyx order.
"""

import argparse
import json
import math
import sys


def require(cond, msg):
    if not cond:
        raise ValueError(msg)


def _num(v):
    return type(v) in (int, float) and math.isfinite(v)


def validate_draft(d):
    require(isinstance(d, dict), "draft must be an object")
    width, height = d.get("width"), d.get("height")
    for name, v in (("width", width), ("height", height)):
        require(type(v) is int and v > 0 and v % 16 == 0, f"{name} must be a positive multiple of 16")
    require(d.get("bbox_coord_space") == "abs", "bbox_coord_space must be 'abs'")
    require(d.get("bbox_format") == "xyxy", "bbox_format must be 'xyxy'")
    summary = d.get("summary")
    require(isinstance(summary, dict) and str(summary.get("caption") or "").strip(), "summary.caption required")
    canvas = summary.get("canvas", "single")
    require(canvas in ("single", "multi_panel", "collage"), "summary.canvas invalid")
    for key in ("meta", "palette"):
        require(isinstance(summary.get(key), list) or key not in summary, f"summary.{key} must be an array")
    items = d.get("items")
    require(isinstance(items, list) and items, "items must be a nonempty array")
    for i, it in enumerate(items):
        where = f"items[{i}]"
        require(isinstance(it, dict), f"{where} must be an object")
        require(it.get("label") in ("object", "character", "text"), f"{where}.label invalid")
        require(str(it.get("caption") or "").strip(), f"{where}.caption required")
        bbox = it.get("bbox")
        require(isinstance(bbox, list) and len(bbox) == 4 and all(_num(v) for v in bbox),
                f"{where}.bbox must be [x1,y1,x2,y2]")
        x1, y1, x2, y2 = bbox
        require(x1 < x2 and y1 < y2, f"{where}.bbox needs positive area")
        require(0 <= x1 and x2 <= width and 0 <= y1 and y2 <= height, f"{where}.bbox outside the canvas")
        if it["label"] == "text":
            require(str(it.get("text") or "").strip(), f"{where}: text items require literal text")
        for key in ("tags", "palette"):
            require(isinstance(it.get(key), list) or key not in it, f"{where}.{key} must be an array")


def compile_prompt(d):
    validate_draft(d)
    width, height = d["width"], d["height"]
    out_items = []
    for it in d["items"]:
        x1, y1, x2, y2 = it["bbox"]
        box = [math.floor(round(y1, 9)) - height // 2,
               math.floor(round(x1, 9)) - width // 2,
               math.ceil(round(y2, 9)) - height // 2,
               math.ceil(round(x2, 9)) - width // 2]
        out = {"label": it["label"], "caption": it["caption"], "bbox": box}
        if it.get("text"):
            out["text"] = it["text"]
        for key in ("tags", "palette"):
            if it.get(key):
                out[key] = it[key]
        out_items.append(out)
    result = {"summary": d["summary"], "items": out_items,
              "bbox_coord_space": "abs_centralized", "bbox_format": "yxyx"}
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def find_studio_node(workflow):
    for node in workflow.get("nodes", []):
        if node.get("type") == "MossLayoutStudio":
            return node
    raise ValueError("no MossLayoutStudio node in workflow")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate"); v.add_argument("draft")
    c = sub.add_parser("compile"); c.add_argument("draft"); c.add_argument("--out")
    g = sub.add_parser("get"); g.add_argument("workflow"); g.add_argument("--out")
    s = sub.add_parser("set"); s.add_argument("workflow"); s.add_argument("draft")
    n = sub.add_parser("new"); n.add_argument("draft"); n.add_argument("width", type=int); n.add_argument("height", type=int); n.add_argument("caption", nargs="?", default="")

    a = p.parse_args()
    try:
        if a.cmd == "validate":
            validate_draft(load_json(a.draft))
            print("OK")
        elif a.cmd == "compile":
            prompt = compile_prompt(load_json(a.draft))
            if a.out:
                with open(a.out, "w", encoding="utf-8") as f:
                    f.write(prompt + "\n")
                print(f"wrote {a.out}", file=sys.stderr)
            else:
                print(prompt)
        elif a.cmd == "get":
            wf = load_json(a.workflow)
            node = find_studio_node(wf)
            draft = node["widgets_values"][0]["draft"]
            if a.out:
                save_json(a.out, draft)
                print(f"wrote {a.out}", file=sys.stderr)
            else:
                print(json.dumps(draft, ensure_ascii=False, indent=2))
        elif a.cmd == "set":
            wf = load_json(a.workflow)
            draft = load_json(a.draft)
            validate_draft(draft)
            node = find_studio_node(wf)
            node["widgets_values"][0]["draft"] = draft
            node["widgets_values"][0]["studio"]["width"] = draft["width"]
            node["widgets_values"][0]["studio"]["height"] = draft["height"]
            save_json(a.workflow, wf)
            print("OK")
        elif a.cmd == "new":
            if a.width % 16 or a.height % 16 or a.width <= 0 or a.height <= 0:
                raise ValueError("width/height must be positive multiples of 16")
            draft = {"width": a.width, "height": a.height,
                     "bbox_coord_space": "abs", "bbox_format": "xyxy",
                     "summary": {"canvas": "single", "caption": a.caption},
                     "items": [{"label": "object", "caption": "",
                                "bbox": [a.width // 5, a.height // 5, a.width * 3 // 5, a.height * 4 // 5]}]}
            save_json(a.draft, draft)
            print(f"wrote {a.draft}", file=sys.stderr)
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as e:
        p.exit(2, f"Error: {e}\n")


if __name__ == "__main__":
    main()
