<template>
  <section class="space-y-5" data-test="logic-board">
    <div v-if="loading" class="glass-card p-10 text-center text-sm text-gray-400" data-test="logic-board-loading">
      正在读取业务板块看板…
    </div>
    <div v-else-if="error" class="glass-card p-10 text-center" data-test="logic-board-error">
      <div class="text-red-400 text-sm mb-2">业务板块看板不可用</div>
      <div class="text-xs text-gray-500 font-mono break-all">{{ error }}</div>
      <p class="text-xs text-gray-500 mt-3 leading-relaxed max-w-xl mx-auto">
        板块划分由后端的业务图谱聚类得出。前端不在浏览器里另造一套划分 ——
        那会立刻产生第二个口径，而"板块边界"正是本项目最容易被质疑的地方。
      </p>
    </div>

    <template v-else-if="board">
      <!-- 看板头 + 计数 -->
      <header class="glass-card p-6 neon-border" data-test="logic-board-header">
        <div class="flex items-start justify-between gap-4 flex-wrap">
          <div class="min-w-0">
            <div class="text-xs text-gray-500 font-mono tracking-widest uppercase mb-1">Step 4 · Section board</div>
            <h2 class="text-lg font-bold text-white">业务板块看板</h2>
            <p class="text-xs text-gray-400 mt-1.5 leading-relaxed max-w-2xl">
              每一张卡片是一个业务板块。点开看它的板块分析：
              它负责什么、<b class="text-pink-200/90">不负责什么</b>、有哪些能力点可以进入沉浸式学习。
              板块的划分与命名都是<b class="text-amber-300/90">引擎推断</b>，每张卡片都带置信度，待教师确认。
            </p>
          </div>
          <div class="text-right shrink-0 space-y-1">
            <div v-if="board.level" class="text-[11px] text-gray-400">
              级别 <span class="font-mono text-white">{{ board.level }}</span>
            </div>
            <div class="text-[10px] text-gray-600 font-mono">
              {{ board.board_version || 'board_version 未给出' }}
              <span v-if="board.algorithm_version">· {{ board.algorithm_version }}</span>
            </div>
            <div v-if="board.source_hash" class="text-[10px] text-gray-600 font-mono" :title="board.source_hash">
              哈希 {{ String(board.source_hash).slice(0, 16) }}
            </div>
          </div>
        </div>

        <!-- 计数：全部来自 counts，不自己数一遍（自己数会和引擎口径对不上） -->
        <div v-if="counts" class="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3" data-test="logic-board-counts">
          <div class="rounded-xl border border-deep-border bg-deep-card/40 px-3 py-2">
            <div class="text-[10px] text-gray-500">板块</div>
            <div class="text-base stat-number text-white">
              {{ counts.sections_shown ?? '—' }}<span class="text-gray-600 text-xs">/{{ counts.sections ?? '—' }}</span>
            </div>
          </div>
          <div class="rounded-xl border border-deep-border bg-deep-card/40 px-3 py-2">
            <div class="text-[10px] text-gray-500">核心板块</div>
            <div class="text-base stat-number text-white">{{ counts.core_sections ?? '—' }}</div>
          </div>
          <div class="rounded-xl border border-deep-border bg-deep-card/40 px-3 py-2">
            <div class="text-[10px] text-gray-500">能力点</div>
            <div class="text-base stat-number text-white">
              {{ counts.capabilities_shown ?? '—' }}<span class="text-gray-600 text-xs">/{{ counts.capabilities ?? '—' }}</span>
            </div>
          </div>
          <div class="rounded-xl border border-deep-border bg-deep-card/40 px-3 py-2">
            <div class="text-[10px] text-gray-500">可进入沉浸式课程</div>
            <div class="text-base stat-number text-white">
              {{ counts.walkthrough_available ?? '—' }}<span class="text-gray-600 text-xs">/{{ counts.walkthrough_requested ?? '—' }}</span>
            </div>
          </div>
        </div>

        <!-- 三个预算的截断状态：截断必须看得见，绝不悄悄少给 -->
        <ul v-if="truncationLines.length" class="mt-4 space-y-1.5" data-test="logic-board-truncation">
          <li
            v-for="(line, i) in truncationLines"
            :key="i"
            class="text-[11px] text-amber-300/90 bg-amber-500/5 border border-amber-500/20 rounded-lg px-3 py-1.5 leading-relaxed"
            data-test="logic-truncation-item"
          >
            {{ line }}
          </li>
        </ul>
        <div v-else class="mt-4 text-[11px] text-gray-500" data-test="logic-board-no-truncation">
          本级策略没有截断：这份载荷里的板块与能力点是全量展示的。
        </div>
      </header>

      <!-- 板块卡片网格 -->
      <div v-if="!sections.length" class="glass-card p-10 text-center text-sm text-gray-400" data-test="logic-board-empty">
        这份载荷里没有任何业务板块。可能是项目太小（没有可识别的业务域），
        也可能是图谱构建失败 —— 请回上一步看 <span class="font-mono">graph_status</span>，这里不替它编一个。
      </div>

      <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4" data-test="logic-board-grid">
        <button
          v-for="section in sections"
          :key="section.section_id"
          type="button"
          class="text-left glass-card p-5 flex flex-col gap-3 transition-all hover:-translate-y-0.5"
          data-test="logic-section-card"
          :data-section-id="section.section_id"
          :data-is-core="String(!!section.is_core)"
          :data-walkthrough-available="walkthroughOf(section).availableText"
          @click="$emit('select-section', section.section_id)"
        >
          <!-- 标题行 -->
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <div class="flex items-center gap-1.5 flex-wrap mb-1">
                <span
                  class="text-[10px] px-1.5 py-0.5 rounded border"
                  :class="roleMeta(section.role).cls"
                  :title="roleMeta(section.role).title"
                  data-test="logic-section-role"
                  :data-role="section.role || ''"
                >{{ roleMeta(section.role).label }}</span>
                <span
                  v-if="section.is_core"
                  class="text-[10px] px-1.5 py-0.5 rounded border bg-neon-blue/10 text-neon-blue border-neon-blue/30"
                  data-test="logic-section-core"
                >核心板块</span>
                <ConfidenceBadge :value="section.confidence" />
              </div>
              <h3 class="text-sm font-bold text-white leading-snug" data-test="logic-section-name">
                {{ section.name_cn || '（未命名板块）' }}
              </h3>
              <div class="text-[10px] text-gray-600 font-mono truncate">{{ section.section_id }}</div>
            </div>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                 class="text-gray-600 flex-shrink-0 mt-1" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
          </div>

          <!-- 命名状态：引擎自己标了"这个名字是怎么来的"，照原样带出来 -->
          <div v-if="section.name_status" class="text-[10px] text-gray-600 font-mono">
            命名状态 name_status = {{ section.name_status }}
          </div>

          <!-- 板块目标 + 它的置信度 -->
          <div data-test="logic-section-objective">
            <div v-if="section.objective" class="text-[11.5px] text-gray-300 leading-relaxed">
              {{ section.objective }}
            </div>
            <div v-else class="text-[11px] text-gray-500 px-2.5 py-1.5 rounded-lg bg-deep-card/60 border border-dashed border-slate-500/40">
              该板块的 objective 为空 —— 引擎给不出业务目标时不会编，等教师补充。
            </div>
            <div class="mt-1">
              <ConfidenceBadge :value="section.objective_confidence" />
            </div>
          </div>

          <!-- 不负责什么：本项目最有记忆点的字段，看板上也要能看见 -->
          <div data-test="logic-section-does-not-preview">
            <div class="text-[10px] text-neon-pink mb-1">不负责什么</div>
            <ul v-if="doesNotOf(section).length" class="space-y-1">
              <li
                v-for="(line, i) in doesNotOf(section).slice(0, 3)"
                :key="i"
                class="text-[11px] text-pink-100/80 leading-relaxed flex gap-1.5"
              >
                <span class="text-neon-pink flex-shrink-0">—</span><span>{{ line }}</span>
              </li>
            </ul>
            <div v-else class="text-[11px] text-gray-500">引擎未给出这一项（边界要业务判断，引擎不编）</div>
            <div v-if="doesNotOf(section).length > 3" class="text-[10px] text-gray-600 mt-0.5">
              还有 {{ doesNotOf(section).length - 3 }} 条，点开看全部
            </div>
          </div>

          <!-- 计数 + 课程覆盖 -->
          <div class="mt-auto pt-3 border-t border-deep-border space-y-2">
            <div class="flex items-center gap-2 flex-wrap text-[10px] text-gray-500" data-test="logic-section-counts">
              <span>能力点 <span class="font-mono text-gray-300">{{ countOf(section, 'capabilities') }}</span></span>
              <span class="text-gray-700">|</span>
              <span>成员 <span class="font-mono text-gray-300">{{ countOf(section, 'members') }}</span></span>
            </div>
            <div
              class="text-[10px]"
              :class="walkthroughOf(section).short ? 'text-amber-400/80' : 'text-neon-green/80'"
              data-test="logic-section-walkthrough-count"
              :data-available="walkthroughOf(section).availableText"
              :data-total="walkthroughOf(section).totalText"
            >
              可进入沉浸式课程 {{ walkthroughOf(section).availableText }} / {{ walkthroughOf(section).totalText }} 个能力点
              <span v-if="walkthroughOf(section).short" class="text-gray-500">
                （其余标注「超出本级预算」，板块分析照常可看）
              </span>
            </div>
            <div v-if="generatedOf(section) > 0" class="text-[10px] text-gray-600" data-test="logic-section-generated">
              其中 {{ generatedOf(section) }} 个已经生成过讲稿（课程索引）
            </div>
          </div>
        </button>
      </div>

      <CaveatsPanel :items="board.caveats" test-id="logic-board-caveats" desc="来自 sections 载荷" />
    </template>
  </section>
