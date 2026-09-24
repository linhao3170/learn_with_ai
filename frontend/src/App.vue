<script setup>
import { ref, computed } from 'vue'
import { useAnalysisStore } from './stores/analysis'
import { useQuizStore } from './stores/quiz'
import TrainingView from './views/TrainingView.vue'
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

const currentView = ref('training')

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

    <!-- 训练页 -->
    <div v-if="currentView === 'training'">
      <div class="fixed top-0 left-0 right-0 z-50 border-b border-deep-border/50 bg-deep-surface/70 backdrop-blur-xl">
        <div class="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-neon-blue via-neon-purple to-neon-pink flex items-center justify-center">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="16 18 22 12 16 6"></polyline>
                <polyline points="8 6 2 12 8 18"></polyline>
              </svg>
            </div>
            <div>
              <div class="text-sm font-bold tracking-wide gradient-text">LearnWithAI</div>
              <div class="text-[10px] text-gray-500 font-mono tracking-wider">PROJECT TRAINING</div>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <button
              @click="goToLogicPlatform"
              class="px-3 py-1.5 text-xs font-medium text-gray-400 hover:text-white border border-deep-border rounded-lg transition-all hover:border-neon-purple/40 hover:bg-neon-purple/5 flex items-center gap-1.5"
              data-test="go-logic-platform"
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
      <TrainingView @view-analysis="goToAnalysis" class="pt-14" />
    </div>

    <!-- 分析详情页（旧版 student_manager 函数级 demo） -->
    <div v-else-if="currentView === 'analysis'">
      <AppHeader :has-data="hasData" @reset="goToTraining" />
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
      它自己负责"返回首页"，所以这里只需要把 back 事件接回训练页 ——
      与 goToAnalysis 不同，进来时**不预加载**任何数据（分析在后端跑，由用户显式投入项目）。
    -->
    <LogicPlatformView
      v-else-if="currentView === 'logic-platform'"
      @back="goToTraining"
    />
  </div>
</template>
