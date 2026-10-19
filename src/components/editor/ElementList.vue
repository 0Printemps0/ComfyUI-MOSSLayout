<template>
  <UiCard style="flex: 1 1 0; min-height: 200px;">
    <template #header>
      <div class="chead">
        <UiPopover align="left">
          <template #trigger>
            <button class="lhead" title="Filter items"><i class="mdi flt" :class="filterIcon"></i> items ({{ rows.length }})<i class="mdi mdi-menu-down"></i></button>
          </template>
          <template #default="{ close }">
            <div class="lmenu">
              <button class="litem" :class="{ on: filter === 'all' }" @click="filter = 'all'; close()"><i class="mdi mdi-format-list-bulleted"></i> all items</button>
              <button class="litem" :class="{ on: filter === 'object' }" @click="filter = 'object'; close()"><i class="mdi mdi-vector-square"></i> objects</button>
              <button class="litem" :class="{ on: filter === 'character' }" @click="filter = 'character'; close()"><i class="mdi mdi-account-outline"></i> characters</button>
              <button class="litem" :class="{ on: filter === 'text' }" @click="filter = 'text'; close()"><i class="mdi mdi-format-text"></i> text</button>
            </div>
          </template>
        </UiPopover>
      </div>
      <div class="adds">
        <UiButton title="Add an object box" @click="store.addElement('object')"><i class="mdi mdi-plus"></i> obj</UiButton>
        <UiButton title="Add a character box" @click="store.addElement('character')"><i class="mdi mdi-plus"></i> char</UiButton>
        <UiButton title="Add a text box" @click="store.addElement('text')"><i class="mdi mdi-plus"></i> text</UiButton>
      </div>
    </template>

    <ul v-if="rows.length" class="ellist" @pointerup="dragArmed = false">
      <li
        v-for="{ el, i } in rows"
        :key="el.id"
        :draggable="dragArmed"
        :class="{ sel: store.isSelected(el.id), primary: el.id === store.selectedId, grouped: !!el.groupId, dragover: overIdx === i && dragId && dragId !== el.id, dragging: dragId === el.id }"
        :style="el.groupId ? { '--gc': groupColor(el.groupId) } : {}"
        @click="rowClick($event, el.id)"
        @contextmenu.prevent="openMenu($event, el.id)"
        @dragstart="onDragStart($event, el.id)"
        @dragover.prevent="overIdx = i"
        @drop="onDrop(i)"
        @dragend="onDragEnd"
      >
        <i v-if="filter === 'all'" class="mdi mdi-drag-vertical handle" title="Drag to reorder" @pointerdown="dragArmed = true" @click.stop></i>
        <span class="typeicon"><i class="mdi" :class="labelIcon(el.label)"></i></span>
        <span class="idxchip" :style="{ background: el.boxColor }">{{ i + 1 }}</span>
        <i v-if="el.linkId" class="mdi mdi-link-variant link" :title="'Linked ×' + store.linkGroupSize(el.id)"></i>
        <span class="snip">{{ el.label === 'text' ? '“' + (el.text || '…') + '”' : (el.caption || el.label + '…') }}</span>
        <button class="more" title="Actions (or right-click the row)" @click.stop="openMenu($event, el.id)"><i class="mdi mdi-dots-horizontal"></i></button>
      </li>
    </ul>
    <p v-else-if="store.state.elements.length" class="empty">no {{ filter }} items</p>
    <p v-else class="empty">No items yet — draw a box on the canvas, or use + obj / + char / + text.</p>
  </UiCard>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useStudioStore } from '@/lib/store'
import { groupColor, type Label } from '@/lib/moss'
import UiCard from '../ui/UiCard.vue'
import UiButton from '../ui/UiButton.vue'
import UiPopover from '../ui/UiPopover.vue'
const store = useStudioStore()

const filter = ref<'all' | Label>('all')
// changing icon (not word) so the header width doesn't shift
const filterIcon = computed(() =>
  filter.value === 'object' ? 'mdi-vector-square' : filter.value === 'character' ? 'mdi-account-outline' : filter.value === 'text' ? 'mdi-format-text' : 'mdi-format-list-bulleted',
)
function labelIcon(label: Label): string {
  return label === 'text' ? 'mdi-format-text' : label === 'character' ? 'mdi-account-outline' : 'mdi-vector-square'
}
// map index before filtering to preserve each item's real index for #N / ops
const rows = computed(() =>
  store.state.elements
    .map((el, i) => ({ el, i }))
    .filter(({ el }) => filter.value === 'all' || el.label === filter.value),
)

