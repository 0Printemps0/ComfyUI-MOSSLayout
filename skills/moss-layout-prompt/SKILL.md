---
name: moss-layout-prompt
description: Turn a natural-language or tag-style image request into a MOSS-Image Layout draft (bbox boxes) and run it in ComfyUI-MOSSLayout. Use when a user asks for a poster, infographic, multi-panel image, or any composition with controlled text placement/object positions, or asks to edit/programmatically read a MOSS Layout workflow. This skill can write the draft JSON, validate and compile it, and submit it to a running ComfyUI server (headless) or inject it into an open editor.
---

# MOSS-Image Layout prompt skill (ComfyUI-MOSSLayout)

You are turning an image request into a **Layout draft** (absolute-pixel
bounding boxes), compiling it into the **model prompt**, and delivering it into
ComfyUI. The tools do coordinate math and validation; you make the creative and
placement decisions.

## When to use this skill

- The user wants text rendered at specific places (posters, menus, covers,
  ads, infographics), several panels, or controlled object relationships.
- The user wants to read/rewrite the bbox prompt inside a saved workflow.
- The user wants to generate from a draft headlessly (script/agent).

Do **not** force a Layout for ordinary scenes without placement requirements —
a plain prose caption is better (MOSS supports caption-only prompts).

## End-to-end loop (this is the actual job)

1. **Decide the canvas.** Pick `width`×`height` as positive multiples of 16
   matching the intended output (1MP ≈ 1024×1024 is the training sweet spot;
   honor explicit user dimensions). Same dimensions are wired into the latent
   of the bundled workflow, so the draft canvas IS the image canvas.
2. **Write the draft** (schema below). One item per coherent visible unit.
   Text items carry the exact visible characters in `text`.
3. **Validate and compile** — never deliver unvalidated geometry:
   ```bash
   python3 skills/moss-layout-prompt/scripts/layout_tool.py validate draft.json
   python3 skills/moss-layout-prompt/scripts/layout_tool.py compile  draft.json
   ```
   `compile` prints the one-line model prompt (center-origin integer yxyx).
   Fix errors in the draft and rerun until it passes.
