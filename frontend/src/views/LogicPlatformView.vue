<template>
  <div class="min-h-screen bg-grid relative overflow-hidden" data-test="logic-platform" :data-stage="store.stage">
    <!-- 背景装饰（与 App.vue / TrainingView 同一套 glow-orb 语言） -->
    <div class="glow-orb w-[640px] h-[640px] -top-48 right-[-180px] bg-neon-purple opacity-20"></div>
    <div class="glow-orb w-[520px] h-[520px] bottom-[-160px] left-[-120px] bg-neon-blue opacity-20"></div>

    <!-- 顶部条 -->
    <div class="fixed top-0 left-0 right-0 z-50 border-b border-deep-border/50 bg-deep-surface/70 backdrop-blur-xl">
      <div class="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between gap-4">
        <div class="flex items-center gap-3 min-w-0">
          <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-neon-blue via-neon-purple to-neon-pink flex items-center justify-center flex-shrink-0">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2"
                 stroke-linecap="round" stroke-linejoin="round">
              <path d="M3 6h18"></path><path d="M6 12h12"></path><path d="M9 18h6"></path>
            </svg>
          </div>
          <div class="min-w-0">
            <div class="text-sm font-bold tracking-wide gradient-text truncate">业务逻辑分析平台</div>
            <div class="text-[10px] text-gray-500 font-mono tracking-wider">BUSINESS LOGIC ANALYSIS · lp-1.0</div>
          </div>
        </div>
        <div class="flex items-center gap-2 flex-shrink-0">
          <span
            class="text-[10px] px-1.5 py-0.5 rounded border font-mono"
            :class="online
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
              : 'bg-amber-500/10 text-amber-400 border-amber-500/30'"
            data-test="logic-platform-mode"
            :data-mode="online ? 'api' : 'offline'"
          >{{ online ? 'API' : '离线演示模式' }}</span>
          <button
            class="px-3 py-1.5 text-xs font-medium text-gray-400 hover:text-white border border-deep-border rounded-lg transition-all hover:border-neon-blue/30 hover:bg-neon-blue/5"
            data-test="logic-back"
            @click="$emit('back')"
          >
            ← 返回首页
          </button>
        </div>
      </div>
    </div>

    <div class="relative z-10 max-w-6xl mx-auto px-6 pt-20 pb-16 space-y-6">
      <!-- =================================================================
           这一步通往哪一步（六步流程）+ 口径立场
           ================================================================= -->
      <section class="space-y-3">
        <ol class="flex flex-wrap items-center gap-x-2 gap-y-2" data-test="logic-stage-steps">
          <li
            v-for="(item, index) in STEPS"
            :key="item.stage"
            class="flex items-center gap-2"
            data-test="logic-stage-step"
            :data-stage="item.stage"
            :data-active="String(activeStepIndex === index)"
            :data-done="String(activeStepIndex > index)"
          >
            <span
              class="text-[11px] px-2.5 py-1 rounded-lg border transition-all"
              :class="activeStepIndex === index
                ? 'border-neon-blue/60 bg-neon-blue/10 text-neon-blue'
                : activeStepIndex > index
                  ? 'border-emerald-500/30 bg-emerald-500/5 text-emerald-400/80'
                  : 'border-deep-border bg-deep-card/40 text-gray-500'"
            >{{ index + 1 }}. {{ item.label }}</span>
            <svg v-if="index < STEPS.length - 1" width="12" height="12" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" stroke-width="2" class="text-gray-700" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
          </li>
        </ol>

        <!-- 立场声明：这个平台的可信度全押在这三句话上，所以放在第一屏 -->
        <div class="glass-card px-4 py-3 flex flex-wrap gap-x-5 gap-y-1.5" data-test="logic-mode-banner">
          <span class="text-[11px] text-gray-400">
            <span class="text-emerald-400">事实来自 AST，可复现</span>
          </span>
          <span class="text-[11px] text-gray-400">
            <span class="text-amber-400">板块划分为引擎推断，待教师确认</span>
          </span>
          <span class="text-[11px] text-gray-400">
            <span class="text-neon-blue">核心度排序是讲解顺序的参考信号</span>
          </span>
          <span class="text-[11px] text-gray-500">
            页面上只出现可追溯到契约字段的事实与置信度，不出现任何没有依据的自动结论。
          </span>
        </div>

        <!-- 项目身份（选中之后一直显示，避免"看的是哪个项目"变成记忆题） -->
        <div v-if="store.analysisId" class="flex items-center gap-3 flex-wrap text-[11px] text-gray-500" data-test="logic-current-project">
          <span>当前项目 <span class="font-mono text-gray-300">{{ store.analysisId }}</span></span>
          <span v-if="store.analysis?.platform_version" class="font-mono text-gray-600">
            platform_version {{ store.analysis.platform_version }}
          </span>
          <span v-if="store.size?.source_hash" class="font-mono text-gray-600" :title="store.size.source_hash">
            源码哈希 {{ String(store.size.source_hash).slice(0, 14) }}…
          </span>
          <button
            class="text-gray-500 hover:text-white transition-colors underline decoration-dotted"
            data-test="logic-restart"
            @click="restart"
          >重新选项目</button>
        </div>
      </section>

      <!-- =================================================================
           离线横幅：任何阶段都要看得见（analysis 类数据全部来自后端）
           ================================================================= -->
      <div
        v-if="!online"
        class="rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3"
        data-test="logic-platform-offline-banner"
      >
        <div class="text-xs font-semibold text-amber-300">离线演示模式：业务逻辑分析平台不可用</div>
        <p class="text-[11px] text-amber-200/80 mt-1 leading-relaxed">
          大小定级、板块划分、沉浸式讲稿与证据校验都在后端执行（AST + 规则引擎）。
          后端不可达时前端<b>不会</b>编一份看板出来 —— 那会造出第二套口径。
          需要后端在 <span class="font-mono">http://127.0.0.1:8000</span> 上运行（同源 <span class="font-mono">/api</span> 由 vite 代理）。
        </p>
      </div>

      <!-- =================================================================
           阶段 1：投入项目
           ================================================================= -->
      <PlatformIntake v-if="store.stage === 'intake'" />

      <!-- =================================================================
           阶段 2 / 3：分析项目大小 + 按大小分流
           ================================================================= -->
      <SizeReport
        v-else-if="store.stage === 'size'"
        :size="store.size"
        :loading="store.loading"
        :error="store.error"
        @next="store.setStage('sections')"
        @reload="onReload"
      />

      <!-- =================================================================
           阶段 4：业务板块看板
           ================================================================= -->
      <SectionBoard
        v-else-if="store.stage === 'sections'"
        :board="store.board"
        :lessons-index="store.lessonsIndex"
        :loading="store.loading"
        :error="store.error"
        @select-section="onSelectSection"
      />

      <!-- =================================================================
           阶段 5：板块分析
           ================================================================= -->
      <SectionAnalysis
        v-else-if="store.stage === 'section'"
        :section="store.currentSection"
        :caveats="store.board?.caveats || []"
        :lessons-index="store.lessonsIndex"
        :notice="store.sectionNotice"
        :loading="store.loading"
        :error="store.error"
        @open-source="openSource"
        @start-lesson="onStartLesson"
        @back="store.backToBoard()"
      />

      <!-- =================================================================
           阶段 6：沉浸式讲稿（组件由另一位工程师维护，这里只按契约挂载）
           + 反幻觉面板
           ================================================================= -->
      <template v-else-if="store.stage === 'lesson'">
        <div class="space-y-4" data-test="logic-lesson-mount">
          <ImmersiveLesson
            v-if="store.currentLesson"
            :lesson="store.currentLesson"
            :verification="store.verification"
            :analysis-id="store.analysisId"
            :loading="store.lessonLoading"
            :error="store.error"
            @close="onLessonClose"
            @open-source="openSource"
            @verify="onVerify"
            @review="onReview"
          />

          <!--
            讲稿没起来时的两种诚实状态。
            特别重要的一种：后端 **409**（能力点超出本级课程预算）时
            `detail` 是"本次没有生成这一课"的结论，必须原样显示 ——
            否则学生看到的就是一个转圈转到天荒地老的按钮。
          -->
          <div
            v-else-if="store.lessonLoading"
            class="glass-card p-10 text-center text-sm text-gray-400"
            data-test="logic-lesson-loading"
          >
            正在生成讲稿并跑确定性校验…
          </div>
          <div v-else class="glass-card p-8 text-center" data-test="logic-lesson-error">
            <div class="text-sm text-red-400 mb-2">这一课没有生成出来</div>
            <div class="text-xs text-gray-400 font-mono break-all max-w-2xl mx-auto">{{ store.error || '后端没有返回原因' }}</div>
            <p class="text-[11px] text-gray-500 mt-3 leading-relaxed max-w-2xl mx-auto">
              提示：后端在「能力点超出本级课程预算」时会回 <span class="font-mono">409</span> 并给出中文说明，
              上面那行就是它的原文。板块分析里也能看到同一个原因 —— 这次没讲，不等于这块没有这个能力点。
            </p>
            <button
              class="mt-3 px-4 py-2 rounded-xl text-xs border border-deep-border text-gray-400 hover:text-white hover:border-neon-blue/40 transition-all"
              data-test="logic-lesson-back"
              @click="onLessonClose"
            >返回板块</button>
          </div>
        </div>

        <VerificationPanel
          v-if="store.currentLesson"
          :lesson="store.currentLesson"
          :verification="store.verification"
          :narration-status="store.narrationStatus"
          :verifying="store.verifying"
          :narrating="store.narrating"
          :narration-notice="store.narrationNotice"
          :error="store.error"
          @verify="onVerify"
          @narrate="onNarrate"
          @open-source="openSource"
        />
      </template>
    </div>

    <!--
      单例证据查看器（与训练页共用同一个组件）。
      `source-loader` 是本平台注入的通道：逻辑平台有**自己的** source 路由
      （/api/logic-platform/{id}/source），不能用训练页那条 /api/projects/{id}/source。
    -->
    <SourceViewerModal
      :visible="sourceViewer.visible"
      :project-id="store.analysisId"
      :path="sourceViewer.path"
      :start="sourceViewer.start"
      :end="sourceViewer.end"
      :hint="sourceViewer.hint"
      :source-loader="loadLogicSource"
      @close="sourceViewer.visible = false"
    />
  </div>
