<template>
  <aside class="module-card-panel glass-card flex flex-col" data-test="module-card" :data-module-id="card?.module_id || ''">
    <!-- 加载 / 错误 / 空：三种诚实状态，都不许静默渲染空白（P0-09） -->
    <div v-if="loading" class="p-6 text-sm text-gray-400">正在加载模块卡片…</div>
    <div v-else-if="error" class="p-6 text-sm">
      <div class="text-red-400 mb-1">模块卡片加载失败</div>
      <div class="text-[11px] text-gray-500 font-mono break-all">{{ error }}</div>
    </div>
    <div v-else-if="!card" class="p-6 text-sm text-gray-500">
      在左侧选择一个业务域或功能点，这里显示它的模块卡片。
    </div>

    <template v-else>
      <!-- 头部 -->
      <header class="p-4 border-b border-deep-border">
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-[10px] px-1.5 py-0.5 rounded bg-deep-card border border-deep-border text-gray-400">
                {{ levelLabel(card.level) }}
              </span>
              <ConfidenceBadge :value="card.confidence" />
              <span
                class="text-[10px] px-1.5 py-0.5 rounded border"
                :class="sourceMeta(card.source).cls"
                :title="sourceMeta(card.source).title"
                data-test="source-badge"
                :data-source="card.source || 'unknown'"
              >{{ sourceMeta(card.source).label }}</span>
            </div>
            <h3 class="text-base font-bold text-white mt-1.5">{{ card.name_cn || '（未命名模块）' }}</h3>
            <div class="text-[10px] text-gray-600 font-mono mt-0.5">{{ card.module_id }}</div>
          </div>
          <button
            type="button"
            class="text-gray-500 hover:text-white transition-colors leading-none text-lg"
            title="关闭"
            @click="$emit('close')"
          >×</button>
        </div>

        <div class="mt-2 flex flex-wrap items-center gap-2 text-[10px]">
          <span
            class="px-1.5 py-0.5 rounded border"
            :class="reviewStatusMeta.cls"
            :title="reviewStatusMeta.title"
          >{{ reviewStatusMeta.label }}</span>
          <span v-if="parentName" class="text-gray-500">所属：{{ parentName }}</span>
        </div>
      </header>

      <div class="p-4 space-y-4 overflow-auto">
        <!-- 模块目标 objective：引擎给不出就如实说"待教师填写"，不编业务含义 -->
        <section>
          <SectionTitle text="模块目标" />
          <div v-if="card.objective" class="text-sm text-gray-200 leading-relaxed">
            {{ card.objective }}
            <div class="mt-1 flex items-center gap-2">
              <ConfidenceBadge :value="card.objective_confidence" />
              <span v-if="objectiveSourceNote" class="text-[10px] text-gray-500">{{ objectiveSourceNote }}</span>
            </div>
          </div>
          <div v-else class="p-2.5 rounded bg-deep-card/60 border border-dashed border-slate-500/40 text-xs text-slate-300">
            <span class="font-semibold">待教师填写</span>
            <span class="text-gray-500">
              （objective 为空，objective_confidence={{ card.objective_confidence || '未标注' }}）
              —— 规则引擎给不出业务目标时不会编，等教师补充。
            </span>
          </div>
        </section>

        <!-- 不负责什么 does_not：README4 §3.2 说它是全套 UI 里最有记忆点的字段，所以单独放大 -->
        <section data-test="does-not" class="does-not-block">
          <div class="flex items-center gap-2 mb-1.5">
            <span class="text-sm font-bold text-neon-pink">✕ 不负责什么</span>
            <ConfidenceBadge :value="card.does_not_confidence" />
          </div>
          <ul v-if="doesNot.length" class="space-y-1.5">
            <li
              v-for="(d, i) in doesNot"
              :key="i"
              class="text-sm text-pink-100/90 leading-relaxed flex gap-2 p-2 rounded bg-neon-pink/5 border border-neon-pink/20"
            >
              <span class="text-neon-pink flex-shrink-0">—</span>
              <span>{{ d }}</span>
            </li>
          </ul>
          <div v-else class="p-2.5 rounded bg-deep-card/60 border border-dashed border-slate-500/40 text-xs text-slate-300">
            <span class="font-semibold">引擎未给出这一项</span>
            <span class="text-gray-500">
              （does_not 为空，does_not_confidence={{ card.does_not_confidence || '未标注' }}）。
              边界需要业务判断，规则引擎不编；请教师补充后再进学生视图。
            </span>
          </div>
          <p class="text-[10px] text-gray-500 mt-1.5">
            这一项训练的是"模块边界"：说清它不做什么，比堆职责更能暴露设计问题。
          </p>
        </section>

        <!-- 业务对象：entity / verb（命名信号，可能为空） -->
        <section>
          <SectionTitle text="业务对象与动作类" />
          <div v-if="card.entity_cn || card.entity || card.verb_cn || card.verb_class" class="flex flex-wrap gap-1.5 text-[11px]">
            <span v-if="card.entity_cn || card.entity" class="px-2 py-0.5 rounded bg-deep-card border border-deep-border text-gray-300">
              对象：{{ card.entity_cn || card.entity }}
              <span v-if="card.entity && card.entity !== card.entity_cn" class="text-gray-600 font-mono"> ({{ card.entity }})</span>
            </span>
            <span v-if="card.verb_cn || card.verb_class" class="px-2 py-0.5 rounded bg-deep-card border border-deep-border text-gray-300">
              动作：{{ card.verb_cn || card.verb_class }}
              <span v-if="card.verb_class && card.verb_class !== card.verb_cn" class="text-gray-600 font-mono"> ({{ card.verb_class }})</span>
            </span>
          </div>
          <div v-else class="text-xs text-gray-500">命名信号未识别（entity / verb 均为空）—— 该项来自函数名词根推断，为空时不代填。</div>
        </section>

        <!-- 输入 / 输出 -->
        <section>
          <SectionTitle text="输入 / 输出（状态字段）" />
          <div class="grid grid-cols-1 gap-2">
            <ChipGroup label="输入" :items="card.inputs" tone="blue" empty-text="未识别出输入字段" />
            <ChipGroup label="输出" :items="card.outputs" tone="purple" empty-text="未识别出输出字段" />
          </div>
        </section>

        <!-- 四类事实：一律显示 code + file:line（可点），text 为空时说明只有代码表达式 -->
        <section v-for="kind in FACT_KINDS" :key="kind.key">
          <SectionTitle :text="kind.label" :count="(card[kind.key] || []).length" />
          <div v-if="!(card[kind.key] || []).length" class="text-xs text-gray-500">
            该类事实为空（引擎在本模块没有绑定到 {{ kind.label }}）。
          </div>
          <div v-else class="space-y-1.5">
            <div
              v-for="fact in card[kind.key]"
              :key="fact.fact_id || (fact.file + ':' + fact.start_line + ':' + (fact.code || ''))"
              data-test="fact"
              :data-fact-id="fact.fact_id || ''"
              :data-fact-kind="fact.kind || kind.kind"
              class="p-2 rounded bg-deep-card border border-deep-border hover:border-neon-blue/30 transition-colors"
            >
              <div class="flex items-start justify-between gap-2">
                <code class="text-[11px] text-gray-200 font-mono break-all flex-1">{{ fact.code || '（无代码表达式）' }}</code>
                <ConfidenceBadge v-if="fact.confidence" :value="fact.confidence" />
              </div>
              <div
                v-if="fact.text"
                class="text-xs text-gray-300 mt-1 leading-relaxed"
              >{{ fact.text }}</div>
              <div v-else class="text-[10px] text-gray-500 mt-1">{{ factTextNote(fact) }}</div>
              <button
                v-if="fact.file"
                type="button"
                data-test="fact-evidence"
                class="mt-1 text-[10px] text-gray-500 font-mono hover:text-neon-blue transition-colors inline-flex items-center gap-1"
                :title="'打开源码：' + rel(fact.file) + ' L' + fact.start_line"
                @click="openFact(fact, kind.label)"
              >
                <FileIcon />
                {{ rel(fact.file) }}:{{ fact.start_line }}<template v-if="fact.end_line && fact.end_line !== fact.start_line">-{{ fact.end_line }}</template>
                <span v-if="fact.symbol" class="text-gray-600">· {{ fact.symbol }}</span>
              </button>
            </div>
          </div>
        </section>

        <!-- 上游 / 下游模块：来自调用图（verified） -->
        <section>
          <SectionTitle text="上游 / 下游模块" />
          <div class="space-y-2">
            <ModuleIdList label="上游（谁调用我）" :ids="card.upstream_modules" :graph="graph" empty-text="调用图里没有上游模块" @select="$emit('select-module', $event)" />
            <ModuleIdList label="下游（我调用谁）" :ids="card.downstream_modules" :graph="graph" empty-text="调用图里没有下游模块" @select="$emit('select-module', $event)" />
          </div>
        </section>

        <!-- 成员函数（动作级）：点一下直接跳到真实源码 -->
        <section>
          <SectionTitle text="成员函数（动作级）" :count="members.length" />
          <div v-if="!members.length" class="text-xs text-gray-500">该模块没有绑定到成员函数。</div>
          <div v-else class="space-y-1.5">
            <div
              v-for="(m, i) in members"
              :key="(m.symbol || '') + i"
              class="p-2 rounded bg-deep-card border border-deep-border"
            >
              <div class="flex items-center gap-2 flex-wrap">
                <code class="text-[12px] text-white font-mono">{{ m.symbol }}</code>
                <span v-if="m.role" class="text-[10px] px-1.5 py-0.5 rounded bg-deep-hover text-gray-400">
                  {{ memberRoleLabel(m.role) }}
                </span>
                <span v-if="m.is_public === false" class="text-[10px] text-gray-500" title="非公开成员（下划线前缀）">非公开</span>
                <span v-if="m.name_cn" class="text-[11px] text-gray-300">{{ m.name_cn }}</span>
              </div>
              <button
                v-if="m.file"
                type="button"
                data-test="member-evidence"
                class="mt-1 text-[10px] text-gray-500 font-mono hover:text-neon-blue transition-colors inline-flex items-center gap-1"
                @click="openMember(m)"
              >
                <FileIcon />
                {{ rel(m.file) }}:{{ m.start_line }}<template v-if="m.end_line && m.end_line !== m.start_line">-{{ m.end_line }}</template>
              </button>
              <div v-if="(m.state_writes || []).length || (m.state_reads || []).length" class="mt-1 flex flex-wrap gap-1 text-[10px]">
                <span v-for="w in (m.state_writes || [])" :key="'w' + w" class="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 font-mono">写 {{ w }}</span>
                <span v-for="r in (m.state_reads || [])" :key="'r' + r" class="px-1.5 py-0.5 rounded bg-deep-hover text-gray-400 border border-deep-border font-mono">读 {{ r }}</span>
              </div>
            </div>
          </div>
        </section>

        <!-- 实现证据：域卡片给的是聚类信号（signal/value/weight），功能点卡片给的是文件行号 -->
        <section>
          <SectionTitle text="实现证据 / 判定依据" :count="(card.evidence || []).length" />
          <div v-if="!(card.evidence || []).length" class="text-xs text-gray-500">该卡片没有证据条目。</div>
          <div v-else class="space-y-1">
            <button
              v-for="(ev, i) in card.evidence"
              :key="i"
              type="button"
              class="w-full text-left text-[11px] rounded px-2 py-1 border border-deep-border bg-deep-card hover:border-neon-blue/30 transition-colors"
              :class="ev.file ? 'cursor-pointer' : 'cursor-default'"
              :disabled="!ev.file"
              @click="openEvidence(ev)"
            >
              <span class="text-gray-300">{{ ev.detail || ev.signal || '证据' }}</span>
              <span v-if="ev.signal" class="text-gray-500 font-mono ml-1">[{{ ev.signal }}]</span>
              <span v-if="ev.value" class="text-gray-400 ml-1">= {{ ev.value }}</span>
              <span v-if="ev.weight !== undefined" class="text-gray-600 font-mono ml-1">w={{ ev.weight }}</span>
              <span v-if="ev.file" class="text-neon-blue font-mono ml-1">
                {{ rel(ev.file) }}:{{ ev.start_line }}<template v-if="ev.end_line && ev.end_line !== ev.start_line">-{{ ev.end_line }}</template>
              </span>
            </button>
          </div>
        </section>

        <!-- 元信息 -->
        <section class="pt-2 border-t border-deep-border text-[10px] text-gray-600 font-mono space-y-0.5">
          <div>module_id: {{ card.module_id }} · level: {{ card.level }} · parent_id: {{ card.parent_id || '—' }}</div>
          <div>confidence: {{ card.confidence || '—' }} · review_status: {{ card.review_status || '—' }} · source: {{ card.source || '—' }}</div>
        </section>
      </div>
    </template>
  </aside>
