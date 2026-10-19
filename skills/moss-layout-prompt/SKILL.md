---
name: moss-layout-prompt
description: Read, validate, edit and compile MOSS-Image Layout draft JSON inside ComfyUI-MOSSLayout workflows. Use for programmatic bbox-layout prompt generation, scripted workflow editing, or compiling a draft into a ready-to-queue MOSS-Image prompt.
---

# MOSS-Image Layout draft tooling (ComfyUI-MOSSLayout)

Turn an image idea into a MOSS-Image Layout draft, embed it in a
ComfyUI-MOSSLayout workflow (or feed it to the node directly), and compile it
into the exact prompt the MOSS-Image model consumes. The bundled Python tool
handles validation and coordinate math; you make the creative decisions.
No third-party dependencies.

## The two formats

**Draft** (editable, stored inside the workflow):
`width`/`height` (positive multiples of 16), `bbox_coord_space: "abs"`,
`bbox_format: "xyxy"`, `summary` (`caption` required; optional `meta`,
`canvas` ∈ single/multi_panel/collage, `palette`), flat `items` array.
Each item: `label` ∈ object/character/text, nonempty `caption`, pixel
`bbox [x1,y1,x2,y2]` from the canvas top-left, `text` (required for text
items — the exact visible characters, JSON `\n` for line breaks), optional
`tags`/`palette` string arrays.

**Compiled prompt** (model-facing, what the `prompt` output sends):
`bbox_coord_space: "abs_centralized"`, `bbox_format: "yxyx"`, integer
center-origin boxes (`floor(min) - dim//2`, `ceil(max) - dim//2`), no canvas
size, one physical line. Never hand-write it — compile with the tool.

Read the official format reference at
`OpenMOSS/MOSS-Image skills/moss-image-prompt-enhancer/references/layout.md`
before writing a Layout from scratch.

## Tool

```bash
python3 skills/moss-layout-prompt/scripts/layout_tool.py <command> ...
  validate <draft.json>                     # schema + geometry check
  compile <draft.json> [--out prompt.txt]   # draft -> model prompt (one line)
  get <workflow.json> [--out draft.json]    # extract the draft from a workflow
  set <workflow.json> <draft.json>          # replace the workflow's draft (validated)
  new <draft.json> <width> <height> [caption]  # scaffold an empty draft
```

`set` keeps the editor state (`studio` sub-object) intact and is the
supported way for scripts/agents to edit a saved workflow; the editor canvas
follows the draft on next load.

## Programmatic interfaces of the node pack

- **Workflow file**: `widgets_values[0].draft` is the whole-segment draft JSON
  (single source of truth). Read/write it directly, or via `get`/`set` above.
- **`draft` STRING input** on MOSS Layout Studio: non-empty value overrides
  the editor content at execution time (accepts draft or compiled JSON).
- **`draft` STRING output**: pretty draft for downstream nodes/files.
- **`prompt` STRING output**: the compiled model prompt.
- **MOSS Layout JSON Sync** node / `moss-layout.json-sync` UI event:
  live-import a draft into open editors.
- **HTTP** (ComfyUI server): `POST /mosslayout/preview` (validate + render),
  `GET /mosslayout/library`, `POST /mosslayout/save_template`.
- **/prompt API**: submit a graph whose `MossLayoutStudio.inputs.studio` is
  `{"draft": <draft object>, "studio": {}}` — see the example workflow.

## Rules

- Keep `width`/`height` equal to the generation resolution (multiples of 16);
  boxes outside the canvas are invalid.
- Preserve the user's subjects, counts, style and exact visible wording.
  Text items carry the literal characters; descriptions stay visual.
- Compile after every geometry or caption edit; fix validation errors in the
  draft, never bypass the compiler.
- The compiled prompt goes into MOSS-Image's positive prompt unchanged; state
  the required width×height outside the prompt.