</template>

<script setup>
/**
 * 业务板块看板（Step 4）
 * =========================
 * 为什么是"网格卡片"而不是列表：这一屏的用途是**让人挑一块进去读**。
 * 卡片上必须同时给出"这块是干什么的 / 它不负责什么 / 里面有几个能讲的能力点"，
 * 学生才能判断哪一块值得先花时间。
 *
 * 四条纪律
 * --------
 * 1. **板块是引擎推断**，所以每张卡片都带 `confidence` 与 `name_status`，
 *    并且 role/is_core 用徽章而不是颜色暗示；本页不写"这是核心业务"这种断言式文案；
 * 2. **截断可见**：`budget.*.truncated` 为真时，必须显示「共 N 项，本级策略展示前 M 项」，
 *    没有截断时也要明确说"没有截断"（否则读者无从判断"就这么多"是事实还是错觉）；
 * 3. **计数全部取自 `counts`**，不在前端重新数一遍（两处各数一次迟早对不上）；
 * 4. `objective` 为空时显示"引擎不编"，不拿 `name_cn` 冒充业务目标。
 */
import { computed } from 'vue'
import ConfidenceBadge from '../ConfidenceBadge.vue'
import CaveatsPanel from './CaveatsPanel.vue'
import { roleMeta } from '../../utils/businessGraph'

