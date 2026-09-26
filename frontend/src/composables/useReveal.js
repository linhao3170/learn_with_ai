/**
 * 层进式动画（UI 重设计一轮）
 * ==========================
 *
 * 这个文件只负责一件事：**在元素进入视口时，按顺序把它"点亮"**。
 * 视觉规则全在 `src/style.css` 的 `[data-layer]` 一节里，这里只加/去 class。
 *
 * 为什么是"加 class"而不是"直接写 style"：
 *   1. 断点、无障碍（`prefers-reduced-motion`）都能在 CSS 里一处关掉；
 *   2. **默认可见**这条约定能成立 —— 不带 `.layer-armed` 的 `[data-layer]` 就是普通
 *      可见元素。只有本模块确认浏览器支持 `IntersectionObserver` 时才加
 *      `.layer-armed`。于是：JS 没跑到 / 浏览器不支持 / jsdom 走查环境里，
 *      内容**照样完整可见**，不会出现"整页 opacity:0"的白屏。
 *      （演示时最怕的就是动画没跑起来、页面却是空的。）
 *
 * 用法：
 *   const rootRef = ref(null)
 *   useLayeredReveal(rootRef, { watchSource: () => mainStage.value })
 *
 * 标记：
 *   - `data-layer`：要逐层点亮的元素（可选 `data-layer-delay="120"`，单位 ms）；
 *   - `:style="{ '--i': i }"` + `.stagger-item`：同一层内**依次**滑入的子项。
 */

import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

/** 浏览器是否真的支持 IntersectionObserver（不支持就什么都不做，内容保持可见）。 */
const IO_SUPPORTED =
  typeof window !== 'undefined' && typeof window.IntersectionObserver === 'function'

/**
 * 扫描 root 内的 `[data-layer]` 并逐个观察。
 *
 * @param {HTMLElement|null} root 容器（通常是视图最外层元素）
 * @param {{threshold?: number, rootMargin?: string}} [options]
 * @returns {() => void} 清理函数（取消观察；已点亮的元素保留 `is-in`，不回退）
 */
export function armLayeredReveal(root, options = {}) {
  const noop = () => {}
  if (!root || typeof root.querySelectorAll !== 'function') return noop
  // 不支持 IO：**不加** `.layer-armed`，元素保持默认可见（这是刻意的降级）。
  if (!IO_SUPPORTED) return noop

  const nodes = Array.from(root.querySelectorAll('[data-layer]'))
  if (!nodes.length) return noop

  const { threshold = 0.08, rootMargin = '0px 0px -6% 0px' } = options

  const io = new window.IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return
        const el = entry.target
        el.classList.add('is-in')
        io.unobserve(el)
      })
    },
    { threshold, rootMargin },
  )

  nodes.forEach((el) => {
    const raw = el.getAttribute('data-layer-delay')
    const delay = Number(raw)
    if (Number.isFinite(delay) && delay > 0) el.style.setProperty('--d', `${delay}ms`)
    el.classList.add('layer-armed')
    io.observe(el)
  })

  return () => {
    try {
      io.disconnect()
    } catch {
      /* 已经断开过就忽略 */
    }
  }
}

/**
 * 把 `armLayeredReveal` 接到一个 ref 上，并在 `watchSource` 变化时**重新武装**。
 *
 * 为什么要重新武装：阶段是 `v-if` 懒挂载的（切一次页签换一批 DOM），
 * 新节点没有 `.layer-armed` 就不会有入场动画。重扫一次即可，代价是几十个
 * `querySelectorAll`，和一次渲染比可以忽略。
 *
 * @param {import('vue').Ref<HTMLElement|null>} rootRef
 * @param {{watchSource?: () => unknown, threshold?: number, rootMargin?: string}} [opts]
 */
export function useLayeredReveal(rootRef, opts = {}) {
  const { watchSource, ...armOptions } = opts
  let cleanup = () => {}
  const armed = ref(false)

  function arm() {
    cleanup()
    cleanup = armLayeredReveal(rootRef.value, armOptions)
    armed.value = Boolean(rootRef.value) && IO_SUPPORTED
  }

  onMounted(() => {
    // 下一帧再扫：等 Vue 把这一轮的 DOM 全部挂上（否则会漏掉刚渲染出来的层）
    if (typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function') {
      window.requestAnimationFrame(arm)
    } else {
      arm()
    }
  })

  if (typeof watchSource === 'function') {
    watch(watchSource, () => {
      if (typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function') {
        window.requestAnimationFrame(arm)
      } else {
        arm()
      }
    })
  }

  onBeforeUnmount(() => cleanup())

  return { refresh: arm, armed }
}
