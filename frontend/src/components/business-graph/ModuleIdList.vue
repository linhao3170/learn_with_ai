<template>
  <div class="flex items-start gap-2 flex-wrap">
    <span class="text-[10px] text-gray-500 w-24 flex-shrink-0 pt-0.5">{{ label }}</span>
    <div v-if="rows.length" class="flex flex-wrap gap-1">
      <button
        v-for="row in rows"
        :key="row.id"
        type="button"
        class="text-[11px] px-1.5 py-0.5 rounded border transition-colors font-mono"
        :class="row.known
          ? 'bg-deep-card text-gray-300 border-deep-border hover:border-neon-blue/40 hover:text-white'
          : 'bg-deep-card text-gray-500 border-deep-border cursor-default'"
        :title="row.known ? '点击查看该模块的卡片' : '该 id 不在当前图谱里（不代填名字）'"
        :disabled="!row.known"
        @click="$emit('select', row.id)"
      >
        {{ row.label }}
      </button>
    </div>
    <span v-else class="text-[11px] text-gray-500">{{ emptyText }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

/**
 * 上游 / 下游模块 id 列表。
 * 契约里给的是 **id 数组**，这里按当前图谱把 id 解析成中文名；
 * 解析不到就原样显示 id 并标灰（诚实降级，不代填名字）。
 */
const props = defineProps({
  label: { type: String, default: '' },
  ids: { type: Array, default: () => [] },
  graph: { type: Object, default: null },
  emptyText: { type: String, default: '无' },
})

defineEmits(['select'])

const nameIndex = computed(() => {
  const map = new Map()
  const g = props.graph
  if (!g) return map
  ;(g.domains || []).forEach((d) => map.set(d.domain_id, d.name_cn || d.domain_id))
  ;(g.capabilities || []).forEach((c) => map.set(c.capability_id, c.name_cn || c.capability_id))
  return map
})

const rows = computed(() => {
  const list = Array.isArray(props.ids) ? props.ids.filter((x) => String(x ?? '').trim()) : []
  return list.map((id) => {
    const name = nameIndex.value.get(id)
    return { id, known: !!name, label: name ? `${name}` : id }
  })
})
</script>
