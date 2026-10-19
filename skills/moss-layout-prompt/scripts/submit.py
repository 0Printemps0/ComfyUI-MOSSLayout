#!/usr/bin/env python3
"""Submit a MOSS-Image Layout draft to a running ComfyUI server.

Injects the draft into the shipped API workflow, queues it, and reports the
output files. Stdlib only.

Usage:
  python3 submit.py draft.json                       # queue on http://127.0.0.1:7860
  python3 submit.py draft.json --server http://host:8188 --timeout 600
  python3 submit.py draft.json --workflow my.api.json
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_WORKFLOW = HERE.parents[2] / "example_workflows" / "moss-layout-t2i.api.json"


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_studio(prompt):
    for node_id, node in prompt.items():
        if node.get("class_type") == "MossLayoutStudio":
            return node
    raise ValueError("workflow has no MossLayoutStudio node")


def post_json(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("draft", help="MOSS Layout draft JSON (see SKILL.md)")
    p.add_argument("--server", default="http://127.0.0.1:7860")
    p.add_argument("--workflow", default=str(DEFAULT_WORKFLOW),
                   help="API-format workflow JSON (default: the bundled t2i example)")
    p.add_argument("--timeout", type=float, default=600)
    a = p.parse_args()

    draft = load(a.draft)
    for key in ("width", "height", "summary", "items"):
        if key not in draft:
            p.exit(2, f"Error: draft is missing '{key}' — run layout_tool.py validate first\n")

    prompt = load(a.workflow)
    studio = find_studio(prompt)
    studio.setdefault("inputs", {})
    studio["inputs"]["studio"] = {"draft": draft, "studio": {"width": draft["width"], "height": draft["height"]}}
    studio["inputs"]["draft"] = ""  # editor content is authoritative; override off

    base = a.server.rstrip("/")
    try:
        r = post_json(base + "/prompt", {"prompt": prompt, "client_id": str(uuid.uuid4())})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        p.exit(2, f"Error: ComfyUI rejected the prompt ({e.code})\n{body}\n")
    pid = r["prompt_id"]
    print(f"queued {pid}", flush=True)

    deadline = time.time() + a.timeout
    while time.time() < deadline:
        time.sleep(2)
        try:
            with urllib.request.urlopen(f"{base}/history/{pid}", timeout=30) as resp:
                hist = json.loads(resp.read())
        except urllib.error.URLError as e:
            p.exit(2, f"Error: lost the server — {e}\n")
        if pid not in hist:
            continue
        entry = hist[pid]
        status = entry.get("status", {})
        if status.get("status_str") != "success":
            for msg in status.get("messages", []):
                if msg and msg[0] == "execution_error":
                    err = msg[1]
                    p.exit(1, f"Error in node {err.get('node_id')} ({err.get('node_type')}): "
                              f"{err.get('exception_message')}\n")
            p.exit(1, f"Error: prompt {status.get('status_str')}\n")
        outputs = []
        for node_id, out in entry.get("outputs", {}).items():
            for value in out.values():
                if isinstance(value, list):
                    outputs += [v["filename"] for v in value
                                if isinstance(v, dict) and "filename" in v]
        print("success")
        for name in outputs:
            print("  output:", name)
        return 0
    p.exit(1, "Error: timed out waiting for the prompt\n")


if __name__ == "__main__":
    sys.exit(main())
