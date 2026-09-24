<template>
  <section class="space-y-5" data-test="logic-intake">
    <!--
      这一屏是整个平台的入口：**先把"要投放什么"说清楚**。
      两件硬规矩写在这里，而不是藏在别处：
        1. 上传的源码会被后端**留存**（因为平台承诺"每条结论都能点开源码的那几行"，
           删掉源码就没法回看证据）；
        2. 分析与板块划分在**后端**执行，浏览器里不算第二份 —— 所以离线时这里是不可用的。
    -->
    <header class="glass-card p-6 neon-border">
      <div class="flex items-start justify-between gap-4 flex-wrap">
        <div class="min-w-0">
          <div class="text-xs text-gray-500 font-mono tracking-widest uppercase mb-1">Step 1 · Intake</div>
          <h2 class="text-lg font-bold text-white">投入项目</h2>
          <p class="text-xs text-gray-400 mt-1.5 leading-relaxed max-w-2xl">
            选一个已有快照的演示项目，或者上传 <span class="font-mono text-gray-300">.py</span> /
            <span class="font-mono text-gray-300">.zip</span>。
            平台会先用 AST 数清这个项目有多大，再按大小决定"讲多少"。
          </p>
        </div>
        <div class="text-right shrink-0">
          <div class="text-[10px] text-gray-500 mb-1">当前数据源</div>
          <span
            class="text-[10px] px-1.5 py-0.5 rounded border font-mono"
            :class="online
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
              : 'bg-amber-500/10 text-amber-400 border-amber-500/30'"
            data-test="logic-source-mode"
            :data-mode="online ? 'api' : 'offline'"
          >{{ online ? 'API（后端在线）' : '离线演示模式' }}</span>
        </div>
      </div>

      <!-- 离线横幅：说清"为什么不能用"，而不是给一个看不出所以然的失败 -->
      <div
        v-if="!online"
        class="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3"
        data-test="logic-offline-banner"
      >
        <div class="text-xs font-semibold text-amber-300">离线演示模式：这个平台当前不可用</div>
        <p class="text-[11px] text-amber-200/80 mt-1 leading-relaxed">
          大小定级、业务板块划分、沉浸式讲稿与证据校验<b>全部在后端执行</b>
          （AST 解析 + 规则引擎）。后端不可达时前端<b>不自己算一份</b> ——
          那会造出第二套口径，而"把推断说成事实"是这个项目明令禁止的。
          请启动后端（<span class="font-mono">http://127.0.0.1:8000</span>）后刷新。
        </p>
      </div>
    </header>

    <!-- ① 选项目：卡片列表（不是一个下拉框 —— 卡片能顺带把"这是什么"讲清楚） -->
    <section class="glass-card p-6" data-test="logic-project-picker">
      <div class="flex items-center gap-2 mb-3 flex-wrap">
        <span class="text-sm font-semibold text-white">① 选一个已有快照的演示项目</span>
        <span class="text-[11px] text-gray-500">列表由后端扫描已有快照得出，前端不认识任何一个项目名</span>
      </div>

      <div v-if="loadingProjects" class="text-xs text-gray-500 py-6 text-center" data-test="logic-project-list-loading">
        正在读取项目列表…
      </div>

      <div v-else-if="listError" class="py-3" data-test="logic-project-list-error">
        <div class="text-xs text-red-400 mb-1">项目列表不可用</div>
        <div class="text-[11px] text-gray-500 font-mono break-all">{{ listError }}</div>
      </div>

      <div v-else-if="!projects.length" class="text-xs text-gray-500 py-6 text-center" data-test="logic-project-list-empty">
        后端没有返回任何演示项目（<span class="font-mono">/api/logic-platform/projects</span> 为空）。
      </div>

      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <button
          v-for="item in projects"
          :key="item.project_id"
          type="button"
          class="text-left rounded-xl border px-4 py-3 transition-all disabled:opacity-50"
          :class="item.project_id === selectedId
            ? 'border-neon-blue/60 bg-neon-blue/10'
            : 'border-deep-border bg-deep-card/40 hover:border-neon-blue/40'"
          data-test="logic-project-card"
          :data-project-id="item.project_id"
          :disabled="busy"
          @click="pick(item.project_id)"
        >
          <div class="flex items-center gap-2">
            <span class="w-6 h-6 rounded-lg bg-gradient-to-br from-neon-blue/30 to-neon-purple/30 flex items-center justify-center flex-shrink-0">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                   class="text-neon-blue" stroke-linecap="round" stroke-linejoin="round">
                <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
              </svg>
            </span>
            <span class="text-xs text-white truncate">{{ item.project_name || item.project_id }}</span>
          </div>
          <div class="text-[10px] text-gray-500 font-mono mt-1.5 truncate">{{ item.project_id }}</div>
        </button>
      </div>

      <div class="flex items-center gap-3 mt-3 flex-wrap">
        <span v-if="selectedId" class="text-[11px] text-gray-500">
          已选 <span class="font-mono text-gray-300">{{ selectedId }}</span>
          —— 点击即开始分析大小（分析在后端执行，可能要几秒）。
        </span>
        <span v-if="listNotice" class="text-[11px] text-amber-400" data-test="logic-project-list-notice">{{ listNotice }}</span>
      </div>
    </section>

    <!-- ② 上传：复用 style.css 里已有的 .upload-zone（它本来就是为这个场景写的） -->
    <section class="glass-card p-6" data-test="logic-upload">
      <div class="flex items-center gap-2 mb-3 flex-wrap">
        <span class="text-sm font-semibold text-white">② 或者上传一个项目</span>
        <span class="text-[11px] text-gray-500">支持 .py 单文件与 .zip 压缩包；上传后源码会留在后端用于证据回看</span>
      </div>

      <div
        class="upload-zone"
        :class="{ 'drag-over': dragOver }"
        data-test="logic-upload-zone"
        :data-drag-over="String(dragOver)"
        @click="openPicker"
        @dragover.prevent="dragOver = true"
        @dragenter.prevent="dragOver = true"
        @dragleave.prevent="dragOver = false"
        @drop.prevent="onDrop"
      >
        <input
          ref="fileInput"
          type="file"
          accept=".py,.zip"
          class="hidden"
          data-test="logic-file-input"
          @change="onPick"
        />

        <div class="flex flex-col items-center gap-3 pointer-events-none">
          <div class="w-12 h-12 rounded-2xl bg-gradient-to-br from-neon-blue/20 via-neon-purple/20 to-neon-pink/20
                      flex items-center justify-center">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="1.6"
                 stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 16V4"></path>
              <path d="M7 9l5-5 5 5"></path>
              <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"></path>
            </svg>
          </div>
          <div class="text-sm text-gray-200">把 <span class="font-mono">.py</span> / <span class="font-mono">.zip</span> 拖到这里，或点击选择</div>
          <div class="text-[11px] text-gray-500 leading-relaxed max-w-md">
            压缩包会先做 zip-slip 校验（成员必须落在解压根目录内），
            包内没有 Python 文件时后端会明确拒绝。只接受这两种格式 —— 其他后缀会被后端返回 400。
          </div>
        </div>
      </div>

      <!-- 选中的文件 + 进度：上传/分析期间必须能看见"正在进行" -->
      <div v-if="pickedName" class="mt-3 flex items-center gap-3 flex-wrap" data-test="logic-upload-picked">
        <span class="text-[11px] text-gray-400">
          已选文件 <span class="font-mono text-gray-200">{{ pickedName }}</span>
          <span class="text-gray-600">（{{ formatSize(pickedSize) }}）</span>
        </span>
        <button
          type="button"
          class="px-4 py-1.5 rounded-lg text-xs font-medium text-white transition-all
                 bg-gradient-to-r from-neon-blue to-neon-purple disabled:opacity-40 disabled:cursor-not-allowed"
          data-test="logic-upload-submit"
          :disabled="busy || !online"
          @click="submit"
        >
          {{ uploading ? '正在分析…' : '开始分析' }}
        </button>
        <span v-if="!online" class="text-[11px] text-amber-400">离线演示模式下不提供上传（分析在后端执行）</span>
      </div>

      <!-- 分析进行中的进度条（不假装知道百分比：后端不报进度，这里就是"在跑"） -->
      <div v-if="uploading" class="mt-3" data-test="logic-upload-progress">
        <div class="h-1 bg-deep-border rounded-full overflow-hidden progress-bar">
          <div class="h-full difficulty-gradient w-1/3 animate-pulse"></div>
        </div>
        <div class="text-[11px] text-gray-500 mt-1.5">
          后端正在解析 AST、聚类业务域、划分板块并裁剪课程预算（单文件项目通常几秒，压缩包更久）。
          这个接口不返回百分比，所以这里不显示一个编出来的进度。
        </div>
      </div>

      <!-- 失败：后端 detail 原样显示（"只支持 .py 单文件或 .zip 压缩包。" 这种句子必须能看见） -->
      <div
        v-if="uploadError"
        class="mt-3 rounded-xl border border-red-500/40 bg-red-500/5 px-4 py-3"
        data-test="logic-upload-error"
      >
        <div class="text-xs font-semibold text-red-300">分析失败</div>
        <div class="text-[11px] text-red-200/80 mt-1 break-all font-mono">{{ uploadError }}</div>
      </div>
    </section>
  </section>
