<template>
  <div class="relative" data-test="quick-search">
    <div class="quick-search-box">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-gray-500 flex-shrink-0"><circle cx="11" cy="11" r="7"></circle><path d="m20 20-4-4"></path></svg>
      <input v-model="query" class="quick-search-input" placeholder="搜索页面、训练阶段或业务模块…" aria-label="搜索页面、训练阶段或业务模块" @focus="focused = true" @keydown.esc="focused = false" @keydown.enter="selectFirst" />
      <kbd class="hidden sm:inline-flex">/</kbd>
    </div>
    <div v-if="focused && (query || filteredItems.length)" class="quick-search-results" data-test="quick-search-results">
      <button v-for="item in filteredItems" :key="item.key" class="quick-search-result" :data-kind="item.kind" @mousedown.prevent="select(item)">
        <span class="quick-search-icon">{{ item.icon || '↗' }}</span>
        <span class="min-w-0 flex-1 text-left"><span class="block text-sm text-gray-200 truncate">{{ item.label }}</span><span class="block text-[10px] text-gray-500 truncate">{{ item.description }}</span></span>
        <span class="text-[10px] text-gray-600 font-mono">{{ item.group }}</span>
      </button>
      <div v-if="!filteredItems.length" class="px-4 py-5 text-xs text-gray-500">没有找到匹配入口</div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({ items: { type: Array, default: () => [] } })
const emit = defineEmits(['select'])
const query = ref('')
const focused = ref(false)
const filteredItems = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return props.items.slice(0, 8)
  return props.items.filter((item) => [item.label, item.description, item.group].join(' ').toLowerCase().includes(q)).slice(0, 10)
})
function select(item) { emit('select', item); query.value = ''; focused.value = false }
function selectFirst() { if (filteredItems.value[0]) select(filteredItems.value[0]) }
function onGlobalKeydown(event) {
  if (event.key === '/' && !['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) { event.preventDefault(); document.querySelector('[data-test="quick-search"] input')?.focus() }
}
onMounted(() => document.addEventListener('keydown', onGlobalKeydown))
onBeforeUnmount(() => document.removeEventListener('keydown', onGlobalKeydown))
</script>