// drag-to-reorder, only armed via the handle so plain clicks/buttons still work
const dragArmed = ref(false)
const dragId = ref<string | null>(null)
const overIdx = ref(-1)
function onDragStart(e: DragEvent, id: string) {
  dragId.value = id
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move'
}
function onDrop(i: number) {
  if (dragId.value) {
    store.moveElementTo(dragId.value, i)
    store.snapshot()
  }
}
function onDragEnd() {
  dragArmed.value = false
  dragId.value = null
  overIdx.value = -1
}

// keep a multi-selection if the row is part of it (bulk actions); else select just it
function openMenu(e: MouseEvent, id: string) {
  if (!store.isSelected(id)) store.select(id)
  store.openContextMenu(e.clientX, e.clientY, id)
}

function rowClick(e: MouseEvent, id: string) {
  if (e.shiftKey || e.ctrlKey || e.metaKey) {
    store.select(id, true)
    return
  }
  const el = store.getElement(id)
  if (el?.groupId) {
    // grouped: re-click the primary deselects; click another member re-targets it
    if (store.selectedId === id) store.select(null)
    else store.select(id)
    return
  }
  if (store.selectedIds.length === 1 && store.isSelected(id)) store.select(null)
  else store.select(id)
}
</script>

<style scoped>
.adds { display: flex; gap: 4px; }
.chead { display: flex; align-items: center; gap: 4px; }
.lhead { display: inline-flex; align-items: center; gap: 1px; background: none; border: none; cursor: pointer; font-size: 10px; font-weight: 700; letter-spacing: .5px; text-transform: uppercase; color: var(--st-muted); padding: 0; }
.lhead:hover { color: var(--st-text); }
.lhead .mdi { font-size: 15px; }
.lhead .flt { font-size: 13px; margin-right: 2px; }
.lmenu { display: flex; flex-direction: column; gap: 1px; min-width: 150px; }
.litem { display: flex; align-items: center; gap: 8px; text-align: left; background: none; border: none; color: var(--st-text); padding: 6px 8px; border-radius: 5px; font-size: 11px; cursor: pointer; }
.litem:hover { background: var(--st-btn); }
.litem.on { color: var(--st-accent); }
.litem .mdi { font-size: 15px; color: var(--st-muted); }
.litem.on .mdi { color: var(--st-accent); }
ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 3px; flex: 1 1 auto; min-height: 0; overflow-y: auto; }
li {
  position: relative;
  display: flex; align-items: center; gap: 6px; padding: 4px 6px; border-radius: 5px;
  background: var(--st-input); border: 1px solid transparent; cursor: pointer; font-size: 12px; color: var(--st-text);
  transition: opacity .12s, box-shadow .12s, background .12s;
}
li:hover { border-color: var(--st-border); }
li.sel { border-color: var(--st-accent); }
/* primary = the item the editor targets */
li.primary { border-color: var(--st-accent); background: color-mix(in srgb, var(--st-accent) 18%, var(--st-input)); }
li.primary .snip { font-weight: 600; }
/* per-group color sliver; absolute inside the existing padding so rows stay aligned */
li.grouped::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; border-radius: 5px 0 0 5px; background: var(--gc, var(--st-accent)); }
li.dragging { opacity: .35; }
li.dragover { box-shadow: inset 0 3px 0 -1px var(--st-accent); background: color-mix(in srgb, var(--st-accent) 12%, var(--st-input)); }
.handle { flex: none; color: var(--st-muted); cursor: grab; font-size: 14px; opacity: .3; margin: 0 -4px 0 -2px; transition: opacity .12s, color .12s; }
li:hover .handle { opacity: .85; }
.handle:hover { color: var(--st-accent); }
.handle:active { cursor: grabbing; }
.typeicon { flex: none; color: var(--st-muted); line-height: 1; display: inline-flex; }
.typeicon .mdi { font-size: 15px; }
.idxchip {
  flex: none; min-width: 17px; height: 16px; padding: 0 4px; box-sizing: border-box;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: 4px; background: var(--st-accent); color: #fff;
  font-size: 10px; font-weight: 700; font-variant-numeric: tabular-nums;
  text-shadow: 0 1px 1px rgba(0, 0, 0, .35);
}
.link { flex: none; font-size: 13px; color: var(--st-muted); }
.snip { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.more { display: inline-flex; align-items: center; justify-content: center; flex: none; background: none; border: none; color: var(--st-muted); border-radius: 4px; width: 20px; height: 20px; cursor: pointer; padding: 0; opacity: 0; transition: opacity .12s; }
.more .mdi { font-size: 16px; }
li:hover .more, li.sel .more { opacity: 1; }
.more:hover { color: var(--st-text); background: var(--st-btn); }
.empty { font-size: 11px; color: var(--st-muted); margin: 2px 0; }
</style>
