/**
 * 证据折叠的自查入口（**仅用于测试打包**，不参与演示产物）
 * ========================================================
 * 为什么单独一个入口：`scripts/check_evidence_fold.mjs` 要在 jsdom 里**单独挂载**
 * 两个组件（沉浸式讲稿渲染器 / 反幻觉面板）并喂它一份真实讲稿载荷，
 * 而不是走整个 App 的动线 —— 走查（`browser_clickthrough.mjs`）走的是用户路径，
 * 这里走的是"折叠这个行为本身对不对"。
 *
 * 导出的三样东西：
 *   - `ImmersiveLesson` / `VerificationPanel`：被测组件；
 *   - `mountInto`：挂载助手（含事件记录器）；
 *   - `NegativeControlFold` / `mountNegativeControl`：**故意做错的对照组件**
 *     （用 `v-if` 收起，正是本项目禁止的写法），用来证明
 *     "收起时内容仍在 DOM 里"这条断言**抓得到**删除，而不是永远绿。
 */
import { createApp, defineComponent, h, ref } from 'vue'
import ImmersiveLesson from './src/components/logic-platform/ImmersiveLesson.vue'
import VerificationPanel from './src/components/logic-platform/VerificationPanel.vue'

export { ImmersiveLesson, VerificationPanel }

/** 把组件挂到指定容器，返回 app 与"按顺序记录下来的事件"。 */
export function mountInto(Component, props, el) {
  const events = []
  // ⚠️ 用 `h()` 手写 props 时，事件必须写成 onXxx（模板里的 `@open-source` 编译成 `onOpenSource`）。
  // 写成 `'open-source'` 不会报错，只是永远收不到事件 —— 这种"假绿"最难查，所以在这里写死。
  const listeners = {
    onClose: (...args) => events.push({ name: 'close', args }),
    onOpenSource: (...args) => events.push({ name: 'open-source', args }),
    onVerify: (...args) => events.push({ name: 'verify', args }),
    onReview: (...args) => events.push({ name: 'review', args }),
    onNarrate: (...args) => events.push({ name: 'narrate', args }),
  }
  const app = createApp({ render: () => h(Component, { ...props, ...listeners }) })
  app.mount(el)
  return { app, events }
}

/**
 * 负向对照组件：**用 `v-if` 收起内容**（等于把证据从 DOM 里摘掉）。
 * 同一个断言函数在它身上必须 FAIL。
 */
export const NegativeControlFold = defineComponent({
  name: 'NegativeControlFold',
  props: { label: { type: String, default: 'fold' } },
  setup(props, { slots }) {
    const open = ref(false)
    return () =>
      h('div', { 'data-test': 'evidence-fold', 'data-open': String(open.value) }, [
        h(
          'button',
          { 'data-test': 'evidence-fold-toggle', onClick: () => { open.value = !open.value } },
          props.label,
        ),
        // ← 错误示范：收起时把内容从 DOM 里摘掉
        open.value ? h('div', { 'data-test': 'evidence-fold-body' }, slots.default?.()) : null,
      ])
  },
})

/** 挂对照组件（带一段槽内容），供负向对照断言使用。 */
export function mountNegativeControl(el) {
  const app = createApp({
    render: () => h(NegativeControlFold, { label: '对照' }, { default: () => '对照内容' }),
  })
  app.mount(el)
  return app
}
