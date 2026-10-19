// Bridge for the Ref Sync node: turns its broadcast temp-image descriptor into a
// /view URL exposed as a reactive ref.

import { api } from '@comfy/api'
import { ref } from 'vue'

export const refSyncImage = ref<string | null>(null)
// Draft JSON from a JSON Sync node; counter forces watchers on identical payloads.
export const jsonSyncCaption = ref<{ json: string; n: number }>({ json: '', n: 0 })

// ComfyUI's api is an EventTarget at runtime; its package types don't expose it.
const events = api as unknown as EventTarget

function eventDetail(ev: Event): Record<string, unknown> {
  if (ev instanceof CustomEvent) {
    const d: unknown = ev.detail
    return typeof d === 'object' && d !== null ? (d as Record<string, unknown>) : {}
  }
  return {}
}

function str(v: unknown, fallback = ''): string {
  return typeof v === 'string' ? v : fallback
}

let inited = false
export function initRefSync() {
  if (inited) return
  inited = true
  try {
    events.addEventListener('moss-layout.ref-sync', (ev) => {
      const d = eventDetail(ev)
      if (typeof d.filename !== 'string') return
      const p = new URLSearchParams({
        filename: d.filename,
        subfolder: str(d.subfolder),
        type: str(d.type, 'temp'),
      })
      // cache-bust so the same filename still triggers watchers + reloads
      refSyncImage.value = `/view?${p.toString()}&r=${Date.now()}`
    })
    events.addEventListener('moss-layout.json-sync', (ev) => {
      const d = eventDetail(ev)
      if (typeof d.json !== 'string') return
      jsonSyncCaption.value = { json: d.json, n: jsonSyncCaption.value.n + 1 }
    })
  } catch (err: unknown) {
    console.warn('[MossLayoutStudio] sync listener failed to register', err)
  }
}
