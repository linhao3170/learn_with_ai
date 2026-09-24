<template>
  <!--
    口径与边界（折叠）。
    为什么默认折叠而不是默认展开：这些句子是后端逐条给的中文边界声明，
    在分析 / 看板 / 板块 / 校验四处都会出现，全展开会把正文淹掉。
    但"折叠"绝不等于"可以丢"—— 入口上直接写清有几条，让评审一眼看得见这里有东西。
    没有 caveat 时**不渲染空壳**（空壳会被读成"后端保证了没有边界"，而事实是这份载荷没给）。
  -->
  <details
    v-if="lines.length"
    class="border border-deep-border rounded-xl bg-deep-card/40"
    :data-test="testId"
    :data-count="lines.length"
  >
    <summary class="px-4 py-2.5 text-xs text-gray-400 cursor-pointer hover:text-gray-200 select-none">
      {{ title }}（{{ lines.length }} 条，后端原文，不是免责声明）
      <span v-if="desc" class="text-gray-600">· {{ desc }}</span>
    </summary>
    <ul class="px-4 pb-3 space-y-1.5">
      <li
        v-for="(line, index) in lines"
        :key="index"
        class="text-[11.5px] text-gray-500 leading-relaxed flex gap-2"
        data-test="logic-caveat-item"
      >
        <span class="text-gray-600 flex-shrink-0">·</span>
        <span>{{ line }}</span>
      </li>
    </ul>
  </details>
</template>

<script setup>
/**
 * 口径与边界面板（逻辑平台通用小组件）
 * ======================================
 * 为什么单独抽一个组件：`size.caveats` / `sections.caveats` / `lesson.caveats` /
 * `verification.caveats` 是**四份不同来源**的中文边界声明，展示方式必须一致 ——
 * 否则学生在"大小页"看到边界、在"讲稿页"看不到，就会误以为讲稿那部分没有边界。
 *
 * 它刻意不做的事：
 *   1. **不改写、不截断、不"翻译"**任何一条 caveat（引擎原文就是证据）；
 *   2. 没有 caveat 时**不渲染空壳**（空壳会被读成"没有边界"，那是另一回事）。
 */
import { computed } from 'vue'

const props = defineProps({
  /** caveat 文本数组（后端原文；缺失/非数组一律当空处理） */
  items: {
    type: Array,
    default: () => [],
  },
  /** 折叠标题 */
  title: {
    type: String,
    default: '口径与边界',
  },
  /** 标题后面的补充说明（可选，例如"来自 size 载荷"） */
  desc: {
    type: String,
    default: '',
  },
  /** data-test 值：同一个页面可能出现多个面板，用不同的值区分断言目标 */
  testId: {
    type: String,
    default: 'logic-caveats',
  },
})

/** 只做"去空 + 去重"，不做任何内容加工（顺序即后端给的顺序）。 */
const lines = computed(() => {
  const out = []
  for (const item of Array.isArray(props.items) ? props.items : []) {
    const text = String(item ?? '').trim()
    if (text && !out.includes(text)) out.push(text)
  }
  return out
})
</script>
