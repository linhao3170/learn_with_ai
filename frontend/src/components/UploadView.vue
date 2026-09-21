<template>
  <div class="min-h-screen flex items-center justify-center pt-14 relative">
    <div class="glow-orb w-[500px] h-[500px] -top-20 right-20 bg-neon-purple"></div>
    <div class="glow-orb w-[400px] h-[400px] bottom-20 -left-20 bg-neon-blue"></div>

    <div class="max-w-2xl w-full px-6 relative z-10">
      <div class="text-center mb-10">
        <div
          class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono mb-6"
          style="background: rgba(0, 212, 255, 0.1); border: 1px solid rgba(0, 212, 255, 0.2); color: #00d4ff;"
        >
          <span class="w-1.5 h-1.5 rounded-full bg-neon-blue animate-pulse"></span>
          AST STATIC ANALYSIS ENGINE
        </div>
        <h1 class="text-4xl md:text-5xl font-bold mb-4 leading-tight">
          <span class="gradient-text">代码业务逻辑</span>
          <br>智能分析引擎
        </h1>
        <p class="text-gray-400 text-sm leading-relaxed max-w-md mx-auto">
          上传 Python 代码，自动识别业务模式、生成交互流程图、
          提取知识点、输出三道闯关测试题。
          基于 AST 静态分析，无需大模型即可运行。
        </p>
      </div>

      <div
        class="upload-zone mb-6 relative overflow-hidden"
        :class="{ 'drag-over': isDragOver }"
        @click="triggerFileInput"
        @dragover.prevent="isDragOver = true"
        @dragleave.prevent="isDragOver = false"
        @drop.prevent="handleDrop"
      >
        <div class="scan-line" v-if="isDragOver"></div>
        <input type="file" ref="fileInput" accept=".py" class="hidden" @change="handleFileSelect" />
        <div class="w-14 h-14 mx-auto mb-4 rounded-xl bg-gradient-to-br from-neon-blue/20 to-neon-purple/20 flex items-center justify-center animate-float">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="17 8 12 3 7 8"></polyline>
            <line x1="12" y1="3" x2="12" y2="15"></line>
          </svg>
        </div>
        <div class="text-white font-medium mb-1">上传 Python 文件</div>
        <div class="text-xs text-gray-500 mb-4">拖拽 .py 文件到此处，或点击选择</div>
        <div class="text-[11px] text-gray-600 font-mono">支持 .py 格式 · 单文件分析 · 纯前端数据处理</div>
      </div>

      <div class="text-center mb-6">
        <span class="text-xs text-gray-600">— 或者 —</span>
      </div>

      <button
        @click="$emit('load-demo')"
        class="w-full py-3.5 rounded-xl font-medium text-white transition-all relative overflow-hidden group
               bg-gradient-to-r from-neon-blue/90 via-neon-purple/90 to-neon-pink/90
               hover:shadow-lg hover:shadow-neon-purple/30 hover:-translate-y-0.5 active:translate-y-0"
      >
        <span class="relative z-10">加载示例：学生管理系统</span>
        <div class="absolute inset-0 bg-gradient-to-r from-neon-blue via-neon-purple to-neon-pink bg-[length:200%_100%] animate-gradient-x opacity-0 group-hover:opacity-100 transition-opacity"></div>
      </button>

      <div class="grid grid-cols-3 gap-4 mt-12">
        <div class="text-center">
          <div class="text-2xl font-bold text-neon-blue mb-1 font-mono">7+</div>
          <div class="text-[11px] text-gray-500">业务模式识别</div>
        </div>
        <div class="text-center">
          <div class="text-2xl font-bold text-neon-purple mb-1 font-mono">3</div>
          <div class="text-[11px] text-gray-500">闯关题生成</div>
        </div>
        <div class="text-center">
          <div class="text-2xl font-bold text-neon-pink mb-1 font-mono">15+</div>
          <div class="text-[11px] text-gray-500">知识点提取</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const emit = defineEmits(['load-demo', 'file-selected'])

const fileInput = ref(null)
const isDragOver = ref(false)

function triggerFileInput() {
  fileInput.value?.click()
}

function handleDrop(e) {
  isDragOver.value = false
  const file = e.dataTransfer.files[0]
  if (file && file.name.endsWith('.py')) {
    readFile(file)
  }
}

function handleFileSelect(e) {
  const file = e.target.files[0]
  if (file) readFile(file)
}

function readFile(file) {
  const reader = new FileReader()
  reader.onload = (e) => {
    emit('file-selected', {
      name: file.name.replace('.py', ''),
      code: e.target.result,
    })
  }
  reader.readAsText(file)
}
</script>
