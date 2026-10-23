<template>
  <div class="studio" ref="rootEl" :class="{ 'panel-open': panelOpen }" @contextmenu.prevent.stop>
    <div class="main">
      <div class="left" ref="leftEl">
        <BBoxCanvas>
          <template #lead>
            <UiButton icon :disabled="!store.canUndo" title="Undo (Ctrl+Z)" @click="store.undo()"><i class="mdi mdi-undo"></i></UiButton>
            <UiButton icon :disabled="!store.canRedo" title="Redo (Ctrl+Shift+Z)" @click="store.redo()"><i class="mdi mdi-redo"></i></UiButton>
            <span class="divider"></span>
            <UiPopover align="left">
              <template #trigger><UiButton title="Resolution — aspect ratio × megapixels">{{ store.state.width }}×{{ store.state.height }} ▾</UiButton></template>
              <div class="resmenu">
                <div class="rsec">aspect ratio</div>
                <div class="aspects">
                  <button v-for="a in CORE_ASPECTS" :key="a.label" class="achip" :class="{ on: aspect === a.label }" :title="a.label + ' · ' + a.name" @click="setAspect(a.label)">
                    <span class="arect" :style="aspectRectStyle(a)"></span>
                    <span class="albl">{{ a.label }}</span>
                  </button>
                </div>
                <div class="rdiv"></div>
                <div class="mprow"><span>megapixels</span>
                  <div class="mppresets">
                    <button v-for="p in MP_PRESETS" :key="p" class="mpp" :class="{ on: mp === p }" @click="setMp(p)">{{ p }}</button>
                  </div>
                  <input type="number" min="0.1" max="16" step="0.1" v-model.number="mp" @input="applyRes" />
                </div>
                <div class="whrow">
                  <label><span>W</span><input type="number" min="16" max="8192" step="16" v-model.number="store.state.width" @change="onWH" /></label>
                  <button class="swap" title="Swap width &amp; height (flip orientation)" @click="swapWH"><i class="mdi mdi-swap-horizontal"></i></button>
                  <label><span>H</span><input type="number" min="16" max="8192" step="16" v-model.number="store.state.height" @change="onWH" /></label>
                </div>
                <div class="rfoot">
                  <span class="rmp">≈ {{ mpActual }} MP</span>
                </div>
                <div v-if="outsideCount" class="roob">
                  <span><i class="mdi mdi-alert-outline"></i> {{ outsideCount }} box{{ outsideCount === 1 ? '' : 'es' }} outside</span>
                  <button class="refit" title="Clamp every box into the current canvas" @click="refitBoxes">refit</button>
                </div>
              </div>
            </UiPopover>
          </template>

          <template #trail>
            <UiButton icon title="Library — save / load layout templates" @click="libraryOpen = true"><i class="mdi mdi-bookshelf"></i></UiButton>
            <UiPopover align="right">
              <template #trigger><UiButton icon title="Help"><i class="mdi mdi-help-circle-outline"></i></UiButton></template>
              <div class="help">
                <p class="h">Canvas</p>
                <dl>
                  <dt>drag empty space</dt><dd>box-select (marquee); hold shift to add</dd>
                  <dt>ctrl / ⌘ + drag</dt><dd>draw a new box</dd>
                  <dt>drag a box</dt><dd>move it</dd>
                  <dt>drag a handle</dt><dd>resize</dd>
                  <dt>click</dt><dd>select; ctrl / shift click to multi-select</dd>
                  <dt>click again</dt><dd>cycle through stacked / overlapping boxes</dd>
                </dl>
                <p class="h">Keyboard</p>
                <dl>
                  <dt>ctrl / ⌘ + C / V</dt><dd>copy / paste the selection (pastes at the cursor)</dd>
                  <dt>ctrl / ⌘ + G</dt><dd>group the selected boxes · + shift to ungroup</dd>
                  <dt>ctrl / ⌘ + Z</dt><dd>undo · + shift to redo</dd>
                  <dt>Delete / Backspace</dt><dd>remove the selected box(es)</dd>
                </dl>
                <p class="h">Items</p>
                <dl>
                  <dt>object / character / text</dt><dd>the MOSS item label — cycle with the toolbar button</dd>
                  <dt>text items</dt><dd>carry the exact visible characters</dd>
                </dl>
                <p class="h">Reference</p>
                <dl>
                  <dt><i class="mdi mdi-image-outline"></i> image</dt><dd>load an image to trace over (or drop one on the canvas)</dd>
                  <dt><i class="mdi mdi-sync"></i> sync</dt><dd>auto-update the reference from a <b>MOSS Layout Studio Ref Sync</b> node</dd>
                  <dt><i class="mdi mdi-television-play"></i> live preview</dt><dd>show the in-progress preview of the sampler feeding your <b>Ref Sync</b> node, until the final image syncs in</dd>
                </dl>
                <p class="h">Outputs</p>
                <dl>
                  <dt>prompt</dt><dd>compiled MOSS-Image JSON (center-origin yxyx) → your sampler's positive prompt</dd>
                  <dt>draft</dt><dd>the editable draft JSON — feed it back, save it, or edit it by script</dd>
                  <dt>extras</dt><dd>→ <b>MOSS Layout Studio Extras</b> node for overlay / alpha / width / height</dd>
                </dl>
                <p class="tip">Tip: open the JSON card and paste a draft (or a compiled prompt) to import it.</p>
                <p class="credit">
                  MOSS edition of <b>ComfyUI-IdeogramHelper</b> by nynxz (GPLv3)<br />
                  <a href="https://github.com/OpenMOSS/MOSS-Image" target="_blank" rel="noopener noreferrer">MOSS-Image prompt spec ↗</a>
                </p>
              </div>
            </UiPopover>
            <UiPopover align="right">
              <template #trigger><UiButton icon title="Clear everything"><i class="mdi mdi-broom"></i></UiButton></template>
              <template #default="{ close }">
                <div class="resetc">
                  <p class="rq"><i class="mdi mdi-alert-outline"></i> Clear the whole studio?</p>
                  <p class="rh">Removes every item and resets the summary — can't be undone past here.</p>
                  <div class="rbtns">
                    <button class="rno" @click="close()">Cancel</button>
                    <button class="ryes" @click="resetAll(); close()"><i class="mdi mdi-broom"></i> Clear all</button>
                  </div>
                </div>
              </template>
            </UiPopover>
            <span class="slim-controls"><UiButton icon :title="panelOpen ? 'Hide controls' : 'Show controls'" @click="panelOpen = !panelOpen"><i class="mdi mdi-dock-right"></i></UiButton></span>
          </template>
        </BBoxCanvas>
      </div>
      <div class="right" ref="rightEl">
        <SummaryPanel />
        <ElementList />
        <JsonControls />
      </div>
      <!-- slim mode (container query): tap-outside backdrop to close the drawer;
           scoped to .main so it doesn't cover the JSON/editor below -->
      <div class="drawer-backdrop" @click="panelOpen = false"></div>
    </div>

    <!-- mutually exclusive with the JSON view so the two don't stack and inflate height -->
    <ElementEditor v-if="!store.state.ui.jsonOpen" />

    <JsonPreview />
    <ElementContextMenu />
    <StudioLibrary v-model:open="libraryOpen" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { createStudioStore, provideStudioStore } from '@/lib/store'
