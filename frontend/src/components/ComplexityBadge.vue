<template>
  <div class="complexity-badge inline-block">
    <!-- 徽章本体：点开才是明细（README4 §五："显示级别徽章 + 点开显示七个维度的分项数值 + 公式 + 算法版本号"） -->
    <button
      type="button"
      data-test="complexity-badge"
      :data-level="missing ? 'unknown' : levelKey"
      class="flex items-center gap-2 px-2.5 py-1 rounded-lg border transition-all"
      :class="levelCls"
      :title="missing ? '该快照没有 complexity 字段' : '点击查看七维明细、公式、判定依据与 caveat'"
      @click="open = !open"
    >
      <span class="stat-number text-sm">{{ missing ? '—' : levelKey }}</span>
      <span class="text-[11px] font-medium">{{ levelLabel }}</span>
      <svg
        width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
        class="transition-transform" :class="{ 'rotate-180': open }"
      >
        <polyline points="6 9 12 15 18 9"></polyline>
      </svg>
    </button>

    <!-- 明细面板 -->
    <div v-if="open" class="glass-card mt-2 p-4 text-xs leading-relaxed" data-test="complexity-detail">
      <!-- 诚实降级：旧快照里没有 complexity 时，说清楚而不是编一个级别 -->
      <div v-if="missing" class="text-amber-400/90">
        该快照没有 <span class="font-mono">complexity</span> 字段（旧契约）。
        引擎无法给出级别与七维明细，这里不做任何推测。
        <span v-if="fallbackLevel" class="block mt-1 text-gray-400">
          只能读到图谱顶层字段 <span class="font-mono">level={{ fallbackLevel }}</span>，但没有依据与明细，不作为训练门槛使用。
        </span>
      </div>

      <template v-else>
        <div class="flex flex-wrap items-center gap-2 mb-2">
          <span class="text-white font-semibold">{{ levelKey }} · {{ c.level_label || '级别未命名' }}</span>
          <span v-if="c.algorithm_version" class="font-mono text-[10px] px-1.5 py-0.5 rounded bg-deep-card text-gray-400 border border-deep-border">
            {{ c.algorithm_version }}
          </span>
          <span v-if="num(c.raw) !== null" class="font-mono text-[10px] text-gray-400">
            辅助分 complexity_raw = {{ c.raw }}
          </span>
        </div>

        <p v-if="c.level_desc" class="text-gray-300 mb-3">{{ c.level_desc }}</p>

        <!-- 七维明细 -->
        <div class="mb-3">
          <div class="text-gray-500 mb-1.5">七维明细（结构信号，不是"AI 智能评估"）</div>
          <div class="grid grid-cols-2 gap-1.5">
            <div
              v-for="dim in dimensions"
              :key="dim.key"
              class="flex items-center justify-between px-2 py-1 rounded bg-deep-card border border-deep-border"
            >
              <span class="text-gray-400">{{ dim.label }}</span>
              <span class="font-mono text-white">
                {{ dim.value }}
                <span v-if="dim.weight !== null" class="text-gray-600">×{{ dim.weight }}</span>
              </span>
            </div>
          </div>
        </div>

        <!-- 定级依据：为什么是这个级别（README5 §13.4-④ 的教训：不能只给总分） -->
        <div v-if="levelBasis.length" class="mb-3">
          <div class="text-gray-500 mb-1">判定依据 level_basis</div>
          <ul class="space-y-1">
            <li v-for="(b, i) in levelBasis" :key="i" class="text-gray-300 flex gap-1.5">
              <span class="text-neon-blue">·</span><span>{{ b }}</span>
            </li>
          </ul>
        </div>

        <!-- 阈值表：四个级别的区间定义（顺带把"未校准"这件事摆在明面上） -->
        <div v-if="thresholds.length" class="mb-3">
          <div class="text-gray-500 mb-1">级别阈值 thresholds</div>
          <div class="space-y-1">
            <div
              v-for="t in thresholds"
              :key="t.level"
              class="flex items-center gap-2 px-2 py-1 rounded border"
              :class="t.level === levelKey ? 'border-neon-blue/40 bg-neon-blue/5' : 'border-deep-border bg-deep-card'"
            >
              <span class="font-mono text-white w-6">{{ t.level }}</span>
              <span class="text-gray-300 w-24 flex-shrink-0">{{ t.label || '—' }}</span>
              <span class="text-gray-500 flex-1">{{ t.desc || '' }}</span>
              <span v-if="t.max_domains !== undefined" class="font-mono text-gray-500">
                ≤{{ t.max_domains === null ? '∞' : t.max_domains }} 域
              </span>
            </div>
          </div>
        </div>

        <!-- 门限：L2/L3/L4 的最低结构条件 -->
        <div v-if="gateRows.length" class="mb-3">
          <div class="text-gray-500 mb-1">门限 gates（进入该级别的最低结构条件）</div>
          <div class="flex flex-wrap gap-1.5">
            <span
              v-for="g in gateRows"
              :key="g.key"
              class="px-1.5 py-0.5 rounded bg-deep-card border border-deep-border font-mono text-gray-400"
            >{{ g.key }} ≥ {{ g.value }}</span>
          </div>
        </div>

        <!-- 公式：必须显示，否则就是个不可信的总分 -->
        <div v-if="c.formula" class="mb-3">
          <div class="text-gray-500 mb-1">公式 formula</div>
          <div class="code-block p-2 text-[11px] text-gray-300 whitespace-pre-wrap break-all">{{ c.formula }}</div>
        </div>

        <!-- 训练任务类型：级别决定训练门槛（README4 §五"项目大小必须决定训练门槛"） -->
        <div v-if="taskTypes.length" class="mb-3">
          <div class="text-gray-500 mb-1">该级别对应的训练任务类型</div>
          <div class="flex flex-wrap gap-1.5">
            <span
              v-for="t in taskTypes"
              :key="t"
              class="px-1.5 py-0.5 rounded bg-neon-purple/10 text-neon-purple border border-neon-purple/20 font-mono"
            >{{ t }}</span>
          </div>
        </div>

        <!--
          caveat 必须**原样**显示（README5 §3.3 纪律："阈值必须标待校准，不许包装成 AI 智能评估"）。
          这里刻意不做任何改写、不截断。
        -->
        <div v-if="c.caveat" data-test="complexity-caveat" class="p-2 rounded bg-amber-500/5 border border-amber-500/30 text-amber-300/90">
          <span class="font-semibold">caveat（引擎原文）：</span>{{ c.caveat }}
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
/**
 * 复杂度徽章 L1–L4（README4 §五 / README5 §3.3）
 * =============================================
 * 三个硬要求：
 *   1. 徽章显示级别 + 中文标签；
 *   2. 点开显示**七维分项数值 + 公式 + 算法版本号 + 判定依据 + 门限**（只给总分就是不可信的总分）；
 *   3. caveat 原样显示 —— 阈值未经校准这件事必须让教师看见。
 * 另外：`complexity` 字段缺失（旧快照）时显示"无复杂度数据"，绝不崩、也绝不编一个级别。
 */