</template>

<script setup>
/**
 * 投入项目 · 平台入口（Step 1）
 * ==============================
 * 为什么用「卡片列表 + 拖拽上传」而不是一个 `<select>`：
 *   平台的第一步要顺带回答"我要分析的是什么东西"。一个下拉框只能说"选哪个"，
 *   卡片能同时给出项目名与 project_id，拖拽区能同时讲清"接受什么格式、之后会发生什么"。
 *
 * 它刻意不做的事
 * --------------
 * 1. **不在离线时假装可用**：项目列表与上传都只走在线通道（分析在后端执行），
 *    离线时如实显示横幅说明原因，而不是给一个能点但注定失败的表单；
 * 2. **不编进度百分比**：后端不返回进度，所以只显示"正在跑"的条，
 *    不显示一个看起来专业的假百分比；
 * 3. **不改写后端错误**：`detail`（"只支持 .py 单文件或 .zip 压缩包。"）原样显示。
 */
import { computed, onMounted, ref } from 'vue'
import { useDataSource } from '../../api/dataSource'
import { useLogicPlatformStore } from '../../stores/logicPlatform'

const store = useLogicPlatformStore()
const ds = useDataSource()

/** 数据源当前是不是真的连上了后端（离线时这一屏整体不可用）。 */
const online = computed(() => ds.mode.value === 'api')