import { emptyState, serialize, resolveToState, parseJsonLoose, type MossState } from '@/lib/moss'
import { jsonSyncCaption } from '@/lib/refSync'
import { isRecord } from '@/lib/guards'
import UiButton from '../ui/UiButton.vue'
import UiPopover from '../ui/UiPopover.vue'
import BBoxCanvas from '../editor/BBoxCanvas.vue'
import StudioLibrary from './StudioLibrary.vue'
import SummaryPanel from '../editor/SummaryPanel.vue'
import ElementList from '../editor/ElementList.vue'
import JsonControls from './JsonControls.vue'
import ElementEditor from '../editor/ElementEditor.vue'
import JsonPreview from './JsonPreview.vue'
import ElementContextMenu from '../editor/ElementContextMenu.vue'

const props = defineProps<{ widget: any; node?: any }>()

const store = createStudioStore()
provideStudioStore(store)

const rootEl = ref<HTMLElement | null>(null)
const libraryOpen = ref(false)
const panelOpen = ref(false) // slim-mode sidebar drawer open/closed
const leftEl = ref<HTMLElement | null>(null)
const rightEl = ref<HTMLElement | null>(null)

// No JS height-sync: sidebar height left to CSS/content so the node can shrink.
// Capture undo/redo keys before the graph; capture phase + stopImmediatePropagation
// so the graph's own undo doesn't also fire. Text fields keep native undo.
function onUndoKey(e: KeyboardEvent) {
  if (!(e.ctrlKey || e.metaKey)) return
  const k = e.key.toLowerCase()
  if (k !== 'z' && k !== 'y') return
  const root = rootEl.value
  const ae = document.activeElement
  if (!root || !ae || !root.contains(ae)) return
  const tag = (ae as HTMLElement).tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || (ae as HTMLElement).isContentEditable) return
  const redo = k === 'y' || (k === 'z' && e.shiftKey)
  if (redo) store.redo()
  else store.undo()
  e.preventDefault()
  e.stopImmediatePropagation()
}
onMounted(() => document.addEventListener('keydown', onUndoKey, true))
onBeforeUnmount(() => document.removeEventListener('keydown', onUndoKey, true))

