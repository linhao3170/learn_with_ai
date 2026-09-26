<script setup>
import { ref, computed } from 'vue'
import { useAnalysisStore } from './stores/analysis'
import { useQuizStore } from './stores/quiz'
import TrainingView from './views/TrainingView.vue'
// UI 重设计一轮：**系统主页面**成为默认落地页。
// 它只回答"这里能做哪两件事、从哪儿进去"，两大核心功能（培训系统 / 业务逻辑分析平台）
// 在主页面各占半屏；点进去才展开成原来的大页面（点击后大展现）。
import HomeView from './views/HomeView.vue'
// 业务逻辑分析平台（lp-1.0）：投入项目 → 分析大小 → 按大小分流 → 板块看板 → 板块分析 → 沉浸式讲稿。
// 它是**顶层视图**（与"训练"和"旧版分析详情"并列），因为它回答的是另一个问题：
// 训练页问"怎么教、你学会了没有"，这个平台问"这个项目有多大、有哪些业务板块、我凭什么这么说"。
import LogicPlatformView from './views/LogicPlatformView.vue'
import AppHeader from './components/AppHeader.vue'
import Sidebar from './components/Sidebar.vue'
import OverviewView from './components/OverviewView.vue'
import PatternsView from './components/PatternsView.vue'
import FlowchartView from './components/FlowchartView.vue'
import CodeView from './components/CodeView.vue'
import KnowledgeView from './components/KnowledgeView.vue'
import QuizView from './components/QuizView.vue'
// 旧版 student_manager 函数级 demo 的静态数据路径也统一由数据源模块管理（P0-13：全仓只剩一处知道 /demo/...）
import { loadLegacyDemo } from './api/dataSource'

const analysis = useAnalysisStore()
const quiz = useQuizStore()

/**
 * 顶层视图：'home'（系统主页面，**默认**）| 'training'（培训工作区，内含五个阶段页签）
 * | 'logic-platform'（业务逻辑分析平台）| 'analysis'（旧版函数级分析详情）。
 *
 * 为什么把默认页从"训练关卡"改成"系统主页面"：
 *   之前一进来就是训练页的项目头部 + 五个平级页签 + 一屏口径说明，第一次打开的人
 *   看不出"这系统有两大块、我该点哪个"。主页面把功能优先级摊开：两个核心各占半屏，
 *   次级入口收成小模块，证据与口径默认收起（需要时点开，一条都没删）。
 */
const currentView = ref('home')

/**
 * 进入培训工作区时要落在哪个阶段。
 * 取值就是 `TrainingView` 的 `mainStage`：orientation / module-card / design / training / graph。
 * 由主页面的六阶段行 → 对应的阶段（点得动的阶段才有按钮）。
 */
const trainingStage = ref('training')
const trainingModuleId = ref('')

const hasData = computed(() => analysis.data !== null)
const activeTab = computed({
  get: () => analysis.activeTab,
  set: (v) => { analysis.activeTab = v },
})

async function loadAnalysisData() {
  // P0-13：原来这里直接 fetch('/demo/student_manager.py') + '/demo/analysis_output.json'，
  // 现在这两个硬编码路径移到了 src/api/dataSource.js（LEGACY_DEMO_PATHS），
  // 旧版函数级分析视图保持原样工作，但全仓只有数据源模块知道 /demo/... 的具体文件名。
  const res = await loadLegacyDemo()
  if (!res.ok) {
    console.error('load error:', res.error)
    return
  }
  analysis.setAnalysis(res.data.analysis, res.data.code)
  quiz.reset()
}

function goToHome() {
  currentView.value = 'home'
}

function goToAnalysis() {
  if (!analysis.data) {
    loadAnalysisData()
  }
  currentView.value = 'analysis'
}

function goToTraining() {
  currentView.value = 'training'
}

/**
 * 从主页面进入培训工作区，并指定落在哪个阶段。
 * `stage` 省略时按"训练关卡"落地（与改动前一致，走查与演示动线不受影响）。
 */
function goToTrainingStage(stage) {
  const target = stage && typeof stage === 'object' ? stage : { stage }
  trainingStage.value = target.stage || 'training'
  trainingModuleId.value = target.moduleId || ''
  currentView.value = 'training'
}

/**
 * 进入业务逻辑分析平台。
 *
 * 刻意**不**在这里预加载任何东西：这个平台的分析全部在后端执行（慢、且要认真对待），
 * 所以由它自己的视图在挂载时先探测后端、再由用户显式"投入项目"。
 * 首页按钮只负责切视图，不替用户做分析。
 */