const fileInput = ref(null)
const dragOver = ref(false)
const pickedFile = ref(null)
const uploadError = ref('')
const listError = ref('')
const listNotice = ref('')
const loadingProjects = ref(false)

const selectedId = computed(() => store.analysisId)
const projects = computed(() => store.projects)
const uploading = computed(() => store.uploading)
const busy = computed(() => store.uploading || store.loading)

const pickedName = computed(() => pickedFile.value?.name || '')
const pickedSize = computed(() => pickedFile.value?.size || 0)

/**
 * 列表错误单独存（不借用 store.error）：
 * 这个页面里"列表拿不到"和"某个项目分析失败"是两件事，
 * 共用同一个 error 会让文案互相盖掉（例如分析失败后列表区也跳出红字）。
 */
async function loadList() {
  loadingProjects.value = true
  listError.value = ''
  // 先补一次真实探测：dataSource 的 mode 初始值是 offline，没探测过就请求会把
  // "还没探测"误报成"离线不可用"（那是另一种不诚实）。
  await store.ensureProbed()
  const res = await store.loadProjects()
  loadingProjects.value = false
  if (!res.ok) listError.value = res.error || '无法获取演示项目列表'
}

onMounted(loadList)

function formatSize(bytes) {
  const n = Number(bytes) || 0
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

function openPicker() {
  if (busy.value) return
  fileInput.value?.click()
}

/** 选项目 = 直接开始分析（多一步"确认"只会让学生以为还需要别的操作）。 */
async function pick(projectId) {
  if (busy.value) return
  uploadError.value = ''
  listNotice.value = ''
  const res = await store.selectProject(projectId)
  if (!res.ok) listNotice.value = `「${projectId}」分析失败：${res.error}`
}

function onPick(event) {
  const file = event.target?.files?.[0]
  if (file) acceptFile(file)
  // 允许重复选同一个文件（否则第二次 change 不触发）
  if (event.target) event.target.value = ''
}

function onDrop(event) {
  dragOver.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) {
    acceptFile(file)
    submit()
  }
}

/**
 * 客户端只做**格式预检**，而且预检失败也要用后端同一句话 ——
 * 前端自作主张编一套错误文案，两边口径就会不一致。
 */
function acceptFile(file) {
  uploadError.value = ''
  const name = String(file?.name || '')
  if (!/\.(py|zip)$/i.test(name)) {
    pickedFile.value = null
    uploadError.value = '只支持 .py 单文件或 .zip 压缩包。'
    return
  }
  pickedFile.value = file
}

async function submit() {
  if (!pickedFile.value || busy.value) return
  uploadError.value = ''
  const res = await store.uploadProject(pickedFile.value)
  if (!res.ok) {
    uploadError.value = res.error || '上传分析失败'
    return
  }
  pickedFile.value = null
}
</script>