watch(
  () => jsonSyncCaption.value.n,
  () => {
    const ev = jsonSyncCaption.value
    const forced = ev.global || ev.force
    // Per-studio toggle stays the default; global/force is an explicit override.
    if (!forced && !store.state.ui.jsonSync) return
    if (!ev.json || !ev.json.trim()) return
    const label = ev.global ? 'Global import' : ev.force ? 'Forced JSON sync' : 'JSON sync'
    const res = store.importDraftJson(ev.json, {
      keepDims: true,
      strict: true,
      bboxMode: ev.bboxMode as 'auto' | 'reject' | 'clamp',
      bboxTolerance: ev.bboxTolerance,
    })
    store.json.syncWarnings = [...new Set([...(ev.warnings || []), ...(res.warnings || [])])]
    if (!res.ok) {
      store.json.syncError = `${label}: ${res.error || 'invalid JSON'}`
      store.json.syncNote = ''
      return
    }
    store.json.syncError = ''
    const count = store.state.elements.length
    const warnCount = store.json.syncWarnings.length
    const warnNote = warnCount ? ` · ${warnCount} warning${warnCount === 1 ? '' : 's'}` : ''
    store.json.syncNote = `${label} applied · ${count} item${count === 1 ? '' : 's'} · ${store.state.width}×${store.state.height}${warnNote}`
  },
)

// total = MP × 1024², exact-ratio scale, /16 round
const CORE_ASPECTS = [
  { label: '1:1', name: 'square', w: 1, h: 1 },
  { label: '3:2', name: 'photo', w: 3, h: 2 },
  { label: '4:3', name: 'standard', w: 4, h: 3 },
  { label: '16:9', name: 'widescreen', w: 16, h: 9 },
  { label: '21:9', name: 'ultrawide', w: 21, h: 9 },
  { label: '2:3', name: 'portrait', w: 2, h: 3 },
  { label: '3:4', name: 'portrait', w: 3, h: 4 },
  { label: '9:16', name: 'portrait', w: 9, h: 16 },
]
const aspect = ref('1:1')
const mp = ref(1)
const MP_PRESETS = [0.5, 1, 2, 4]
const mpActual = computed(() => ((store.state.width * store.state.height) / (1024 * 1024)).toFixed(2))
const outsideCount = computed(() =>
  store.state.elements.filter((e) =>
    e.bbox[0] < 0 || e.bbox[1] < 0
    || e.bbox[2] > store.state.width || e.bbox[3] > store.state.height,
  ).length,
)
function aspectRectStyle(a: { w: number; h: number }) {
  const s = 15 / Math.max(a.w, a.h)
  return { width: Math.round(a.w * s) + 'px', height: Math.round(a.h * s) + 'px' }
}
function setAspect(label: string) {
  aspect.value = label
  applyRes()
}
function setMp(p: number) {
  mp.value = p
  applyRes()
}
function swapWH() {
  const w = store.state.width
  store.state.width = store.state.height
  store.state.height = w
  seedRes()
}
function onWH() {
  store.state.width = snap16(store.state.width)
  store.state.height = snap16(store.state.height)
  seedRes()
}
// MOSS dimensions are multiples of 16
const snap16 = (v: number) => Math.max(16, Math.round(v / 16) * 16)
function applyRes() {
  const a = CORE_ASPECTS.find((x) => x.label === aspect.value) || CORE_ASPECTS[0]
  const total = Math.max(0.1, mp.value || 1) * 1024 * 1024
  const scale = Math.sqrt(total / (a.w * a.h))
  store.state.width = snap16(a.w * scale)
  store.state.height = snap16(a.h * scale)
}
function seedRes() {
  // reflect current dims in the aspect/MP controls without resizing
  const w = store.state.width
  const h = store.state.height
  mp.value = Math.max(0.1, Number((((w * h) / (1024 * 1024))).toFixed(2)))
  const r = w / h
  aspect.value = CORE_ASPECTS.reduce(
    (best, x) => (Math.abs(x.w / x.h - r) < Math.abs(best.w / best.h - r) ? x : best),
    CORE_ASPECTS[0],
  ).label
}
function refitBoxes() {
  const n = store.refitToCanvas()
  if (!n) return
  store.json.syncError = ''
  store.json.syncWarnings = []
  store.json.syncNote = `Canvas refit · ${n} box${n === 1 ? '' : 'es'} clamped`
}

