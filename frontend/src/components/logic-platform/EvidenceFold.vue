<template>
  <div
    class="rounded-lg border border-deep-border/70 bg-deep-surface/30"
    :data-test="testId"
    :data-open="String(open)"
  >
    <!--
      折叠头：**数量写在头上**。
      收起之后读的人仍然知道"这里面有几条"，而不是面对一个匿名的箭头。
    -->
    <button
      type="button"
      class="w-full flex items-center justify-between gap-2 px-2.5 py-1.5 text-left rounded-lg
             hover:bg-neon-blue/5 transition-colors"
      :aria-expanded="String(open)"
      :title="hint || ''"
      :data-test="`${testId}-toggle`"
      @click="open = !open"
    >
      <span class="flex items-center gap-1.5 min-w-0">
        <svg
          width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"
          class="text-gray-500 flex-shrink-0"
        >
          <path d="M4 6h16"></path><path d="M4 12h10"></path><path d="M4 18h7"></path>
        </svg>
        <span class="text-[10px] text-gray-400 truncate">
          {{ label }}<template v-if="count !== null && count !== undefined">（{{ count }}）</template>
        </span>
      </span>
      <span class="flex items-center gap-1.5 flex-shrink-0">
        <span class="text-[10px] text-gray-600 font-mono">{{ open ? '收起' : '展开' }}</span>
        <svg
          class="drawer-chevron text-gray-500" :class="{ open }"
          width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"
        >
          <polyline points="9 18 15 12 9 6"></polyline>
        </svg>
      </span>
    </button>

    <!--
      内容**默认收起但仍然在 DOM 里**（`drawer-body` 只把高度收到 0）。
      「收起」不等于「删掉」：证据一直在页面上，只是不跟主内容抢视线。
    -->
    <div class="drawer-body" :class="{ open }" :data-test="`${testId}-body`">
      <div class="drawer-inner">
        <div class="px-2.5 pb-2 pt-0.5">
          <slot />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 证据折叠容器 EvidenceFold
 * ==========================
 * 为什么单独做成一个组件：这个平台的"复杂"集中在一处 —— **证据**。
 * 一条断言下面挂着 1~4 个 `文件:行号` 按钮 + 置信度徽章 + 两个教师标注按钮，
 * 一屏十段就是几十个按钮，主结论反而被淹掉。
 *
 * 于是约定一条呈现纪律：**主张（结论）常驻，佐证（证据与标注）默认收起**。
 * 收起的是"体积"，不是"内容"：
 *
 * 1. **内容仍然在 DOM 里**（复用 `style.css` 的 `.drawer-body`，只把高度收到 0），
 *    所以任何"证据必须完整存在"的检查、检索与评审都照旧拿得到它；
 * 2. **数量写在折叠头上**（`（3）`），收起之后读的人仍然知道里面有几条；
 * 3. **`defaultOpen` 是留给"这里出事了"的**：有失败项时调用方把它设成 true，
 *    这样"不许把失败藏起来"这条纪律不需要靠读者点一下才成立。
 *
 * 它刻意不做的事
 * --------------
 * - 不做成 `v-if`：`v-if` 会把证据从 DOM 里摘掉 —— 那正是本项目明令禁止的"静默删除"；
 * - 不自己决定"要不要收起"：判定留在调用方（哪个区域该收、什么时候必须默认展开，是业务口径）。
 */
import { ref, watch } from 'vue'

const props = defineProps({
  /** 折叠头文案（例如「逐条证据与教师标注」）。 */
  label: { type: String, required: true },
  /** 条数：显示成「（n）」。`null` / `undefined` 表示不显示数量。 */
  count: { type: Number, default: null },
  /** 走查与测试钩子（根节点 `data-test="<testId>"`，头是 `-toggle`，体是 `-body`）。 */
  testId: { type: String, default: 'evidence-fold' },
  /** 悬停提示（可选）。 */
  hint: { type: String, default: '' },
  /**
   * 初始是否展开。默认收起；
   * 调用方在"有失败 / 有拦截"时必须传 true —— 失败默认要看得见，不能藏在一次点击之后。
   */
  defaultOpen: { type: Boolean, default: false },
})

const open = ref(props.defaultOpen)

/**
 * `defaultOpen` 变了要跟着走：数据是异步回来的（先渲染空讲稿、再拿到校验报告），
 * 只在初始化时读一次 prop，会让"有失败就默认展开"在最需要它的那次渲染里失效。
 * 用户手点过之后就听用户的（`open` 已经是新值），这里只在调用方改口径时同步。
 */
watch(
  () => props.defaultOpen,
  (value) => {
    open.value = value
  },
)
</script>
