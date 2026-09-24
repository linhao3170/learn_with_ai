<template>
  <div class="flex items-start gap-2 flex-wrap">
    <span class="text-[10px] text-gray-500 w-8 flex-shrink-0 pt-0.5">{{ label }}</span>
    <div v-if="list.length" class="flex flex-wrap gap-1">
      <span
        v-for="item in list"
        :key="item"
        class="text-[11px] px-1.5 py-0.5 rounded font-mono border"
        :class="toneCls"
      >{{ item }}</span>
    </div>
    <span v-else class="text-[11px] text-gray-500">{{ emptyText }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

/**
 * 字段名的胶囊列表（模块卡片的 inputs / outputs 用）。
 * `inputs`/`outputs` 在契约里是**字符串数组**（状态字段名），不是对象数组。
 */
const props = defineProps({
  label: { type: String, default: '' },
  items: { type: Array, default: () => [] },
  emptyText: { type: String, default: '未识别' },
  tone: { type: String, default: 'blue' }, // blue | purple
})

const list = computed(() => (Array.isArray(props.items) ? props.items.filter((x) => String(x ?? '').trim()) : []))

const toneCls = computed(() =>
  props.tone === 'purple'
    ? 'bg-neon-purple/10 text-neon-purple/90 border-neon-purple/20'
    : 'bg-neon-blue/10 text-neon-blue/90 border-neon-blue/20')
</script>
