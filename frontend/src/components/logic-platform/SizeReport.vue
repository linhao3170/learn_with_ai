<template>
  <section class="space-y-5" data-test="logic-size">
    <!-- 失败 / 加载：不静默渲染空白 -->
    <div v-if="loading" class="glass-card p-10 text-center text-sm text-gray-400" data-test="logic-size-loading">
      正在分析项目大小…
    </div>
    <div v-else-if="error" class="glass-card p-10 text-center" data-test="logic-size-error">
      <div class="text-red-400 text-sm mb-2">大小分析不可用</div>
      <div class="text-xs text-gray-500 font-mono break-all">{{ error }}</div>
      <p class="text-xs text-gray-500 mt-3 leading-relaxed max-w-xl mx-auto">
        定级与分流策略都在后端计算（AST 解析 → 业务图谱 → 预算裁剪）。
        这里不做任何推测，也不显示一个凑出来的级别。
      </p>
    </div>

    <template v-else-if="size">
      <!-- ===================================================================
           A. 项目到底多大
           =================================================================== -->
      <header class="glass-card p-6 neon-border" data-test="logic-size-header">
        <div class="flex items-start justify-between gap-4 flex-wrap">
          <div class="min-w-0">
            <div class="text-xs text-gray-500 font-mono tracking-widest uppercase mb-1">Step 2 · Size</div>
            <h2 class="text-lg font-bold text-white">分析项目大小</h2>
            <div class="text-[11px] text-gray-500 font-mono mt-1 space-x-2">
              <span>{{ size.project_id }}</span>
              <span v-if="size.algorithm_version" class="text-gray-600">· {{ size.algorithm_version }}</span>
              <span v-if="size.source_hash" class="text-gray-600" :title="size.source_hash">
                · 源码哈希 {{ shortHash }}
              </span>
            </div>
          </div>
          <div class="text-right shrink-0" data-test="logic-size-badge">
            <!-- 复用既有的复杂度徽章（七维明细 / 公式 / 阈值 / caveat 都在它里面） -->
            <ComplexityBadge
              v-if="levelKnown"
              :complexity="size.complexity"
              :fallback-level="size.level"
            />
          </div>
        </div>

        <!--
          级别判不出来时**不显示级别**。
          `level_known === false` 是引擎在说"我没算出来"，这时候给一个数字/字母，
          不管标得多小，都会被当成结论读走。
        -->
        <div
          v-if="!levelKnown"
          class="mt-4 rounded-xl border border-amber-500/40 bg-amber-500/5 px-4 py-3"
          data-test="logic-size-level-unknown"
        >
          <div class="text-xs font-semibold text-amber-300">本项目本次<b>没有定级结果</b>（level_known = false）</div>
          <p class="text-[11px] text-amber-200/80 mt-1 leading-relaxed">
            定级需要业务图谱的七维结构信号；本次没算出来，所以这里<b>不显示任何级别</b>。
            下一条只列出引擎给出的原始依据，请按"未定级"对待。
          </p>
          <div v-if="size.level_desc" class="text-[11px] text-gray-400 mt-2">{{ size.level_desc }}</div>
        </div>
        <div v-else class="mt-4" data-test="logic-size-level">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-sm font-semibold text-white">{{ size.level }}</span>
            <span class="text-xs text-gray-300">{{ size.level_label || '级别未命名' }}</span>
          </div>
          <p v-if="size.level_desc" class="text-[11.5px] text-gray-400 mt-1 leading-relaxed">{{ size.level_desc }}</p>
        </div>

        <!-- 定级依据（为什么是这个级别） -->
        <div v-if="levelBasis.length" class="mt-4" data-test="logic-level-basis">
          <div class="text-[11px] text-gray-500 mb-1.5">定级依据 level_basis（引擎原文）</div>
          <ul class="space-y-1">
            <li v-for="(line, i) in levelBasis" :key="i" class="text-[11.5px] text-gray-300 leading-relaxed flex gap-2">
              <span class="text-neon-blue flex-shrink-0">·</span><span>{{ line }}</span>
            </li>
          </ul>
        </div>

        <!-- 业务图谱失败：这是"板块看不了"的根因，必须显式说，而且要带后端原文 -->
        <div
          v-if="size.graph_status === 'failed'"
          class="mt-4 rounded-xl border border-red-500/40 bg-red-500/5 px-4 py-3"
          data-test="logic-graph-failed"
        >
          <div class="text-xs font-semibold text-red-300">业务图谱构建失败（graph_status = failed）</div>
          <p class="text-[11px] text-red-200/80 mt-1 leading-relaxed">
            AST 层的数字（文件数 / 行数 / 类 / 函数）仍然可复现、可以照常看；
            但<b>业务板块、能力点与沉浸式讲稿都依赖图谱</b>，本次给不出来。
            下面表格里标着 <span class="font-mono">business_graph</span> 的那些行因此不是"零"，而是<b>没有值</b>。
          </p>
          <div v-if="size.graph_error" class="text-[11px] text-red-200/70 font-mono mt-2 break-all">{{ size.graph_error }}</div>
        </div>
      </header>

      <!-- ===================================================================
           B. 结构数字（每一行都带来源，这是这一屏的证据纪律）
           =================================================================== -->
      <section class="glass-card p-6" data-test="logic-structure">
        <div class="flex items-center gap-2 mb-3 flex-wrap">
          <span class="text-sm font-semibold text-white">结构数字与它们的来源</span>
          <span class="text-[11px] text-gray-500">
            同一个数字来自 AST 还是来自图谱推断，可靠性不一样，所以<b>必须分行标注</b>
          </span>
        </div>

        <div v-if="!rows.length" class="text-xs text-gray-500 py-4" data-test="logic-structure-empty">
          这份载荷没有 <span class="font-mono">structure_rows</span>（旧契约）—— 如实说明，不在这里补一套统计。
        </div>

        <div v-else class="overflow-x-auto border border-deep-border rounded-xl">
          <table class="w-full text-[12px]" data-test="logic-structure-table">
            <thead class="bg-deep-surface/60">
              <tr>
                <th class="text-left px-3 py-2 text-gray-400 font-medium whitespace-nowrap">指标</th>
                <th class="text-right px-3 py-2 text-gray-400 font-medium whitespace-nowrap">数值</th>
                <th class="text-left px-3 py-2 text-gray-400 font-medium whitespace-nowrap">来源</th>
                <th class="text-left px-3 py-2 text-gray-400 font-medium">口径说明（引擎原文）</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in rows"
                :key="row.key"
                class="border-t border-deep-border/60 align-top"
                data-test="logic-structure-row"
                :data-row-key="row.key"
                :data-source="row.source"
              >
                <td class="px-3 py-2 text-gray-200 whitespace-nowrap">
                  {{ row.label || row.key }}
                  <span class="text-[10px] text-gray-600 font-mono block">{{ row.key }}</span>
                </td>
                <td class="px-3 py-2 text-right font-mono text-white whitespace-nowrap">
                  {{ row.value }}<span v-if="row.unit" class="text-gray-500 ml-0.5">{{ row.unit }}</span>
                </td>
                <td class="px-3 py-2 whitespace-nowrap">
                  <span
                    class="text-[10px] px-1.5 py-0.5 rounded border font-medium"
                    :class="sourceOf(row.source).cls"
                    :title="sourceOf(row.source).title"
                    data-test="logic-structure-source"
                    :data-source="row.source || ''"
                  >{{ sourceOf(row.source).label }}</span>
                </td>
                <td class="px-3 py-2 text-gray-500 leading-relaxed">
                  {{ row.note || '（引擎未给这一行的口径说明）' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 规模判据（为什么说它"大"） -->
        <div v-if="sizeBasis.length" class="mt-4" data-test="logic-size-basis">
          <div class="text-[11px] text-gray-500 mb-1.5">规模判据 size_basis（引擎原文）</div>
          <ul class="space-y-1">
            <li v-for="(line, i) in sizeBasis" :key="i" class="text-[11.5px] text-gray-300 leading-relaxed flex gap-2">
              <span class="text-neon-purple flex-shrink-0">·</span><span>{{ line }}</span>
            </li>
          </ul>
        </div>
      </section>

      <!-- ===================================================================
           C. 按大小分流：这个规模会得到什么处理
           =================================================================== -->
      <section v-if="tier" class="glass-card p-6" data-test="logic-tier">
        <div class="flex items-center gap-2 mb-1 flex-wrap">
          <span class="text-xs text-gray-500 font-mono tracking-widest uppercase">Step 3 · Tiered strategy</span>
        </div>
        <div class="flex items-center gap-2 mb-3 flex-wrap">
          <span class="text-sm font-semibold text-white">按大小分流：这个规模会得到什么处理</span>
          <span class="text-[10px] px-1.5 py-0.5 rounded border bg-neon-purple/10 text-neon-purple border-neon-purple/30">
            {{ tier.tier_label || '策略未命名' }}
          </span>
          <span v-if="tier.algorithm_version" class="text-[10px] text-gray-600 font-mono">{{ tier.algorithm_version }}</span>
          <span
            v-if="!tier.level_known"
            class="text-[10px] px-1.5 py-0.5 rounded border bg-amber-500/10 text-amber-400 border-amber-500/30"
            data-test="logic-tier-unknown-level"
          >
            级别未知，按最保守策略处理
          </span>
        </div>

        <!-- 级别未知时的回退说明：说清"用的是哪一档"，而不是让人以为这就是本项目的级别 -->
        <div v-if="!tier.level_known" class="mb-3 rounded-xl border border-dashed border-amber-500/40 bg-amber-500/5 px-4 py-2.5 text-[11px] text-amber-200/85 leading-relaxed">
          {{ tier.level ? '' : '本项目本次没有定级结果，' }}此处采用的是<b>回退档
          <span class="font-mono">{{ tier.fallback_level || 'L1' }}</span></b> 的预算。
          回退档只影响"讲多少"（板块数 / 课程数 / 段行上限），<b>不影响事实判定</b> ——
          事实永远来自 AST，与项目大小无关。
        </div>

        <p v-if="tier.rationale" class="text-[11.5px] text-gray-300 leading-relaxed mb-2" data-test="logic-tier-rationale">
          {{ tier.rationale }}
        </p>
        <p v-if="tier.student_note" class="text-[11.5px] text-neon-blue/90 leading-relaxed mb-4" data-test="logic-tier-student-note">
          {{ tier.student_note }}
        </p>

        <!-- 三个预算：全部来自契约，`null` 一律显示"不限"，不换算成一个大数字 -->
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3" data-test="logic-tier-budgets">
          <div
            v-for="budget in budgetCards"
            :key="budget.key"
            class="rounded-xl border border-deep-border bg-deep-card/40 px-4 py-3"
            data-test="logic-tier-budget"
            :data-budget-key="budget.key"
            :data-budget-value="budget.raw === null || budget.raw === undefined ? 'unlimited' : String(budget.raw)"
          >
            <div class="text-[10px] text-gray-500">{{ budget.label }}</div>
            <div class="text-lg stat-number text-white mt-1">{{ budget.display }}</div>
            <div class="text-[10px] text-gray-500 mt-1 leading-relaxed">{{ budget.note }}</div>
          </div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-3">
          <div class="rounded-xl border border-deep-border bg-deep-card/40 px-4 py-3">
            <div class="text-[10px] text-gray-500">单课最多几段（母本上限 9 段的余量）</div>
            <div class="text-lg stat-number text-white mt-1">{{ numOrDash(tier.segments_per_lesson_cap) }}</div>
          </div>
          <div class="rounded-xl border border-deep-border bg-deep-card/40 px-4 py-3">
            <div class="text-[10px] text-gray-500">单段最多几行源码</div>
            <div class="text-lg stat-number text-white mt-1">{{ numOrDash(tier.statements_per_segment_cap) }}</div>
          </div>
          <div class="rounded-xl border border-deep-border bg-deep-card/40 px-4 py-3">
            <div class="text-[10px] text-gray-500">板块分析展开程度</div>
            <div class="text-sm text-white mt-1.5">{{ depthMeta.label }}</div>
            <div class="text-[10px] text-gray-600 font-mono">{{ tier.analysis_depth || '未标注' }}</div>
          </div>
        </div>

        <div class="mt-3 text-[11px] text-gray-500" data-test="logic-tier-selection">
          课程挑选方式：<span class="text-gray-300">{{ selectionMeta.label }}</span>
          <span class="text-gray-600 font-mono ml-1">{{ tier.walkthrough_selection || '未标注' }}</span>
        </div>

        <!-- 预算表的 caveat：口径必须原样带出来（这份数字是工程常数，不是学出来的） -->
        <div
          v-if="tier.caveat"
          class="mt-3 rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-2.5 text-[11px] text-amber-200/85 leading-relaxed"
          data-test="logic-tier-caveat"
        >
          <span class="font-semibold">tier.caveat（引擎原文）：</span>{{ tier.caveat }}
        </div>
      </section>

      <!-- ===================================================================
           D. 口径与边界（可折叠，但绝不丢）
           =================================================================== -->
      <CaveatsPanel :items="size.caveats" test-id="logic-size-caveats" desc="来自 size 载荷" />

      <!-- 进入下一步 -->
      <div class="flex items-center gap-3 flex-wrap">
        <button
          type="button"
          class="px-6 py-2.5 rounded-xl text-sm font-medium text-white transition-all
                 bg-gradient-to-r from-neon-blue to-neon-purple hover:-translate-y-0.5"
          data-test="logic-to-sections"
          @click="$emit('next')"
        >
          继续看业务板块看板 →
        </button>
        <button
          type="button"
          class="px-4 py-2.5 rounded-xl text-xs border border-deep-border text-gray-400 hover:text-white hover:border-neon-blue/40 transition-all"
          data-test="logic-reanalyze"
          :disabled="loading"
          @click="$emit('reload')"
        >
          让后端重算一次（force）
        </button>
        <span class="text-[11px] text-gray-500">
          分流只决定"讲多少"：板块数、课程数、每课段数上限。<b>它不参与任何事实判定</b>。
        </span>
      </div>
    </template>
  </section>
</template>

<script setup>
/**
 * 分析项目大小（Step 2 / Step 3 合屏）
 * ====================================
 * 这一屏要同时回答两个问题：
 *   「这个项目多大？」（size）与「这个大小会得到什么处理？」（tier 分流策略）。
 * 两者是同一个决定的两面（README §12 的"小项目不能生成过重的训练，
 * 复杂项目也不能只给四道题"），拆成两屏反而会让人以为它们是独立的。
 *
 * 四条不可让的纪律（都直接来自这个项目的诚实文化）
 * -------------------------------------------------
 * 1. **level_known === false 就不显示级别**。定级依据照常列出，但一个字母都不给 ——
 *    任何"暂定为 L2"的说法都会被读成结论。
 * 2. **每个结构数字都带来源列**。同一个数字来自 `ast`（解析器直出、可复现）
 *    还是 `business_graph`（聚类推断、需教师确认），可靠性不一样，
 *    长得一样就是在暗示它们一样可靠。
 * 3. **图谱失败时不说"0"**。`graph_status === 'failed'` 表示那些数字是**没有值**，
 *    不是零；同时把 `graph_error` 原文摆出来。
 * 4. **tier.caveat 原样显示**。预算数字是工程常数、待实测校准，不许包装成"智能评估"。
 *
 * 它刻意不做的事
 * --------------
 * - 不把 `None` 预算换算成一个具体数字（"不限"就写"不限"）；
 * - 不自己根据行数猜一个级别（那是第二套定级实现，本项目铁律禁止）；
 * - 不隐藏 caveats（折叠可以，丢不行）。
 */
import { computed } from 'vue'
import ComplexityBadge from '../ComplexityBadge.vue'
import CaveatsPanel from './CaveatsPanel.vue'

const props = defineProps({
  /** size 对象（analysis.size） */
  size: {
    type: Object,
    default: null,
  },
  /** 正在加载 */
  loading: {
    type: Boolean,
    default: false,
  },
  /** 失败原因（后端原文优先） */
  error: {
    type: String,
    default: '',
  },
})

defineEmits(['next', 'reload'])

/**
 * `structure_rows[].source` 的两种取值（引擎里是常数，不是自由文本）。
 * `business_graph` 归到"引擎推断"：里面的域/能力点本身是 inferred，
 * 这一列的存在意义就是让评审一眼看出"这个数字不是 AST 直出的"。
 */
const SOURCE_META = {
  ast: {
    label: 'AST（可复现）',
    cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    title: '来自抽象语法树解析：同一份源码每次结果一致，可复现、可逐行回指',
  },
  business_graph: {
    label: '业务图谱（引擎推断）',
    cls: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    title: '来自业务图谱的聚类推断（命名/注释/结构启发式），需要教师确认',
  },
}

function sourceOf(value) {
  const v = String(value || '').trim().toLowerCase()
  return SOURCE_META[v] || {
    label: v ? `来源未登记（${v}）` : '来源未标注',
    cls: 'bg-deep-card text-gray-500 border-deep-border',
    title: '契约没有标注这一行数字的来源 —— 如实显示"未标注"，不代为归类',
  }
}

/** 分析深度：只做标签映射，不改含义；遇到没见过的取值就原样显示。 */
const DEPTH_META = {
  full: { label: '全量展开板块分析' },
  prioritized: { label: '核心优先（非核心的仍然展示，只是课程不展开）' },
  sampled: { label: '抽样展开（给核心地图 + 少量精读样本）' },
}
const SELECTION_META = {
  all: { label: '全部能力点（按核心度排序后取前 N 个）' },
  core_ranked: { label: '核心优先（只在核心能力点里按核心度取前 N 个）' },
}

const levelKnown = computed(() => props.size?.level_known === true && !!props.size?.level)
const rows = computed(() => (Array.isArray(props.size?.structure_rows) ? props.size.structure_rows : []))
const levelBasis = computed(() => (Array.isArray(props.size?.level_basis) ? props.size.level_basis : []))
const sizeBasis = computed(() => (Array.isArray(props.size?.size_basis) ? props.size.size_basis : []))
const tier = computed(() => props.size?.tier || null)

const shortHash = computed(() => String(props.size?.source_hash || '').slice(0, 22))

const depthMeta = computed(
  () => DEPTH_META[String(tier.value?.analysis_depth || '')] || { label: '取值未登记（引擎可能新增了档位）' },
)
const selectionMeta = computed(
  () => SELECTION_META[String(tier.value?.walkthrough_selection || '')] || { label: '取值未登记' },
)

function numOrDash(v) {
  return Number.isFinite(Number(v)) && v !== null && v !== '' ? Number(v) : '—'
}

/** `null` 是契约里"不限"的表达（不是"0 个"），所以两种取值必须显示成不同的话。 */
function budgetDisplay(raw) {
  if (raw === null || raw === undefined) return '不限'
  return String(raw)
}

const budgetCards = computed(() => {
  const t = tier.value || {}
  return [
    {
      key: 'section_budget',
      label: '最多展示几个业务板块',
      raw: t.section_budget,
      display: budgetDisplay(t.section_budget),
      note: t.section_budget === null ? '本级不截断板块：全部展示' : '超出部分整个板块不出现（截断会在看板上写明）',
    },
    {
      key: 'capability_budget',
      label: '最多展示几个能力点（全部板块合计）',
      raw: t.capability_budget,
      display: budgetDisplay(t.capability_budget),
      note: t.capability_budget === null ? '本级不截断能力点' : '超出部分能力点不出现（截断会在看板上写明）',
    },
    {
      key: 'walkthrough_capability_budget',
      label: '最多给几个能力点生成沉浸式课程',
      raw: t.walkthrough_capability_budget,
      display: budgetDisplay(t.walkthrough_capability_budget),
      note: '未进入预算的能力点，板块分析照常可看，只是课程入口会标注「超出本级预算」',
    },
  ]
})
</script>
