<template>
  <UiCard v-if="el">
    <template #header>
      <div class="ehead">
        <!-- index chip doubles as the color picker -->
        <label class="idchip" :title="'Item ' + (index + 1) + (linked ? ' · linked ×' + groupSize : '') + ' — click to recolour'">
          <span class="n" :style="{ background: el.boxColor }">{{ index + 1 }}</span>
          <input type="color" :value="el.boxColor" @input="setShared('boxColor', ($event.target as HTMLInputElement).value)" />
        </label>
        <div class="seg">
          <UiButton icon :active="el.label === 'object'" title="Object" @click="setShared('label', 'object')"><i class="mdi mdi-vector-square"></i></UiButton>
          <UiButton icon :active="el.label === 'character'" title="Character" @click="setShared('label', 'character')"><i class="mdi mdi-account-outline"></i></UiButton>
          <UiButton icon :active="el.label === 'text'" title="Text" @click="setShared('label', 'text')"><i class="mdi mdi-format-text"></i></UiButton>
        </div>
        <span class="grow"></span>
        <UiButton icon title="Linked copy — shares content, keeps its own position" @click="store.duplicateLinked(el.id)"><i class="mdi mdi-link-variant-plus"></i></UiButton>
        <UiButton v-if="linked" icon :title="'Unlink from group (×' + groupSize + ')'" @click="store.unlink(el.id)"><i class="mdi mdi-link-variant-off"></i></UiButton>
      </div>
    </template>

    <label v-if="el.label === 'text'" class="filine">
      <span>text</span>
      <input :value="el.text" type="text" placeholder="exact visible characters (line breaks via \n)"
        @input="setShared('text', ($event.target as HTMLInputElement).value)" />
    </label>
    <label class="filine">
      <span>caption</span>
      <textarea :value="el.caption" rows="2" :placeholder="el.label === 'text' ? 'typography and surface treatment of this text' : 'visible appearance of this ' + el.label"
        @input="setShared('caption', ($event.target as HTMLTextAreaElement).value)"></textarea>
    </label>
    <div class="filine">
      <span>tags</span>
      <ComboInput v-model="sharedTags" :options="opts" placeholder="optional visual tags, comma-separated" />
    </div>
    <!-- div, not label: a label would route clicks to the first color input -->
    <div class="filine">
      <span>colours</span>
      <PaletteEditor :modelValue="el.palette" :max="8" label="item colours"
        @update:modelValue="setShared('palette', $event)" />
    </div>
  </UiCard>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useStudioStore, SHARED_KEYS } from '@/lib/store'
import UiCard from '../ui/UiCard.vue'
import UiButton from '../ui/UiButton.vue'
import PaletteEditor from './PaletteEditor.vue'
import ComboInput from './ComboInput.vue'
import { PRESETS } from '@/lib/presets'

const store = useStudioStore()
const el = computed(() => store.getElement(store.selectedId))
const index = computed(() => store.state.elements.findIndex((e) => e.id === store.selectedId))
const linked = computed(() => !!el.value?.linkId)
const groupSize = computed(() => (el.value ? store.linkGroupSize(el.value.id) : 1))
const opts = computed(() => (store.state.ui.showPresets ? PRESETS.tags : []))

// tags edit via ComboInput (comma-separated string input); keep it shared like the rest
const sharedTags = computed({
  get: () => (el.value ? el.value.tags.join(', ') : ''),
  set: (v: string) => {
    if (el.value) store.setShared(el.value.id, 'tags', v.split(',').map((s) => s.trim()).filter(Boolean))
  },
})

function setShared(key: (typeof SHARED_KEYS)[number], value: unknown) {
  if (el.value) store.setShared(el.value.id, key, value)
}
</script>

<style scoped>
.ehead { display: flex; align-items: center; gap: 6px; width: 100%; flex-wrap: wrap; }
.grow { flex: 1 1 auto; }
/* overflow:hidden clips the absolute color input to the chip so it can't overlap the type buttons */
.idchip { position: relative; display: inline-flex; flex: none; cursor: pointer; overflow: hidden; border-radius: 5px; }
.idchip .n {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 22px; height: 22px; padding: 0 6px; box-sizing: border-box;
  border-radius: 5px; color: #fff; font-size: 11px; font-weight: 700;
  font-variant-numeric: tabular-nums; text-shadow: 0 1px 1px rgba(0, 0, 0, .35);
  border: 1px solid rgba(0, 0, 0, .25);
}
.idchip input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.seg { display: flex; gap: 2px; }

.filine { display: flex; gap: 8px; align-items: flex-start; font-size: 11px; color: var(--st-muted); }
.filine > span { width: 44px; flex: none; padding-top: 5px; text-align: right; }
.filine input[type='text'], .filine textarea {
  flex: 1; background: var(--st-input); border: 1px solid var(--st-border); color: var(--st-text);
  border-radius: 5px; padding: 6px; font-size: 12px; resize: vertical; font-family: inherit;
}
.filine :deep(.palette) { flex: 1; }
</style>
