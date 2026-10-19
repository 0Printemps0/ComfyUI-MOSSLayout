// MOSS-Image Layout model + client-side compiler. Mirrors backend/utils/moss.py
// (key order, floor/ceil centering, minified separators); Python is authoritative.

import { isRecord } from './guards'

export type Label = 'object' | 'character' | 'text'
export const LABELS: Label[] = ['object', 'character', 'text']
export const CANVAS_MODES = ['single', 'multi_panel', 'collage'] as const
export type CanvasMode = (typeof CANVAS_MODES)[number]

export interface MossElement {
  id: string
  label: Label
  bbox: [number, number, number, number] // pixel [x1,y1,x2,y2], top-left origin
  caption: string
  text: string        // literal text (text items)
  tags: string[]
  palette: string[]   // hex colors
  // editor-only (never in the draft)
  boxColor: string
  linkId: string | null
  groupId: string | null
}

export interface SummaryState {
  caption: string
  meta: string[]
  canvas: CanvasMode
  palette: string[]
}

export interface OverlaySettings {
  lineWidth: number
  fillAlpha: number
  labelSize: number
  showIndex: boolean
  showText: boolean
}

export interface UiPrefs {
  showLabels: boolean
  backdropOpacity: number
  newType: Label
  jsonOpen: boolean
  summaryOpen: boolean
  itemsOpen: boolean
  showPresets: boolean
  jsonSync: boolean
  livePreview: boolean
  sync: boolean
}

export interface MossState {
  width: number
  height: number
  summary: SummaryState
  elements: MossElement[]
  overlay: OverlaySettings
  ui: UiPrefs
}

export interface DraftItem {
  label: Label
  caption: string
  bbox: [number, number, number, number]
  text?: string
  tags?: string[]
  palette?: string[]
}

export interface Draft {
  width: number
  height: number
  bbox_coord_space: 'abs'
  bbox_format: 'xyxy'
  summary: { caption: string; meta?: string[]; canvas?: CanvasMode; palette?: string[] }
  items: DraftItem[]
}

// ---- guards for untrusted JSON (workflow values, pasted text, sync payloads) ----

function isNumArray(v: unknown): v is number[] {
  return Array.isArray(v) && v.length === 4 && v.every((x) => typeof x === 'number' && Number.isFinite(x))
}

function isStrArray(v: unknown): v is string[] {
  return Array.isArray(v) && v.every((s) => typeof s === 'string' && s.trim() !== '')
}

// Colors auto-assigned to new boxes.
export const BOX_PALETTE = ['#60a5fa', '#f472b6', '#34d399', '#fbbf24', '#a78bfa', '#22d3ee', '#f87171', '#a3e635']
let _colorSeq = 0
export function nextBoxColor(): string {
  return BOX_PALETTE[_colorSeq++ % BOX_PALETTE.length]
}

export function groupColor(groupId: string): string {
  let h = 0
  for (let i = 0; i < groupId.length; i++) h = (h * 31 + groupId.charCodeAt(i)) >>> 0
  return `hsl(${h % 360} 70% 55%)`
}

export function emptyOverlay(): OverlaySettings {
  return { lineWidth: 3, fillAlpha: 0.18, labelSize: 16, showIndex: true, showText: true }
}

export function emptyUi(): UiPrefs {
  return { sync: true, showLabels: true, backdropOpacity: 0.5, newType: 'object', jsonOpen: false, summaryOpen: true, itemsOpen: true, showPresets: false, jsonSync: false, livePreview: false }
}

let _seq = 0
export function newId(): string {
  return `e${++_seq}_${Math.random().toString(36).slice(2, 7)}`
}

export function syncSeq(ids: Array<string | null | undefined>) {
  for (const id of ids) {
    const m = id && /^(?:e)(\d+)_/.exec(id)
    if (m) _seq = Math.max(_seq, parseInt(m[1], 10))
  }
}

export function newElement(label: Label, bbox: MossElement['bbox']): MossElement {
  return { id: newId(), label, bbox, caption: '', text: '', tags: [], palette: [], boxColor: nextBoxColor(), linkId: null, groupId: null }
}

