<script setup>
import { ref, computed } from 'vue'
import { useAnalysisStore } from './stores/analysis'
import { useQuizStore } from './stores/quiz'
import TrainingView from './views/TrainingView.vue'
import AppHeader from './components/AppHeader.vue'
import Sidebar from './components/Sidebar.vue'
import OverviewView from './components/OverviewView.vue'
import PatternsView from './components/PatternsView.vue'
import FlowchartView from './components/FlowchartView.vue'
import CodeView from './components/CodeView.vue'
import KnowledgeView from './components/KnowledgeView.vue'
import QuizView from './components/QuizView.vue'

const analysis = useAnalysisStore()
const quiz = useQuizStore()

const currentView = ref('training')

const hasData = computed(() => analysis.data !== null)
const activeTab = computed({
  get: () => analysis.activeTab,
  set: (v) => { analysis.activeTab = v },
})

async function loadAnalysisData() {
  try {
    const codeResp = await fetch('/demo/student_manager.py')
    const code = await codeResp.text()
    const dataResp = await fetch('/demo/analysis_output.json')
    const data = await dataResp.json()
    analysis.setAnalysis(data, code)
    quiz.reset()
  } catch (e) {
    console.error('load error:', e)
  }
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
          <button
            @click="goToAnalysis"
            class="px-3 py-1.5 text-xs font-medium text-gray-400 hover:text-white border border-deep-border rounded-lg transition-all hover:border-neon-blue/30 hover:bg-neon-blue/5"
          >
            查看完整分析 →
          </button>
        </div>
      </div>
      <TrainingView @view-analysis="goToAnalysis" class="pt-14" />
    </div>

    <!-- 分析详情页 -->
    <div v-else>
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
  </div>
</template>