</template>

<script setup>
/**
 * 模块卡片面板（README4 §3.2）
 * ===========================
 * 渲染契约里 module_cards[id] 的**全部字段**，三条 UI 纪律：
 *   1.「不负责什么」单独放大 —— README4 说它是全套 UI 里最有记忆点的教学字段；
 *   2. `objective` 为空时显示"待教师填写"，绝不拿 name_cn 冒充目标；
 *   3. 事实（business_rules / preconditions / exceptions / state_changes）一律渲染
 *      `code` + 可点击的 `file:line`；`text` 为空时说明"只有代码表达式"（引擎故意不编业务含义）。
 */
import { computed } from 'vue'
import ConfidenceBadge from './ConfidenceBadge.vue'
import SectionTitle from './business-graph/SectionTitle.vue'
import ChipGroup from './business-graph/ChipGroup.vue'
import ModuleIdList from './business-graph/ModuleIdList.vue'
import FileIcon from './business-graph/FileIcon.vue'
import { factTextNote, levelLabel, memberRoleLabel, sourceMeta, toProjectRelative } from '../utils/businessGraph'

const props = defineProps({
  /** module_cards[<id>]（可能为 null：还没选） */
  card: {
    type: Object,
    default: null,
  },
  /** 整个 business_graph：用来把 upstream/downstream 的 id 解析成中文名 */
  graph: {
    type: Object,
    default: null,
  },
  loading: Boolean,
  error: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['close', 'evidence', 'select-module'])

const FACT_KINDS = [
  { key: 'business_rules', kind: 'business_rule', label: '业务规则' },
  { key: 'preconditions', kind: 'guard', label: '前置校验' },
  { key: 'exceptions', kind: 'exception', label: '异常处理' },
  { key: 'state_changes', kind: 'state_change', label: '状态变化' },
]

const doesNot = computed(() => {
  const list = props.card?.does_not
  return Array.isArray(list) ? list.filter((x) => String(x || '').trim()) : []
})

const members = computed(() => (Array.isArray(props.card?.members) ? props.card.members : []))

/** 父模块中文名（一级域卡片 parent_id 为 null）。 */
const parentName = computed(() => {
  const pid = props.card?.parent_id
  if (!pid) return ''
  const d = (props.graph?.domains || []).find((x) => x.domain_id === pid)
  return d?.name_cn || pid
})

const reviewStatusMeta = computed(() => {
  const v = String(props.card?.review_status || '').trim()
  if (v === 'approved') return { label: '已审核', cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30', title: '教师已审核该卡片' }
  if (v === 'needs_review') return { label: '待教师审核', cls: 'bg-amber-500/10 text-amber-400 border-amber-500/30', title: '该卡片尚未经教师审核，学生视图需标明' }
  return { label: '审核状态未标注', cls: 'bg-deep-card text-gray-500 border-deep-border', title: '' }
})

const objectiveSourceNote = computed(() => {
  const v = String(props.card?.objective_confidence || '').trim()
  if (v === 'from_docstring') return '来自成员函数的中文 docstring（inferred）'
  if (v === 'unconfirmed') return '该目标尚未确认'
  return ''
})

function rel(file) {
  return toProjectRelative(file)
}

function openFact(fact, kindLabel) {
  if (!fact?.file) return
  emit('evidence', {
    path: rel(fact.file),
    start: Number.isFinite(Number(fact.start_line)) ? Number(fact.start_line) : null,
    end: Number.isFinite(Number(fact.end_line)) ? Number(fact.end_line) : null,
    hint: `${kindLabel} · ${fact.symbol || ''} · ${rel(fact.file)}:${fact.start_line}`.replace(/\s·\s$/, ''),
  })
}

function openMember(m) {
  if (!m?.file) return
  emit('evidence', {
    path: rel(m.file),
    start: Number.isFinite(Number(m.start_line)) ? Number(m.start_line) : null,
    end: Number.isFinite(Number(m.end_line)) ? Number(m.end_line) : null,
    hint: `成员函数 ${m.symbol} · ${rel(m.file)}:${m.start_line}`,
  })
}

function openEvidence(ev) {
  if (!ev?.file) return
  emit('evidence', {
    path: rel(ev.file),
    start: Number.isFinite(Number(ev.start_line)) ? Number(ev.start_line) : null,
    end: Number.isFinite(Number(ev.end_line)) ? Number(ev.end_line) : null,
    hint: `证据 · ${ev.signal || ''} · ${rel(ev.file)}:${ev.start_line}`,
  })
}
</script>

<style scoped>
/* 卡片面板自己滚动，父容器（BusinessGraphView 右侧栏）只负责定宽 */
.module-card-panel {
  max-height: 100%;
  overflow: hidden;
}

/*「不负责什么」用粉色描边强调：README4 §3.2 要求它"视觉上显眼" */
.does-not-block {
  padding: 10px;
  border-radius: 10px;
  border: 1px solid rgba(236, 72, 153, 0.28);
  background: rgba(236, 72, 153, 0.04);
}
</style>