export function emptyState(): MossState {
  return {
    width: 1024, height: 1024,
    summary: { caption: '', meta: [], canvas: 'single', palette: [] },
    elements: [],
    overlay: emptyOverlay(),
    ui: emptyUi(),
  }
}

const HEX_RE = /^#[0-9A-Fa-f]{6}$/

export function normalizeHex(raw: string): string | null {
  const s = raw.trim()
  if (HEX_RE.test(s)) return s.toUpperCase()
  if (/^#[0-9A-Fa-f]{3}$/.test(s)) return '#' + s.slice(1).split('').map((c) => c + c).join('').toUpperCase()
  return null
}

export function snapDim(v: number): number {
  const n = Math.round(v)
  return Math.max(16, Math.floor(n / 16) * 16)
}

function clampBbox(b: [number, number, number, number], w: number, h: number): [number, number, number, number] {
  let [x1, y1, x2, y2] = b
  x1 = Math.max(0, Math.min(w, x1)); x2 = Math.max(0, Math.min(w, x2))
  y1 = Math.max(0, Math.min(h, y1)); y2 = Math.max(0, Math.min(h, y2))
  if (x1 > x2) [x1, x2] = [x2, x1]
  if (y1 > y2) [y1, y2] = [y2, y1]
  return [x1, y1, x2, y2]
}

// The canonical draft exactly as it appears in the workflow JSON.
export function buildDraft(state: MossState): Draft {
  const width = snapDim(state.width)
  const height = snapDim(state.height)
  const summary: Draft['summary'] = { canvas: state.summary.canvas, caption: state.summary.caption }
  if (state.summary.meta.length) summary.meta = [...state.summary.meta]
  if (state.summary.palette.length) summary.palette = [...state.summary.palette]
  const items: DraftItem[] = state.elements.map((el) => {
    const it: DraftItem = { label: el.label, caption: el.caption, bbox: clampBbox(el.bbox, width, height) }
    if (el.label === 'text' || el.text) it.text = el.text
    if (el.tags.length) it.tags = [...el.tags]
    if (el.palette.length) it.palette = [...el.palette]
    return it
  })
  return { width, height, bbox_coord_space: 'abs', bbox_format: 'xyxy', summary, items }
}

// Compiled model prompt: integer center-origin yxyx boxes, minified one line.
// Mirrors the official compiler (floor mins / ceil maxs, then subtract center).
export function compileDraft(draft: Draft): { json: string; warnings: string[] } {
  const warnings: string[] = []
  const width = draft.width, height = draft.height
  const items = draft.items.map((it) => {
    const [x1, y1, x2, y2] = it.bbox
    const box = [
      Math.floor(y1) - (height >> 1),
      Math.floor(x1) - (width >> 1),
      Math.ceil(y2) - (height >> 1),
      Math.ceil(x2) - (width >> 1),
    ]
    const out: Record<string, unknown> = { label: it.label, caption: it.caption, bbox: box }
    if (it.text) out.text = it.text
    if (it.tags?.length) out.tags = it.tags
    if (it.palette?.length) out.palette = it.palette
    return out
  })
  const result = { summary: draft.summary, items, bbox_coord_space: 'abs_centralized', bbox_format: 'yxyx' }
  return { json: JSON.stringify(result), warnings }
}

export function serialize(state: MossState): { draft: Draft; draftPretty: string; prompt: string; warnings: string[] } {
  const draft = buildDraft(state)
  const compiled = compileDraft(draft)
  return { draft, draftPretty: JSON.stringify(draft, null, 2), prompt: compiled.json, warnings: compiled.warnings }
}

// Recover a JSON object from text that may be wrapped in code fences or prose.
export function parseJsonLoose(text: string): { ok: true; obj: Record<string, unknown> } | { ok: false; error: string } {
  if (!text || !text.trim()) return { ok: false, error: 'empty input' }
  let s = text.trim()
  if (s.startsWith('```')) {
    s = s.replace(/^`+/, '').replace(/`+$/, '')
    if (/^json/i.test(s.trim())) s = s.trim().slice(4)
    s = s.trim()
  }
  const start = s.indexOf('{')
  const end = s.lastIndexOf('}')
  if (start < 0 || end <= start) return { ok: false, error: 'no JSON object found' }
  try {
    const obj: unknown = JSON.parse(s.slice(start, end + 1))
    if (!isRecord(obj)) return { ok: false, error: 'payload is not a JSON object' }
    return { ok: true, obj }
  } catch (e: unknown) {
    return { ok: false, error: String((e as Error)?.message || e) }
  }
}

// Any of: draft JSON, compiled prompt JSON, {'caption': ...} -> editor state.
// Compiled boxes are de-centered onto the given canvas. Mirrors resolve_payload.
export function resolveToState(obj: unknown, width: number, height: number): { state: Partial<MossState>; warnings: string[] } {
  const warnings: string[] = []
  if (!isRecord(obj)) return { state: {}, warnings: ['payload is not a JSON object'] }
  let src: Record<string, unknown> = obj
  if (src.bbox_format === 'yxyx' || src.bbox_coord_space === 'abs_centralized') {
    const rawItems = Array.isArray(src.items) ? src.items : []
    src = {
      width, height,
      summary: src.summary ?? {},
      items: rawItems.map((it) => {
        if (!isRecord(it)) return it
        const bb = it.bbox
        const half_w = width >> 1, half_h = height >> 1
        if (isNumArray(bb)) {
          const [y1, x1, y2, x2] = bb
          return { ...it, bbox: [x1 + half_w, y1 + half_h, x2 + half_w, y2 + half_h] }
        }
        return { ...it, bbox: [0, 0, Math.min(256, width), Math.min(256, height)] }
      }),
    }
    warnings.push(`imported a compiled prompt; boxes mapped onto the current canvas ${width}x${height} — set the canvas to the generation size for exact coordinates`)
  } else if (typeof src.caption === 'string' && !('items' in src)) {
    src = { width, height, summary: { caption: src.caption }, items: [] }
    warnings.push('caption-only payload imported; add boxes to build a Layout')
  }

  const w = snapDim(typeof src.width === 'number' ? src.width : 1024)
  const h = snapDim(typeof src.height === 'number' ? src.height : 1024)
  const rawSummary = isRecord(src.summary) ? src.summary : {}
  const summary: SummaryState = {
    caption: typeof rawSummary.caption === 'string' ? rawSummary.caption : '',
    meta: isStrArray(rawSummary.meta) ? rawSummary.meta : [],
    canvas: (CANVAS_MODES as readonly string[]).includes(rawSummary.canvas as string) ? (rawSummary.canvas as CanvasMode) : 'single',
    palette: isStrArray(rawSummary.palette) ? rawSummary.palette : [],
  }
  const elements: MossElement[] = (Array.isArray(src.items) ? src.items : []).map((raw, i) => {
    const it = isRecord(raw) ? raw : {}
    const label: Label = (LABELS as string[]).includes(it.label as string) ? (it.label as Label) : 'object'
    let bbox: [number, number, number, number]
    if (isNumArray(it.bbox)) {
      bbox = clampBbox(it.bbox, w, h)
    } else {
      bbox = [0, 0, Math.min(256, w), Math.min(256, h)]
      warnings.push(`items[${i}].bbox invalid; reset`)
    }
    const el = newElement(label, bbox)
    el.caption = typeof it.caption === 'string' ? it.caption : ''
    el.text = typeof it.text === 'string' ? it.text : ''
    el.tags = isStrArray(it.tags) ? it.tags : []
    el.palette = isStrArray(it.palette) ? it.palette : []
    return el
  })
  if (!elements.length) warnings.push('items is empty; the compiled prompt requires at least one item')
  if (!summary.caption.trim()) warnings.push('summary.caption is empty')
  return { state: { width: w, height: h, summary, elements }, warnings }
}

// Parse an aspect-ratio string ("16:9", "16x9") into width/height preserving the
// megapixel count (snapped to /16). Null if not a ratio.
export function aspectToWH(ar: string, refW = 1024, refH = 1024): { w: number; h: number } | null {
  const m = /^\s*(\d+(?:\.\d+)?)\s*[:x/]\s*(\d+(?:\.\d+)?)\s*$/.exec(ar)
  if (!m) return null
  const rw = parseFloat(m[1]), rh = parseFloat(m[2])
  if (!rw || !rh) return null
  const scale = Math.sqrt((refW * refH) / (rw * rh))
  return { w: snapDim(rw * scale), h: snapDim(rh * scale) }
}