const props = defineProps({
  /** sections 看板对象（analysis.sections） */
  board: {
    type: Object,
    default: null,
  },
  /** 课程索引 {lessons:{capabilityId:{generated,...}}}：用来标注"已经生成过讲稿" */
  lessonsIndex: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  error: {
    type: String,
    default: '',
  },
})

defineEmits(['select-section'])

const sections = computed(() => (Array.isArray(props.board?.sections) ? props.board.sections : []))
const counts = computed(() => props.board?.counts || null)

function doesNotOf(section) {
  const list = section?.does_not
  return Array.isArray(list) ? list.filter((x) => String(x || '').trim()) : []
}

function countOf(section, key) {
  const v = section?.counts?.[key]
  return v === undefined || v === null ? '—' : v
}

/**
 * 板块级的课程覆盖：契约里叫 `counts.walkthrough_available` / `walkthrough_total`。
 *
 * 缺失时**不显示 0**：`0/0` 会被读成"一个都没排"，而事实是这份载荷没给这两个数。
 * 所以这里保留数字给比较用，另外给一组显示文本（缺失 → `—`）。
 */
function walkthroughOf(section) {
  const available = Number.isFinite(Number(section?.counts?.walkthrough_available))
    ? Number(section.counts.walkthrough_available)
    : null
  const total = Number.isFinite(Number(section?.counts?.walkthrough_total))
    ? Number(section.counts.walkthrough_total)
    : null
  return {
    available,
    total,
    availableText: available === null ? '—' : String(available),
    totalText: total === null ? '—' : String(total),
    // 只有两个数都在、且确实有覆盖缺口时才提示"其余超出预算"
    short: available !== null && total !== null && available < total,
  }
}

/** 这个板块里已经生成过讲稿的能力点数（来自课程索引，不是猜的）。 */
function generatedOf(section) {
  const lessons = props.lessonsIndex?.lessons
  if (!lessons || !Array.isArray(section?.capabilities)) return 0
  return section.capabilities.filter((c) => lessons[c.capability_id]?.generated).length
}

/**
 * 截断说明（截断必须可见）。
 * 三种预算各自独立：板块数、能力点数、课程数。`budget === null` 是"不限"，
 * 这时候 `truncated` 必然为 false，不会出现在这里。
 */
const truncationLines = computed(() => {
  const budget = props.board?.budget
  if (!budget) return []
  const out = []
  const push = (label, item) => {
    if (!item || !item.truncated) return
    out.push(`本级策略（${budget.tier_label || '未命名'}）对${label}做了截断：共 ${item.total} 项，本级策略展示前 ${item.shown} 项（预算 ${item.budget}）。`)
  }
  push('业务板块', budget.section_budget)
  push('能力点', budget.capability_budget)
  push('沉浸式课程', budget.walkthrough_budget)
  const wt = budget.walkthrough_budget
  if (wt && wt.eligible_pool) {
    out.push(
      wt.eligible_pool === 'core_capabilities_only'
        ? '课程候选池只含核心能力点（walkthrough_selection = core_ranked）：非核心板块的能力点本次不生成课程，但板块分析照常可看。'
        : '课程候选池包含全部能力点（walkthrough_selection = all），按核心度排序取前 N 个。',
    )
  }
  return out
})
</script>