function plainState(): MossState {
  return JSON.parse(JSON.stringify(store.state)) as MossState
}
function resetAll() {
  store.load(emptyState())
  store.select(null)
  store.resetHistory()
}

let snapTimer: ReturnType<typeof setTimeout> | undefined
function scheduleSnapshot() {
  clearTimeout(snapTimer)
  snapTimer = setTimeout(() => store.snapshot(), 350)
}

// widget payload = { draft: canonical draft JSON, studio: full editor state }.
// On load, `studio` wins when its own derived draft matches the saved `draft`
// byte-for-byte; otherwise (a script edited the draft) the draft is authoritative
// and editor-only metadata is regenerated. This keeps the whole-segment JSON the
// single source of truth for scripts while the editor round-trips losslessly.
function deriveDraft(state: MossState) {
  return JSON.stringify(serialize(state).draft)
}

onMounted(() => {
  const v = props.widget?.value
  if (isRecord(v) && isRecord(v.studio)) {
    const fromStudio = deriveDraft(v.studio as unknown as MossState)
    const savedDraft = typeof v.draft === 'string' ? v.draft : JSON.stringify(v.draft ?? {})
    if (fromStudio === savedDraft) {
      store.load(v.studio as Partial<MossState>)
    } else {
      const parsed = parseJsonLoose(savedDraft)
      if (parsed.ok) {
        const { state } = resolveToState(parsed.obj, (v.studio as MossState).width || 1024, (v.studio as MossState).height || 1024)
        const ui = (v.studio as Partial<MossState>).ui
        const overlay = (v.studio as Partial<MossState>).overlay
        store.load({ ...state, ui, overlay })
      } else {
        store.load(v.studio as Partial<MossState>)
      }
    }
  } else if (isRecord(v) && (v.draft || v.caption)) {
    const parsed = parseJsonLoose(typeof v.draft === 'string' ? v.draft : JSON.stringify(v.draft))
    if (parsed.ok) {
      const { state } = resolveToState(parsed.obj, 1024, 1024)
      store.load(state)
    }
  }
  seedRes()
  store.resetHistory()

  props.widget.serializeValue = async () => {
    const { draft } = serialize(store.state)
    return { draft, studio: plainState() }
  }

  watch(
    () => store.state,
    () => {
      const { draft } = serialize(store.state)
      props.widget.value = { draft, studio: plainState() }
      if (!store.restoring) scheduleSnapshot()
    },
    { deep: true, immediate: true },
  )
})
</script>