</template>

<script setup>
/**
 * 业务逻辑分析平台（顶层视图）
 * =============================
 * 流程：投入项目 → 分析项目大小 → 按大小分流 → 业务板块看板 → 板块分析 → 沉浸式讲稿。
 *
 * 为什么是一个独立顶层视图而不是 TrainingView 里的又一个页签：
 *   这条流程回答的是**另一个问题**。训练页问"这个项目怎么教、你学会了没有"；
 *   这个平台问"这个项目有多大、它有哪些业务板块、我凭什么说这些"。
 *   后者是前者的前置材料，混在一个页签条里会让"新平台"看起来只是加了一页。
 *
 * 这个视图只做编排，不做判定：
 *   - 所有数据来自 `stores/logicPlatform`（它再走 `api/dataSource` 的双通道纪律）；
 *   - 讲稿渲染在 `components/logic-platform/ImmersiveLesson.vue`（另一位工程师维护，
 *     这里只按约定挂载，不碰它的内部）；
 *   - 证据回看复用 `SourceViewerModal`（全应用只有这一个证据查看器）。
 *
 * 它刻意不做的事
 * --------------
 * 1. **不在离线时造一份看板**：后端不可达就显示「离线演示模式：不可用」，
 *    并说明分析在后端执行。伪造一份"板块划分"比报错严重得多。
 * 2. **不隐藏失败**：409（超出课程预算）、503（讲解层未启用）这类后端结论
 *    都原样显示在它发生的位置上。
 * 3. **不自己算任何数字**：页面上出现的每个数字都能追到某个契约字段。
 */
