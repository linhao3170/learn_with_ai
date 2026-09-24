<template>
  <span
    class="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded border font-medium whitespace-nowrap leading-none"
    :class="meta.cls"
    data-test="confidence-badge"
    :data-confidence="normalized"
    :title="meta.title"
  >
    <span class="w-1.5 h-1.5 rounded-full flex-shrink-0" :class="meta.dot"></span>
    {{ meta.label }}
    <span v-if="showRaw" class="font-mono opacity-60">{{ normalized }}</span>
  </span>
</template>

<script setup>
/**
 * 置信度徽章（README4 §2.1 铁律 / README5 §10.3 红线 #4）
 * =====================================================
 * 任何一条结论都必须带三档置信度之一（本项目实测还出现了第四档 `inferred-low`）。
 * 这个徽章是"不许把未审核的推断展示为已确认事实"的唯一落点：
 * 凡是渲染域 / 功能点 / 模块卡片 / 事实链的地方，都要把它带上。
 *
 * 注意：<template> 里不写 HTML 注释 —— Vue 会把模板注释编译成 comment vnode 渲染进 DOM。
 */
import { computed } from 'vue'
import { confidenceMeta, normalizeConfidence } from '../utils/businessGraph'

const props = defineProps({
  /** 契约里的 confidence 原始值：verified | inferred | inferred-low | unconfirmed */
  value: {
    type: String,
    default: '',
  },
  /** 是否额外显示原始英文档位（教师排查用；默认只显示中文标签） */
  showRaw: {
    type: Boolean,
    default: false,
  },
})

const normalized = computed(() => normalizeConfidence(props.value))
const meta = computed(() => confidenceMeta(props.value))
</script>