<style scoped>
/* Map ComfyUI theme vars to semantic names (dark fallbacks); inherited by children. */
.studio {
  --st-bg: var(--comfy-menu-bg, #1a1a1f);
  --st-panel: var(--comfy-menu-secondary-bg, #202026);
  --st-input: var(--comfy-input-bg, #15151a);
  --st-btn: var(--comfy-input-bg, #2a2a30);
  --st-border: var(--border-color, #3a3a44);
  --st-text: var(--input-text, #e5e5ea);
  --st-muted: var(--descrip-text, #9aa0aa);
  --st-accent: var(--p-primary-color, #60a5fa);
  --st-on-accent: var(--p-primary-button-text-color, #fff);
  --st-radius: var(--radius-md, 6px);
  color: var(--st-text);
  background: var(--st-bg);
  font-family: var(--p-font-family, -apple-system, system-ui, sans-serif);
  height: 100%;
  overflow-y: auto;
  overscroll-behavior: contain;
}
.main { display: flex; gap: 8px; }
.left { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; }
.right { flex: none; width: 265px; display: flex; flex-direction: column; gap: 8px; }
.drawer-backdrop { display: none; }
.slim-controls { display: none; }
@media (max-width: 760px) {
  .main { position: relative; }
  .right {
    position: absolute; right: 0; top: 0; bottom: 0; z-index: 30;
    background: var(--st-panel); padding: 8px; width: 260px;
    transform: translateX(100%); transition: transform .15s;
  }
  .studio.panel-open .right { transform: none; }
  .studio.panel-open .drawer-backdrop { display: block; position: absolute; inset: 0; z-index: 29; background: rgba(0,0,0,.4); }
  .slim-controls { display: inline-flex; }
}
.resmenu { display: flex; flex-direction: column; gap: 6px; min-width: 210px; }
.rsec, .rdiv { font-size: 9px; text-transform: uppercase; letter-spacing: .5px; color: var(--st-muted); }
.rdiv { border-top: 1px solid var(--st-border); margin: 2px 0; }
.aspects { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; }
.achip { display: flex; flex-direction: column; align-items: center; gap: 3px; background: var(--st-btn); border: 1px solid var(--st-border); color: var(--st-text); border-radius: 6px; padding: 6px 2px; cursor: pointer; }
.achip.on { border-color: var(--st-accent); color: var(--st-accent); }
.arect { border: 1.5px solid currentColor; border-radius: 2px; display: block; }
.albl { font-size: 9px; font-variant-numeric: tabular-nums; }
.mprow { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--st-muted); }
.mppresets { display: flex; gap: 3px; }
.mpp { background: var(--st-btn); border: 1px solid var(--st-border); color: var(--st-text); border-radius: 4px; font-size: 10px; padding: 2px 6px; cursor: pointer; }
.mpp.on { border-color: var(--st-accent); color: var(--st-accent); }
.mprow input[type='number'] { width: 52px; background: var(--st-input); border: 1px solid var(--st-border); color: var(--st-text); border-radius: 4px; padding: 3px; font-size: 11px; }
.whrow { display: flex; align-items: center; gap: 8px; }
.whrow label { display: flex; align-items: center; gap: 4px; font-size: 10px; color: var(--st-muted); flex: 1; }
.whrow input { width: 100%; background: var(--st-input); border: 1px solid var(--st-border); color: var(--st-text); border-radius: 4px; padding: 4px; font-size: 12px; }
.swap { background: var(--st-btn); border: 1px solid var(--st-border); color: var(--st-muted); border-radius: 4px; width: 26px; height: 26px; cursor: pointer; flex: none; }
.swap:hover { color: var(--st-accent); border-color: var(--st-accent); }
.rfoot { display: flex; align-items: center; gap: 6px; font-size: 10px; color: var(--st-muted); }
.roob { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding-top: 5px; border-top: 1px solid var(--st-border); font-size: 10px; color: #f59e0b; }
.roob .refit { background: var(--st-btn); border: 1px solid rgba(245, 158, 11, .45); color: #fbbf24; border-radius: 4px; padding: 2px 8px; font-size: 10px; cursor: pointer; }
.roob .refit:hover { border-color: #fbbf24; }
.help { display: flex; flex-direction: column; gap: 6px; min-width: 240px; max-width: 300px; font-size: 11px; }
.help .h { font-size: 9px; text-transform: uppercase; letter-spacing: .5px; color: var(--st-muted); margin: 2px 0 0; }
.help dl { display: grid; grid-template-columns: auto 1fr; gap: 2px 10px; margin: 0; }
.help dt { color: var(--st-muted); white-space: nowrap; }
.help dd { margin: 0; }
.help .tip { color: var(--st-muted); font-size: 10px; margin: 4px 0 0; }
.help .credit { color: var(--st-muted); font-size: 9px; margin: 6px 0 0; border-top: 1px solid var(--st-border); padding-top: 6px; }
.help .credit a { color: var(--st-accent); }
.resetc { display: flex; flex-direction: column; gap: 6px; min-width: 210px; }
.resetc .rq { margin: 0; font-size: 12px; font-weight: 600; }
.resetc .rh { margin: 0; font-size: 10px; color: var(--st-muted); }
.rbtns { display: flex; gap: 6px; justify-content: flex-end; }
.rno, .ryes { border: 1px solid var(--st-border); background: var(--st-btn); color: var(--st-text); border-radius: 5px; padding: 4px 10px; font-size: 11px; cursor: pointer; }
.ryes { background: #b91c1c; border-color: #b91c1c; color: #fff; }
</style>