import { computed, onMounted, ref } from 'vue'
import PlatformIntake from '../components/logic-platform/PlatformIntake.vue'
import SizeReport from '../components/logic-platform/SizeReport.vue'
import SectionBoard from '../components/logic-platform/SectionBoard.vue'
import SectionAnalysis from '../components/logic-platform/SectionAnalysis.vue'
import VerificationPanel from '../components/logic-platform/VerificationPanel.vue'
// 另一位工程师并发维护的讲稿渲染器：这里**只挂载**，不改它的实现。
// 契约：props {lesson(必填), verification, analysisId, loading, error}
//       emits close / open-source(file,start,end,hint) / verify / review(payload)
import ImmersiveLesson from '../components/logic-platform/ImmersiveLesson.vue'
import SourceViewerModal from '../components/SourceViewerModal.vue'
import { useDataSource } from '../api/dataSource'
import { useLogicPlatformStore } from '../stores/logicPlatform'

defineEmits(['back'])

const store = useLogicPlatformStore()
const ds = useDataSource()

const online = computed(() => ds.mode.value === 'api')

/** 六步流程（第 3 步"按大小分流"与第 2 步同屏：它们本来就是同一个决定的两面）。 */
const STEPS = [
  { stage: 'intake', label: '投入项目' },
  { stage: 'size', label: '分析项目大小' },
  { stage: 'tier', label: '按大小分流' },
  { stage: 'sections', label: '业务板块看板' },
  { stage: 'section', label: '板块分析' },
  { stage: 'lesson', label: '沉浸式讲稿' },
]