4. **Deliver — pick one path:**
   - **Saved workflow:** `layout_tool.py set workflow.json draft.json`
     (validates, keeps editor state; the canvas follows on next load).
   - **Open editor, live:** wire the draft through **MOSS Layout Studio JSON
     Sync** (or paste it into the studio's JSON panel) — studios with *json
     sync* on import it immediately.
   - **Headless generation (recommended for agents):**
     ```bash
     python3 skills/moss-layout-prompt/scripts/submit.py draft.json \
       --server http://127.0.0.1:7860
     ```
     Injects the draft into the bundled API workflow, queues it, prints the
     output filenames (clean result + annotated overlay). Exit code 0 = files
     written.
5. **Report** the compiled prompt, the canvas size, and the output filenames.

## Composition rules

- Canvas top-left is `(0,0)`; `bbox = [x1,y1,x2,y2]` in pixels, `x1<x2`,
  `y1<y2`, inside the canvas. Margins of 5–8% of the short side look designed;
  full-bleed is allowed when the user wants it.
- Reading order: lay out items in the order they should be read (top→bottom,
  left→right); item order in `items` is the prompt's order.
- Split into separate items only when independent placement matters; a
  paragraph of copy is one text item with `\n` line breaks.
- Text fit: estimate 1 em ≈ 0.55×box-height per line and ~0.55×font-size per
  Latin character (CJK ≈ 1 em per character). Enlarge boxes rather than
  shrink unreadable copy.
- `summary.caption` describes the whole image (subject, setting, medium,
  lighting, mood, global style). Items describe visible appearance; for text
  items also typography/surface treatment. Never put JSON or tool notes into
  descriptions.
- `summary.palette` / item `palette` are optional `#RRGGBB` arrays;
  `summary.meta` holds medium/genre tags; `summary.canvas` ∈
  single/multi_panel/collage.
- Preserve user-supplied counts, exact wording, language and exclusions.

## Formats

**Draft** (editable, what you write):

```json
{
  "width": 768, "height": 768,
  "bbox_coord_space": "abs", "bbox_format": "xyxy",
  "summary": {"meta": ["poster"], "canvas": "single",
              "caption": "A clean modern coffee-shop opening poster...",
              "palette": ["#6F4E37"]},
  "items": [
    {"label": "object", "caption": "A ceramic latte cup ...", "bbox": [48, 240, 380, 640]},
    {"label": "text", "caption": "Large bold Chinese headline ...",
     "text": "新店开业", "bbox": [420, 200, 720, 380]}
  ]
}
```

`label` ∈ `object` / `character` / `text`. Optional item `tags`/`palette`.

**Compiled prompt** (model-facing; produced by the compiler, never hand-write):
`bbox_coord_space: "abs_centralized"`, `bbox_format: "yxyx"`, integer
center-origin boxes (`floor(min) - dim//2`, `ceil(max) - dim//2`), no canvas
size, single line. It goes into the MOSS positive prompt unchanged; state the
required width×height outside the prompt. If a request quotes text to draw,
keep it verbatim (punctuation, case, line breaks); text that is merely
referenced (not visible) stays in the summary.

## Tools

```bash
python3 skills/moss-layout-prompt/scripts/layout_tool.py <command>
  validate <draft.json>                       # schema + geometry check
  compile  <draft.json> [--out prompt.txt]    # draft -> one-line model prompt
  get      <workflow.json> [--out draft.json] # extract the draft from a workflow
  set      <workflow.json> <draft.json>       # replace a workflow's draft (validated)
  new      <draft.json> <w> <h> [caption]     # scaffold a draft

python3 skills/moss-layout-prompt/scripts/submit.py <draft.json>
  [--server http://127.0.0.1:7860] [--workflow custom.api.json] [--timeout 600]
  # inject draft -> POST /prompt -> poll /history -> print output files
```

Both scripts are stdlib-only. The bundled API workflow
(`example_workflows/moss-layout-t2i.api.json`) targets the official
int8-convrot weights; pass `--workflow` to use your own API prompt.

## Failure handling

- `validate` errors name the item and field — fix the draft, rerun.
- submit.py prints the ComfyUI validation/execution error; common causes:
  `CLIPLoader type` not `moss_image` (shape errors like
  `mat1 and mat2 shapes cannot be multiplied` mean the wrong text encoder
  type), or missing model files.
- Compiled boxes can extend outside the canvas (negative coordinates) — that
  is expected: they are center-origin, not canvas-clipped.

## Programmatic interfaces of the node pack

- Workflow file: `widgets_values[0].draft` is the whole-segment draft JSON
  (single source of truth); `widgets_values[0].studio` holds editor-only state.
- `MOSS Layout Studio` node: optional `draft` STRING input (non-empty overrides
  the editor at execution), `prompt` (compiled) and `draft` (pretty) outputs,
  `extras` bundle (`overlay`, `alpha`, `width`, `height`, `bboxes`).
- `MOSS Layout Studio JSON Sync` node / `moss-layout.json-sync` UI event:
  live-import into open editors. `global` ignores the per-studio toggle;
  `force` overrides it. Compiled JSON without dims needs the node's
  `width`/`height`.
- HTTP global import: `POST /mosslayout/import` with
  `{"json": ..., "width": 1536, "height": 1024}`. Returns the canonical
  `abs`/`xyxy` draft, `warnings`, `errors`, item counts and importer version;
  broadcasts to every open Studio by default (`broadcast`, `global`, `force`
  default true). Use `"bbox_mode": "clamp"` to accept out-of-canvas boxes.
  Schema errors return HTTP 400 and `draft: null`. Unknown `bbox_format` /
  `bbox_coord_space` are rejected, not reinterpreted.
- HTTP: `GET /mosslayout/library`, `POST /mosslayout/save_template`,
  `POST /mosslayout/preview` (validate + render), plus ComfyUI's `/prompt`,
  `/history`, `/view`.