import { computed, ref } from 'vue'
import { COMPLEXITY_DIMENSIONS } from '../utils/businessGraph'

const props = defineProps({
  /** business_graph.complexity（可能整体缺失） */
  complexity: {
    type: Object,
    default: null,
  },
  /** 图谱顶层 level：只作为"没有 complexity 时"的兜底展示，不当作级别结论 */
  fallbackLevel: {
    type: String,
    default: '',
  },
})

const open = ref(false)

const c = computed(() => props.complexity || {})
const missing = computed(() => !props.complexity || !props.complexity.level)
const levelKey = computed(() => String(c.value.level || props.fallbackLevel || '').trim() || 'N/A')
const levelLabel = computed(() => c.value.level_label || (missing.value ? '无复杂度数据' : '级别未命名'))

const LEVEL_CLS = {
  L1: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30 hover:border-emerald-400/60',
  L2: 'bg-neon-blue/10 text-neon-blue border-neon-blue/30 hover:border-neon-blue/60',
  L3: 'bg-neon-purple/10 text-neon-purple border-neon-purple/30 hover:border-neon-purple/60',
  L4: 'bg-neon-pink/10 text-neon-pink border-neon-pink/30 hover:border-neon-pink/60',
}
const levelCls = computed(() =>
  missing.value
    ? 'bg-deep-card text-gray-400 border-deep-border hover:border-gray-500'
    : (LEVEL_CLS[levelKey.value] || 'bg-deep-card text-gray-300 border-deep-border hover:border-gray-500'))

function num(v) {
  return Number.isFinite(Number(v)) && v !== null && v !== '' ? Number(v) : null
}

/** 七维：值 + 权重都显示（权重来自契约，不写死）。 */
const dimensions = computed(() => {
  const breakdown = c.value.breakdown || {}
  const weights = c.value.weights || {}
  const rows = COMPLEXITY_DIMENSIONS.filter((d) => d.key in breakdown)
  // 契约里万一多给了维度，也不吞掉（README5 §9.1：换一份项目数据前端不改代码即可正确渲染）
  const extra = Object.keys(breakdown)
    .filter((k) => !COMPLEXITY_DIMENSIONS.some((d) => d.key === k))
    .map((k) => ({ key: k, label: k }))
  return [...rows, ...extra].map((d) => ({
    ...d,
    value: breakdown[d.key] ?? '—',
    weight: num(weights[d.key]),
  }))
})

const levelBasis = computed(() => (Array.isArray(c.value.level_basis) ? c.value.level_basis : []))
const thresholds = computed(() => (Array.isArray(c.value.thresholds) ? c.value.thresholds : []))
const taskTypes = computed(() => (Array.isArray(c.value.training_task_types) ? c.value.training_task_types : []))

const gateRows = computed(() => {
  const gates = c.value.gates || {}
  return Object.keys(gates).map((k) => ({ key: k, value: gates[k] }))
})
</script>