/** store 的 stage 只有 5 个值，`tier` 归到 size 那一格。 */
const activeStepIndex = computed(() => {
  const map = { intake: 0, size: 2, sections: 3, section: 4, lesson: 5 }
  return map[store.stage] ?? 0
})

// ---------------------------------------------------------------------------
// 证据查看器（与 TrainingView 完全同一套状态形状：path/start/end/hint）
// ---------------------------------------------------------------------------
const sourceViewer = ref({ visible: false, path: '', start: null, end: null, hint: '' })

/**
 * 打开证据：与 TrainingView 的 openSource 一样，只把"要看哪几行"记下来，
 * 真正的取数交给 SourceViewerModal（它会在 visible/path 变化时调用 sourceLoader）。
 * 路径统一归一成 POSIX —— 后端只认项目内相对路径。
 */
function openSource(path, start, end, hint = '') {
  if (!path) return
  sourceViewer.value = {
    visible: true,
    path: String(path).replace(/\\/g, '/'),
    start: Number.isFinite(Number(start)) && Number(start) > 0 ? Number(start) : null,
    end: Number.isFinite(Number(end)) && Number(end) > 0 ? Number(end) : null,
    hint: hint || `${path}${start ? ' · L' + start : ''}`,
  }
}

/**
 * 注入给 SourceViewerModal 的加载器。
 * 返回结构与 `dataSource.getSource()` 一致（{ok, data:{lines,total_lines,...}, source, error}），
 * 所以弹窗的渲染逻辑一个字都不用改。
 */
function loadLogicSource(path, start, end) {
  return ds.loadLogicPlatformSource(store.analysisId, path, start, end)
}

// ---------------------------------------------------------------------------
// 各阶段的动作（都委托给 store；视图不自己发请求）
// ---------------------------------------------------------------------------
async function onSelectSection(sectionId) {
  const res = await store.selectSection(sectionId)
  if (!res.ok) console.warn('[logicPlatform] 板块打开失败：', res.error)
}

async function onStartLesson(capabilityId) {
  const res = await store.openLesson(capabilityId)
  if (!res.ok) {
    // 409（超出本级课程预算）会走到这里：detail 已经被 store 放进 error，
    // 由下面的 logic-lesson-error 区块原样显示 —— 这里只留一条控制台痕迹。
    console.warn('[logicPlatform] 讲稿未能生成：', res.error)
  }
}

async function onReload() {
  await store.reloadAnalysis({ force: true })
}

async function onVerify() {
  await store.reverify()
}

async function onReview(payload) {
  const res = await store.reviewLesson(payload)
  if (!res.ok) console.warn('[logicPlatform] 审核失败：', res.error)
}

async function onNarrate() {
  await store.requestNarration()
}

function onLessonClose() {
  store.closeLesson()
}

function restart() {
  store.reset()
}

// ---------------------------------------------------------------------------
// 进入平台时先做一次真实探测
// ---------------------------------------------------------------------------
onMounted(async () => {
  // `mode` 是 dataSource 的模块级单例。如果用户没走过训练页就直接进这里，
  // 不补一次探测的话页面会把"还没探测"显示成"离线演示模式"——那也是一种不诚实。
  await store.ensureProbed()
})
</script>
