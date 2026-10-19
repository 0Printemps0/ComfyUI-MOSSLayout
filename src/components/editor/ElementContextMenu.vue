<template>
  <Teleport to="body">
    <div v-if="m && el" class="ctxbg" @pointerdown="close" @contextmenu.prevent="close" @wheel="close">
      <div class="ctx" :style="style" @pointerdown.stop @contextmenu.prevent.stop>
        <template v-if="bulk">
          <div class="ctxhead">
            <i class="mdi" :class="isOneGroup ? 'mdi-group' : 'mdi-checkbox-multiple-marked-outline'"></i>
            <span class="cnum">{{ isOneGroup ? 'Group · ' + store.selectedIds.length : store.selectedIds.length + ' selected' }}</span>
          </div>
          <button v-if="!isOneGroup" class="ctxitem" @click="run(() => store.group(store.selectedIds))"><i class="mdi mdi-group"></i> group</button>
          <button v-if="anyGrouped" class="ctxitem" @click="run(ungroupBulk)"><i class="mdi mdi-ungroup"></i> ungroup</button>
          <button class="ctxitem" @click="run(() => store.duplicateMany(store.selectedIds))"><i class="mdi mdi-content-copy"></i> duplicate{{ isOneGroup ? ' group' : '' }}</button>
          <button class="ctxitem" @click="run(store.copySelection)"><i class="mdi mdi-content-duplicate"></i> copy <span class="ctxkey">⌘C</span></button>
          <div class="ctxdiv"></div>
          <button class="ctxitem del" @click="runBulk((id) => store.removeElement(id))"><i class="mdi mdi-delete-outline"></i> delete {{ store.selectedIds.length }}</button>
        </template>

        <template v-else>
          <div class="ctxhead">
            <span class="cdot" :style="{ background: el.boxColor }"></span>
            <span class="cnum">#{{ index + 1 }}</span>
            <i class="mdi" :class="labelIcon(el.label)"></i>
          </div>
          <input
            ref="editEl"
            class="ctxedit"
            :value="el.label === 'text' ? el.text : el.caption"
            :placeholder="el.label === 'text' ? 'text to render…' : 'caption…'"
            @input="onEdit(($event.target as HTMLInputElement).value)"
            @keydown.stop
          />
          <button class="ctxitem" @click="run(() => store.duplicateLinked(m!.id))"><i class="mdi mdi-link-variant-plus"></i> linked copy</button>
          <button class="ctxitem" @click="run(() => store.duplicateElement(m!.id))"><i class="mdi mdi-content-copy"></i> duplicate</button>
          <button class="ctxitem" @click="run(store.copySelection)"><i class="mdi mdi-content-duplicate"></i> copy <span class="ctxkey">⌘C</span></button>
          <button v-if="el.linkId" class="ctxitem" @click="run(() => store.unlink(m!.id))"><i class="mdi mdi-link-variant-off"></i> unlink</button>
          <div class="ctxdiv"></div>
          <button class="ctxitem" @click="run(() => store.moveElement(m!.id, -1))"><i class="mdi mdi-arrow-up"></i> move up</button>
          <button class="ctxitem" @click="run(() => store.moveElement(m!.id, 1))"><i class="mdi mdi-arrow-down"></i> move down</button>
          <div class="ctxdiv"></div>
          <button class="ctxitem del" @click="run(() => store.removeElement(m!.id))"><i class="mdi mdi-delete-outline"></i> delete</button>
        </template>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useStudioStore } from '@/lib/store'
import type { Label } from '@/lib/moss'

const store = useStudioStore()
const m = computed(() => store.ctxMenu)
const el = computed(() => store.getElement(m.value?.id ?? null))
const index = computed(() => store.state.elements.findIndex((e) => e.id === m.value?.id))
const editEl = ref<HTMLInputElement | null>(null)
// bulk mode: the right-clicked item is part of a multi-selection
const bulk = computed(() => !!m.value && store.selectedIds.length > 1 && store.selectedIds.includes(m.value.id))
const anyGrouped = computed(() => store.selectedIds.some((id) => store.getElement(id)?.groupId))
// selection is exactly one whole group → nothing new to group
const isOneGroup = computed(() => {
  const ids = store.selectedIds
  if (ids.length < 2) return false
  const g = store.getElement(ids[0])?.groupId
  if (!g || !ids.every((id) => store.getElement(id)?.groupId === g)) return false
  return store.groupSize(ids[0]) === ids.length
})

