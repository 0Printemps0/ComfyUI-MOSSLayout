// Shared subset of the /mosslayout/ routes used by both the Studio library
// overlay and the Browser.

export const J = { 'Content-Type': 'application/json' }

// Cached thumbnail URL for a file in a library dir.
export function thumbUrl(dir: string, name: string, size = 256): string {
  return `/mosslayout/thumb?dir=${encodeURIComponent(dir)}&name=${encodeURIComponent(name)}&size=${size}`
}

export interface PreviewResult {
  preview: string
  valid: boolean
  errors: string[]
  warnings: string[]
  error?: string
}

// Render a bbox preview for a draft JSON. Pass dir+name to composite over the
// source image; omit for a dark-backdrop render.
export async function previewJson(
  json: string,
  opts: { dir?: string; name?: string; width?: number; height?: number } = {},
): Promise<PreviewResult> {
  const r = await fetch('/mosslayout/preview', {
    method: 'POST',
    headers: J,
    body: JSON.stringify({ json, width: 768, height: 768, ...opts }),
  })
  return r.json()
}

// List the managed template library.
export async function listLibrary(): Promise<{ dir: string; templates: { name: string; stem: string; caption: string }[] }> {
  const r = await fetch('/mosslayout/library')
  return r.json()
}

// Save a JSON template (+ optional baked thumbnail) to a folder.
export async function saveTemplate(out_dir: string, name: string, json: string, overwrite = false, thumb = ''): Promise<{ ok?: boolean; path?: string; name?: string; error?: string }> {
  const r = await fetch('/mosslayout/save_template', { method: 'POST', headers: J, body: JSON.stringify({ out_dir, name, json, overwrite, thumb }) })
  return r.json()
}

// Delete a library template (.json + any .thumb.jpg sidecar).
export async function deleteTemplate(name: string): Promise<{ ok?: boolean; removed?: string[]; error?: string }> {
  const r = await fetch('/mosslayout/delete_template', { method: 'POST', headers: J, body: JSON.stringify({ name }) })
  return r.json()
}
