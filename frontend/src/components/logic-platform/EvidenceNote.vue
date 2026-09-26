<template>
  <div
    class="rounded-lg border border-deep-border bg-deep-card/40"
    :data-test="testId"
    :data-open="String(open)"
  >
    <!-- 常驻摘要：一句话说清"这些证据能证明什么、不能证明什么" -->
    <div class="flex items-start gap-2 px-3 py-2">
      <svg
        width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
        class="text-neon-blue/70 flex-shrink-0 mt-0.5"
      >
        <circle cx="12" cy="12" r="9"></circle><path d="M12 8h.01"></path><path d="M11 12h1v4h1"></path>
      </svg>
      <p class="text-[11px] text-gray-400 leading-relaxed flex-1 min-w-0" :data-test="`${testId}-summary`">
        {{ summary }}
      </p>
      <button
        type="button"
        class="flex items-center gap-1.5 flex-shrink-0 text-gray-500 hover:text-gray-300 transition-colors"
        :aria-expanded="String(open)"
        :data-test="`${testId}-toggle`"
        @click="open = !open"
      >
        <span class="text-[10px] font-mono">{{ open ? '收起说明' : label }}</span>
        <svg
          class="drawer-chevron" :class="{ open }"
          width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"
        >
          <polyline points="9 18 15 12 9 6"></polyline>
        </svg>
      </button>
    </div>

    <!-- 完整说明：默认收起，**一条不删** -->
    <div class="drawer-body" :class="{ open }" :data-test="`${testId}-body`">
      <div class="drawer-inner">
        <ul class="px-3 pb-2.5 space-y-1">
          <li
            v-for="(line, index) in lines"
            :key="index"
            class="drawer-row text-[11px] text-gray-500 leading-relaxed flex gap-2"
            :style="{ '--i': index }"
          >
            <span class="text-gray-600 flex-shrink-0">·</span>
            <span class="min-w-0">{{ line }}</span>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 证据口径说明 EvidenceNote
 * ==========================
 * 为什么需要它：这一屏上面摆着一堆 `文件:行号`，而**引用成立 ≠ 解释正确**。
 * 不说清这条界线，读的人就会把"机械复核通过"读成"业务解释也是对的"——
 * 那正是这个项目最不能犯的错（`docs/09-discipline-and-defense.md` §13 的措辞纪律）。
 *
 * 形态是**摘要常驻 + 详述收起**：
 * - **摘要常驻**（一句话）：读完就记住"证据只证明引用存在"，不需要点任何东西；
 * - **详述收起**：把"机器检查了什么 / 检查不到什么 / 还剩哪些幻觉风险 / 怎么核"摊开写清，
 *   但它不该抢主内容的视线 —— 与主页面「来源依据与口径」是同一个形态、同一套 CSS 抽屉。
 *
 * 它刻意不做的事
 * --------------
 * - **不写一句没有代码支撑的话**：这里的每一条都对应 `engine/logic_platform/verify.py`
 *   的实际检查项与 `engine/logic_platform/narration.py` 的实际把关规则；
 * - **不用"请放心""已确保"这类词**：平台的可信度靠把边界写出来，不靠形容词；
 * - **不隐藏详述内容**：收起用的是 `.drawer-body`（高度归零），文本仍在 DOM 里。
 */
import { ref } from 'vue'

defineProps({
  /** 常驻摘要（一句话，必须自己站得住）。 */
  summary: { type: String, required: true },
  /** 完整说明的条目（收起在抽屉里）。 */
  lines: { type: Array, default: () => [] },
  /** 抽屉按钮文案。 */
  label: { type: String, default: '完整说明' },
  /** 走查与测试钩子（根 `data-test`，另有 `-summary` / `-toggle` / `-body`）。 */
  testId: { type: String, default: 'evidence-note' },
})

/** 默认收起：它是口径，不是主内容。 */
const open = ref(false)
</script>