function labelIcon(label: Label): string {
  return label === 'text' ? 'mdi-format-text' : label === 'character' ? 'mdi-account-outline' : 'mdi-vector-square'
}

function ungroupBulk() {
  for (const id of [...store.selectedIds]) store.ungroup(id)
}

// writes the item's primary content (respects link groups)
function onEdit(v: string) {
  if (el.value) store.setShared(el.value.id, el.value.label === 'text' ? 'text' : 'caption', v)
}

function close() {
  store.closeContextMenu()
}
function run(fn: () => void) {
  fn()
  close()
}
function runBulk(fn: (id: string) => void) {
  for (const id of [...store.selectedIds]) fn(id) // copy: removeElement mutates the list
  close()
}
const style = computed(() => {
  if (!m.value) return {}
  const x = Math.max(4, Math.min(m.value.x, window.innerWidth - 190))
  const y = Math.max(4, Math.min(m.value.y, window.innerHeight - 260))
  return { left: `${x}px`, top: `${y}px` }
})
function onEsc(e: KeyboardEvent) {
  if (e.key === 'Escape') close()
}
watch(m, (v) => {
  if (v) {
    document.addEventListener('keydown', onEsc, true)
    nextTick(() => editEl.value?.focus()) // focus the quick-edit field
  } else {
    document.removeEventListener('keydown', onEsc, true)
  }
})
</script>

<style scoped>
.ctxbg { position: fixed; inset: 0; z-index: 10000; }
.ctx {
  --st-panel: var(--comfy-menu-secondary-bg, #202026);
  --st-input: var(--comfy-input-bg, #15151a);
  --st-btn: var(--comfy-input-bg, #2a2a30);
  --st-text: var(--input-text, #e5e5ea);
  --st-muted: var(--descrip-text, #9aa0aa);
  --st-border: var(--border-color, #3a3a44);
  --st-accent: var(--p-primary-color, #3b82f6);
  --st-radius: var(--radius-md, 6px);
  position: fixed; min-width: 172px; z-index: 10001;
  background: var(--st-panel); border: 1px solid var(--st-border); border-radius: var(--st-radius);
  padding: 4px; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
  font-family: var(--p-font-family, -apple-system, system-ui, sans-serif);
  display: flex; flex-direction: column; gap: 1px;
}
.ctxhead { display: flex; align-items: center; gap: 6px; padding: 4px 9px 6px; color: var(--st-muted); }
.ctxhead .cdot { width: 9px; height: 9px; border-radius: 2px; flex: none; }
.ctxhead .cnum { font-size: 11px; font-weight: 600; }
.ctxhead .mdi { font-size: 14px; margin-left: auto; }
.ctxedit { margin: 0 4px 4px; padding: 5px 7px; background: var(--st-input, #15151a); border: 1px solid var(--st-border); color: var(--st-text); border-radius: 5px; font-size: 12px; font-family: inherit; }
.ctxedit:focus { outline: none; border-color: var(--st-accent); }
.ctxitem { display: flex; align-items: center; gap: 8px; text-align: left; background: none; border: none; color: var(--st-text); padding: 6px 9px; border-radius: calc(var(--st-radius) - 1px); cursor: pointer; font-size: 12px; }
.ctxitem:hover { background: var(--st-btn); }
.ctxitem .mdi { font-size: 15px; color: var(--st-muted); }
.ctxkey { margin-left: auto; font-size: 10px; color: var(--st-muted); opacity: .7; }
.ctxitem.del:hover { background: #b91c1c; color: #fff; }
.ctxitem.del:hover .mdi { color: #fff; }
.ctxdiv { border-top: 1px solid var(--st-border); margin: 3px 0; }
</style>