function goToLogicPlatform() {
  currentView.value = 'logic-platform'
}

function handleNavigate(tab) {
  activeTab.value = tab
}
</script>

<template>
  <div class="min-h-screen bg-grid relative">
    <div class="glow-orb w-[600px] h-[600px] -top-40 -right-40 bg-neon-purple"></div>
    <div class="glow-orb w-[500px] h-[500px] -bottom-40 -left-40 bg-neon-blue"></div>

    <!--
      系统主页面（默认落地页，UI 重设计一轮）
      ---------------------------------------------------------------
      它自带顶部条与背景装饰，所以这里不再套 AppHeader。
      三个出口：进入培训工作区（可指定阶段）/ 业务逻辑分析平台 / 旧版函数级分析详情。
    -->
    <HomeView
      v-if="currentView === 'home'"
      @enter-training="goToTrainingStage"
      @view-analysis="goToAnalysis"
      @enter-logic="goToLogicPlatform"
    />

    <!-- 培训工作区（原训练页） -->
    <div v-else-if="currentView === 'training'">
      <div class="fixed top-0 left-0 right-0 z-50 border-b border-deep-border/50 bg-deep-surface/70 backdrop-blur-xl">
        <div class="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div class="flex items-center gap-3">
            <button
              class="flex items-center gap-3 text-left group"
              data-test="back-home"
              title="返回系统主页面"
              @click="goToHome"
            >
              <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-neon-blue via-neon-purple to-neon-pink flex items-center justify-center transition-transform group-hover:scale-105">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="16 18 22 12 16 6"></polyline>
                  <polyline points="8 6 2 12 8 18"></polyline>
                </svg>
              </div>
              <div>
                <div class="text-sm font-bold tracking-wide gradient-text">LearnWithAI</div>
                <div class="text-[10px] text-gray-500 font-mono tracking-wider group-hover:text-gray-400">← 返回系统主页面</div>
              </div>
            </button>
          </div>
          <div class="flex items-center gap-2">
            <button
              @click="goToLogicPlatform"
              class="px-3 py-1.5 text-xs font-medium text-gray-400 hover:text-white border border-deep-border rounded-lg transition-all hover:border-neon-purple/40 hover:bg-neon-purple/5 flex items-center gap-1.5"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                   stroke-linecap="round" stroke-linejoin="round">
                <path d="M3 6h18"></path><path d="M6 12h12"></path><path d="M9 18h6"></path>
              </svg>
              业务逻辑分析平台 →
            </button>
            <button
              @click="goToAnalysis"
              class="px-3 py-1.5 text-xs font-medium text-gray-400 hover:text-white border border-deep-border rounded-lg transition-all hover:border-neon-blue/30 hover:bg-neon-blue/5"
            >
              查看完整分析 →
            </button>
          </div>
        </div>
      </div>
      <TrainingView :initial-stage="trainingStage" :initial-module-id="trainingModuleId" @view-analysis="goToAnalysis" class="pt-14" />
    </div>

    <!-- 分析详情页（旧版 student_manager 函数级 demo） -->
    <div v-else-if="currentView === 'analysis'">
      <AppHeader :has-data="hasData" @reset="goToHome" />
      <div class="pt-14 flex min-h-screen">
        <Sidebar :active-tab="activeTab" @navigate="handleNavigate" />
        <main class="flex-1 ml-64 p-6 max-w-[calc(100vw-16rem)]">
          <OverviewView v-show="activeTab === 'overview'" />
          <PatternsView v-show="activeTab === 'patterns'" />
          <FlowchartView v-show="activeTab === 'flowchart'" />
          <CodeView v-show="activeTab === 'code'" />
          <KnowledgeView v-show="activeTab === 'knowledge'" />
          <QuizView v-show="activeTab === 'quiz'" />
        </main>
      </div>
    </div>

    <!--
      业务逻辑分析平台（顶层视图，自带顶部条与背景装饰）。
      它自己负责"返回首页"，所以这里只需要把 back 事件接回主页面 ——
      与 goToAnalysis 不同，进来时**不预加载**任何数据（分析在后端跑，由用户显式投入项目）。
    -->
    <LogicPlatformView
      v-else-if="currentView === 'logic-platform'"
      @back="goToHome"
    />
  </div>
</template>
